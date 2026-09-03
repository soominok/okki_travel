"""SourceRegistry, build_registry, CrawlPolicy 테스트."""

from __future__ import annotations

import pytest

from app.sources.base import SourceAdapter
from app.sources.flight.travelpayouts import TravelpayoutsAdapter
from app.sources.http import RateLimitedClient
from app.sources.policy import CrawlPolicy
from app.sources.registry import SourceRegistry, build_registry


def _tp() -> TravelpayoutsAdapter:
    return TravelpayoutsAdapter(token="tok", client=RateLimitedClient(min_interval_sec=0))


class TestSourceRegistry:
    def test_register_and_get_by_role(self):
        reg = SourceRegistry()
        reg.register(_tp())
        adapters = reg.get(kind="flight", role="scan")
        assert len(adapters) == 1
        assert adapters[0].name == "travelpayouts"

    def test_get_wrong_role_returns_empty(self):
        reg = SourceRegistry()
        reg.register(_tp())
        assert reg.get(kind="flight", role="verify") == []

    def test_get_by_name(self):
        reg = SourceRegistry()
        reg.register(_tp())
        a = reg.get_by_name("travelpayouts")
        assert a is not None
        assert isinstance(a, SourceAdapter)

    def test_get_by_name_missing_returns_none(self):
        reg = SourceRegistry()
        assert reg.get_by_name("nonexistent") is None

    def test_adapter_protocol_satisfied(self):
        a = _tp()
        assert isinstance(a, SourceAdapter)


class TestBuildRegistry:
    def test_no_keys_empty_registry(self, monkeypatch):
        monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "")
        from app.config import Settings

        settings = Settings(
            app_api_token="x" * 32,
            database_url="postgresql+asyncpg://trip:trip@localhost:5434/trippick_test",
            travelpayouts_token=None,
            brightdata_api_key=None,
        )
        reg = build_registry(settings)
        assert reg.get(kind="flight", role="scan") == []
        assert reg.get(kind="flight", role="verify") == []

    def test_tp_token_registers_tp_and_hl(self, monkeypatch):
        from pydantic import SecretStr

        from app.config import Settings

        settings = Settings(
            app_api_token="x" * 32,
            database_url="postgresql+asyncpg://trip:trip@localhost:5434/trippick_test",
            travelpayouts_token=SecretStr("tp-test"),
            brightdata_api_key=None,
        )
        reg = build_registry(settings)
        flight_scan = reg.get(kind="flight", role="scan")
        stay_scan = reg.get(kind="stay", role="scan")
        assert any(a.name == "travelpayouts" for a in flight_scan)
        assert any(a.name == "hotellook" for a in stay_scan)


class TestCrawlPolicy:
    def test_require_enabled_raises_when_disabled(self, monkeypatch):
        monkeypatch.setenv("CRAWL_ENABLED", "false")
        with pytest.raises(RuntimeError, match="CRAWL_ENABLED"):
            CrawlPolicy.require_enabled()

    def test_check_allowed_returns_false(self):
        assert CrawlPolicy.check_allowed("example.com") is False
