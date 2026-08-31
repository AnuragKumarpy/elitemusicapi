"""
In-memory FFmpeg 7.x RAM pipeline executor.
Streams raw PCM 48kHz audio and H.264 video chunks directly through pipes with zero disk writes.
"""
import asyncio
from typing import Optional, Tuple
from app.services.media.dsp import DSPFilterBuilder
from app.models.schemas import DSPConfig


class FFmpegStreamProcess:
    def __init__(
        self,
        stream_url: str,
        is_video: bool = False,
        dsp: Optional[DSPConfig] = None,
        seek_seconds: int = 0
    ):
        self.stream_url = stream_url
        self.is_video = is_video
        self.dsp = dsp
        self.seek_seconds = seek_seconds
        self.process: Optional[asyncio.subprocess.Process] = None
        self._is_running = False

    async def start(self) -> asyncio.subprocess.Process:
        """
        Launch FFmpeg sub-process with direct stdout pipe.
        """
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]

        # Fast seek offset if resuming playback
        if self.seek_seconds > 0:
            cmd.extend(["-ss", str(self.seek_seconds)])

        # Input stream URL (HTTP/HTTPS buffer)
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", self.stream_url
        ])

        if not self.is_video:
            # Audio Stream: Decode directly to raw 16-bit 48kHz Stereo PCM (s16le)
            audio_filter = DSPFilterBuilder.build_audio_filtergraph(self.dsp)
            cmd.extend([
                "-filter:a", audio_filter,
                "-f", "s16le",
                "-ac", "2",
                "-ar", "48000",
                "pipe:1"
            ])
        else:
            # Video Stream: Scale to 720p @ 30fps H.264 baseline + raw Opus/PCM
            video_filter = DSPFilterBuilder.build_video_filtergraph(1280, 720, 30)
            cmd.extend([
                "-filter:v", video_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-f", "rawvideo",
                "-pix_fmt", "yuv420p",
                "pipe:1"
            ])

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._is_running = True
        return self.process

    async def read_chunk(self, chunk_size: int = 3840) -> bytes:
        """
        Read exact chunk size from FFmpeg stdout pipe.
        Default 3840 bytes = 20ms of 48kHz 16-bit stereo PCM.
        """
        if not self.process or not self.process.stdout:
            return b""
        return await self.process.stdout.read(chunk_size)

    async def stop(self):
        """
        Terminate and wait for FFmpeg process to close.
        """
        self._is_running = False
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    @property
    def is_running(self) -> bool:
        return self._is_running and (self.process is not None and self.process.returncode is None)
