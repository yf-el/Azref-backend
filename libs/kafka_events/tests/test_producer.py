import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from kafka_events.config import KafkaConfig
from kafka_events.producer import KafkaEventProducer
from kafka_events.schemas import AgentQuestionAnsweredPayload, AgentQuestionAnsweredV1


@pytest.fixture
def config() -> KafkaConfig:
    return KafkaConfig(
        bootstrap_servers="pkc-x.eu-west-1.aws.confluent.cloud:9092",
        api_key="test-key",
        api_secret="test-secret",
        client_id="azref-test",
    )


@pytest.fixture
def mock_aiokafka(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace AIOKafkaProducer with a mock that records init kwargs and calls."""
    mock_instance = MagicMock()
    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()
    mock_instance.send_and_wait = AsyncMock()

    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("kafka_events.producer.AIOKafkaProducer", mock_class)
    mock_class.instance = mock_instance  # type: ignore[attr-defined]
    return mock_class


def _event() -> AgentQuestionAnsweredV1:
    return AgentQuestionAnsweredV1(
        user_id="user_42",
        payload=AgentQuestionAnsweredPayload(
            user_email="u@example.com",
            user_name="U",
            question_text="q?",
            answer_text="a.",
            language="fr",
            llm_provider="groq",
            llm_model="llama-3.3-70b",
            duration_ms=10,
        ),
    )


class TestLazyInit:
    @pytest.mark.asyncio
    async def test_constructing_does_not_start_aiokafka(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        # The whole point of lazy init: no broker connection at __init__.
        KafkaEventProducer(config)
        mock_aiokafka.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_publish_triggers_init_with_sasl_ssl_config(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.publish("azref.agent.events", _event(), key="user_42")

        mock_aiokafka.assert_called_once()
        kwargs = mock_aiokafka.call_args.kwargs
        assert kwargs["bootstrap_servers"] == config.bootstrap_servers
        assert kwargs["client_id"] == "azref-test"
        assert kwargs["security_protocol"] == "SASL_SSL"
        assert kwargs["sasl_mechanism"] == "PLAIN"
        assert kwargs["sasl_plain_username"] == "test-key"
        assert kwargs["sasl_plain_password"] == "test-secret"
        assert kwargs["enable_idempotence"] is True
        assert kwargs["acks"] == "all"
        assert kwargs["compression_type"] == "gzip"
        mock_aiokafka.instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subsequent_publishes_reuse_underlying_producer(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.publish("azref.agent.events", _event(), key="user_42")
        await producer.publish("azref.agent.events", _event(), key="user_42")
        await producer.publish("azref.agent.events", _event(), key="user_42")
        # Init happens exactly once, then producer is reused.
        mock_aiokafka.assert_called_once()
        mock_aiokafka.instance.start.assert_awaited_once()
        assert mock_aiokafka.instance.send_and_wait.await_count == 3

    @pytest.mark.asyncio
    async def test_concurrent_first_publishes_init_once(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        # The asyncio.Lock inside _ensure_started must prevent two concurrent
        # first-time publishes from creating two AIOKafkaProducer instances.
        producer = KafkaEventProducer(config)
        await asyncio.gather(
            producer.publish("azref.agent.events", _event(), key="user_42"),
            producer.publish("azref.agent.events", _event(), key="user_42"),
            producer.publish("azref.agent.events", _event(), key="user_42"),
        )
        mock_aiokafka.assert_called_once()
        mock_aiokafka.instance.start.assert_awaited_once()


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_after_init_calls_underlying_stop(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.publish("azref.agent.events", _event(), key="user_42")
        await producer.stop()
        mock_aiokafka.instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_before_any_publish_is_noop(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.stop()
        mock_aiokafka.instance.stop.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stop_then_publish_reinitializes(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.publish("azref.agent.events", _event(), key="user_42")
        await producer.stop()
        await producer.publish("azref.agent.events", _event(), key="user_42")
        assert mock_aiokafka.call_count == 2


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_serializes_to_json_bytes(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        event = _event()
        await producer.publish("azref.agent.events", event, key="user_42")

        send = mock_aiokafka.instance.send_and_wait
        send.assert_awaited_once()
        args, kwargs = send.call_args
        assert args[0] == "azref.agent.events"
        decoded = json.loads(kwargs["value"].decode("utf-8"))
        assert decoded["event_type"] == "agent.question_answered.v1"
        assert decoded["user_id"] == "user_42"
        assert decoded["payload"]["question_text"] == "q?"

    @pytest.mark.asyncio
    async def test_publish_passes_key_as_bytes(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.publish("azref.agent.events", _event(), key="user_42")
        send = mock_aiokafka.instance.send_and_wait
        assert send.call_args.kwargs["key"] == b"user_42"

    @pytest.mark.asyncio
    async def test_publish_propagates_broker_errors(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        mock_aiokafka.instance.send_and_wait.side_effect = RuntimeError("broker down")
        producer = KafkaEventProducer(config)
        with pytest.raises(RuntimeError, match="broker down"):
            await producer.publish("azref.agent.events", _event(), key="user_42")

    @pytest.mark.asyncio
    async def test_publish_propagates_init_errors(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        # If broker is unreachable, `start()` raises — `publish` must surface it
        # so the caller can decide. (publish_nowait swallows separately.)
        mock_aiokafka.instance.start.side_effect = RuntimeError("kafka unreachable")
        producer = KafkaEventProducer(config)
        with pytest.raises(RuntimeError, match="kafka unreachable"):
            await producer.publish("azref.agent.events", _event(), key="user_42")


class TestPublishNowait:
    @pytest.mark.asyncio
    async def test_returns_task_that_completes(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        task = producer.publish_nowait("azref.agent.events", _event(), key="user_42")
        assert isinstance(task, asyncio.Task)
        await task
        mock_aiokafka.instance.send_and_wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_init_errors(
        self,
        config: KafkaConfig,
        mock_aiokafka: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Kafka unreachable at first publish — user response must NEVER fail
        # because of this. The error is logged with full event context.
        mock_aiokafka.instance.start.side_effect = RuntimeError("kafka unreachable")
        producer = KafkaEventProducer(config)
        event = _event()

        with caplog.at_level(logging.ERROR, logger="kafka_events.producer"):
            task = producer.publish_nowait(
                "azref.agent.events", event, key="user_42"
            )
            await task  # must not raise

        assert any(
            "kafka_publish_failed" in record.message for record in caplog.records
        )
        assert any(
            getattr(record, "event_id", None) == str(event.event_id)
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_swallows_broker_errors(
        self,
        config: KafkaConfig,
        mock_aiokafka: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_aiokafka.instance.send_and_wait.side_effect = RuntimeError("broker down")
        producer = KafkaEventProducer(config)
        event = _event()

        with caplog.at_level(logging.ERROR, logger="kafka_events.producer"):
            task = producer.publish_nowait(
                "azref.agent.events", event, key="user_42"
            )
            await task  # must not raise

        assert any(
            "kafka_publish_failed" in record.message for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_does_not_block_caller(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        # send_and_wait sleeps to simulate a slow broker; the caller of
        # publish_nowait must return immediately because we wrap in create_task.
        slow = asyncio.Event()

        async def slow_send(*args: object, **kwargs: object) -> None:
            await slow.wait()

        mock_aiokafka.instance.send_and_wait.side_effect = slow_send
        producer = KafkaEventProducer(config)

        task = producer.publish_nowait("azref.agent.events", _event(), key="user_42")
        # Yield once to let the task progress past _ensure_started + into send.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not task.done()
        slow.set()
        await task
        assert task.done()


class TestModuleSingleton:
    def test_singleton_is_exported_and_lazy(self) -> None:
        from kafka_events import producer

        # Importing the module-level singleton must NOT have started anything,
        # NOT have required env vars, NOT have touched the network.
        assert isinstance(producer, KafkaEventProducer)
        assert producer._producer is None
        assert producer._explicit_config is None
