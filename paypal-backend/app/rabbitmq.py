import aio_pika
import structlog
from app.config import settings

logger = structlog.get_logger()

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect_rabbitmq():
    global _connection, _channel, _exchange
    try:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        _channel = await _connection.channel()
        await _channel.set_qos(prefetch_count=10)
        _exchange = await _channel.declare_exchange(
            "minipay.events",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        # Declare and bind the notifications queue
        notifications_queue = await _channel.declare_queue(
            "notifications",
            durable=True,
        )
        await notifications_queue.bind(_exchange, routing_key="payment.#")
        await notifications_queue.bind(_exchange, routing_key="user.#")
        await notifications_queue.bind(_exchange, routing_key="withdrawal.#")
        logger.info("rabbitmq_connected")
    except Exception as e:
        logger.warning("rabbitmq_connection_failed", error=str(e))
        _connection = None
        _channel = None
        _exchange = None


async def close_rabbitmq():
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()


def get_exchange() -> aio_pika.abc.AbstractExchange | None:
    return _exchange


def get_channel() -> aio_pika.abc.AbstractChannel | None:
    return _channel
