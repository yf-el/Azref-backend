from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import UserOut, UserUpdate
from auth_clerk import ClerkClaims, get_current_clerk_user

router = APIRouter()


async def current_user(
    claims: ClerkClaims = Depends(get_current_clerk_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await User.get_or_create_from_clerk(
        session,
        clerk_user_id=claims.sub,
        email=claims.email,
    )


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
async def patch_me(
    payload: UserUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided",
        )

    return await User.update(session, user, **updates)
