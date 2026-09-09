"""GET /api/watches/{id}/stats 통합 테스트."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models.price import PriceSnapshot

_TOKEN = "x" * 32

_FLIGHT_BODY_NRT = {
    "kind": "flight",
    "title": "Stats Test",
    "params": {
        "kind": "flight",
        "origin": "ICN",
        "destination": "NRT",
        "depart_from": "2026-10-01",
        "depart_to": "2026-10-31",
    },
    "rules": [],
    "interval_min": 360,
}

_FLIGHT_BODY_CJU = {
    "kind": "flight",
    "title": "Stats Monthly",
    "params": {
        "kind": "flight",
        "origin": "GMP",
        "destination": "CJU",
        "depart_from": "2026-09-01",
        "depart_to": "2026-09-30",
    },
    "rules": [],
    "interval_min": 360,
}


def _auth():
    return {"Authorization": f"Bearer {_TOKEN}"}


@pytest_asyncio.fixture
async def client(migrated_engine):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_stats_returns_empty_for_no_snapshots(client):
    r = await client.post("/api/watches", json=_FLIGHT_BODY_NRT, headers=_auth())
    assert r.status_code == 201
    watch_id = r.json()["id"]

    resp = await client.get(f"/api/watches/{watch_id}/stats", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert data["monthly_min"] == []
    assert data["overall_min"] is None
    assert data["data_months"] == 0


@pytest.mark.asyncio
async def test_stats_monthly_aggregation(client):
    r = await client.post("/api/watches", json=_FLIGHT_BODY_CJU, headers=_auth())
    assert r.status_code == 201
    watch_id = r.json()["id"]

    # 2026-08 스냅샷 2개: 300000, 350000 → 월 최저 300000
    async with SessionLocal() as session:
        for price in [300_000, 350_000]:
            snap = PriceSnapshot(
                watch_id=watch_id,
                min_price_krw=price,
            )
            session.add(snap)
        await session.commit()

        # captured_at을 2026-08로 강제 업데이트 (server_default가 now()라 직접 set 필요)
        await session.execute(
            text(
                "UPDATE price_snapshots SET captured_at = '2026-08-15 00:00:00+00'"
                " WHERE watch_id = :wid"
            ),
            {"wid": str(watch_id)},
        )
        await session.commit()

    resp = await client.get(f"/api/watches/{watch_id}/stats", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["monthly_min"]) == 1
    assert data["monthly_min"][0]["month"] == "2026-08"
    assert data["monthly_min"][0]["min_krw"] == 300_000
    assert data["overall_min"] == 300_000
    assert data["data_months"] == 1
