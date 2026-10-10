from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.database import engine, Base
from app.config import settings
from app.chaos.middleware import ChaosMiddleware

# Import models to ensure tables are registered
import app.auth.models  # noqa
import app.accounts.models  # noqa

# Routers
from app.auth.router import router as auth_router
from app.accounts.router import router as accounts_router
from app.api.router import router as api_router
from app.linking.router import router as linking_router
from app.chaos.router import router as chaos_router
from app.notifications.router import router as notifications_router

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("bank_startup", bank_id=settings.BANK_ID, bank_name=settings.BANK_NAME)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    logger.info("bank_shutdown", bank_id=settings.BANK_ID)


app = FastAPI(
    title=f"MiniPay Mock Bank — {settings.BANK_NAME}",
    description="Mock Bank service with seed accounts, debit/credit/status endpoints and chaos simulation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ChaosMiddleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(linking_router, prefix="/linking", tags=["linking"])
app.include_router(chaos_router, prefix="/admin/chaos", tags=["chaos"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])


@app.get("/health")
async def health():
    return {"status": "ok", "bank_id": settings.BANK_ID, "bank_name": settings.BANK_NAME}
