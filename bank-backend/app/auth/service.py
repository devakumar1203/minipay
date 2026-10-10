import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from app.config import settings
from app.database import get_db
from app.auth.models import BankUser
from app.accounts.models import BankAccount

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    payload = {
        "sub": str(user_id),
        "bank_id": settings.BANK_ID,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def register_bank_user(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    gender: str,
    date_of_birth,
    aadhaar_no: str,
    pan_no: str,
) -> BankUser:
    clean_email = email.lower().strip()
    clean_aadhaar = aadhaar_no.strip()
    clean_pan = pan_no.upper().strip()

    stmt = select(BankUser).where(
        (BankUser.email == clean_email)
        | (BankUser.aadhaar_no == clean_aadhaar)
        | (BankUser.pan_no == clean_pan)
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        if existing.email == clean_email:
            msg = "Email already registered at this bank"
            code = "EMAIL_EXISTS"
        elif existing.aadhaar_no == clean_aadhaar:
            msg = "Aadhaar number already registered at this bank"
            code = "AADHAAR_EXISTS"
        else:
            msg = "PAN number already registered at this bank"
            code = "PAN_EXISTS"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": msg, "code": code},
        )

    user = BankUser(
        email=clean_email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        gender=gender,
        date_of_birth=date_of_birth,
        aadhaar_no=clean_aadhaar,
        pan_no=clean_pan,
    )
    session.add(user)
    await session.flush()

    # Create Bank Account with Seed Balance
    prefix = "BX" if settings.BANK_ID == "bank_x" else "BY"
    rand_digits = f"{random.randint(100000, 999999)}"
    account_no = f"{prefix}-{rand_digits}"

    account = BankAccount(
        account_no=account_no,
        user_id=user.id,
        balance=settings.SEED_BALANCE,
    )
    session.add(account)
    await session.commit()
    await session.refresh(user)

    logger.info("bank_user_registered", user_id=str(user.id), account_no=account_no, balance=settings.SEED_BALANCE)
    return user


async def login_bank_user(session: AsyncSession, email: str, password: str) -> str:
    clean_email = email.lower().strip()
    stmt = select(BankUser).where(BankUser.email == clean_email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid credentials", "code": "INVALID_CREDENTIALS"},
        )

    return create_access_token(user.id)


async def get_current_bank_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_db),
) -> BankUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Authentication token required", "code": "UNAUTHORIZED"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = uuid.UUID(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid or expired token", "code": "INVALID_TOKEN"},
        )

    user = await session.get(BankUser, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Bank user not found", "code": "USER_NOT_FOUND"},
        )
    return user

