# `producer` and `KafkaEventProducer` are intentionally NOT re-exported here:
# importing them would eagerly pull in aiokafka, breaking consumers (like
# crm-sync-lambda) that only need the event schemas. Producing services
# import them explicitly: `from kafka_events.producer import producer`.
from kafka_events.config import KafkaConfig
from kafka_events.schemas import (
    AgentEvent,
    AgentQuestionAnsweredPayload,
    AgentQuestionAnsweredV1,
    BaseEvent,
    SignupAttribution,
    UserEvent,
    UserOnboardedPayload,
    UserOnboardedV1,
    UserProfileUpdatedPayload,
    UserProfileUpdatedV1,
    UserSignedUpPayload,
    UserSignedUpV1,
)
from kafka_events.topics import TOPIC_AGENT_EVENTS, TOPIC_USER_EVENTS

__all__ = [
    "AgentEvent",
    "AgentQuestionAnsweredPayload",
    "AgentQuestionAnsweredV1",
    "BaseEvent",
    "KafkaConfig",
    "SignupAttribution",
    "TOPIC_AGENT_EVENTS",
    "TOPIC_USER_EVENTS",
    "UserEvent",
    "UserOnboardedPayload",
    "UserOnboardedV1",
    "UserProfileUpdatedPayload",
    "UserProfileUpdatedV1",
    "UserSignedUpPayload",
    "UserSignedUpV1",
]
