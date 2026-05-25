from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from kafka_events.schemas.base import BaseEvent


class SignupAttribution(BaseModel):
    """First-touch attribution captured client-side at the user's initial landing.

    Sent by the front as an URL-encoded JSON header `X-Signup-Attribution`.
    All fields are nullable — direct traffic with no UTMs is the common case.
    """

    model_config = ConfigDict(extra="forbid")

    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    referrer: str | None = None
    landing_path: str | None = None
    captured_at: str | None = None


class UserSignedUpPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_email: str | None
    attribution: SignupAttribution | None


class UserOnboardedPayload(BaseModel):
    """Snapshot at the moment onboarding becomes complete."""

    model_config = ConfigDict(extra="forbid")

    user_email: str | None
    profession: str
    usage_type: str


class UserProfileUpdatedPayload(BaseModel):
    """Snapshot of the current profile after an update (post-onboarding).

    Consumers maintain their own previous state if they need a diff — emitting
    a diff here would couple producer to every consumer's data model.
    """

    model_config = ConfigDict(extra="forbid")

    user_email: str | None
    profession: str | None
    usage_type: str | None


class UserSignedUpV1(BaseEvent):
    event_type: Literal["user.signed_up.v1"] = "user.signed_up.v1"
    user_id: str
    payload: UserSignedUpPayload


class UserOnboardedV1(BaseEvent):
    event_type: Literal["user.onboarded.v1"] = "user.onboarded.v1"
    user_id: str
    payload: UserOnboardedPayload


class UserProfileUpdatedV1(BaseEvent):
    event_type: Literal["user.profile_updated.v1"] = "user.profile_updated.v1"
    user_id: str
    payload: UserProfileUpdatedPayload


# Discriminated union over every event type carried by azref.user.events.
# Consumers parse incoming messages via `UserEvent` and Pydantic dispatches
# to the right concrete type based on the `event_type` field.
UserEvent = Annotated[
    Union[UserSignedUpV1, UserOnboardedV1, UserProfileUpdatedV1],
    Field(discriminator="event_type"),
]
