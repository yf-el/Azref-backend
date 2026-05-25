import asyncio
import logging
import ssl
from contextlib import asynccontextmanager
from typing import AsyncIterator

from aiokafka import AIOKafkaProducer

from kafka_events.config import KafkaConfig
from kafka_events.schemas.base import BaseEvent

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """Async wrapper around aiokafka tuned for the Azref event pipeline.

    Defaults chosen for at-least-once delivery with no duplicates on retry:
    SASL_SSL (Confluent Cloud), idempotent producer, acks=all, gzip
    compression to keep Confluent data-in costs minimal.

    Two publish modes:
    - `publish(...)`           : awaits broker ack, raises on failure.
    - `publish_nowait(...)`    : fire-and-forget; never blocks the caller,
                                 logs failures. Use from request handlers so
                                 the user response is never coupled to Kafka.
    """

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if self._producer is not None:
            return
        # Cap at TLS 1.2: aiokafka 0.14 + Python 3.13 + OpenSSL 3.x reset
        # mid-handshake against Confluent Cloud when negotiating TLS 1.3.
        ssl_context = ssl.create_default_context()
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        producer = AIOKafkaProducer(
            bootstrap_servers=self._config.bootstrap_servers,
            client_id=self._config.client_id,
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            sasl_plain_username=self._config.api_key,
            sasl_plain_password=self._config.api_secret,
            ssl_context=ssl_context,
            enable_idempotence=True,
            acks="all",
            compression_type="gzip",
        )
        await producer.start()
        self._producer = producer
        logger.info(
            "kafka_producer_started",
            extra={"client_id": self._config.client_id},
        )

    async def stop(self) -> None:
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None
        logger.info("kafka_producer_stopped")

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator["KafkaEventProducer"]:
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    async def publish(self, topic: str, event: BaseEvent, *, key: str) -> None:
        """Publish an event with a partition key, awaiting broker ack."""
        if self._producer is None:
            raise RuntimeError("KafkaEventProducer.start() must be called first")
        payload = event.model_dump_json().encode("utf-8")
        await self._producer.send_and_wait(
            topic,
            value=payload,
            key=key.encode("utf-8"),
        )

    def publish_nowait(
        self, topic: str, event: BaseEvent, *, key: str
    ) -> "asyncio.Task[None]":
        """Fire-and-forget publish. Errors are logged but not raised."""
        return asyncio.create_task(self._publish_swallowing(topic, event, key=key))

    async def _publish_swallowing(
        self, topic: str, event: BaseEvent, *, key: str
    ) -> None:
        try:
            await self.publish(topic, event, key=key)
        except Exception:
            logger.exception(
                "kafka_publish_failed",
                extra={
                    "topic": topic,
                    "event_type": event.event_type,
                    "event_id": str(event.event_id),
                    "key": key,
                },
            )
