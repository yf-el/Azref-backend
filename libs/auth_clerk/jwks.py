import time
from typing import Any

import httpx


class JWKSClient:
    def __init__(self, jwks_url: str, cache_ttl_seconds: int = 3600):
        self._url = jwks_url
        self._ttl = cache_ttl_seconds
        self._cache: dict[str, dict[str, Any]] = {}
        self._expires_at: float = 0.0

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self._url)
            response.raise_for_status()
            data = response.json()
        self._cache = {key["kid"]: key for key in data.get("keys", [])}
        self._expires_at = time.time() + self._ttl

    async def get_signing_key(self, kid: str) -> dict[str, Any]:
        if kid not in self._cache or time.time() >= self._expires_at:
            await self._refresh()
        if kid not in self._cache:
            raise ValueError(f"Unknown kid: {kid}")
        return self._cache[kid]
