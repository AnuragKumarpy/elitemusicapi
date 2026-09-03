"""
SQLAlchemy database models for Elite Music API & Bot Ecosystem.
Includes Tenancy, API Keys, Assistant Sessions, and Unified User & Chat Analytics for Broadcasting.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    api_keys = relationship("ApiKey", back_populates="tenant", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    prefix = Column(String(16), nullable=False)
    tier = Column(String(32), default="tier_free", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    daily_limit = Column(Integer, default=50, nullable=False)
    max_concurrent_vcs = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_keys_active_tier", "is_active", "tier"),
    )


class AssistantSession(Base):
    __tablename__ = "assistant_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone_number = Column(String(32), nullable=True)
    user_id = Column(BigInteger, nullable=True, index=True)
    session_string = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    current_load = Column(Integer, default=0, nullable=False)
    max_load = Column(Integer, default=5, nullable=False)
    last_active_at = Column(DateTime, default=get_utc_now, nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    api_key_id = Column(String(36), nullable=True, index=True)
    room_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)


class BotUser(Base):
    """
    Unified User Telemetry across Main Bot (@EliteMusicApiBot) and all User Clones.
    """
    __tablename__ = "bot_users"

    id = Column(BigInteger, primary_key=True, index=True)  # Telegram User ID
    username = Column(String(128), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_bot = Column(Boolean, default=False)
    source_bot = Column(String(128), default="EliteMusicApiBot", index=True)
    bot_token_id = Column(String(32), nullable=True, index=True)
    is_blocked = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=get_utc_now, nullable=False)
    last_seen = Column(DateTime, default=get_utc_now, nullable=False)

    __table_args__ = (
        Index("idx_bot_users_source", "source_bot", "is_blocked"),
    )


class BotChat(Base):
    """
    Unified Supergroup/Channel Telemetry across Main Bot and all User Clones.
    """
    __tablename__ = "bot_chats"

    id = Column(BigInteger, primary_key=True, index=True)  # Telegram Chat ID (e.g. -100...)
    title = Column(String(255), nullable=True)
    chat_type = Column(String(32), default="supergroup")
    username = Column(String(128), nullable=True)
    members_count = Column(Integer, nullable=True)
    added_by_user_id = Column(BigInteger, nullable=True)
    source_bot = Column(String(128), default="EliteMusicApiBot", index=True)
    bot_token_id = Column(String(32), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    last_active_at = Column(DateTime, default=get_utc_now, nullable=False)

    __table_args__ = (
        Index("idx_bot_chats_source", "source_bot", "is_active"),
    )


class BroadcastRecord(Base):
    """
    Telemetry log for mass announcements and broadcasts.
    """
    __tablename__ = "broadcast_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sender_id = Column(BigInteger, nullable=False)
    sender_name = Column(String(255), nullable=True)
    target_type = Column(String(32), default="users")  # 'users', 'chats', 'all'
    source_bot = Column(String(128), default="global")
    total_targets = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    message_snippet = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=get_utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class UserDSPSettings(Base):
    """
    Per-User Custom DSP Sound Profile (Bass Boost, 8D Spatial, Nightcore, Tempo).
    Automatically applied to all songs queued/requested by this user.
    """
    __tablename__ = "user_dsp_settings"

    user_id = Column(BigInteger, primary_key=True, index=True)
    bass_boost_db = Column(Integer, default=0)
    spatial_8d = Column(Boolean, default=False)
    nightcore = Column(Boolean, default=False)
    speed = Column(Integer, default=100) # Stored as integer (100 = 1.0x, 125 = 1.25x)
    volume = Column(Integer, default=100)
    updated_at = Column(DateTime, default=get_utc_now, nullable=False)
