import json
import aio_pika
from sqlalchemy import select
import structlog

from app.database import AsyncSessionLocal
from app.outbox.models import Outbox
from app.rabbitmq import get_exchange

logger = structlog.get_logger()


async def publish_outbox_events() -> int:
    """APScheduler job: publishes unpublished outbox events to RabbitMQ."""
    exchange = get_exchange()
    if not exchange:
        return 0

    published_count = 0
    async with AsyncSessionLocal() as session:
        try:
            stmt = (
                select(Outbox)
                .where(Outbox.published.is_(False))
                .order_by(Outbox.created_at.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()

            for event in events:
                routing_key = f"minipay.{event.event_type}"
                message = aio_pika.Message(
                    body=json.dumps(event.payload).encode("utf-8"),
                    headers={"event_type": event.event_type},
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=str(event.id),
                )
                await exchange.publish(message, routing_key=routing_key)
                event.published = True
                published_count += 1

            if published_count > 0:
                await session.commit()
                logger.info("outbox_events_published", count=published_count)

        except Exception as e:
            await session.rollback()
            logger.error("outbox_publisher_error", error=str(e))

    return published_count
