from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import UserOut
from auth_clerk import ClerkClaims, get_current_clerk_user

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def me(
    claims: ClerkClaims = Depends(get_current_clerk_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(User).where(User.clerk_user_id == claims.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(clerk_user_id=claims.sub, email=claims.email)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user
