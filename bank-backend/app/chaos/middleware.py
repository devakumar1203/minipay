import asyncio
import random
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import structlog

from app.chaos.router import current_chaos

logger = structlog.get_logger()


class ChaosMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Only apply chaos to PayPal-facing APIs (/api/*)
        if request.url.path.startswith("/api/"):
            # 1. Bank Down simulation
            if current_chaos.down:
                logger.warning("chaos_bank_down_simulated", path=request.url.path)
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Bank is currently offline for maintenance", "code": "BANK_DOWN"},
                )

            # 2. Injected latency
            if current_chaos.latency_ms > 0:
                logger.info("chaos_latency_injected", latency_ms=current_chaos.latency_ms)
                await asyncio.sleep(current_chaos.latency_ms / 1000.0)

            # 3. Random error probability
            if current_chaos.error_probability > 0:
                if random.random() < current_chaos.error_probability:
                    logger.warning("chaos_random_error_injected", path=request.url.path)
                    return JSONResponse(
                        status_code=500,
                        content={"detail": "Bank internal server error simulated", "code": "SIMULATED_ERROR"},
                    )

            # 4. Drop response after processing
            if current_chaos.drop_response:
                logger.warning("chaos_drop_response_after_processing", path=request.url.path)
                # Process the request first (it commits to DB)
                _ = await call_next(request)
                # Then drop/abort the connection simulation by returning 504 Gateway Timeout or truncated response
                return Response(status_code=504, content=b"Gateway Timeout (Simulated response drop)")

        return await call_next(request)

