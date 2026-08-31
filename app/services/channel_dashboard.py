import asyncio

class ChannelDashboardService:
    def __init__(self, bot=None):
        self.bot = bot
        self._task = None

    def start(self):
        pass

    async def sync_now(self):
        pass

    async def stop(self):
        pass

async def sync_channel_post():
    pass

async def run_dashboard_loop():
    while True:
        await asyncio.sleep(3600)
