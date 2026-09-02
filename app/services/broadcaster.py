"""
High-Speed Distributed Mass Broadcasting Engine.
Supports broadcasting to DM users and Supergroups across the main bot and all clone bots.
Complies with Telegram flood limits (25-30 msgs/sec per bot token).
"""
import asyncio
import os
import json
import time
import logging
from typing import List, Optional, Dict, Any
from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from app.services.db_service import db_service

logger = logging.getLogger("elitemusic.broadcaster")


class Broadcaster:
    @staticmethod
    def _load_clone_tokens() -> Dict[str, str]:
        """Loads bot_username -> token mapping from cloned_bots.json."""
        paths = [
            "/home/ubuntu/elitemusicapi/cloned_bots.json",
            "/Users/mac/Desktop/mybots/elitemusicapi/cloned_bots.json",
            os.path.join(os.getcwd(), "cloned_bots.json"),
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        data = json.load(f)
                        tokens = {}
                        for item in data:
                            u = item.get("username") or item.get("bot_name")
                            t = item.get("token")
                            if u and t:
                                tokens[u.lower().replace("@", "")] = t
                        return tokens
                except Exception as e:
                    logger.warning(f"Error reading cloned_bots.json: {e}")
        return {}

    @classmethod
    async def broadcast_message(
        cls,
        bot: Bot,
        target_ids: List[int],
        source_message: Message,
        is_chat: bool = False,
        source_bot: str = "global"
    ) -> Dict[str, Any]:
        """
        Broadcast a message across targeted IDs with rate-limit handling.
        """
        total = len(target_ids)
        success = 0
        failed = 0
        start_time = time.time()

        for idx, target_id in enumerate(target_ids):
            try:
                await source_message.copy_to(chat_id=target_id)
                success += 1
            except TelegramForbiddenError:
                failed += 1
                if is_chat:
                    await db_service.mark_chat_inactive(target_id)
                else:
                    await db_service.mark_user_blocked(target_id)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await source_message.copy_to(chat_id=target_id)
                    success += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1

            if idx % 20 == 0:
                await asyncio.sleep(0.8)

        elapsed = time.time() - start_time
        snippet = source_message.text or source_message.caption or "Media Broadcast"

        sender_id = source_message.from_user.id if source_message.from_user else 0
        sender_name = source_message.from_user.full_name if source_message.from_user else "Admin"
        await db_service.log_broadcast(
            sender_id=sender_id,
            sender_name=sender_name,
            target_type="chats" if is_chat else "users",
            source_bot=source_bot,
            total_targets=total,
            success_count=success,
            failed_count=failed,
            snippet=snippet
        )

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "elapsed_seconds": round(elapsed, 2)
        }

    @classmethod
    async def distributed_broadcast(
        cls,
        main_bot: Bot,
        source_message: Message,
        target_type: str = "users"  # 'users' or 'chats'
    ) -> Dict[str, Any]:
        """
        Groups targets by source_bot and dispatches via each clone bot token in parallel.
        """
        clone_tokens = cls._load_clone_tokens()
        start_time = time.time()
        overall_total = 0
        overall_success = 0
        overall_failed = 0

        # Query all active targets
        if target_type == "chats":
            all_targets = await db_service.get_all_active_chats()
        else:
            all_targets = await db_service.get_all_active_users()

        # Group by source_bot
        bot_groups: Dict[str, List[int]] = {}
        for t in all_targets:
            s_bot = (t.source_bot or "main").lower().replace("@", "")
            bot_groups.setdefault(s_bot, []).append(t.chat_id if hasattr(t, "chat_id") else t.user_id)

        tasks = []
        # Main bot broadcast
        main_targets = bot_groups.pop("main", []) + bot_groups.pop("elitemusicapibot", [])
        if main_targets:
            overall_total += len(main_targets)
            tasks.append(cls.broadcast_message(main_bot, main_targets, source_message, is_chat=(target_type == "chats"), source_bot="EliteMusicApiBot"))

        # Clone bots broadcast
        for bot_username, target_list in bot_groups.items():
            token = clone_tokens.get(bot_username)
            if token and target_list:
                overall_total += len(target_list)
                async def _run_clone_bc(c_token, c_targets, c_name):
                    c_bot = Bot(token=c_token)
                    try:
                        return await cls.broadcast_message(c_bot, c_targets, source_message, is_chat=(target_type == "chats"), source_bot=c_name)
                    finally:
                        await c_bot.session.close()
                tasks.append(_run_clone_bc(token, target_list, bot_username))
            elif target_list:
                # Fallback to main bot if clone token not found
                overall_total += len(target_list)
                tasks.append(cls.broadcast_message(main_bot, target_list, source_message, is_chat=(target_type == "chats"), source_bot=bot_username))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                overall_success += r.get("success", 0)
                overall_failed += r.get("failed", 0)

        elapsed = time.time() - start_time
        return {
            "total": overall_total,
            "success": overall_success,
            "failed": overall_failed,
            "elapsed_seconds": round(elapsed, 2),
            "bots_dispatched": len(tasks)
        }


broadcaster = Broadcaster()
