from unittest.mock import MagicMock

from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.main import app


async def test_healthz_returns_ok():
    """DB가 살아 있으면 healthz가 status=ok, db=ok 를 반환한다."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


async def test_healthz_reports_degraded_and_logs_when_db_down(monkeypatch):
    """DB 연결이 실패하면 degraded 상태와 예외 타입명을 반환하고, structlog로 남긴다."""

    class _BrokenEngine:
        def connect(self):
            raise ConnectionRefusedError("boom")

    monkeypatch.setattr(main_module, "engine", _BrokenEngine())
    mock_log = MagicMock()
    monkeypatch.setattr(main_module, "log", mock_log)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")

    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error: ConnectionRefusedError"
    mock_log.warning.assert_called_once_with(
        "healthz.db_check_failed", error="ConnectionRefusedError"
    )
