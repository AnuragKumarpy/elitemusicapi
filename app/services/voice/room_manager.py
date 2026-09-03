"""
Room and Queue Management Service with Persistent DSP Profile.
Tracks in queue automatically inherit the room's active DSP equalizers (Bass, 8D, Speed).
Features seamless automated queue advancement when songs complete, and leaves VC when queue is empty.
"""
import asyncio
from typing import Dict, List, Optional, Any
from app.models.schemas import (
    TrackInfo,
    DSPConfig,
    DSPUpdateRequest,
    PlaybackResponse,
    RoomStateResponse
)
from app.services.voice.assistant_pool import assistant_pool, AssistantAccount
from app.services.voice.ntg_streamer import VoiceStreamSession


class VoiceRoom:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.queue: List[TrackInfo] = []
        self.current_track: Optional[TrackInfo] = None
        self.active_session: Optional[VoiceStreamSession] = None
        self.assistant: Optional[AssistantAccount] = None
        self.dsp: DSPConfig = DSPConfig()
        self.is_paused: bool = False
        self._lock = asyncio.Lock()
        self._duration_task: Optional[asyncio.Task] = None

    async def enqueue_and_play(
        self,
        track: TrackInfo,
        dsp_override: Optional[DSPConfig] = None,
        force_play: bool = False
    ) -> PlaybackResponse:
        """Enqueue track. If no track currently playing or force_play=True, start streaming immediately."""
        async with self._lock:
            if dsp_override:
                self.dsp = dsp_override

            if force_play and self.active_session:
                if self._duration_task:
                    self._duration_task.cancel()
                    self._duration_task = None
                await self.active_session.stop()
                self.active_session = None
                self.current_track = None

            if not self.current_track or force_play:
                if self.active_session and force_play:
                    await self.active_session.stop()
                    self.active_session = None

                self.current_track = track
                if not self.assistant:
                    self.assistant = await assistant_pool.acquire_assistant_for_room(self.chat_id)
                self.active_session = VoiceStreamSession(
                    room_id=self.chat_id,
                    assistant=self.assistant,
                    track=track,
                    dsp=self.dsp
                )
                await self.active_session.start_streaming()
                self._schedule_duration_watcher(track.duration_seconds)
                return PlaybackResponse(
                    status="STREAMING",
                    room_id=self.chat_id,
                    track=track,
                    worker_node=self.assistant.username or f"assistant_{self.assistant.assistant_id}",
                    allocated_ram_mb=48.0,
                    message="Stream initiated successfully"
                )
            else:
                self.queue.append(track)
                asyncio.create_task(self._prefetch_queue_streams())
                return PlaybackResponse(
                    status="QUEUED",
                    room_id=self.chat_id,
                    track=track,
                    worker_node=self.assistant.username if self.assistant else "queued",
                    allocated_ram_mb=48.0,
                    message="Track added to room queue"
                )

    async def _prefetch_queue_streams(self):
        """Pre-extract upcoming queued tracks in the background for 0ms gapless playback."""
        try:
            from app.services.extractor.resolver import media_resolver
            for track in list(self.queue)[:2]:  # Pre-cache next 2 tracks
                if not track.stream_url or 'youtube.com' in track.stream_url:
                    vid_url = f'https://www.youtube.com/watch?v={track.video_id}' if track.video_id else (track.url or '')
                    if vid_url:
                        direct_url = await media_resolver._extract_ytdlp_stream(vid_url)
                        if direct_url:
                            track.stream_url = direct_url
                            track.audio_stream_url = direct_url
                            print(f'[VoiceRoom] ⚡ Pre-cached background stream for: {track.title}')
        except Exception as e:
            print(f'[VoiceRoom] Pre-fetch background task notice: {e}')

    def _schedule_duration_watcher(self, duration_sec: int):
        if self._duration_task:
            self._duration_task.cancel()
        if duration_sec > 0:
            self._duration_task = asyncio.create_task(self._watch_track_end(duration_sec + 3))

    async def _watch_track_end(self, wait_sec: int):
        try:
            await asyncio.sleep(wait_sec)
            print(f"[VoiceRoom] Watchdog timer expired for VC {self.chat_id}. Advancing queue...")
            from app.services.voice.room_manager import room_manager
            await room_manager.on_stream_end(self.chat_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[VoiceRoom] Watchdog note: {e}")

    async def skip(self) -> Optional[TrackInfo]:
        async with self._lock:
            if self._duration_task:
                self._duration_task.cancel()
                self._duration_task = None

            if self.active_session:
                await self.active_session.stop()
                self.active_session = None

            if self.queue:
                next_track = self.queue.pop(0)
                asyncio.create_task(self._prefetch_queue_streams())
                self.current_track = next_track
                if not self.assistant:
                    self.assistant = await assistant_pool.acquire_assistant_for_room(self.chat_id)
                self.active_session = VoiceStreamSession(
                    room_id=self.chat_id,
                    assistant=self.assistant,
                    track=next_track,
                    dsp=self.dsp
                )
                await self.active_session.start_streaming()
                self._schedule_duration_watcher(next_track.duration_seconds)
                print(f"[VoiceRoom] VC {self.chat_id}: Advanced to next track '{next_track.title}'")
                return next_track
            else:
                self.current_track = None
                if self.assistant:
                    await assistant_pool.release_assistant_from_room(self.chat_id, self.assistant.assistant_id)
                    self.assistant = None
                print(f"[VoiceRoom] VC {self.chat_id}: Queue empty. Assistant left voice chat.")
                return None

    async def stop(self):
        async with self._lock:
            if self._duration_task:
                self._duration_task.cancel()
                self._duration_task = None
            if self.active_session:
                await self.active_session.stop()
                self.active_session = None
            self.queue.clear()
            self.current_track = None
            if self.assistant:
                await assistant_pool.release_assistant_from_room(self.chat_id, self.assistant.assistant_id)
                self.assistant = None

    async def pause(self):
        if self.active_session:
            await self.active_session.pause()
            self.is_paused = True

    async def resume(self):
        if self.active_session:
            await self.active_session.resume()
            self.is_paused = False

    async def seek(self, position_ms: int):
        if self.active_session:
            await self.active_session.seek(position_ms)

    async def update_dsp(self, dsp_req: DSPUpdateRequest) -> DSPConfig:
        """Update persistent room DSP and apply immediately to live voice chat session."""
        if dsp_req.bass_boost_db is not None:
            self.dsp.bass_boost_db = dsp_req.bass_boost_db
        if dsp_req.spatial_8d is not None:
            self.dsp.spatial_8d = dsp_req.spatial_8d
        if dsp_req.speed is not None:
            self.dsp.speed = dsp_req.speed
        if dsp_req.volume is not None:
            self.dsp.volume = dsp_req.volume
        if dsp_req.nightcore is not None:
            self.dsp.nightcore = dsp_req.nightcore

        if self.active_session:
            await self.active_session.update_dsp(self.dsp)
        return self.dsp

    def get_state(self) -> RoomStateResponse:
        return RoomStateResponse(
            chat_id=self.chat_id,
            status="STREAMING" if self.current_track and not self.is_paused else ("PAUSED" if self.is_paused else "IDLE"),
            current_track=self.current_track,
            queue_length=len(self.queue),
            active_assistant_id=self.assistant.assistant_id if self.assistant else None,
            dsp=self.dsp,
            progress_ms=self.active_session.current_progress_ms if self.active_session else 0
        )


class RoomManager:
    def __init__(self):
        self.rooms: Dict[int, VoiceRoom] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_room(self, chat_id: int) -> VoiceRoom:
        async with self._lock:
            if chat_id not in self.rooms:
                self.rooms[chat_id] = VoiceRoom(chat_id)
            return self.rooms[chat_id]

    async def play_track(
        self,
        redis: Any,
        room_id: int,
        track: TrackInfo,
        dsp: Optional[DSPConfig] = None,
        position: str = "end",
        tier: str = "Free"
    ) -> PlaybackResponse:
        room = await self.get_or_create_room(room_id)
        force_now = (position in ("instant", "force", "now") or track.media_type == "video")
        return await room.enqueue_and_play(track, dsp_override=dsp, force_play=force_now)

    async def update_dsp(self, chat_id: int, req: DSPUpdateRequest) -> DSPConfig:
        room = await self.get_or_create_room(chat_id)
        return await room.update_dsp(req)

    async def pause(self, chat_id: int):
        room = await self.get_or_create_room(chat_id)
        await room.pause()

    async def resume(self, chat_id: int):
        room = await self.get_or_create_room(chat_id)
        await room.resume()

    async def skip(self, redis: Any, chat_id: int, tier: str = "Free") -> Optional[TrackInfo]:
        room = await self.get_or_create_room(chat_id)
        next_track = await room.skip()
        if not next_track:
            async with self._lock:
                self.rooms.pop(chat_id, None)
        return next_track

    async def seek(self, chat_id: int, position_ms: int):
        room = await self.get_or_create_room(chat_id)
        await room.seek(position_ms)

    async def get_room_state(self, redis: Any, chat_id: int) -> RoomStateResponse:
        room = await self.get_or_create_room(chat_id)
        return room.get_state()

    async def stop(self, redis: Any, chat_id: int) -> bool:
        async with self._lock:
            if chat_id in self.rooms:
                await self.rooms[chat_id].stop()
                del self.rooms[chat_id]
                return True
            return False

    async def on_stream_end(self, chat_id: int):
        """
        Invoked when PyTgCalls or Watchdog reports stream completion.
        If more songs in queue -> play next.
        If queue is empty -> automatically leave voice chat and release assistant.
        """
        async with self._lock:
            room = self.rooms.get(chat_id)
            if not room:
                return

        next_track = await room.skip()
        if not next_track:
            async with self._lock:
                self.rooms.pop(chat_id, None)
            print(f"[RoomManager] Voice Chat {chat_id}: Queue is empty. Assistant left VC.")
        else:
            print(f"[RoomManager] Voice Chat {chat_id}: Automatically streaming next track '{next_track.title}'")


room_manager = RoomManager()
