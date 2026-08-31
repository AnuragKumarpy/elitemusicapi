"""
WebSocket Real-time Event Hub for Telegram Mini App (TMA).
Streams track position ticks, real-time synced lyrics, and room state updates.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.voice.room_manager import room_manager

router = APIRouter(tags=["Real-time WebSockets"])


@router.websocket("/rooms/{chat_id}/ws")
async def room_websocket_endpoint(
    websocket: WebSocket,
    chat_id: int,
    api_key: str = Query(default="")
):
    """
    Sub-50ms synchronized WebSocket feed for TMA Live Collaborative DJ Consoles.
    """
    await websocket.accept()
    room_manager.register_ws_client(chat_id, websocket)

    try:
        # Send initial connected greeting
        await websocket.send_text(json.dumps({
            "event": "CONNECTED",
            "data": {
                "room_id": chat_id,
                "message": "Connected to Elite Music API Real-Time Room Bus"
            }
        }))

        while True:
            # Keep-alive ping/pong and client actions (e.g. voting upvotes, slider updates)
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                action = msg.get("action")
                if action == "PING":
                    await websocket.send_text(json.dumps({"event": "PONG"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        room_manager.unregister_ws_client(chat_id, websocket)
    except Exception:
        room_manager.unregister_ws_client(chat_id, websocket)
