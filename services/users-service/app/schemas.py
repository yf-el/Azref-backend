from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clerk_user_id: str
    email: str | None
    profession: str | None
    usage_type: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def onboarded(self) -> bool:
        return self.profession is not None and self.usage_type is not None


class UserUpdate(BaseModel):
    profession: str | None = Field(default=None, max_length=120)
    usage_type: str | None = Field(default=None, max_length=120)
