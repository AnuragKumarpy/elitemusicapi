"""
Batched asynchronous logger for Telegram Admin Channel.
Flushes formatted alerts every 2 seconds in batches to avoid Telegram 429 FLOOD_WAIT.
"""
import asyncio
import html
from typing import List, Optional
import aiohttp
from app.config import settings


class TelegramAdminLogger:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_LOGGER_BOT_TOKEN
        self.channel_id = settings.TELEGRAM_LOGGER_CHANNEL_ID
        self.enabled = settings.TELEGRAM_LOGGER_ENABLED and bool(self.bot_token) and bool(self.channel_id)
        self.flush_interval = settings.TELEGRAM_LOG_FLUSH_INTERVAL_SECONDS
        self.batch_size = settings.TELEGRAM_LOG_BATCH_SIZE
        self.queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Start background worker task."""
        if not self.enabled:
            return
        self._session = aiohttp.ClientSession()
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """Flush remaining logs and cleanly close background task."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()

    async def log_security_event(
        self,
        event_type: str,
        api_key_prefix: str,
        tier: str,
        user_id: Optional[int],
        room_id: Optional[int],
        violation: str,
        action: str,
        client_ip: Optional[str] = None
    ):
        """Enqueue security breach or quota alert."""
        text = (
            f"🚨 <b>[SECURITY ALERT: {html.escape(event_type)}]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Key:</b> <code>{html.escape(api_key_prefix)}...</code> (Tier: <i>{html.escape(tier)}</i>)\n"
            f"👤 <b>User ID:</b> <code>{user_id or 'N/A'}</code> | <b>IP:</b> <code>{client_ip or 'Private'}</code>\n"
            f"🎯 <b>Room ID:</b> <code>{room_id or 'N/A'}</code>\n"
            f"⚠️ <b>Violation:</b> {html.escape(violation)}\n"
            f"🛡️ <b>Action:</b> {html.escape(action)}"
        )
        await self._enqueue(text)

    async def log_stream_event(
        self,
        event: str,
        room_id: int,
        track_title: str,
        duration_sec: int,
        worker_node: str,
        tier: str
    ):
        """Enqueue regular stream event."""
        text = (
            f"🎧 <b>[STREAM EVENT: {html.escape(event)}]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎵 <b>Track:</b> {html.escape(track_title)} ({duration_sec}s)\n"
            f"🎯 <b>Room ID:</b> <code>{room_id}</code>\n"
            f"⚙️ <b>Worker:</b> <code>{html.escape(worker_node)}</code>\n"
            f"📊 <b>Tier:</b> <i>{html.escape(tier)}</i>"
        )
        await self._enqueue(text)

    async def log_system_health(
        self,
        active_streams: int,
        worker_ram_mb: float,
        ipv6_status: str
    ):
        """Enqueue system health report."""
        text = (
            f"📊 <b>[NODE HEALTH METRICS]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>Active Streams:</b> {active_streams}\n"
            f"🧠 <b>Worker RAM:</b> {worker_ram_mb:.1f} MB\n"
            f"🌐 <b>IPv6 Status:</b> {html.escape(ipv6_status)}"
        )
        await self._enqueue(text)

    async def _enqueue(self, formatted_message: str):
        if not self.enabled:
            return
        await self.queue.put(formatted_message)

    async def _worker_loop(self):
        base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        while True:
            try:
                batch: List[str] = []
                while not self.queue.empty() and len(batch) < self.batch_size:
                    item = await self.queue.get()
                    batch.append(item)
                    self.queue.task_done()

                if batch and self._session:
                    payload_text = "\n\n".join(batch)
                    try:
                        async with self._session.post(
                            base_url,
                            json={
                                "chat_id": self.channel_id,
                                "text": payload_text,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True,
                            },
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 429:
                                body = await resp.json()
                                retry_after = int(body.get("parameters", {}).get("retry_after", 5))
                                await asyncio.sleep(retry_after)
                    except Exception as err:
                        print(f"[TelegramLogger] Error posting logs: {err}")

                await asyncio.sleep(self.flush_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[TelegramLogger] Worker exception: {e}")
                await asyncio.sleep(self.flush_interval)


admin_logger = TelegramAdminLogger()
