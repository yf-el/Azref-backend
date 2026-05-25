import os
import sys
from pathlib import Path

import fakeredis.aioredis
import pytest

# Make `libs/` importable when running pytest from this dir or repo root.
_LIBS = Path(__file__).resolve().parents[2]
if str(_LIBS) not in sys.path:
    sys.path.insert(0, str(_LIBS))

os.environ.setdefault("REDIS_URL", "redis://fake/0")


@pytest.fixture
async def fake_redis(monkeypatch):
    """Replace the cache_semantic singleton with an in-memory fakeredis."""
    import cache_semantic.client as client_mod

    fake = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr(client_mod, "_client", fake)
    yield fake
    await fake.aclose()
