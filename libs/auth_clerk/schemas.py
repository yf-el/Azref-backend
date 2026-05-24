from pydantic import BaseModel, ConfigDict


class ClerkClaims(BaseModel):
    model_config = ConfigDict(extra="allow")

    sub: str
    iss: str
    iat: int
    exp: int
    email: str | None = None
    azp: str | None = None
