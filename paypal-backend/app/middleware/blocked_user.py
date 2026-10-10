from fastapi import HTTPException, status
from app.redis_client import get_redis


async def check_user_not_blocked(user_id: str) -> None:
    """Check Redis blocked_users set. Raise 403 if blocked."""
    redis = await get_redis()
    is_blocked = await redis.sismember("blocked_users", str(user_id))
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Account is blocked", "code": "USER_BLOCKED"},
        )
