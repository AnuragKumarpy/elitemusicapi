"""
Pydantic Request & Response Schemas for Elite Music API V1.
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# --- Auth & Key Schemas ---
class TenantRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    tier: Literal["tier_free", "tier_pro", "tier_enterprise"] = "tier_free"


class ApiKeyResponse(BaseModel):
    api_key: str
    tier: str
    daily_limit: int
    max_concurrent_vcs: int
    created_at: str


class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    tier: str
    api_key: Optional[str] = None


# --- DSP Configuration Schemas ---
class DSPConfig(BaseModel):
    bass_boost_db: float = Field(default=0.0, ge=-20.0, le=20.0, description="Bass Boost in dB (-20 to +20)")
    spatial_8d: bool = Field(default=False, description="Enable 8D dynamic spatial circular audio panning")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Playback speed factor (0.5x to 2.0x)")
    pitch: float = Field(default=1.0, ge=0.5, le=2.0, description="Playback pitch factor (0.5 to 2.0)")
    volume: int = Field(default=100, ge=0, le=200, description="Volume percentage (0 to 200%)")
    nightcore: bool = Field(default=False, description="Enable Nightcore filter (speed 1.25x + pitch 1.25x)")
    treble_boost_db: float = Field(default=0.0, ge=-20.0, le=20.0, description="Treble Boost in dB")


class DSPUpdateRequest(BaseModel):
    bass_boost_db: Optional[float] = Field(default=None, ge=-20.0, le=20.0)
    spatial_8d: Optional[bool] = Field(default=None)
    speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    pitch: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    volume: Optional[int] = Field(default=None, ge=0, le=200)
    nightcore: Optional[bool] = Field(default=None)
    treble_boost_db: Optional[float] = Field(default=None, ge=-20.0, le=20.0)


# --- Media Stream Requests ---
class RequestedByInfo(BaseModel):
    user_id: int
    name: Optional[str] = "Anonymous"


class PlayAudioRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Track URL or search query")
    source_preference: List[str] = Field(
        default=["youtube", "spotify", "soundcloud"],
        description="Priority order for resolving media tracks"
    )
    requested_by: Optional[RequestedByInfo] = None
    position: Literal["tail", "head", "instant"] = "tail"
    dsp: Optional[DSPConfig] = None
    invite_link: Optional[str] = Field(default=None, description="Group invite link for assistant userbot auto-joining")


class PlayVideoRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Video track URL or search query")
    requested_by: Optional[RequestedByInfo] = None
    resolution: Literal["360p", "480p", "720p"] = "720p"
    frame_rate: Literal[24, 30] = 30
    invite_link: Optional[str] = Field(default=None, description="Group invite link for assistant userbot auto-joining")


class SeekRequest(BaseModel):
    position_ms: int = Field(..., ge=0, description="Target seek offset in milliseconds")


class VolumeRequest(BaseModel):
    volume: int = Field(..., ge=0, le=200, description="Volume percentage (0 to 200%)")


class StopRequest(BaseModel):
    reason: Optional[str] = Field(default="CLIENT_REQUEST", max_length=100)


# --- Track & Playback State Schemas ---
class TrackInfo(BaseModel):
    id: str
    title: str
    artist: Optional[str] = None
    duration_seconds: int
    stream_url: Optional[str] = None
    audio_stream_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_type: Literal["audio", "video"] = "audio"
    source: str
    position_in_queue: Optional[int] = None
    requested_by: Optional[RequestedByInfo] = None
    invite_link: Optional[str] = None


class VideoConfig(BaseModel):
    width: int = 1280
    height: int = 720
    fps: int = 30
    bitrate_kbps: int = 1500


class PlaybackResponse(BaseModel):
    status: Literal["STREAMING", "QUEUED"]
    room_id: int
    track: TrackInfo
    video_config: Optional[VideoConfig] = None
    allocated_ram_mb: int = 48
    worker_node: str
    active_assistant_id: Optional[int] = None


class RoomStateResponse(BaseModel):
    chat_id: int
    status: Literal["IDLE", "STREAMING", "PAUSED"]
    current_track: Optional[TrackInfo] = None
    queue_length: int = 0
    active_assistant_id: Optional[int] = None
    dsp: DSPConfig = Field(default_factory=DSPConfig)
    progress_ms: int = 0


class TerminatedResponse(BaseModel):
    room_id: int
    status: Literal["TERMINATED"]
    resources_freed: Dict[str, Any]
