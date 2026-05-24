from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    profession: Mapped[str | None] = mapped_column(String, nullable=True)
    usage_type: Mapped[str | None] = mapped_column(String, nullable=True)

    @classmethod
    async def get_or_create_from_clerk(
        cls,
        session: AsyncSession,
        *,
        clerk_user_id: str,
        email: str | None,
    ) -> "User":
        result = await session.execute(
            select(cls).where(cls.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = cls(clerk_user_id=clerk_user_id, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    @classmethod
    async def update(
        cls,
        session: AsyncSession,
        user: "User",
        **fields: object,
    ) -> "User":
        for key, value in fields.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user
