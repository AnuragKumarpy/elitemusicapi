"""
Digital Signal Processing (DSP) filtergraph builder for FFmpeg in-memory audio/video pipes.
"""
from typing import List, Optional
from app.models.schemas import DSPConfig


class DSPFilterBuilder:
    @classmethod
    def build_audio_filtergraph(cls, dsp: Optional[DSPConfig]) -> str:
        """
        Generate FFmpeg audio filter chain (-af / -filter:a).
        """
        if not dsp:
            return "aresample=48000,pan=stereo|c0=c0|c1=c1"

        filters: List[str] = []

        # 1. Volume adjustment
        if dsp.volume != 100:
            vol_multiplier = max(0.0, min(2.0, dsp.volume / 100.0))
            filters.append(f"volume={vol_multiplier:.2f}")

        # 2. Bass Boost Filter (Low-shelf EQ at 110 Hz)
        if dsp.bass_boost_db != 0:
            filters.append(f"bass=g={dsp.bass_boost_db:.1f}:f=110:w=0.6")

        # 3. Treble Boost Filter (High-shelf EQ at 3000 Hz)
        if dsp.treble_boost_db != 0:
            filters.append(f"treble=g={dsp.treble_boost_db:.1f}:f=3000:w=0.5")

        # 4. 8D Dynamic Spatial Audio (Binaural circular pan rotation)
        if dsp.spatial_8d:
            # apulsator generates circular panning across left and right channels
            filters.append("apulsator=hz=0.125:amount=1:offset_l=0:offset_r=0.5")

        # 5. Nightcore Filter (Speed + Pitch 1.25x)
        if dsp.nightcore:
            filters.append("atempo=1.25,asetrate=48000*1.25,aresample=48000")
        else:
            # Custom speed & pitch
            if dsp.pitch != 1.0:
                filters.append(f"asetrate=48000*{dsp.pitch:.2f},aresample=48000")

            if dsp.speed != 1.0:
                # atempo supports 0.5 to 2.0
                filters.append(f"atempo={dsp.speed:.2f}")

        # 6. Standardize output to 48kHz Stereo PCM
        filters.append("aresample=48000,pan=stereo|c0=c0|c1=c1")

        return ",".join(filters)

    @classmethod
    def build_video_filtergraph(cls, width: int = 1280, height: int = 720, fps: int = 30) -> str:
        """
        Generate FFmpeg video filter chain (-vf / -filter:v).
        Scales cleanly with letterbox padding to standard 720p@30fps (Telegram VC Max).
        """
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
