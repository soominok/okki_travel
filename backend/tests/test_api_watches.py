"""Watch CRUD API 테스트."""

from __future__ import annotations

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


_FLIGHT_BODY = {
    "kind": "flight",
    "title": "가을 후쿠오카",
    "params": {
        "kind": "flight",
        "origin": "ICN",
        "destination": "FUK",
        "depart_from": "2026-10-01",
        "depart_to": "2026-10-31",
        "nights_min": 2,
        "nights_max": 3,
        "adults": 1,
    },
    "rules": [{"id": "t1", "type": "threshold", "price_krw": 250000}],
    "interval_min": 360,
}


@pytest.mark.asyncio
async def test_create_watch(client):
    r = await client.post("/api/watches", json=_FLIGHT_BODY, headers=_auth())
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "flight"
    assert body["status"] == "active"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_watches(client):
    await client.post("/api/watches", json=_FLIGHT_BODY, headers=_auth())
    r = await client.get("/api/watches", headers=_auth())
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_get_watch(client):
    create = await client.post("/api/watches", json=_FLIGHT_BODY, headers=_auth())
    wid = create.json()["id"]
    r = await client.get(f"/api/watches/{wid}", headers=_auth())
    assert r.status_code == 200
    assert r.json()["id"] == wid


@pytest.mark.asyncio
async def test_patch_watch(client):
    create = await client.post("/api/watches", json=_FLIGHT_BODY, headers=_auth())
    wid = create.json()["id"]
    r = await client.patch(
        f"/api/watches/{wid}",
        json={"interval_min": 120, "status": "paused"},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["interval_min"] == 120
    assert r.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_delete_watch(client):
    create = await client.post("/api/watches", json=_FLIGHT_BODY, headers=_auth())
    wid = create.json()["id"]
    r = await client.delete(f"/api/watches/{wid}", headers=_auth())
    assert r.status_code == 204
    r2 = await client.get(f"/api/watches/{wid}", headers=_auth())
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_returns_403(client):
    r = await client.get("/api/watches")
    assert r.status_code in (401, 403)
