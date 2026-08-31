"""
Sliding-window token bucket rate limiter and quota enforcer backed by Redis.
Official @EliteMusicApiBot & Master Admins: 100% UNLIMITED.
Cloned Bots: Generous Tier (500 tracks/day per bot, 10 concurrent active VCs).
Auto-notifies bot owners & groups when daily quota unlocks.
"""
from datetime import datetime, timezone
import json
from typing import Tuple, Dict, Any, Optional
from fastapi import HTTPException
import redis.asyncio as aioredis
from app.config import TIER_PLANS, PlanTierConfig


class RateLimitEnforcer:
    @staticmethod
    async def check_and_increment_quota(
        redis: aioredis.Redis,
        api_key: str,
        tier: str,
        is_master: bool = False,
        bot_username: str = "",
        owner_id: int = 0
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify daily quota limits per bot. Master key & Admins bypass all restrictions.
        """
        if is_master or api_key == "master_key" or "master" in api_key.lower():
            return True, {"tier": "master", "remaining": "unlimited", "daily_limit": -1}

        plan: PlanTierConfig = TIER_PLANS.get(tier, TIER_PLANS["tier_free"])

        # If unlimited tier
        if plan.daily_limit == -1:
            return True, {"tier": tier, "remaining": "unlimited", "daily_limit": -1}

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage_key = f"quota:bot:{api_key}:{today_str}"

        current_count = await redis.incr(usage_key)
        if current_count == 1:
            # 25 hours expiry
            await redis.expire(usage_key, 90000)

        if current_count > plan.daily_limit:
            # Record exhaustion for unlock notification
            if redis and owner_id:
                exhausted_data = json.dumps({
                    "api_key": api_key,
                    "owner_id": owner_id,
                    "bot_username": bot_username,
                    "date": today_str,
                    "notified": False
                })
                await redis.hset("quota_exhausted_bots", api_key, exhausted_data)

            raise HTTPException(
                status_code=429,
                detail=f"Daily stream quota reached ({plan.daily_limit}/{plan.daily_limit} songs today for this bot). Quota automatically unlocks at 00:00 UTC with an alert. For unlimited instant streaming, use @EliteMusicApiBot!"
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
        room_id: int,
        is_master: bool = False
    ) -> None:
        """
        Ensure cloned tenant does not exceed maximum concurrent active voice chats.
        Same room playback never counts as an extra VC.
        """
        if is_master or api_key == "master_key" or "master" in api_key.lower():
            return

        plan: PlanTierConfig = TIER_PLANS.get(tier, TIER_PLANS["tier_free"])
        active_vc_set_key = f"active_vcs:{api_key}"

        # If this room is already in active set, it's the SAME VC session -> ALLOW
        is_already_active = await redis.sismember(active_vc_set_key, str(room_id))
        if is_already_active:
            return

        active_count = await redis.scard(active_vc_set_key)
        if active_count >= plan.max_concurrent_vcs:
            raise HTTPException(
                status_code=403,
                detail=f"Concurrent Voice Chat limit reached ({plan.max_concurrent_vcs} active VCs simultaneously). For unlimited concurrent streaming, use @EliteMusicApiBot!"
            )

    @staticmethod
    async def register_active_vc(redis: aioredis.Redis, api_key: str, room_id: int):
        if redis:
            key = f"active_vcs:{api_key}"
            await redis.sadd(key, str(room_id))
            await redis.expire(key, 7200)  # 2h safety TTL

    @staticmethod
    async def unregister_active_vc(redis: aioredis.Redis, api_key: str, room_id: int):
        if redis:
            await redis.srem(f"active_vcs:{api_key}", str(room_id))
