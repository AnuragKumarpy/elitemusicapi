"""
PyTgCalls / NTgCalls WebRTC Voice & Video Streaming Engine.
Coordinates lossless audio and video transmission to Telegram Group Calls.
DSP Equalizers (Bass / 8D / Speed) are applied to audio tracks, while video streams bypass DSP
for maximum synchronization and stability.
"""
import asyncio
import time
from typing import Optional
from app.services.media.dsp import DSPFilterBuilder
from app.models.schemas import DSPConfig, TrackInfo
from app.services.voice.assistant_pool import AssistantAccount


class VoiceStreamSession:
    def __init__(
        self,
        room_id: int,
        assistant: AssistantAccount,
        track: TrackInfo,
        dsp: Optional[DSPConfig] = None,
        seek_ms: int = 0
    ):
        self.room_id = room_id
        self.assistant = assistant
        self.assistant_id = assistant.assistant_id
        self.track = track
        self.dsp = dsp
        self.seek_ms = seek_ms
        self.start_timestamp = time.time() - (seek_ms / 1000.0)
        self.is_paused = False
        self.is_running = False

    async def start_streaming(self):
        """
        Instruct assistant's PyTgCalls client to stream media into the voice chat.
        Supports motion video, 16:9 artwork video canvas, and pristine 320kbps audio.
        """
        self.is_running = True
        media_url = self.track.stream_url or ""
        is_video = (self.track.media_type == "video")
        
        # Build clean PyTgCalls FFmpeg parameters (---start for input flags, ---mid for filter flags)
        proxy_str = self.track.proxy or "http://nioqtqce:89o0hbtuubix@45.38.107.97:6014"
        start_flags = f"-http_proxy {proxy_str}"
        mid_flags = ""

        if self.seek_ms > 0:
            seek_sec = int(self.seek_ms / 1000)
            start_flags += f" -ss {seek_sec}"

        if not is_video and self.dsp and (self.dsp.bass_boost_db != 0 or self.dsp.spatial_8d or self.dsp.speed != 1.0 or self.dsp.volume != 100 or self.dsp.nightcore):
            audio_filter = DSPFilterBuilder.build_audio_filtergraph(self.dsp)
            mid_flags = f"-af {audio_filter}"

        ffmpeg_params = f"---start {start_flags} ---mid {mid_flags}".strip() if mid_flags else f"---start {start_flags}".strip()

        audio_url = self.track.audio_stream_url or (media_url if is_video else None)
        
        # If is_video and source is canvas (or audio stream fallback): download/prepare 16:9 thumbnail for video feed
        if is_video and (self.track.source == "youtube_v3_video_canvas" or (audio_url and media_url == audio_url)):
            thumb_path = f"/tmp/thumb_{self.track.id}.jpg"
            if self.track.thumbnail_url:
                try:
                    import urllib.request, ssl
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(self.track.thumbnail_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, context=ssl_ctx, timeout=4) as r:
                        with open(thumb_path, 'wb') as f:
                            f.write(r.read())
                    media_url = thumb_path
                except Exception as e:
                    print(f"[NTGStreamer] Thumbnail fetch note: {e}")

        await self.assistant.play(
            chat_id=self.room_id,
            media_url=media_url,
            audio_url=audio_url,
            is_video=is_video,
            ffmpeg_params=ffmpeg_params,
            invite_link=self.track.invite_link
        )

    @property
    def current_progress_ms(self) -> int:
        if not self.is_running:
            return 0
        elapsed_sec = time.time() - self.start_timestamp
        return min(int(elapsed_sec * 1000), self.track.duration_seconds * 1000)

    async def update_dsp(self, new_dsp: DSPConfig):
        """Update DSP profile for session and apply immediately to live voice chat."""
        self.dsp = new_dsp
        if self.is_running and not self.is_paused:
            self.seek_ms = self.current_progress_ms
            await self.start_streaming()

    async def seek(self, target_ms: int):
        self.seek_ms = target_ms
        self.start_timestamp = time.time() - (target_ms / 1000.0)
        await self.start_streaming()

    async def pause(self):
        self.is_paused = True
        await self.assistant.pause(self.room_id)

    async def resume(self):
        self.is_paused = False
        await self.assistant.resume(self.room_id)

    async def stop(self):
        self.is_running = False
