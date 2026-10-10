from apscheduler.schedulers.asyncio import AsyncIOScheduler
import structlog

logger = structlog.get_logger()
_scheduler: AsyncIOScheduler | None = None


def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler()
    # Outbox publisher job (every 2 seconds)
    from app.outbox.publisher import publish_outbox_events
    _scheduler.add_job(publish_outbox_events, "interval", seconds=2, id="outbox_publisher")
    # Reconciliation job (every 5 minutes)
    from app.reconciliation.job import reconciliation_job
    _scheduler.add_job(reconciliation_job, "interval", minutes=5, id="reconciliation")
    _scheduler.start()
    logger.info("scheduler_started")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
