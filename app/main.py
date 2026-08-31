"""
Elite Music API — Main Application Entrypoint
Zero-Trust, High-Performance Headless Audio & Video Streaming Engine for Telegram Voice Chats.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import init_db
from app.core.redis import get_redis_client, close_redis_client
from app.services.logger.telegram_logger import admin_logger
from app.services.voice.assistant_pool import assistant_pool
from app.services.quota_notifier import quota_notifier
from app.api.v1.router import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler: handles database, Redis, logger, assistant fleet, and quota reset monitor lifecycle."""
    # 1. Initialize SQLite / PostgreSQL Database Tables
    try:
        await init_db()
        print("[EliteMusicAPI] Database tables initialized.")
    except Exception as e:
        print(f"[EliteMusicAPI] Database initialization warning: {e}")

    # 2. Connect Redis Pool
    redis = None
    try:
        redis = await get_redis_client()
        await redis.ping()
        print("[EliteMusicAPI] Connected to Redis Cluster.")
    except Exception as e:
        print(f"[EliteMusicAPI] Redis connection warning: {e}")

    # 3. Start Batched Telegram Admin Channel Logger
    await admin_logger.start()
    if admin_logger.enabled:
        print("[EliteMusicAPI] Telegram Admin Logger worker started.")

    # 4. Start Warm PyTgCalls Assistant Fleet
    try:
        await assistant_pool.start_pool()
        print(f"[EliteMusicAPI] Assistant Session Pool ready ({len(assistant_pool.assistants)} active userbots).")
    except Exception as e:
        print(f"[EliteMusicAPI] Assistant Pool start warning: {e}")

    # 5. Start Daily Limit Unlock Notifier
    if redis:
        await quota_notifier.start(redis)

    yield

    # Shutdown sequence
    await assistant_pool.stop_pool()
    await admin_logger.stop()
    await close_redis_client()
    print("[EliteMusicAPI] Graceful shutdown complete.")


app = FastAPI(
    title="Elite Music API",
    description="Production Headless Audio/Video Streaming Engine for Telegram Voice Chats (Group Calls)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Configuration for Telegram Mini Apps and Dashboard Clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System Health"])
async def health_check():
    """System health check and uptime probe for AWS ALB."""
    return {
        "status": "HEALTHY",
        "service": "Elite Music API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "active_assistants": len(assistant_pool.assistants)
    }


# Include V1 API
app.include_router(v1_router)
