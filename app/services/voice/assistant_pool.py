"""
Optimized High-Density Assistant Session Pool.
Maximizes traffic packing: One assistant userbot streams concurrently in multiple Voice Chats
(up to 5-8 VCs simultaneously) in sequential priority before spilling over to the next assistant.
Registers PyTgCalls event handlers to auto-leave Voice Chats when queues are empty.
"""
import asyncio
from typing import Dict, List, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UserAlreadyParticipantError
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, Update, StreamEnded, ChatUpdate
from app.config import settings

MAX_CONCURRENT_VCS_PER_ASSISTANT = 5


class AssistantAccount:
    def __init__(self, priority_index: int, session_string: str, max_concurrent_vcs: int = MAX_CONCURRENT_VCS_PER_ASSISTANT):
        self.priority_index = priority_index
        self.assistant_id: int = 0
        self.username: str = ""
        self.first_name: str = ""
        self.session_string = session_string
        self.max_concurrent_vcs = max_concurrent_vcs
        self.active_vcs: set = set()
        self.is_healthy: bool = True
        self.client: Optional[TelegramClient] = None
        self.call_app: Optional[PyTgCalls] = None

    @property
    def current_load(self) -> int:
        return len(self.active_vcs)

    @property
    def is_available(self) -> bool:
        return self.is_healthy and self.current_load < self.max_concurrent_vcs

    async def start(self):
        if not self.session_string:
            return
        try:
            self.client = TelegramClient(
                StringSession(self.session_string),
                settings.TELEGRAM_API_ID,
                settings.TELEGRAM_API_HASH
            )
            await self.client.connect()
            if await self.client.is_user_authorized():
                me = await self.client.get_me()
                self.assistant_id = me.id
                self.username = me.username or f"user_{me.id}"
                self.first_name = me.first_name or "Assistant"
                self.call_app = PyTgCalls(self.client)
                
                self._register_handlers()

                await self.call_app.start()
                try:
                    await self.client.get_dialogs(limit=30)
                except Exception:
                    pass
                print(f"[AssistantPool] Priority #{self.priority_index+1}: {self.first_name} (@{self.username}, ID: {self.assistant_id}) READY. Capacity: {self.max_concurrent_vcs} concurrent VCs.")
            else:
                self.is_healthy = False
                print(f"[AssistantPool] Warning: Assistant priority #{self.priority_index+1} not authorized.")
        except Exception as e:
            self.is_healthy = False
            print(f"[AssistantPool] Failed to start assistant #{self.priority_index+1}: {e}")

    def _register_handlers(self):
        if not self.call_app:
            return

        @self.call_app.on_update()
        async def handle_call_update(client: PyTgCalls, update: Update):
            try:
                from app.services.voice.room_manager import room_manager
                if isinstance(update, StreamEnded):
                    chat_id = update.chat_id
                    print(f"[AssistantPool] StreamEnded event in VC {chat_id} on @{self.username}. Checking queue...")
                    asyncio.create_task(room_manager.on_stream_end(chat_id))
                elif isinstance(update, ChatUpdate):
                    chat_id = update.chat_id
                    if update.status in (
                        ChatUpdate.Status.LEFT_CALL,
                        ChatUpdate.Status.CLOSED_VOICE_CHAT,
                        ChatUpdate.Status.KICKED,
                        ChatUpdate.Status.DISCARDED_CALL
                    ):
                        print(f"[AssistantPool] ChatUpdate ({update.status}) in VC {chat_id} on @{self.username}. Cleaning up...")
                        asyncio.create_task(room_manager.stop(None, chat_id))
            except Exception as e:
                print(f"[AssistantPool] Error handling call update: {e}")

    async def stop(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass

    async def ensure_in_chat(self, chat_id: int, invite_link: Optional[str] = None):
        """Auto-join group via invite link and force-populate Telethon entity cache."""
        if not self.client:
            return

        try:
            return await self.client.get_entity(chat_id)
        except Exception:
            pass

        if invite_link:
            try:
                clean_link = invite_link.strip()
                if "+" in clean_link:
                    hash_val = clean_link.split("+")[-1].split("?")[0].split("/")[0]
                    try:
                        await self.client(ImportChatInviteRequest(hash=hash_val))
                    except UserAlreadyParticipantError:
                        pass
                elif "joinchat/" in clean_link:
                    hash_val = clean_link.split("joinchat/")[-1].split("?")[0].split("/")[0]
                    try:
                        await self.client(ImportChatInviteRequest(hash=hash_val))
                    except UserAlreadyParticipantError:
                        pass
                elif "t.me/" in clean_link:
                    uname = clean_link.split("t.me/")[-1].split("/")[0].split("?")[0]
                    await self.client(JoinChannelRequest(channel=uname))
            except Exception as e:
                print(f"[AssistantPool] Assistant auto-join note ({chat_id}): {e}")

        try:
            return await self.client.get_entity(chat_id)
        except Exception:
            try:
                await self.client.get_dialogs(limit=50)
                return await self.client.get_entity(chat_id)
            except Exception as e:
                print(f"[AssistantPool] Could not resolve entity for {chat_id} after dialog refresh: {e}")

    async def play(
        self,
        chat_id: int,
        media_url: str,
        audio_url: Optional[str] = None,
        is_video: bool = False,
        ffmpeg_params: Optional[str] = None,
        invite_link: Optional[str] = None
    ):
        if not self.call_app:
            raise RuntimeError(f"Assistant {self.assistant_id} PyTgCalls is not initialized.")
        
        await self.ensure_in_chat(chat_id, invite_link=invite_link)

        if is_video:
            media_stream = MediaStream(
                media_path=media_url,
                audio_path=audio_url if audio_url else media_url,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.HD_720p,
                ffmpeg_parameters=ffmpeg_params
            )
        else:
            media_stream = MediaStream(
                media_path=media_url,
                audio_path=media_url,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                ffmpeg_parameters=ffmpeg_params
            )

        # Smooth in-call stream switch (no disconnect/rejoin jitter)

        await self.call_app.play(chat_id, media_stream)
        self.active_vcs.add(chat_id)
        print(f"[AssistantPool] Assistant @{self.username} (Priority #{self.priority_index+1}) streaming in VC {chat_id}. Active concurrent VCs: {self.current_load}/{self.max_concurrent_vcs}")

    async def pause(self, chat_id: int):
        if self.call_app:
            await self.call_app.pause(chat_id)

    async def resume(self, chat_id: int):
        if self.call_app:
            await self.call_app.resume(chat_id)

    async def leave_call(self, chat_id: int):
        if self.call_app:
            try:
                await self.call_app.leave_call(chat_id)
            except Exception:
                pass
        self.active_vcs.discard(chat_id)
        print(f"[AssistantPool] Assistant @{self.username} left VC {chat_id}. Active concurrent VCs: {self.current_load}/{self.max_concurrent_vcs}")

    async def change_volume(self, chat_id: int, volume: int):
        if self.call_app:
            try:
                await self.call_app.change_volume_call(chat_id, volume)
            except Exception:
                pass


class AssistantSessionPool:
    def __init__(self):
        self.assistants: Dict[int, AssistantAccount] = {}
        self.assistants_priority_list: List[AssistantAccount] = []
        self._lock = asyncio.Lock()
        self._initialized = False

    async def start_pool(self):
        async with self._lock:
            if self._initialized:
                return
            
            raw_sessions = [s.strip() for s in settings.ASSISTANT_SESSION_STRINGS.split(",") if s.strip()]
            for idx, session in enumerate(raw_sessions):
                asst = AssistantAccount(idx, session)
                await asst.start()
                if asst.assistant_id:
                    self.assistants[asst.assistant_id] = asst
                    self.assistants_priority_list.append(asst)
            
            self._initialized = True
            print(f"[AssistantPool] Initialized {len(self.assistants_priority_list)} active priority assistants with multi-VC capacity packing.")

    async def stop_pool(self):
        async with self._lock:
            for asst in self.assistants_priority_list:
                await asst.stop()
            self._initialized = False

    async def acquire_assistant_for_room(self, room_id: int) -> AssistantAccount:
        """
        High-Density Traffic Packing Strategy:
        1. If assistant is already streaming in this room -> reuse it.
        2. Priority Packing: Route traffic to Priority #1 until its capacity (5 concurrent VCs) is full.
        3. Only when Priority #1 is at 5/5, spill over to Priority #2 (0/5 -> 5/5), and so on.
        """
        async with self._lock:
            # 1. Existing room check
            for asst in self.assistants_priority_list:
                if room_id in asst.active_vcs:
                    return asst

            # 2. Sequential Priority Packing (Fill #1 to capacity before touching #2)
            for asst in self.assistants_priority_list:
                if asst.is_healthy and asst.is_available:
                    asst.active_vcs.add(room_id)
                    return asst

            # 3. Fallback: least loaded if all at maximum capacity
            available = sorted([a for a in self.assistants_priority_list if a.is_healthy], key=lambda a: a.current_load)
            if not available:
                raise RuntimeError("No assistant accounts configured in pool.")
            
            selected = available[0]
            selected.active_vcs.add(room_id)
            return selected

    async def release_assistant_from_room(self, room_id: int, assistant_id: Optional[int] = None):
        async with self._lock:
            if assistant_id and assistant_id in self.assistants:
                await self.assistants[assistant_id].leave_call(room_id)
            else:
                for asst in self.assistants_priority_list:
                    if room_id in asst.active_vcs:
                        await asst.leave_call(room_id)

    async def handle_assistant_failover(self, room_id: int, failed_assistant_id: int) -> AssistantAccount:
        async with self._lock:
            if failed_assistant_id in self.assistants:
                self.assistants[failed_assistant_id].is_healthy = False
                await self.assistants[failed_assistant_id].leave_call(room_id)

            for asst in self.assistants_priority_list:
                if asst.assistant_id != failed_assistant_id and asst.is_available:
                    asst.active_vcs.add(room_id)
                    return asst

            for asst in self.assistants_priority_list:
                if asst.assistant_id != failed_assistant_id:
                    asst.active_vcs.add(room_id)
                    return asst

            raise RuntimeError("All assistant accounts in pool are currently unavailable.")


assistant_pool = AssistantSessionPool()
