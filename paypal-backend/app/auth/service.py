import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import structlog

from app.config import settings
from app.auth.models import User
from app.wallet.models import Account
from app.redis_client import get_redis

logger = structlog.get_logger()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: uuid.UUID, role: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def register(session: AsyncSession, email: str, password: str) -> User:
    # Check duplicate
    stmt = select(User).where(User.email == email.lower().strip())
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Email already registered", "code": "EMAIL_EXISTS"},
        )

    # Hash password
    pw_hash = hash_password(password)

    # Create User
    user = User(
        email=email.lower().strip(),
        password_hash=pw_hash,
        role="USER",
        status="ACTIVE",
        onboarding_step=1,
        email_verified=False,
    )
    session.add(user)
    await session.flush()  # to generate user.id

    # Create User Wallet
    wallet = Account(
        user_id=user.id,
        type="USER_WALLET",
        balance=0,
        version=1,
    )
    session.add(wallet)
    await session.commit()
    await session.refresh(user)

    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user


async def login(session: AsyncSession, email: str, password: str) -> tuple[str, int]:
    clean_email = email.lower().strip()
    redis = await get_redis()
    lockout_key = f"login_attempts:{clean_email}"

    # Check brute-force lockout
    attempts = await redis.get(lockout_key)
    if attempts and int(attempts) >= settings.FRAUD_LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Account temporarily locked due to multiple failed login attempts. Please try again later.",
                "code": "ACCOUNT_LOCKED",
            },
        )

    # Find user
    stmt = select(User).where(User.email == clean_email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        # Increment failed attempts
        new_attempts = await redis.incr(lockout_key)
        if new_attempts == 1:
            await redis.expire(lockout_key, settings.FRAUD_LOGIN_LOCKOUT_MINUTES * 60)
        logger.warning("failed_login_attempt", email=clean_email, attempts=new_attempts)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid email or password", "code": "INVALID_CREDENTIALS"},
        )

    # Clear login attempts on success
    await redis.delete(lockout_key)

    # Check blocked status
    if user.status == "BLOCKED":
        await redis.sadd("blocked_users", str(user.id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": f"Account is blocked: {user.blocked_reason or 'No reason specified'}", "code": "USER_BLOCKED"},
        )

    token = create_access_token(user.id, user.role)
    logger.info("user_logged_in", user_id=str(user.id), email=user.email)
    return token, user.onboarding_step


async def seed_admin(session: AsyncSession) -> None:
    try:
        stmt = select(User).where(User.email == settings.ADMIN_EMAIL.lower().strip())
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            logger.info("seeding_admin_user", email=settings.ADMIN_EMAIL)
            admin = User(
                email=settings.ADMIN_EMAIL.lower().strip(),
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="ADMIN",
                status="ACTIVE",
                onboarding_step=4,
                email_verified=True,
                full_name="System Administrator",
            )
            session.add(admin)
            await session.flush()

            wallet = Account(
                user_id=admin.id,
                type="USER_WALLET",
                balance=0,
                version=1,
            )
            session.add(wallet)
            await session.commit()
            logger.info("admin_user_seeded", admin_id=str(admin.id))
    except Exception as e:
        await session.rollback()
        logger.info("admin_user_already_seeded_or_concurrent", error=str(e))

