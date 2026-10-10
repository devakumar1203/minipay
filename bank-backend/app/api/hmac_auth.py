import time
import hmac
import hashlib
from fastapi import Request, HTTPException, status
import structlog

from app.config import settings

logger = structlog.get_logger()


async def verify_hmac(request: Request) -> None:
    api_key = request.headers.get("X-Api-Key")
    timestamp = request.headers.get("X-Timestamp")
    signature = request.headers.get("X-Signature")

    if not api_key or not timestamp or not signature:
        logger.warning("hmac_missing_headers")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Missing HMAC authentication headers", "code": "HMAC_HEADERS_MISSING"},
        )

    if api_key != settings.API_KEY:
        logger.warning("hmac_invalid_api_key", received_key=api_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid API key", "code": "INVALID_API_KEY"},
        )

    try:
        req_time = float(timestamp)
        if abs(time.time() - req_time) > 300:  # 5 minutes window
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Request timestamp expired or skewed", "code": "TIMESTAMP_EXPIRED"},
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid timestamp format", "code": "INVALID_TIMESTAMP"},
        )

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8") if body_bytes else ""
    message = f"{request.method}\n{request.url.path}\n{body_str}\n{timestamp}"
    expected_sig = hmac.new(
        settings.HMAC_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        logger.warning("hmac_signature_mismatch", path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "HMAC signature mismatch", "code": "INVALID_SIGNATURE"},
        )

