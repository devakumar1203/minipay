import json
import asyncio
import aio_pika
import structlog

from app.config import settings
from app.redis_client import get_redis

logger = structlog.get_logger()
_consumer_task: asyncio.Task | None = None


async def handle_notification(event_type: str, event: dict, message_id: str) -> None:
    # Consumer idempotency via Redis set
    redis = await get_redis()
    is_new = await redis.sadd("processed_notification_ids", message_id)
    if not is_new:
        logger.info("notification_already_processed", message_id=message_id)
        return

    # Set 24h expiration on key set
    await redis.expire("processed_notification_ids", 86400)

    if event_type == "PaymentCompleted":
        amt_inr = event.get("amount", 0) / 100.0
        logger.info(
            "📧 [NOTIF EMAIL] Payment Completed",
            txn_id=event.get("txn_id"),
            amount_inr=amt_inr,
            from_user=event.get("from_user_id"),
            to_user=event.get("to_user_id"),
        )
    elif event_type == "PaymentFailed":
        logger.info(
            "📧 [NOTIF EMAIL] Payment Failed",
            txn_id=event.get("txn_id"),
            reason=event.get("reason"),
        )
    elif event_type == "WithdrawalCompleted":
        amt_inr = event.get("amount", 0) / 100.0
        logger.info(
            "📱 [NOTIF SMS] Withdrawal to Bank Completed",
            txn_id=event.get("txn_id"),
            amount_inr=amt_inr,
            user_id=event.get("user_id"),
        )
    elif event_type == "UserBlocked":
        logger.warning(
            "📧 [NOTIF EMAIL] Account Suspended/Blocked",
            user_id=event.get("user_id"),
            reason=event.get("reason"),
        )
    elif event_type == "UserUnblocked":
        logger.info(
            "📧 [NOTIF EMAIL] Account Restored/Unblocked",
            user_id=event.get("user_id"),
        )
    else:
        logger.info("notification_event_received", event_type=event_type, payload=event)


async def start_notification_consumer_loop() -> None:
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        queue = await channel.declare_queue("notifications", durable=True)

        logger.info("notification_consumer_started")
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        event_type = message.headers.get("event_type", "Unknown")
                        payload = json.loads(message.body.decode("utf-8"))
                        msg_id = message.message_id or str(hash(message.body))
                        await handle_notification(event_type, payload, msg_id)
                    except Exception as e:
                        logger.error("error_processing_notification_message", error=str(e))

    except asyncio.CancelledError:
        logger.info("notification_consumer_cancelled")
    except Exception as e:
        logger.warning("notification_consumer_connection_error", error=str(e))

