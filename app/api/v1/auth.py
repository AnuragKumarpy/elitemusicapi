"""
Authentication, Tenant Registration, and API Key Management Endpoints.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.redis import get_redis_client
from app.core.security import generate_new_api_key, hash_api_key, get_security_context, SecurityContext
from app.models.db_models import Tenant, ApiKey
from app.models.schemas import TenantRegisterRequest, TenantResponse, ApiKeyResponse
from app.config import TIER_PLANS

router = APIRouter(prefix="/auth", tags=["Authentication & API Keys"])


@router.post("/register", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(
    req: TenantRegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Register a new developer account and issue an initial API key.
    """
    # Check if email already registered
    existing = await db.execute(select(Tenant).where(Tenant.email == req.email))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A developer account with this email already exists."
        )

    # 1. Create Tenant Record
    tenant = Tenant(name=req.name, email=req.email)
    db.add(tenant)
    await db.flush()

    # 2. Generate API Key
    raw_key = generate_new_api_key(req.tier)
    key_hash = hash_api_key(raw_key)
    prefix = raw_key[:16]

    plan = TIER_PLANS.get(req.tier, TIER_PLANS["tier_free"])

    api_key_record = ApiKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        prefix=prefix,
        tier=req.tier,
        daily_limit=plan.daily_limit,
        max_concurrent_vcs=plan.max_concurrent_vcs,
        is_active=True
    )
    db.add(api_key_record)
    await db.commit()

    # 3. Cache API Key in Redis
    await redis.hset(
        f"apikey:{key_hash}",
        mapping={
            "tier": req.tier,
            "tenant_id": tenant.id,
            "daily_limit": str(plan.daily_limit),
            "max_vcs": str(plan.max_concurrent_vcs)
        }
    )
    await redis.expire(f"apikey:{key_hash}", 86400)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        email=tenant.email,
        tier=req.tier,
        api_key=raw_key
    )


@router.get("/me", response_model=ApiKeyResponse)
async def get_current_key_info(
    sec: SecurityContext = Depends(get_security_context)
):
    """
    Inspect the calling API Key's tier, quotas, and permissions.
    """
    return ApiKeyResponse(
        api_key=f"{sec.api_key[:12]}...",
        tier=sec.tier,
        daily_limit=sec.daily_limit,
        max_concurrent_vcs=sec.max_concurrent_vcs,
        created_at=datetime.now(timezone.utc).isoformat()
    )
