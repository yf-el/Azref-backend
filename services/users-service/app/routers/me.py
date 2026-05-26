import json
import logging
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import UserOut, UserUpdate
from auth_clerk import ClerkClaims, get_current_clerk_user
from kafka_events import (
    TOPIC_USER_EVENTS,
    SignupAttribution,
    UserOnboardedPayload,
    UserOnboardedV1,
    UserProfileUpdatedPayload,
    UserProfileUpdatedV1,
    UserSignedUpPayload,
    UserSignedUpV1,
)
from kafka_events.producer import producer as kafka_producer

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_attribution(raw: str | None) -> SignupAttribution | None:
    """Decode the `X-Signup-Attribution` header (URL-encoded JSON).

    Returns None on any decoding/parsing failure — attribution is best-effort
    telemetry, never fatal to the signup flow.
    """
    if not raw:
        return None
    try:
        return SignupAttribution.model_validate_json(unquote(raw))
    except (ValueError, ValidationError) as exc:
        logger.warning("Discarding malformed X-Signup-Attribution header: %s", exc)
        return None


def _emit_signed_up(
    *,
    clerk_user_id: str,
    email: str | None,
    attribution: SignupAttribution | None,
) -> None:
    event = UserSignedUpV1(
        user_id=clerk_user_id,
        payload=UserSignedUpPayload(user_email=email, attribution=attribution),
    )
    kafka_producer.publish_nowait(TOPIC_USER_EVENTS, event, key=clerk_user_id)


@router.get("/me", response_model=UserOut)
async def get_me(
    claims: ClerkClaims = Depends(get_current_clerk_user),
    session: AsyncSession = Depends(get_session),
    x_signup_attribution: str | None = Header(default=None, alias="X-Signup-Attribution"),
):
    user, created = await User.get_or_create_from_clerk(
        session, clerk_user_id=claims.sub, email=claims.email
    )
    if created:
        _emit_signed_up(
            clerk_user_id=claims.sub,
            email=claims.email,
            attribution=_parse_attribution(x_signup_attribution),
        )
    return user


@router.patch("/me", response_model=UserOut)
async def patch_me(
    payload: UserUpdate,
    claims: ClerkClaims = Depends(get_current_clerk_user),
    session: AsyncSession = Depends(get_session),
    x_signup_attribution: str | None = Header(default=None, alias="X-Signup-Attribution"),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided",
        )

    user, created = await User.get_or_create_from_clerk(
        session, clerk_user_id=claims.sub, email=claims.email
    )

    # First interaction is a PATCH → emit signed_up before any profile event so
    # consumers see existence before profile data on the same partition.
    if created:
        _emit_signed_up(
            clerk_user_id=claims.sub,
            email=claims.email,
            attribution=_parse_attribution(x_signup_attribution),
        )

    was_onboarded = user.profession is not None and user.usage_type is not None
    user = await User.update(session, user, **updates)
    is_onboarded = user.profession is not None and user.usage_type is not None

    if not was_onboarded and is_onboarded:
        onboarded = UserOnboardedV1(
            user_id=claims.sub,
            payload=UserOnboardedPayload(
                user_email=user.email,
                profession=user.profession,  # type: ignore[arg-type]
                usage_type=user.usage_type,  # type: ignore[arg-type]
            ),
        )
        kafka_producer.publish_nowait(TOPIC_USER_EVENTS, onboarded, key=claims.sub)
    elif was_onboarded:
        updated = UserProfileUpdatedV1(
            user_id=claims.sub,
            payload=UserProfileUpdatedPayload(
                user_email=user.email,
                profession=user.profession,
                usage_type=user.usage_type,
            ),
        )
        kafka_producer.publish_nowait(TOPIC_USER_EVENTS, updated, key=claims.sub)
    # else: partial update that did NOT complete onboarding → no event emitted

    return user
