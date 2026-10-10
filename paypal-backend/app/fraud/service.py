import time
import uuid
from datetime import datetime, timezone, date, timedelta
from enum import Enum
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import structlog

from app.config import settings
from app.auth.models import User
from app.wallet.models import Account, LedgerEntry
from app.payment.models import Transaction

logger = structlog.get_logger()


class FraudDecision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


async def get_fraud_config(redis: aioredis.Redis) -> dict:
    """Gets fraud config from Redis hash if configured, otherwise falls back to settings."""
    cfg = await redis.hgetall("fraud_config")
    return {
        "max_txn_amount": int(cfg.get("max_txn_amount", settings.FRAUD_MAX_TXN_AMOUNT)),
        "daily_max_amount": int(cfg.get("daily_max_amount", settings.FRAUD_DAILY_MAX_AMOUNT)),
        "max_txn_per_minute": int(cfg.get("max_txn_per_minute", settings.FRAUD_MAX_TXN_PER_MINUTE)),
        "new_account_days": int(cfg.get("new_account_days", settings.FRAUD_NEW_ACCOUNT_DAYS)),
        "new_account_max_txn": int(cfg.get("new_account_max_txn", settings.FRAUD_NEW_ACCOUNT_MAX_TXN)),
    }


async def check_fraud(
    user_id: uuid.UUID,
    amount: int,
    txn_type: str,
    redis: aioredis.Redis,
    session: AsyncSession,
) -> FraudDecision:
    config = await get_fraud_config(redis)

    # Rule 1: Per-transaction max
    if amount > config["max_txn_amount"]:
        logger.warning("fraud_flag_max_txn_amount", user_id=str(user_id), amount=amount)
        return FraudDecision.REVIEW

    # Rule 2: Daily volume limit
    today_str = date.today().isoformat()
    daily_key = f"daily_volume:{user_id}:{today_str}"
    current_daily = int(await redis.get(daily_key) or 0)
    if current_daily + amount > config["daily_max_amount"]:
        logger.warning("fraud_flag_daily_limit_exceeded", user_id=str(user_id), current=current_daily, amount=amount)
        return FraudDecision.REVIEW

    # Rule 3: Velocity limit — N payments per minute using sorted set
    velocity_key = f"txn_velocity:{user_id}"
    now = time.time()
    await redis.zadd(velocity_key, {str(now): now})
    await redis.zremrangebyscore(velocity_key, 0, now - 60)
    count = await redis.zcard(velocity_key)
    await redis.expire(velocity_key, 120)

    if count > config["max_txn_per_minute"]:
        logger.warning("fraud_flag_velocity_blocked", user_id=str(user_id), count=count)
        return FraudDecision.BLOCK

    # Rule 4: New account stricter limits (for outbound transfers, exclude ADD_MONEY)
    if txn_type != "ADD_MONEY":
        user = await session.get(User, user_id)
        if user:
            age_days = (datetime.now(timezone.utc) - user.created_at).days
            if age_days < config["new_account_days"] and amount > config["new_account_max_txn"]:
                logger.warning("fraud_flag_new_account_high_amount", user_id=str(user_id), age_days=age_days, amount=amount)
                return FraudDecision.REVIEW

    # Rule 5: Large withdrawal right after incoming deposit (only for large amounts >= 10,000 INR / 1,000,000 paise)
    if txn_type == "WITHDRAW":
        wallet_stmt = select(Account.id).where(Account.user_id == user_id, Account.type == "USER_WALLET")
        wallet_res = await session.execute(wallet_stmt)
        wallet_id = wallet_res.scalar_one_or_none()
        if wallet_id:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            deposit_stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == wallet_id,
                LedgerEntry.direction == "CREDIT",
                LedgerEntry.created_at >= one_hour_ago,
            )
            deposit_res = await session.execute(deposit_stmt)
            recent_credits = deposit_res.scalar() or 0
            if recent_credits > 0 and amount >= 1000000 and amount >= int(recent_credits * 0.8):
                logger.warning("fraud_flag_large_withdrawal_after_deposit", user_id=str(user_id), amount=amount)
                return FraudDecision.REVIEW

    # Record daily volume
    await redis.incrby(daily_key, amount)
    await redis.expire(daily_key, 86400)

    return FraudDecision.ALLOW

