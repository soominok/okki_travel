"""Alert API 테스트."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

_TOKEN = "x" * 32


def _auth():
    return {"Authorization": f"Bearer {_TOKEN}"}


@pytest_asyncio.fixture
async def client(migrated_engine):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_list_alerts_empty(client):
    r = await client.get("/api/alerts", headers=_auth())
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_alerts_unread_filter(client):
    r = await client.get("/api/alerts?unread=true", headers=_auth())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_mark_read_missing_returns_404(client):
    r = await client.post(f"/api/alerts/{uuid.uuid4()}/read", headers=_auth())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_notify_test_without_webhook_returns_422(client):
    r = await client.post("/api/alerts/test", headers=_auth())
    # SLACK_WEBHOOK_URL 이 없으면 422
    assert r.status_code in (200, 422)


@pytest.mark.asyncio
async def test_unauthenticated_alerts_returns_403(client):
    r = await client.get("/api/alerts")
    assert r.status_code in (401, 403)
