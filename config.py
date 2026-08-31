"""
Elite Music API — Configuration & Global Settings
"""
from typing import Dict, Any, Set
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class PlanTierConfig:
    def __init__(
        self,
        name: str,
        daily_limit: int,
        max_concurrent_vcs: int,
        max_audio_duration_sec: int,
        max_video_duration_sec: int,
        audio_bitrate_kbps: int,
        allow_video: bool,
        allow_custom_dsp: bool,
        allow_live_stream: bool = False,
    ):
        self.name = name
        self.daily_limit = daily_limit  # -1 = unlimited
        self.max_concurrent_vcs = max_concurrent_vcs
        self.max_audio_duration_sec = max_audio_duration_sec
        self.max_video_duration_sec = max_video_duration_sec
        self.audio_bitrate_kbps = audio_bitrate_kbps
        self.allow_video = allow_video
        self.allow_custom_dsp = allow_custom_dsp
        self.allow_live_stream = allow_live_stream


# Tier Configuration Mapping
TIER_PLANS: Dict[str, PlanTierConfig] = {
    "tier_free": PlanTierConfig(
        name="Free / Trial",
        daily_limit=50,
        max_concurrent_vcs=1,
        max_audio_duration_sec=1200,  # 20 minutes
        max_video_duration_sec=0,
        audio_bitrate_kbps=128,
        allow_video=False,
        allow_custom_dsp=False,
    ),
    "tier_pro": PlanTierConfig(
        name="Pro Bot Developer",
        daily_limit=2500,
        max_concurrent_vcs=5,
        max_audio_duration_sec=3600,  # 60 minutes
        max_video_duration_sec=600,   # 10 minutes
        audio_bitrate_kbps=320,
        allow_video=True,
        allow_custom_dsp=True,
    ),
    "tier_enterprise": PlanTierConfig(
        name="Enterprise",
        daily_limit=-1,
        max_concurrent_vcs=25,
        max_audio_duration_sec=10800, # 3 hours
        max_video_duration_sec=1800,  # 30 minutes
        audio_bitrate_kbps=320,
        allow_video=True,
        allow_custom_dsp=True,
        allow_live_stream=True,
    ),
}

# Whitelisted Media Ingestion Domains
ALLOWED_MEDIA_DOMAINS: Set[str] = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
    "spotify.com",
    "open.spotify.com",
    "soundcloud.com",
    "deezer.com",
    "music.apple.com",
    "jiosaavn.com",
}


class Settings(BaseSettings):
    # App & Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    WORKERS_COUNT: int = Field(default=2)

    # Master Admin Key (Complete Bypass of All Quotas)
    MASTER_ADMIN_KEY: str = Field(default="master_live_sec_999a8b7c6d5e4f3a2b1c0d9e8f7a6b5c")

    # PostgreSQL / SQLite Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./elitemusic.db")

    # Redis URL
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Telegram Bot & Mini App
    BOT_TOKEN: str = Field(default="")
    TMA_APP_URL: str = Field(default="https://tma.elitemusic.internal")

    # Telegram Admin Logger
    TELEGRAM_LOGGER_ENABLED: bool = Field(default=True)
    TELEGRAM_LOGGER_BOT_TOKEN: str = Field(default="")
    TELEGRAM_LOGGER_CHANNEL_ID: int = Field(default=-1004210053506)
    TELEGRAM_LOG_FLUSH_INTERVAL_SECONDS: float = Field(default=2.0)
    TELEGRAM_LOG_BATCH_SIZE: int = Field(default=15)

    # MTProto Telegram Client Credentials
    TELEGRAM_API_ID: int = Field(default=28102220)
    TELEGRAM_API_HASH: str = Field(default="c9ff5d60c4b80bf5f7de1092082207a5")
    ASSISTANT_SESSION_STRINGS: str = Field(default="")

    # AWS Dynamic IPv6 Subnet for Egress
    AWS_IPV6_SUBNET: str = Field(default="")

    # Hard Streaming RAM & Process Limits
    MAX_STREAM_RAM_AUDIO_MB: int = Field(default=64)
    MAX_STREAM_RAM_VIDEO_MB: int = Field(default=256)
    DEFAULT_AUDIO_SAMPLE_RATE: int = Field(default=48000)
    DEFAULT_AUDIO_CHANNELS: int = Field(default=2)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
