"""
Integration & End-to-End API Route Tests.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.core.database import init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Ensure database tables are initialized before running route tests."""
    await init_db()


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "HEALTHY"
        assert data["service"] == "Elite Music API"


@pytest.mark.asyncio
async def test_auth_registration_and_me():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_email = f"alex_{datetime.now(timezone.utc).timestamp()}@test.com"
        # 1. Register Developer Tenant
        reg_payload = {
            "name": "Alex Developer",
            "email": unique_email,
            "tier": "tier_pro"
        }
        reg_resp = await client.post("/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert "api_key" in reg_data
        client_api_key = reg_data["api_key"]

        # 2. Query /v1/auth/me using issued API key
        me_resp = await client.get("/v1/auth/me", headers={"X-API-Key": client_api_key})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["tier"] == "tier_pro"
        assert me_data["daily_limit"] == 2500
        assert me_data["max_concurrent_vcs"] == 5


@pytest.mark.asyncio
async def test_master_key_bypass():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        me_resp = await client.get("/v1/auth/me", headers={"X-API-Key": settings.MASTER_ADMIN_KEY})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["daily_limit"] == -1
        assert me_data["max_concurrent_vcs"] == 9999


@pytest.mark.asyncio
async def test_streaming_room_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-API-Key": settings.MASTER_ADMIN_KEY}
        chat_id = -100192837465

        # 1. Play Track
        play_payload = {
            "query": "The Weeknd - Starboy",
            "dsp": {"bass_boost_db": 4.0, "spatial_8d": True, "volume": 100}
        }
        play_resp = await client.post(f"/v1/rooms/{chat_id}/play", json=play_payload, headers=headers)
        assert play_resp.status_code == 202
        play_data = play_resp.json()
        assert play_data["status"] in ("STREAMING", "QUEUED")
        assert play_data["room_id"] == chat_id

        # 2. Get Room State
        state_resp = await client.get(f"/v1/rooms/{chat_id}/state", headers=headers)
        assert state_resp.status_code == 200
        state_data = state_resp.json()
        assert state_data["room_id"] == chat_id

        # 3. Apply DSP Update
        dsp_payload = {"bass_boost_db": 8.0, "speed": 1.1}
        dsp_resp = await client.patch(f"/v1/rooms/{chat_id}/dsp", json=dsp_payload, headers=headers)
        assert dsp_resp.status_code == 200
        assert dsp_resp.json()["bass_boost_db"] == 8.0

        # 4. Pause and Resume
        pause_resp = await client.post(f"/v1/rooms/{chat_id}/pause", headers=headers)
        assert pause_resp.status_code == 200

        resume_resp = await client.post(f"/v1/rooms/{chat_id}/resume", headers=headers)
        assert resume_resp.status_code == 200

        # 5. Stop and Eject
        stop_resp = await client.delete(f"/v1/rooms/{chat_id}/stop", headers=headers)
        assert stop_resp.status_code == 200
        stop_data = stop_resp.json()
        assert stop_data["status"] == "TERMINATED"
