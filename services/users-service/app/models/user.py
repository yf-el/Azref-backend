from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    profession: Mapped[str | None] = mapped_column(String, nullable=True)
    usage_type: Mapped[str | None] = mapped_column(String, nullable=True)
