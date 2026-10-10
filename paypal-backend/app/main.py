import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.database import engine, Base
from app.logging_config import configure_logging
from app.middleware.request_id import RequestIDMiddleware

# Import all models to ensure metadata registration
import app.auth.models  # noqa
import app.wallet.models  # noqa
import app.payment.models  # noqa
import app.funding.models  # noqa
import app.outbox.models  # noqa
import app.admin.models  # noqa

# Routers
from app.auth.router import router as auth_router
from app.wallet.router import router as wallet_router
from app.payment.router import router as payment_router
from app.funding.router import router as funding_router
from app.admin.router import router as admin_router

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("minipay_paypal_startup")
    from app.rabbitmq import connect_rabbitmq
    from app.redis_client import redis_client

    # 1. Create DB tables (idempotent; handle race between 2 instances gracefully)
    from sqlalchemy.exc import IntegrityError
    import asyncio as _asyncio
    for _attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except IntegrityError:
            # Race condition: another instance created tables simultaneously — safe to ignore
            logger.warning("db_create_all_race_ignored", attempt=_attempt)
            break
        except Exception as _e:
            if _attempt == 4:
                raise
            await _asyncio.sleep(1)

    # 2. Connect to RabbitMQ (non-fatal if temporarily offline)
    await connect_rabbitmq()

    # 3. Seed Admin User
    from app.auth.service import seed_admin
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await seed_admin(session)

    # 4. Ensure BANK_EXTERNAL accounts exist
    from app.wallet.service import ensure_bank_external_accounts
    async with AsyncSessionLocal() as session:
        await ensure_bank_external_accounts(session)

    # 5. Start APScheduler (Outbox publisher & Reconciliation)
    from app.scheduler import start_scheduler
    start_scheduler()

    # 6. Start Notification consumer background worker
    from app.notification.consumer import start_notification_consumer_loop
    consumer_task = asyncio.create_task(start_notification_consumer_loop())

    yield

    # Shutdown
    from app.rabbitmq import close_rabbitmq
    from app.scheduler import stop_scheduler
    consumer_task.cancel()
    await close_rabbitmq()
    stop_scheduler()
    await engine.dispose()
    await redis_client.aclose()
    logger.info("minipay_paypal_shutdown")


app = FastAPI(
    title="MiniPay PayPal Service",
    description="Mini PayPal-style payment system for learning distributed systems",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

# API Routers
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(wallet_router, prefix="/api/wallet", tags=["wallet"])
app.include_router(payment_router, prefix="/api/payments", tags=["payments"])
app.include_router(funding_router, prefix="/api/funding", tags=["funding"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "paypal-backend"}
