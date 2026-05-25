import asyncio
import logging
import ssl

from aiokafka import AIOKafkaProducer

from kafka_events.config import KafkaConfig
from kafka_events.schemas.base import BaseEvent

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """Lazy async wrapper around aiokafka tuned for the Azref event pipeline.

    The underlying AIOKafkaProducer is created and connected on the FIRST
    publish, NOT at construction time. This means importing this module —
    or even constructing a producer — does NOT require Kafka to be
    reachable; the app boots normally even when Confluent is down.

    All connection/auth/network errors raised during init or publish are
    caught inside `publish_nowait`'s background task and logged. The caller
    (HTTP handler) never sees them — Kafka availability is fully decoupled
    from user-facing responses.

    Defaults: SASL_SSL (Confluent Cloud), idempotent producer, acks=all,
    gzip compression to keep Confluent data-in costs minimal.
    """

    def __init__(self, config: KafkaConfig | None = None) -> None:
        # `config=None` defers env-var loading to first publish, so importing
        # this module is safe before env vars are set (e.g. in test setup).
        self._explicit_config = config
        self._producer: AIOKafkaProducer | None = None
        self._init_lock = asyncio.Lock()

    async def _ensure_started(self) -> None:
        if self._producer is not None:
            return
        async with self._init_lock:
            if self._producer is not None:
                return
            config = self._explicit_config or KafkaConfig()
            # Cap at TLS 1.2: aiokafka 0.14 + Python 3.13 + OpenSSL 3.x reset
            # mid-handshake against Confluent Cloud when negotiating TLS 1.3.
            ssl_context = ssl.create_default_context()
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
            producer = AIOKafkaProducer(
                bootstrap_servers=config.bootstrap_servers,
                client_id=config.client_id,
                security_protocol="SASL_SSL",
                sasl_mechanism="PLAIN",
                sasl_plain_username=config.api_key,
                sasl_plain_password=config.api_secret,
                ssl_context=ssl_context,
                enable_idempotence=True,
                acks="all",
                compression_type="gzip",
            )
            await producer.start()
            self._producer = producer
            logger.info(
                "kafka_producer_started",
                extra={"client_id": config.client_id},
            )

    async def stop(self) -> None:
        """Flush pending sends and close the broker connection.

        Safe to call before any publish ever happened (no-op in that case).
        Useful in FastAPI lifespan shutdown to drain buffered messages.
        """
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None
        logger.info("kafka_producer_stopped")

    async def publish(self, topic: str, event: BaseEvent, *, key: str) -> None:
        """Publish an event with a partition key, awaiting broker ack.

        Lazily starts the underlying producer on first call. Raises on any
        init or broker error — use this only when the caller wants to handle
        failures. For request handlers, prefer `publish_nowait`.
        """
        await self._ensure_started()
        assert self._producer is not None  # post-condition of _ensure_started
        payload = event.model_dump_json().encode("utf-8")
        await self._producer.send_and_wait(
            topic,
            value=payload,
            key=key.encode("utf-8"),
        )

    def publish_nowait(
        self, topic: str, event: BaseEvent, *, key: str
    ) -> "asyncio.Task[None]":
        """Fire-and-forget publish. Catches init AND broker errors.

        Returns immediately. The actual init + send happen in a background
        task. Any exception (Kafka down, bad creds, missing env vars,
        broker rejection, network blip) is logged with full context and
        swallowed — the caller never sees a Kafka-related failure.
        """
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


# Module-level singleton — every service that imports this shares the same
# instance within its process. The `client_id` is read from KAFKA_CLIENT_ID
# env var at first publish, so each service gets its own identity in
# Confluent metrics (azref-agent, azref-users-service, ...).
producer = KafkaEventProducer()
