"""
High-Speed Mass Broadcasting & Announcement Engine.
Supports broadcasting to DM users and Supergroups with Telegram rate limit compliance.
"""
import asyncio
import time
from typing import List, Optional, Dict, Any
from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from app.services.db_service import db_service


class Broadcaster:
    @staticmethod
    async def broadcast_message(
        bot: Bot,
        target_ids: List[int],
        source_message: Message,
        is_chat: bool = False,
        source_bot: str = "global"
    ) -> Dict[str, Any]:
        """
        Broadcast a message (text, photo, video, audio, forward) to a list of Telegram IDs.
        """
        total = len(target_ids)
        success = 0
        failed = 0
        start_time = time.time()

        for idx, target_id in enumerate(target_ids):
            try:
                # Copy source message with all media, caption, buttons, entities preserved
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

            # Comply with Telegram flood limits (~25 msgs/sec for bots)
            if idx % 20 == 0:
                await asyncio.sleep(0.8)

        elapsed = time.time() - start_time
        snippet = source_message.text or source_message.caption or "Media Broadcast"

        # Log broadcast to DB
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


broadcaster = Broadcaster()
