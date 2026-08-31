"""
Sliding-window token bucket rate limiter and quota enforcer backed by Redis.
"""
from datetime import datetime, timezone
from typing import Tuple, Dict, Any
from fastapi import HTTPException
import redis.asyncio as aioredis
from app.config import TIER_PLANS, PlanTierConfig


class RateLimitEnforcer:
    @staticmethod
    async def check_and_increment_quota(
        redis: aioredis.Redis,
        api_key: str,
        tier: str,
        is_master: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify daily quota limits. Master key bypasses all restrictions.
        """
        if is_master:
            return True, {"tier": "master", "remaining": "unlimited", "daily_limit": -1}

        plan: PlanTierConfig = TIER_PLANS.get(tier, TIER_PLANS["tier_free"])

        # If unlimited tier
        if plan.daily_limit == -1:
            return True, {"tier": tier, "remaining": "unlimited", "daily_limit": -1}

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage_key = f"quota:{api_key}:{today_str}"

        # Increment daily counter
        current_count = await redis.incr(usage_key)
        if current_count == 1:
            # Expire after 24 hours + 1 hour buffer (90000 sec)
            await redis.expire(usage_key, 90000)

        if current_count > plan.daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily stream quota exceeded ({plan.daily_limit} tracks/day for {plan.name}). Please upgrade tier."
            )

        remaining = max(0, plan.daily_limit - current_count)
        return True, {
            "tier": tier,
            "used_today": current_count,
            "daily_limit": plan.daily_limit,
            "remaining_today": remaining
        }

    @staticmethod
    async def check_concurrent_vcs(
        redis: aioredis.Redis,
        api_key: str,
        tier: str,
        is_master: bool = False
    ) -> None:
        """
        Ensure tenant does not exceed maximum concurrent active voice chats.
        """
        if is_master:
            return

        plan: PlanTierConfig = TIER_PLANS.get(tier, TIER_PLANS["tier_free"])
        active_vc_set_key = f"active_vcs:{api_key}"
        active_count = await redis.scard(active_vc_set_key)

        if active_count >= plan.max_concurrent_vcs:
            raise HTTPException(
                status_code=403,
                detail=f"Maximum concurrent Voice Chat limit reached ({plan.max_concurrent_vcs} active rooms for {plan.name})."
            )

    @staticmethod
    async def register_active_vc(redis: aioredis.Redis, api_key: str, room_id: int):
        await redis.sadd(f"active_vcs:{api_key}", str(room_id))

    @staticmethod
    async def unregister_active_vc(redis: aioredis.Redis, api_key: str, room_id: int):
        await redis.srem(f"active_vcs:{api_key}", str(room_id))
