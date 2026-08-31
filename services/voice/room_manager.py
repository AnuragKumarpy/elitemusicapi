"""
Room State and Distributed Queue Coordinator.
Maintains active voice sessions, Redis playlist queues, and WebSocket event broadcasting.
"""
import asyncio
import json
from typing import Dict, List, Optional, Set
from fastapi import WebSocket, HTTPException
import redis.asyncio as aioredis

from app.models.schemas import (
    TrackInfo,
    DSPConfig,
    DSPUpdateRequest,
    RoomStateResponse,
    PlaybackResponse,
    VideoConfig
)
from app.services.voice.assistant_pool import assistant_pool
from app.services.voice.ntg_streamer import VoiceStreamSession
from app.services.logger.telegram_logger import admin_logger


class RoomManager:
    def __init__(self):
        self.active_sessions: Dict[int, VoiceStreamSession] = {}
        self.room_dsp: Dict[int, DSPConfig] = {}
        self.ws_subscribers: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def play_track(
        self,
        redis: aioredis.Redis,
        room_id: int,
        track: TrackInfo,
        dsp: Optional[DSPConfig] = None,
        position: str = "tail",
        tier: str = "tier_free"
    ) -> PlaybackResponse:
        """
        Play track immediately or append to Redis queue.
        """
        async with self._lock:
            existing_session = self.active_sessions.get(room_id)
            current_dsp = dsp or self.room_dsp.get(room_id) or DSPConfig()
            self.room_dsp[room_id] = current_dsp

            # If room is currently streaming and not instant override
            if existing_session and existing_session.is_running and position != "instant":
                # Push to Redis Queue
                queue_key = f"queue:{room_id}"
                track_json = track.model_dump_json()
                if position == "head":
                    await redis.lpush(queue_key, track_json)
                else:
                    await redis.rpush(queue_key, track_json)

                queue_len = await redis.llen(queue_key)
                track.position_in_queue = queue_len

                await self._broadcast_event(room_id, "QUEUE_UPDATE", {
                    "action": "TRACK_ADDED",
                    "track": track.model_dump(),
                    "queue_length": queue_len
                })

                return PlaybackResponse(
                    status="QUEUED",
                    room_id=room_id,
                    track=track,
                    allocated_ram_mb=64 if track.media_type == "audio" else 192,
                    worker_node="worker-ec2-az1-priv",
                    active_assistant_id=existing_session.assistant_id
                )

            # Otherwise, start streaming immediately
            if existing_session:
                await existing_session.stop()

            # Acquire assistant from session pool
            assistant = await assistant_pool.acquire_assistant_for_room(room_id)

            session = VoiceStreamSession(
                room_id=room_id,
                assistant_id=assistant.assistant_id,
                track=track,
                dsp=current_dsp
            )
            await session.start_streaming()
            self.active_sessions[room_id] = session

            # Broadcast to TMA WebSocket listeners
            await self._broadcast_event(room_id, "PLAYBACK_START", {
                "track": track.model_dump(),
                "assistant_id": assistant.assistant_id,
                "dsp": current_dsp.model_dump()
            })

            # Telegram Logging
            await admin_logger.log_stream_event(
                event="TRACK_STARTED",
                room_id=room_id,
                track_title=track.title,
                duration_sec=track.duration_seconds,
                worker_node="worker-ec2-az1-priv",
                tier=tier
            )

            return PlaybackResponse(
                status="STREAMING",
                room_id=room_id,
                track=track,
                video_config=VideoConfig() if track.media_type == "video" else None,
                allocated_ram_mb=64 if track.media_type == "audio" else 192,
                worker_node="worker-ec2-az1-priv",
                active_assistant_id=assistant.assistant_id
            )

    async def update_dsp(self, room_id: int, dsp_update: DSPUpdateRequest) -> DSPConfig:
        """
        Dynamically update active audio DSP filter parameters.
        """
        async with self._lock:
            current_dsp = self.room_dsp.get(room_id) or DSPConfig()
            update_data = dsp_update.model_dump(exclude_unset=True)

            for key, val in update_data.items():
                if val is not None:
                    setattr(current_dsp, key, val)

            self.room_dsp[room_id] = current_dsp
            session = self.active_sessions.get(room_id)
            if session:
                await session.update_dsp(current_dsp)

            await self._broadcast_event(room_id, "DSP_UPDATE", current_dsp.model_dump())
            return current_dsp

    async def pause(self, room_id: int):
        session = self.active_sessions.get(room_id)
        if not session:
            raise HTTPException(status_code=404, detail="No active stream found in this room.")
        session.pause()
        await self._broadcast_event(room_id, "PLAYBACK_PAUSED", {"room_id": room_id})

    async def resume(self, room_id: int):
        session = self.active_sessions.get(room_id)
        if not session:
            raise HTTPException(status_code=404, detail="No active stream found in this room.")
        session.resume()
        await self._broadcast_event(room_id, "PLAYBACK_RESUMED", {"room_id": room_id})

    async def seek(self, room_id: int, target_ms: int):
        session = self.active_sessions.get(room_id)
        if not session:
            raise HTTPException(status_code=404, detail="No active stream found in this room.")
        await session.seek(target_ms)
        await self._broadcast_event(room_id, "SEEK", {"position_ms": target_ms})

    async def skip(self, redis: aioredis.Redis, room_id: int, tier: str = "tier_free") -> Optional[PlaybackResponse]:
        """
        Skip current track and immediately play next in queue.
        """
        async with self._lock:
            session = self.active_sessions.get(room_id)
            if session:
                await session.stop()

            queue_key = f"queue:{room_id}"
            next_track_json = await redis.lpop(queue_key)
            if not next_track_json:
                # Queue empty, clean up
                await assistant_pool.release_assistant_from_room(room_id)
                self.active_sessions.pop(room_id, None)
                await self._broadcast_event(room_id, "PLAYBACK_ENDED", {"room_id": room_id})
                return None

            next_track_data = json.loads(next_track_json)
            next_track = TrackInfo(**next_track_data)

        # Play next track
        return await self.play_track(
            redis=redis,
            room_id=room_id,
            track=next_track,
            position="instant",
            tier=tier
        )

    async def stop(self, redis: aioredis.Redis, room_id: int) -> Dict[str, Any]:
        """
        Terminate room stream, release assistant, flush queue, and free RAM.
        """
        async with self._lock:
            session = self.active_sessions.pop(room_id, None)
            asst_id = None
            if session:
                asst_id = session.assistant_id
                await session.stop()

            await assistant_pool.release_assistant_from_room(room_id, asst_id)
            await redis.delete(f"queue:{room_id}")

            freed = {
                "assistant_id": asst_id,
                "ffmpeg_processes_killed": 1 if session else 0,
                "ram_freed_mb": 184 if (session and session.track.media_type == "video") else 64
            }

            await self._broadcast_event(room_id, "ROOM_TERMINATED", freed)
            return freed

    async def get_room_state(self, redis: aioredis.Redis, room_id: int) -> RoomStateResponse:
        session = self.active_sessions.get(room_id)
        queue_key = f"queue:{room_id}"
        raw_queue = await redis.lrange(queue_key, 0, -1)
        queue_tracks = [TrackInfo(**json.loads(item)) for item in raw_queue]

        dsp = self.room_dsp.get(room_id) or DSPConfig()
        connected_listeners = len(self.ws_subscribers.get(room_id, set()))

        if not session or not session.is_running:
            return RoomStateResponse(
                room_id=room_id,
                status="IDLE",
                dsp=dsp,
                queue_length=len(queue_tracks),
                queue=queue_tracks,
                connected_listeners=connected_listeners
            )

        status_str = "PAUSED" if session.is_paused else "PLAYING"
        progress = session.current_progress_ms

        return RoomStateResponse(
            room_id=room_id,
            status=status_str,
            active_assistant_id=session.assistant_id,
            current_track=session.track,
            progress_ms=progress,
            duration_ms=session.track.duration_seconds * 1000,
            dsp=dsp,
            queue_length=len(queue_tracks),
            queue=queue_tracks,
            connected_listeners=connected_listeners,
            is_video=(session.track.media_type == "video")
        )

    # --- WebSocket Event Hub ---
    def register_ws_client(self, room_id: int, ws: WebSocket):
        if room_id not in self.ws_subscribers:
            self.ws_subscribers[room_id] = set()
        self.ws_subscribers[room_id].add(ws)

    def unregister_ws_client(self, room_id: int, ws: WebSocket):
        if room_id in self.ws_subscribers:
            self.ws_subscribers[room_id].discard(ws)
            if not self.ws_subscribers[room_id]:
                del self.ws_subscribers[room_id]

    async def _broadcast_event(self, room_id: int, event_type: str, data: Dict[str, Any]):
        clients = list(self.ws_subscribers.get(room_id, set()))
        if not clients:
            return
        payload = json.dumps({"event": event_type, "data": data})
        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:
                pass


room_manager = RoomManager()
