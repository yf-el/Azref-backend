"""
Async PostgreSQL connection pool (singleton).
"""

import asyncpg
from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def query(sql: str, *params) -> list[dict]:
    """Execute a SELECT query and return rows as dicts."""
    pool = await get_pool()
    rows = await pool.fetch(sql, *params)
    return [dict(r) for r in rows]
