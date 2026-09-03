"""BrightDataAdapter 테스트 — respx로 HTTP 목킹."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.base import FetchRequest
from app.sources.flight.brightdata import BrightDataAdapter, BD_SERP_URL
from app.sources.http import RateLimitedClient

FIXTURES = Path(__file__).parent / "fixtures" / "brightdata"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> BrightDataAdapter:
    return BrightDataAdapter(api_key="test-key", client=RateLimitedClient(min_interval_sec=0))


def _req(**kw) -> FetchRequest:
    defaults = dict(
        origin="ICN",
        destination="FUK",
        depart_from=date(2026, 10, 7),
        depart_to=date(2026, 10, 7),
        nights_min=2,
        nights_max=2,
    )
    defaults.update(kw)
    return FetchRequest(**defaults)


@pytest.mark.asyncio
async def test_fetch_returns_ok_and_offers():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(
            return_value=httpx.Response(200, json=_load("google_flights.json"))
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) > 0
    assert result.credits_used == 1


@pytest.mark.asyncio
async def test_price_is_int():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(
            return_value=httpx.Response(200, json=_load("google_flights.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(isinstance(o.price_krw, int) for o in result.offers)
    assert all(o.price_krw > 0 for o in result.offers)


@pytest.mark.asyncio
async def test_freshness_is_live():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(
            return_value=httpx.Response(200, json=_load("google_flights.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(o.freshness == "live" for o in result.offers)
    assert all(o.cache_age_days is None for o in result.offers)


@pytest.mark.asyncio
async def test_http_401_returns_ok_false():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(return_value=httpx.Response(401))
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
    assert result.offers == []
