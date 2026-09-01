from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_healthz_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "db" in body


async def test_healthz_reports_db_connected():
    """DB가 살아 있으면 healthz가 db=ok 를 반환한다."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.json()["db"] == "ok"
