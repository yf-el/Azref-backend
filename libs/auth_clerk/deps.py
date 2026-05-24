import os
from functools import lru_cache

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth_clerk.jwks import JWKSClient
from auth_clerk.schemas import ClerkClaims
from auth_clerk.verify import verify_token

_security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_client() -> tuple[str, JWKSClient]:
    issuer = os.environ["CLERK_ISSUER"]
    jwks_url = os.environ.get("CLERK_JWKS_URL") or f"{issuer}/.well-known/jwks.json"
    return issuer, JWKSClient(jwks_url)


async def get_current_clerk_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> ClerkClaims:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    issuer, jwks = _get_client()
    try:
        return await verify_token(credentials.credentials, issuer=issuer, jwks=jwks)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
