"""
Daily Quota Reset Notifier for Cloned Bots.
Monitors Redis for quota unlocks and alerts bot owners and supergroups when streaming becomes available.
"""
import asyncio
import json
from datetime import datetime, timezone
import aiohttp
from app.config import settings

POWERED_BY_FOOTER = '<tg-emoji emoji-id="6267107057304868214">⚡</tg-emoji> <i>Powered by</i> <a href="https://t.me/EliteBotsTelegram"><b>Elite Bots</b></a>'


class QuotaResetNotifier:
    def __init__(self):
        self._running = False
        self._task = None

    async def start(self, redis):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(redis))
        print("[QuotaNotifier] Daily limit reset notification monitor started.")

    async def _monitor_loop(self, redis):
        while self._running:
            try:
                if redis:
                    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    exhausted = await redis.hgetall("quota_exhausted_bots")
                    for api_key_bytes, val_bytes in exhausted.items():
                        api_key = api_key_bytes.decode() if isinstance(api_key_bytes, bytes) else str(api_key_bytes)
                        val = json.loads(val_bytes.decode() if isinstance(val_bytes, bytes) else str(val_bytes))
                        
                        recorded_date = val.get("date")
                        if recorded_date != today_str:
                            # Quota unlocked for the new day!
                            owner_id = val.get("owner_id")
                            bot_uname = val.get("bot_username", "Your Music Bot")
                            
                            notify_msg = (
                                f'<tg-emoji emoji-id="6264785189394717307">🎉</tg-emoji> <b>DAILY STREAMING LIMIT UNLOCKED!</b> <tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>\n\n'
                                f'<tg-emoji emoji-id="6267107057304868214">⚡</tg-emoji> <i>Your daily streaming quota for <b>@{bot_uname}</b> has been refreshed!</i>\n\n'
                                f'• <tg-emoji emoji-id="5463107823946717464">🎵</tg-emoji> <b>Daily Quota:</b> <code>500 Free Songs Available</code>\n'
                                f'• <tg-emoji emoji-id="5309832892262654231">🤖</tg-emoji> <b>Voice Concurrency:</b> <code>10 Active VCs</code>\n'
                                f'• <tg-emoji emoji-id="5251203410396458957">🛡</tg-emoji> <b>Engine Status:</b> <code>ONLINE (AWS eu-north-1)</code>\n\n'
                                f'👉 You and your supergroups can start streaming music again with <code>/play</code>!\n\n'
                                f"{POWERED_BY_FOOTER}"
                            )

                            if owner_id:
                                await self._send_telegram(owner_id, notify_msg)

                            await redis.hdel("quota_exhausted_bots", api_key)
            except Exception as e:
                print(f"[QuotaNotifier] Monitor loop error: {e}")

            await asyncio.sleep(60)

    async def _send_telegram(self, chat_id: int, text: str):
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        conn = aiohttp.TCPConnector(ssl=False)
        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
                async with session.post(url, json=payload) as r:
                    await r.json()
        except Exception:
            pass


quota_notifier = QuotaResetNotifier()
