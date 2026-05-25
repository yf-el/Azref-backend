import json
import logging
from functools import wraps
from typing import Any, Awaitable, Callable

import numpy as np

from cache_semantic.client import get_redis
from cache_semantic.hashing import hash_key

log = logging.getLogger(__name__)

EmbedFn = Callable[[str], Awaitable[np.ndarray]]


def cache_semantic(
    namespace: str,
    embed_fn: EmbedFn,
    ttl: int = 86400,
    prompt_arg: str = "prompt",
    bits: int = 8,
) -> Callable:
    """Decorator: cache an async LLM call by the semantic hash of its prompt.

    The wrapped function must be async and accept a string prompt argument
    (positional or keyword) under the name `prompt_arg`. The return value
    must be JSON-serializable.
    """

    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            prompt = kwargs.get(prompt_arg)
            if prompt is None and args:
                prompt = args[0]
            if not isinstance(prompt, str):
                return await fn(*args, **kwargs)

            redis = get_redis()
            vec = await embed_fn(prompt)
            key = hash_key(namespace, vec, bits=bits)

            cached = await redis.get(key)
            if cached is not None:
                log.info("cache_semantic hit", extra={"namespace": namespace, "key": key})
                return json.loads(cached)

            log.info("cache_semantic miss", extra={"namespace": namespace, "key": key})
            result = await fn(*args, **kwargs)
            await redis.set(key, json.dumps(result), ex=ttl)
            return result

        return wrapper

    return deco
