"""
Room and Queue Management Endpoints for Elite Music API V1.
Manages Voice Chat streaming sessions, queue manipulation, and real-time DSP audio filters.
"""
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.models.schemas import (
    PlayAudioRequest,
    PlayVideoRequest,
    PlaybackResponse,
    RoomStateResponse,
    SeekRequest,
    VolumeRequest,
    StopRequest,
    DSPUpdateRequest,
    DSPConfig,
    TrackInfo,
    VideoConfig
)
from app.core.security import get_security_context, SecurityContext
from app.core.redis import get_redis_client
from app.core.ratelimit import RateLimitEnforcer
from app.services.extractor.resolver import MediaResolver
from app.services.voice.room_manager import room_manager
from app.services.media.dsp import DSPFilterBuilder

router = APIRouter(prefix="/rooms", tags=["Rooms & Playback Engine"])


@router.post("/{chat_id}/play", response_model=PlaybackResponse)
async def play_audio_stream(
    chat_id: int,
    req: PlayAudioRequest,
    sec: SecurityContext = Depends(get_security_context),
    redis: Any = Depends(get_redis_client)
):
    """
    Enqueue or instantly stream an audio track into a Telegram Supergroup Voice Chat.
    """
    if redis:
        try:
            await RateLimitEnforcer.check_concurrent_vcs(redis, sec.api_key, sec.tier, chat_id, sec.is_master)
            await RateLimitEnforcer.check_and_increment_quota(redis, sec.api_key, sec.tier, sec.is_master)
            await RateLimitEnforcer.register_active_vc(redis, sec.api_key, chat_id)
        except HTTPException:
            raise
        except Exception:
            pass

    track = await MediaResolver.resolve(
        query=req.query,
        tier=sec.tier,
        is_video=False,
        is_master=sec.is_master,
        requested_by=req.requested_by
    )
    track.invite_link = req.invite_link

    response = await room_manager.play_track(
        redis=redis,
        room_id=chat_id,
        track=track,
        dsp=req.dsp,
        position=req.position,
        tier=sec.tier
    )

    return response


@router.post("/{chat_id}/play/video", response_model=PlaybackResponse)
async def play_video_stream(
    chat_id: int,
    req: PlayVideoRequest,
    sec: SecurityContext = Depends(get_security_context),
    redis: Any = Depends(get_redis_client)
):
    """
    Stream a video broadcast (720p@30fps) into a Telegram Voice Chat.
    """
    if redis:
        try:
            await RateLimitEnforcer.check_concurrent_vcs(redis, sec.api_key, sec.tier, chat_id, sec.is_master)
            await RateLimitEnforcer.check_and_increment_quota(redis, sec.api_key, sec.tier, sec.is_master)
            await RateLimitEnforcer.register_active_vc(redis, sec.api_key, chat_id)
        except HTTPException:
            raise
        except Exception:
            pass

    track = await MediaResolver.resolve(
        query=req.query,
        tier=sec.tier,
        is_video=True,
        is_master=sec.is_master,
        requested_by=req.requested_by
    )
    track.invite_link = req.invite_link

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
    return await room_manager.update_dsp(chat_id, req)


@router.post("/{chat_id}/pause")
async def pause_stream(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context)
):
    await room_manager.pause(chat_id)
    return {"status": "PAUSED", "chat_id": chat_id}


@router.post("/{chat_id}/resume")
async def resume_stream(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context)
):
    await room_manager.resume(chat_id)
    return {"status": "STREAMING", "chat_id": chat_id}


@router.post("/{chat_id}/skip", response_model=Optional[PlaybackResponse])
async def skip_track(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context),
    redis: Any = Depends(get_redis_client)
):
    next_track = await room_manager.skip(redis, chat_id, tier=sec.tier)
    if not next_track:
        if redis:
            try:
                await RateLimitEnforcer.unregister_active_vc(redis, sec.api_key, chat_id)
            except Exception:
                pass
        return None
    return PlaybackResponse(
        status="STREAMING",
        room_id=chat_id,
        track=next_track,
        allocated_ram_mb=48,
        worker_node="assistant",
        message="Track skipped successfully"
    )


@router.post("/{chat_id}/seek")
async def seek_stream(
    chat_id: int,
    req: SeekRequest,
    sec: SecurityContext = Depends(get_security_context)
):
    await room_manager.seek(chat_id, req.position_ms)
    return {"status": "SEEKED", "position_ms": req.position_ms}


@router.get("/{chat_id}/state", response_model=RoomStateResponse)
async def get_room_playback_state(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context),
    redis: Any = Depends(get_redis_client)
):
    return await room_manager.get_room_state(redis, chat_id)


@router.delete("/{chat_id}/stop")
async def stop_playback_session(
    chat_id: int,
    sec: SecurityContext = Depends(get_security_context),
    redis: Any = Depends(get_redis_client)
):
    stopped = await room_manager.stop(redis, chat_id)
    if redis:
        try:
            await RateLimitEnforcer.unregister_active_vc(redis, sec.api_key, chat_id)
        except Exception:
            pass
    return {"status": "STOPPED", "chat_id": chat_id, "stopped": stopped}
