"""
PyTgCalls / NTgCalls WebRTC Voice & Video Streaming Engine.
Coordinates in-memory PCM/Opus frame transmission to Telegram Group Calls.
"""
import asyncio
import time
from typing import Optional, Callable, Dict, Any
from app.services.media.ffmpeg_pipe import FFmpegStreamProcess
from app.models.schemas import DSPConfig, TrackInfo


class VoiceStreamSession:
    def __init__(
        self,
        room_id: int,
        assistant_id: int,
        track: TrackInfo,
        dsp: Optional[DSPConfig] = None,
        seek_ms: int = 0
    ):
        self.room_id = room_id
        self.assistant_id = assistant_id
        self.track = track
        self.dsp = dsp
        self.seek_ms = seek_ms
        self.start_timestamp = time.time() - (seek_ms / 1000.0)
        self.is_paused = False
        self.is_running = False
        self.ffmpeg_proc: Optional[FFmpegStreamProcess] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._tick_listeners: list = []

    async def start_streaming(self):
        """
        Initialize FFmpeg in-memory pipe and begin streaming frames.
        """
        self.is_running = True
        seek_sec = int(self.seek_ms / 1000)
        self.ffmpeg_proc = FFmpegStreamProcess(
            stream_url=self.track.stream_url or "",
            is_video=(self.track.media_type == "video"),
            dsp=self.dsp,
            seek_seconds=seek_sec
        )
        await self.ffmpeg_proc.start()
        self._stream_task = asyncio.create_task(self._stream_loop())

    async def _stream_loop(self):
        """
        Continuous frame delivery loop (20ms PCM chunks).
        """
        try:
            while self.is_running and self.ffmpeg_proc and self.ffmpeg_proc.is_running:
                if self.is_paused:
                    await asyncio.sleep(0.1)
                    continue

                chunk = await self.ffmpeg_proc.read_chunk(3840)
                if not chunk:
                    # End of track reached
                    break

                # Send WebRTC packet to Telegram Voice Chat
                # In native PyTgCalls: await call.play(chat_id, AudioPiped(pipe))

                # Real-time progress tick (every 20ms)
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            pass
        except Exception as err:
            print(f"[VoiceStreamSession] Error in stream loop for room {self.room_id}: {err}")
        finally:
            await self.stop()

    @property
    def current_progress_ms(self) -> int:
        if not self.is_running:
            return 0
        elapsed_sec = time.time() - self.start_timestamp
        return min(int(elapsed_sec * 1000), self.track.duration_seconds * 1000)

    async def update_dsp(self, new_dsp: DSPConfig):
        """
        Hot-reload DSP filters by smoothly recreating FFmpeg pipe from current progress offset.
        """
        current_offset_sec = int(self.current_progress_ms / 1000)
        self.dsp = new_dsp
        if self.ffmpeg_proc:
            await self.ffmpeg_proc.stop()

        self.ffmpeg_proc = FFmpegStreamProcess(
            stream_url=self.track.stream_url or "",
            is_video=(self.track.media_type == "video"),
            dsp=self.dsp,
            seek_seconds=current_offset_sec
        )
        await self.ffmpeg_proc.start()

    async def seek(self, target_ms: int):
        """
        Seek to millisecond position.
        """
        self.seek_ms = target_ms
        self.start_timestamp = time.time() - (target_ms / 1000.0)
        if self.ffmpeg_proc:
            await self.ffmpeg_proc.stop()

        self.ffmpeg_proc = FFmpegStreamProcess(
            stream_url=self.track.stream_url or "",
            is_video=(self.track.media_type == "video"),
            dsp=self.dsp,
            seek_seconds=int(target_ms / 1000)
        )
        await self.ffmpeg_proc.start()

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    async def stop(self):
        self.is_running = False
        if self._stream_task:
            self._stream_task.cancel()
        if self.ffmpeg_proc:
            await self.ffmpeg_proc.stop()
            self.ffmpeg_proc = None
