from fastapi import Header, HTTPException, status
from typing import Optional


async def require_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> str:
    """Dependency that requires Idempotency-Key header on money-moving endpoints."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Idempotency-Key header is required", "code": "MISSING_IDEMPOTENCY_KEY"},
        )
    return idempotency_key
