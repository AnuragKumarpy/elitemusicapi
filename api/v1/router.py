"""
V1 Master Router aggregating Auth, Rooms, and WebSockets.
"""
from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.rooms import router as rooms_router
from app.api.v1.ws import router as ws_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth_router)
v1_router.include_router(rooms_router)
v1_router.include_router(ws_router)
