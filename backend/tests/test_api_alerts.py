"""Alert API 테스트."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import SessionLocal
from app.main import app
from app.models.alert import Alert

_TOKEN = "x" * 32

_WATCH_BODY = {
    "kind": "flight",
    "title": "테스트 워치",
    "params": {
        "kind": "flight",
        "origin": "ICN",
        "destination": "NRT",
        "depart_from": "2026-10-01",
        "depart_to": "2026-10-31",
        "nights_min": 2,
        "nights_max": 3,
        "adults": 1,
    },
    "rules": [{"id": "t1", "type": "threshold", "price_krw": 200000}],
    "interval_min": 360,
}


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
    # 워치 생성 (Alert FK 충족)
    r = await client.post("/api/watches", json=_WATCH_BODY, headers=_auth())
    assert r.status_code == 201
    watch_id = uuid.UUID(r.json()["id"])

    # Alert 2개 삽입: 하나 unread, 하나 read
    async with SessionLocal() as session:
        unread_alert = Alert(
            watch_id=watch_id,
            rule_id="t1",
            severity="info",
            title="Unread Alert",
            body="body",
            dedup_key="dk-unread",
        )
        read_alert = Alert(
            watch_id=watch_id,
            rule_id="t1",
            severity="info",
            title="Read Alert",
            body="body",
            dedup_key="dk-read",
            read_at=datetime.now(tz=UTC),
        )
        session.add_all([unread_alert, read_alert])
        await session.commit()

    r = await client.get("/api/alerts?unread=true", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["dedup_key"] == "dk-unread"


@pytest.mark.asyncio
async def test_mark_read_missing_returns_404(client):
    r = await client.post(f"/api/alerts/{uuid.uuid4()}/read", headers=_auth())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mark_read_success_and_idempotent(client):
    # 워치 생성
    r = await client.post("/api/watches", json=_WATCH_BODY, headers=_auth())
    assert r.status_code == 201
    watch_id = uuid.UUID(r.json()["id"])

    # Alert 삽입
    async with SessionLocal() as session:
        alert = Alert(
            watch_id=watch_id,
            rule_id="t1",
            severity="info",
            title="Mark Read Test",
            body="body",
            dedup_key=str(uuid.uuid4()),
        )
        session.add(alert)
        await session.commit()
        alert_id = alert.id

    # 읽음 처리 → 204
    r1 = await client.post(f"/api/alerts/{alert_id}/read", headers=_auth())
    assert r1.status_code == 204

    # 재호출 → 204 (멱등)
    r2 = await client.post(f"/api/alerts/{alert_id}/read", headers=_auth())
    assert r2.status_code == 204


@pytest.mark.asyncio
async def test_notify_test_without_webhook_returns_422(client):
    # SLACK_WEBHOOK_URL이 설정되지 않은 테스트 환경에서 422 반환
    r = await client.post("/api/notify/test", headers=_auth())
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_alerts_returns_403(client):
    r = await client.get("/api/alerts")
    assert r.status_code in (401, 403)
