"""
Elite Music Python SDK — Models and Data Structures.
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class DSP:
    bass_boost_db: float = 0.0
    spatial_8d: bool = False
    speed: float = 1.0
    pitch: float = 1.0
    volume: int = 100
    nightcore: bool = False
    treble_boost_db: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bass_boost_db": self.bass_boost_db,
            "spatial_8d": self.spatial_8d,
            "speed": self.speed,
            "pitch": self.pitch,
            "volume": self.volume,
            "nightcore": self.nightcore,
            "treble_boost_db": self.treble_boost_db,
        }


@dataclass
class Track:
    id: str
    title: str
    artist: Optional[str]
    duration_seconds: int
    media_type: str
    source: str
    stream_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    position_in_queue: Optional[int] = None


@dataclass
class PlaybackResult:
    status: str
    room_id: int
    track: Track
    allocated_ram_mb: int
    worker_node: str
    active_assistant_id: Optional[int] = None


@dataclass
class RoomState:
    room_id: int
    status: str
    active_assistant_id: Optional[int]
    current_track: Optional[Track]
    progress_ms: int
    duration_ms: int
    dsp: DSP
    queue_length: int
    queue: List[Track]
    connected_listeners: int
    is_video: bool
