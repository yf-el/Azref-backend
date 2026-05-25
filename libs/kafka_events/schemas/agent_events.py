from typing import Literal

from pydantic import BaseModel, ConfigDict

from kafka_events.schemas.base import BaseEvent


class AgentQuestionAnsweredPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_email: str | None
    user_name: str | None

    question_text: str
    answer_text: str
    language: Literal["fr", "ar"]

    llm_provider: Literal["groq", "cerebras", "mistral"]
    llm_model: str
    duration_ms: int


class AgentQuestionAnsweredV1(BaseEvent):
    event_type: Literal["agent.question_answered.v1"] = "agent.question_answered.v1"
    user_id: str
    payload: AgentQuestionAnsweredPayload


# Discriminated union over every event type carried by azref.agent.events.
# Currently a single member — when we add e.g. AgentQuestionFailedV1, wrap as:
#   AgentEvent = Annotated[
#       Union[AgentQuestionAnsweredV1, AgentQuestionFailedV1],
#       Field(discriminator="event_type"),
#   ]
AgentEvent = AgentQuestionAnsweredV1
