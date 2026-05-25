import pytest
from pydantic import BaseModel

from cache_semantic import cache_exact


async def test_miss_then_hit_returns_same_value(fake_redis):
    calls = 0

    @cache_exact(namespace="test", ttl=60)
    async def expensive(prompt: str) -> dict:
        nonlocal calls
        calls += 1
        return {"answer": f"echo:{prompt}", "n": calls}

    r1 = await expensive("hello")
    r2 = await expensive("hello")

    assert r1 == r2 == {"answer": "echo:hello", "n": 1}
    assert calls == 1, "second call should hit cache, not re-execute fn"


async def test_different_prompts_dont_collide(fake_redis):
    seen = []

    @cache_exact(namespace="test", ttl=60)
    async def fn(prompt: str) -> str:
        seen.append(prompt)
        return prompt.upper()

    assert await fn("a") == "A"
    assert await fn("b") == "B"
    assert await fn("a") == "A"  # cache hit

    assert seen == ["a", "b"]


async def test_loads_reconstructs_pydantic_on_hit(fake_redis):
    class Resp(BaseModel):
        value: int
        label: str

    @cache_exact(namespace="test", ttl=60, loads=Resp.model_validate)
    async def fn(prompt: str) -> Resp:
        return Resp(value=42, label=prompt)

    miss = await fn("x")
    hit = await fn("x")

    assert isinstance(miss, Resp) and isinstance(hit, Resp)
    assert miss == hit == Resp(value=42, label="x")


async def test_non_string_arg_bypasses_cache(fake_redis):
    calls = 0

    @cache_exact(namespace="test", ttl=60)
    async def fn(prompt) -> int:
        nonlocal calls
        calls += 1
        return calls

    assert await fn(123) == 1
    assert await fn(123) == 2  # not cached → fn re-run


async def test_namespaces_are_isolated(fake_redis):
    @cache_exact(namespace="ns-a", ttl=60)
    async def a(prompt: str) -> str:
        return f"A:{prompt}"

    @cache_exact(namespace="ns-b", ttl=60)
    async def b(prompt: str) -> str:
        return f"B:{prompt}"

    # Same prompt, two namespaces → no cross-pollution
    assert await a("hello") == "A:hello"
    assert await b("hello") == "B:hello"
    assert await a("hello") == "A:hello"  # cache hit, not "B:hello"


async def test_custom_prompt_arg_name(fake_redis):
    calls = 0

    @cache_exact(namespace="test", ttl=60, prompt_arg="question")
    async def fn(question: str) -> str:
        nonlocal calls
        calls += 1
        return question[::-1]

    assert await fn(question="abc") == "cba"
    assert await fn(question="abc") == "cba"
    assert calls == 1


async def test_ttl_is_persisted_in_redis(fake_redis):
    @cache_exact(namespace="test", ttl=42)
    async def fn(prompt: str) -> str:
        return "x"

    await fn("hello")

    # Inspect raw key in fakeredis
    keys = await fake_redis.keys("cache:test:exact:*")
    assert len(keys) == 1
    ttl = await fake_redis.ttl(keys[0])
    assert 0 < ttl <= 42
