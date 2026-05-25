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
    # Avoid touching the network / cert store for SSL context creation.
    monkeypatch.setattr(
        "kafka_events.producer.create_ssl_context", lambda: MagicMock(name="ssl_ctx")
    )
    # Expose both the class (to assert constructor kwargs) and the instance.
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


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_aiokafka_producer_with_sasl_ssl_config(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.start()

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
    async def test_start_is_idempotent(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.start()
        await producer.start()
        mock_aiokafka.assert_called_once()
        mock_aiokafka.instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_calls_underlying_stop(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.start()
        await producer.stop()
        mock_aiokafka.instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.stop()
        mock_aiokafka.instance.stop.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stop_then_restart_creates_new_underlying(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.start()
        await producer.stop()
        await producer.start()
        assert mock_aiokafka.call_count == 2


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_before_start_raises(self, config: KafkaConfig) -> None:
        producer = KafkaEventProducer(config)
        with pytest.raises(RuntimeError, match="start"):
            await producer.publish("azref.agent.events", _event(), key="user_42")

    @pytest.mark.asyncio
    async def test_publish_serializes_to_json_bytes(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.start()
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
        await producer.start()
        await producer.publish("azref.agent.events", _event(), key="user_42")
        send = mock_aiokafka.instance.send_and_wait
        assert send.call_args.kwargs["key"] == b"user_42"

    @pytest.mark.asyncio
    async def test_publish_propagates_broker_errors(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        mock_aiokafka.instance.send_and_wait.side_effect = RuntimeError("broker down")
        producer = KafkaEventProducer(config)
        await producer.start()
        with pytest.raises(RuntimeError, match="broker down"):
            await producer.publish("azref.agent.events", _event(), key="user_42")


class TestPublishNowait:
    @pytest.mark.asyncio
    async def test_returns_task_that_completes(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        await producer.start()
        task = producer.publish_nowait("azref.agent.events", _event(), key="user_42")
        assert isinstance(task, asyncio.Task)
        await task
        mock_aiokafka.instance.send_and_wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_broker_errors_and_logs(
        self,
        config: KafkaConfig,
        mock_aiokafka: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_aiokafka.instance.send_and_wait.side_effect = RuntimeError("broker down")
        producer = KafkaEventProducer(config)
        await producer.start()
        event = _event()

        with caplog.at_level(logging.ERROR, logger="kafka_events.producer"):
            task = producer.publish_nowait(
                "azref.agent.events", event, key="user_42"
            )
            await task  # must not raise

        assert any(
            "kafka_publish_failed" in record.message for record in caplog.records
        )
        # event_id must be in the log record for traceability.
        assert any(
            getattr(record, "event_id", None) == str(event.event_id)
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_does_not_block_caller(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        # send_and_wait sleeps to simulate a slow broker; caller must return
        # immediately because publish_nowait wraps in create_task.
        slow = asyncio.Event()

        async def slow_send(*args: object, **kwargs: object) -> None:
            await slow.wait()

        mock_aiokafka.instance.send_and_wait.side_effect = slow_send
        producer = KafkaEventProducer(config)
        await producer.start()

        task = producer.publish_nowait("azref.agent.events", _event(), key="user_42")
        assert not task.done()
        slow.set()
        await task
        assert task.done()


class TestLifespan:
    @pytest.mark.asyncio
    async def test_starts_on_enter_and_stops_on_exit(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        async with producer.lifespan() as yielded:
            assert yielded is producer
            mock_aiokafka.instance.start.assert_awaited_once()
            mock_aiokafka.instance.stop.assert_not_awaited()
        mock_aiokafka.instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stops_even_on_exception(
        self, config: KafkaConfig, mock_aiokafka: MagicMock
    ) -> None:
        producer = KafkaEventProducer(config)
        with pytest.raises(ValueError, match="boom"):
            async with producer.lifespan():
                raise ValueError("boom")
        mock_aiokafka.instance.stop.assert_awaited_once()
