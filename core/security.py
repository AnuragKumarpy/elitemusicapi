"""
API Key authentication, tier resolution, and security context provider.
"""
import hashlib
import secrets
from typing import Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.config import settings
from app.core.database import get_db
from app.core.redis import get_redis_client
from app.models.db_models import ApiKey

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class SecurityContext(BaseModel):
    api_key: str
    key_hash: str
    tier: str
    is_master: bool
    tenant_id: Optional[str] = None
    daily_limit: int = 50
    max_concurrent_vcs: int = 1


def hash_api_key(key: str) -> str:
    """Generate SHA-256 hash of API key for secure database indexing."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_new_api_key(tier: str = "tier_free") -> str:
    """Generate cryptographically secure client API key."""
    prefix = "client_live_"
    random_part = secrets.token_hex(16)
    return f"{prefix}{random_part}"


async def get_security_context(
    x_api_key: Optional[str] = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
) -> SecurityContext:
    """
    Authenticate incoming request using X-API-Key header.
    Handles Master Admin Key bypass and Redis-cached API key lookups.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: X-API-Key header is missing."
        )

    # 1. Check Master / Owner Admin Key
    if x_api_key == settings.MASTER_ADMIN_KEY:
        return SecurityContext(
            api_key=x_api_key,
            key_hash=hash_api_key(x_api_key),
            tier="tier_enterprise",
            is_master=True,
            tenant_id="master_owner",
            daily_limit=-1,
            max_concurrent_vcs=9999
        )

    # 2. Check Redis Cache for Fast Verification (<1ms)
    key_hash = hash_api_key(x_api_key)
    cached_tier = await redis.hget(f"apikey:{key_hash}", "tier")
    if cached_tier:
        cached_tenant = await redis.hget(f"apikey:{key_hash}", "tenant_id")
        cached_limit = int(await redis.hget(f"apikey:{key_hash}", "daily_limit") or 50)
        cached_vcs = int(await redis.hget(f"apikey:{key_hash}", "max_vcs") or 1)
        return SecurityContext(
            api_key=x_api_key,
            key_hash=key_hash,
            tier=cached_tier,
            is_master=False,
            tenant_id=cached_tenant,
            daily_limit=cached_limit,
            max_concurrent_vcs=cached_vcs
        )

    # 3. Fallback to Database Query
    query = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    result = await db.execute(query)
    api_key_record = result.scalars().first()

    if not api_key_record:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Invalid or revoked API key."
        )

    # 4. Cache in Redis for 1 Hour
    await redis.hset(
        f"apikey:{key_hash}",
        mapping={
            "tier": api_key_record.tier,
            "tenant_id": api_key_record.tenant_id,
            "daily_limit": str(api_key_record.daily_limit),
            "max_vcs": str(api_key_record.max_concurrent_vcs)
        }
    )
    await redis.expire(f"apikey:{key_hash}", 3600)

    return SecurityContext(
        api_key=x_api_key,
        key_hash=key_hash,
        tier=api_key_record.tier,
        is_master=False,
        tenant_id=api_key_record.tenant_id,
        daily_limit=api_key_record.daily_limit,
        max_concurrent_vcs=api_key_record.max_concurrent_vcs
    )
