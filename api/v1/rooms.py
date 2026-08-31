"""
Room and Voice Chat Playback Management Endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import redis.asyncio as aioredis

from app.core.redis import get_redis_client
from app.core.security import get_security_context, SecurityContext
from app.core.ratelimit import RateLimitEnforcer
from app.models.schemas import (
    PlayAudioRequest,
    PlayVideoRequest,
    DSPUpdateRequest,
    DSPConfig,
    SeekRequest,
    StopRequest,
    PlaybackResponse,
    RoomStateResponse,
    TerminatedResponse
)
from app.services.extractor.resolver import MediaResolver
from app.services.voice.room_manager import room_manager

router = APIRouter(prefix="/rooms", tags=["Voice Chat Streaming"])


@router.post("/{chat_id}/play", response_model=PlaybackResponse, status_code=status.HTTP_202_ACCEPTED)
async def play_audio_stream(
    chat_id: int,
    req: PlayAudioRequest,
    sec: SecurityContext = Depends(get_security_context),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Resolve audio query and immediately stream or enqueue to the Telegram Voice Chat.
    """
    # 1. Enforce Daily Quota Limits
    await RateLimitEnforcer.check_and_increment_quota(
        redis=redis,
        api_key=sec.key_hash,
        tier=sec.tier,
        is_master=sec.is_master
    )

    # 2. Check Concurrent VC Limit
    await RateLimitEnforcer.check_concurrent_vcs(
        redis=redis,
        api_key=sec.key_hash,
        tier=sec.tier,
        is_master=sec.is_master
    )

    # 3. Resolve Media Stream & Metadata
    track = await MediaResolver.resolve(
        query=req.query,
        tier=sec.tier,
        is_video=False,
        is_master=sec.is_master,
        requested_by=req.requested_by
    )

    # 4. Register Active Room & Execute Playback
    await RateLimitEnforcer.register_active_vc(redis, sec.key_hash, chat_id)

    response = await room_manager.play_track(
        redis=redis,
        room_id=chat_id,
        track=track,
        dsp=req.dsp,
        position=req.position,
        tier=sec.tier
    )

    return response


@router.post("/{chat_id}/play/video", response_model=PlaybackResponse, status_code=status.HTTP_202_ACCEPTED)
async def play_video_stream(
    chat_id: int,
    req: PlayVideoRequest,
    sec: SecurityContext = Depends(get_security_context),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Stream video track (capped at 720p@30fps) to the Telegram Voice Chat.
    """
    # 1. Enforce Daily Quota Limits
    await RateLimitEnforcer.check_and_increment_quota(
        redis=redis,
        api_key=sec.key_hash,
        tier=sec.tier,
        is_master=sec.is_master
    )

    # 2. Check Concurrent VC Limit
    await RateLimitEnforcer.check_concurrent_vcs(
        redis=redis,
        api_key=sec.key_hash,
        tier=sec.tier,
        is_master=sec.is_master
    )

    # 3. Resolve Media Stream & Metadata (Video Mode)
    track = await MediaResolver.resolve(
        query=req.query,
        tier=sec.tier,
        is_video=True,
        is_master=sec.is_master,
        requested_by=req.requested_by
    )

    # 4. Register Active Room & Execute Playback
    await RateLimitEnforcer.register_active_vc(redis, sec.key_hash, chat_id)

    response = await room_manager.play_track(
        redis=redis,
        room_id=chat_id,
        track=track,
        dsp=None,
        position="instant",
        tier=sec.tier
    )

    return response


@router.patch("/{chat_id}/dsp", response_model=DSPConfig)
async def update_room_dsp(
    chat_id: int,
    req: DSPUpdateRequest,
    sec: SecurityContext = Depends(get_security_context)
):
    """
    Apply real-time audio filters (Bass Boost, 8D Spatial, Speed, Volume) without stopping the stream.
    """
    return await room_manager.update_dsp(chat_id, req)


@router.post("/{chat_id}/pause")
async def pause_stream(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context)
):
    """
    Pause current audio playback without leaving the Voice Chat.
    """
    await room_manager.pause(chat_id)
    return {"room_id": chat_id, "status": "PAUSED"}


@router.post("/{chat_id}/resume")
async def resume_stream(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context)
):
    """
    Resume paused audio playback.
    """
    await room_manager.resume(chat_id)
    return {"room_id": chat_id, "status": "PLAYING"}


@router.post("/{chat_id}/skip", response_model=Optional[PlaybackResponse])
async def skip_track(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Skip active track and transition to the next item in the playlist queue.
    """
    return await room_manager.skip(redis, chat_id, tier=sec.tier)


@router.post("/{chat_id}/seek")
async def seek_stream(
    chat_id: int,
    req: SeekRequest,
    sec: SecurityContext = Depends(get_security_context)
):
    """
    Seek to a specific millisecond offset.
    """
    await room_manager.seek(chat_id, req.position_ms)
    return {"room_id": chat_id, "position_ms": req.position_ms}


@router.get("/{chat_id}/state", response_model=RoomStateResponse)
async def get_room_state(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Fetch active room playback state, progress ms, queue, and connected listeners.
    """
    return await room_manager.get_room_state(redis, chat_id)


@router.delete("/{chat_id}/stop", response_model=TerminatedResponse)
async def stop_stream(
    chat_id: int,
    req: Optional[StopRequest] = None,
    sec: SecurityContext = Depends(get_security_context),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Instant Killswitch / Room Eject: Terminates FFmpeg, releases assistant, flushes queue, and frees RAM.
    """
    freed = await room_manager.stop(redis, chat_id)
    await RateLimitEnforcer.unregister_active_vc(redis, sec.key_hash, chat_id)

    return TerminatedResponse(
        room_id=chat_id,
        status="TERMINATED",
        resources_freed=freed
    )
