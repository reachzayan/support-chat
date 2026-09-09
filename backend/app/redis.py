import redis.asyncio as redis

from app.settings import get_settings

_pool: redis.ConnectionPool | None = None
_client: redis.Redis | None = None


def _pool_from_settings() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def get_redis() -> redis.Redis:
    global _pool, _client
    if _client is None:
        _pool = _pool_from_settings()
        _client = redis.Redis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    global _pool, _client
    if _client is not None:
        await _client.aclose()
    if _pool is not None:
        await _pool.aclose()
    _client = None
    _pool = None


def reset_redis() -> None:
    global _pool, _client
    _client = None
    _pool = None
