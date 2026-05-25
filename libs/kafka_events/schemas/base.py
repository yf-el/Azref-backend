from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseEvent(BaseModel):
    """CloudEvents-style envelope shared by every event published to Kafka.

    Subclasses override `event_type` with a Literal[...] discriminator matching
    the `domain.entity.action.v<n>` convention so consumers can dispatch by
    type-tag inside a topic that carries multiple event types.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=_utcnow)
