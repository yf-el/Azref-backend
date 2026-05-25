"""Process-wide Kafka producer for the agent service.

A single AIOKafkaProducer is shared across all requests — instantiated at
app startup via `lifespan`, closed at shutdown. Handlers access it through
`get_producer()`; calling before `init_producer()` raises so we fail loud
rather than silently dropping events.
"""

from kafka_events import KafkaConfig, KafkaEventProducer

_producer: KafkaEventProducer | None = None


async def init_producer() -> KafkaEventProducer:
    """Build the singleton from env vars and open the broker connection."""
    global _producer
    if _producer is not None:
        return _producer
    config = KafkaConfig(client_id="azref-agent")
    producer = KafkaEventProducer(config)
    await producer.start()
    _producer = producer
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer is None:
        return
    await _producer.stop()
    _producer = None


def get_producer() -> KafkaEventProducer:
    if _producer is None:
        raise RuntimeError(
            "Kafka producer not initialized — init_producer() must run in lifespan"
        )
    return _producer
