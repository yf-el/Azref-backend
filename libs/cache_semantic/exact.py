import hashlib
import json
import logging
from functools import wraps
from typing import Any, Awaitable, Callable

from cache_semantic.client import get_redis

log = logging.getLogger(__name__)


def _exact_key(namespace: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"cache:{namespace}:exact:{digest}"


def _jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def cache_exact(
    namespace: str,
    ttl: int = 86400,
    prompt_arg: str = "prompt",
    loads: Callable[[Any], Any] | None = None,
) -> Callable:
    """Decorator: cache an async call by the SHA256 of one string argument.

    Wrapped function must be async. Return value is stored as JSON; pass
    `loads` to reconstruct a richer type on hit (e.g. `MyModel.model_validate`).
    Lookup is exact-match — use [[cache_semantic]] for fuzzy matching.
    """

    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            text = kwargs.get(prompt_arg)
            if text is None and args:
                text = args[0]
            if not isinstance(text, str):
                return await fn(*args, **kwargs)

            redis = get_redis()
            key = _exact_key(namespace, text)

            cached = await redis.get(key)
            if cached is not None:
                log.info("cache_exact hit", extra={"namespace": namespace, "key": key})
                payload = json.loads(cached)
                return loads(payload) if loads is not None else payload

            log.info("cache_exact miss", extra={"namespace": namespace, "key": key})
            result = await fn(*args, **kwargs)
            await redis.set(key, json.dumps(result, default=_jsonable), ex=ttl)
            return result

        return wrapper

    return deco
