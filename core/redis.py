"""
Redis async client connection pool and state management.
"""
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings

redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5.0,
            retry_on_timeout=True
        )
    return redis_client


async def close_redis_client():
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
