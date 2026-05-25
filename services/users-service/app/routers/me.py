from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.kafka_client import get_producer
from app.models import User
from app.schemas import UserOut, UserUpdate
from auth_clerk import ClerkClaims, get_current_clerk_user
from kafka_events import (
    TOPIC_USER_EVENTS,
    UserOnboardedPayload,
    UserOnboardedV1,
    UserProfileUpdatedPayload,
    UserProfileUpdatedV1,
    UserSignedUpPayload,
    UserSignedUpV1,
)

router = APIRouter()


def _emit_signed_up(
    *, clerk_user_id: str, email: str | None, signup_source: str | None
) -> None:
    event = UserSignedUpV1(
        user_id=clerk_user_id,
        payload=UserSignedUpPayload(user_email=email, signup_source=signup_source),
    )
    get_producer().publish_nowait(TOPIC_USER_EVENTS, event, key=clerk_user_id)


@router.get("/me", response_model=UserOut)
async def get_me(
    claims: ClerkClaims = Depends(get_current_clerk_user),
    session: AsyncSession = Depends(get_session),
    signup_source: str | None = Header(default=None, alias="X-Signup-Source"),
):
    user, created = await User.get_or_create_from_clerk(
        session, clerk_user_id=claims.sub, email=claims.email
    )
    if created:
        _emit_signed_up(
            clerk_user_id=claims.sub,
            email=claims.email,
            signup_source=signup_source,
        )
    return user


@router.patch("/me", response_model=UserOut)
async def patch_me(
    payload: UserUpdate,
    claims: ClerkClaims = Depends(get_current_clerk_user),
    session: AsyncSession = Depends(get_session),
    signup_source: str | None = Header(default=None, alias="X-Signup-Source"),
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
            signup_source=signup_source,
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
        get_producer().publish_nowait(TOPIC_USER_EVENTS, onboarded, key=claims.sub)
    elif was_onboarded:
        updated = UserProfileUpdatedV1(
            user_id=claims.sub,
            payload=UserProfileUpdatedPayload(
                user_email=user.email,
                profession=user.profession,
                usage_type=user.usage_type,
            ),
        )
        get_producer().publish_nowait(TOPIC_USER_EVENTS, updated, key=claims.sub)
    # else: partial update that did NOT complete onboarding → no event emitted

    return user
