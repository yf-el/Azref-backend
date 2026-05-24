import os
from functools import lru_cache

from fastapi import Header, HTTPException

from auth_clerk.jwks import JWKSClient
from auth_clerk.schemas import ClerkClaims
from auth_clerk.verify import verify_token


@lru_cache(maxsize=1)
def _get_client() -> tuple[str, JWKSClient]:
    issuer = os.environ["CLERK_ISSUER"]
    jwks_url = os.environ.get("CLERK_JWKS_URL") or f"{issuer}/.well-known/jwks.json"
    return issuer, JWKSClient(jwks_url)


async def get_current_clerk_user(
    authorization: str = Header(default=""),
) -> ClerkClaims:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    issuer, jwks = _get_client()
    try:
        return await verify_token(token, issuer=issuer, jwks=jwks)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
