import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from kafka_events.schemas import (
    AgentQuestionAnsweredPayload,
    AgentQuestionAnsweredV1,
    BaseEvent,
)


def _payload(**overrides: object) -> AgentQuestionAnsweredPayload:
    base = dict(
        user_email="user@example.com",
        user_name="Jane Doe",
        question_text="Quels sont mes droits ?",
        answer_text="Voici une réponse.",
        language="fr",
        llm_provider="groq",
        llm_model="llama-3.3-70b",
        duration_ms=420,
    )
    base.update(overrides)
    return AgentQuestionAnsweredPayload(**base)


class TestBaseEvent:
    def test_event_id_is_auto_generated_uuid(self) -> None:
        a = AgentQuestionAnsweredV1(user_id="user_1", payload=_payload())
        b = AgentQuestionAnsweredV1(user_id="user_1", payload=_payload())
        assert isinstance(a.event_id, UUID)
        assert a.event_id != b.event_id

    def test_occurred_at_is_utc_and_recent(self) -> None:
        event = AgentQuestionAnsweredV1(user_id="user_1", payload=_payload())
        assert event.occurred_at.tzinfo == timezone.utc
        delta = datetime.now(timezone.utc) - event.occurred_at
        assert delta.total_seconds() < 2

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BaseEvent(event_type="x", extra_field="nope")  # type: ignore[call-arg]


class TestAgentQuestionAnsweredV1:
    def test_event_type_is_pinned_and_immutable(self) -> None:
        event = AgentQuestionAnsweredV1(user_id="user_1", payload=_payload())
        assert event.event_type == "agent.question_answered.v1"

    def test_event_type_rejects_other_literals(self) -> None:
        with pytest.raises(ValidationError):
            AgentQuestionAnsweredV1(
                event_type="agent.question_failed.v1",  # type: ignore[arg-type]
                user_id="user_1",
                payload=_payload(),
            )

    def test_payload_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentQuestionAnsweredV1(
                user_id="user_1",
                payload=_payload(rogue_field="boom"),  # type: ignore[call-arg]
            )

    def test_language_constrained(self) -> None:
        with pytest.raises(ValidationError):
            _payload(language="es")  # type: ignore[arg-type]

    def test_llm_provider_constrained(self) -> None:
        with pytest.raises(ValidationError):
            _payload(llm_provider="openai")  # type: ignore[arg-type]

    def test_user_email_can_be_null(self) -> None:
        event = AgentQuestionAnsweredV1(
            user_id="user_1",
            payload=_payload(user_email=None, user_name=None),
        )
        assert event.payload.user_email is None
        assert event.payload.user_name is None

    def test_json_roundtrip_preserves_all_fields(self) -> None:
        event = AgentQuestionAnsweredV1(user_id="user_1", payload=_payload())
        rebuilt = AgentQuestionAnsweredV1.model_validate_json(event.model_dump_json())
        assert rebuilt == event

    def test_json_serialization_uses_iso_datetime(self) -> None:
        event = AgentQuestionAnsweredV1(user_id="user_1", payload=_payload())
        data = json.loads(event.model_dump_json())
        assert "T" in data["occurred_at"]
        assert data["event_type"] == "agent.question_answered.v1"
