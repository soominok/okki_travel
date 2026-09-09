"""GET /api/events 엔드포인트 기본 테스트."""

from tests.test_api_alerts import _auth, client  # noqa: F401


async def test_events_empty_list(client):
    # 존재하지 않는 source 필터 → 빈 목록 보장 (다른 테스트의 삽입 데이터에 독립)
    resp = await client.get("/api/events?source=__nonexistent__", headers=_auth())
    assert resp.status_code == 200
    assert resp.json() == []


async def test_events_limit_enforced(client):
    resp = await client.get("/api/events?limit=200", headers=_auth())
    assert resp.status_code == 422  # limit le=100 validation


async def test_events_requires_auth(client):
    resp = await client.get("/api/events")
    assert resp.status_code in (401, 403)
