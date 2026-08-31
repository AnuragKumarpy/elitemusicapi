"""
Redis async client connection pool and state management.
"""
import asyncio
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings

_redis_client: Optional[aioredis.Redis] = None
_loop_id: Optional[int] = None


async def get_redis_client() -> aioredis.Redis:
    global _redis_client, _loop_id
    current_loop = id(asyncio.get_running_loop())

    if _redis_client is None or _loop_id != current_loop:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5.0,
            retry_on_timeout=True
        )
        _loop_id = current_loop
    return _redis_client


async def close_redis_client():
    global _redis_client, _loop_id
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
        _loop_id = None
