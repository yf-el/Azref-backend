import os

from redis.asyncio import Redis, from_url

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        url = os.environ["REDIS_URL"]
        _client = from_url(url, encoding="utf-8", decode_responses=False)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
