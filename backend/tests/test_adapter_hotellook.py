"""HotellookAdapter 테스트 — respx로 HTTP 목킹."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.base import FetchRequest
from app.sources.http import RateLimitedClient
from app.sources.stay.hotellook import HL_CACHE_URL, HotellookAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "hotellook"


def _load(name: str) -> list:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> HotellookAdapter:
    return HotellookAdapter(token="test-token", client=RateLimitedClient(min_interval_sec=0))


def _req(**kw) -> FetchRequest:
    defaults = dict(
        origin="ICN",
        destination="FUK",
        depart_from=date(2026, 10, 7),
        depart_to=date(2026, 10, 9),
        nights_min=2,
        nights_max=2,
    )
    defaults.update(kw)
    return FetchRequest(**defaults)


@pytest.mark.asyncio
async def test_fetch_returns_ok_and_offers():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(return_value=httpx.Response(200, json=_load("cache.json")))
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) == 2


@pytest.mark.asyncio
async def test_prices_are_krw_int():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(return_value=httpx.Response(200, json=_load("cache.json")))
        result = await _adapter().fetch(_req())

    assert all(isinstance(o.price_krw, int) for o in result.offers)
    assert all(o.price_krw > 0 for o in result.offers)


@pytest.mark.asyncio
async def test_offer_kind_is_stay():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(return_value=httpx.Response(200, json=_load("cache.json")))
        result = await _adapter().fetch(_req())

    assert all(o.kind == "stay" for o in result.offers)


@pytest.mark.asyncio
async def test_http_error_returns_ok_false():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(return_value=httpx.Response(403))
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
