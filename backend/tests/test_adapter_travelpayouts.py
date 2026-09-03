"""TravelpayoutsAdapter 테스트 — respx로 HTTP 목킹."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.base import FetchRequest
from app.sources.flight.travelpayouts import TravelpayoutsAdapter
from app.sources.http import RateLimitedClient

FIXTURES = Path(__file__).parent / "fixtures" / "travelpayouts"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> TravelpayoutsAdapter:
    return TravelpayoutsAdapter(token="test-token", client=RateLimitedClient(min_interval_sec=0))


def _req(**kw) -> FetchRequest:
    defaults = dict(
        origin="ICN",
        destination="FUK",
        depart_from=date(2026, 10, 1),
        depart_to=date(2026, 10, 31),
        nights_min=2,
        nights_max=3,
    )
    defaults.update(kw)
    return FetchRequest(**defaults)


@pytest.mark.asyncio
async def test_fetch_returns_ok_and_offers():
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=_load("prices_for_dates.json"))
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_prices_are_krw_int():
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=_load("prices_for_dates.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(isinstance(o.price_krw, int) for o in result.offers)
    assert all(o.price_krw > 0 for o in result.offers)


@pytest.mark.asyncio
async def test_nights_filter_applied():
    """nights_min=2, nights_max=3 → 1박 항목은 제외된다."""
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=_load("prices_for_dates.json"))
        )
        result = await _adapter().fetch(_req(nights_min=2, nights_max=3))

    # Oct21(1박)과 ZE Oct10→11(1박)은 제외 → grouped 3 + prices 1 = 4
    assert len(result.offers) == 4
    for o in result.offers:
        if o.depart_date and o.return_date:
            nights = (o.return_date - o.depart_date).days
            assert 2 <= nights <= 3


@pytest.mark.asyncio
async def test_http_error_returns_ok_false():
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(401)
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(401)
        )
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
    assert result.offers == []


@pytest.mark.asyncio
async def test_dedup_same_external_id():
    """grouped와 prices_for_dates가 같은 항공편을 반환해도 중복 제거된다."""
    # grouped에는 Oct7 항목이 있다; prices에도 같은 external_id가 나오면 1개만.
    dup_prices = {
        "data": [
            {
                "airline": "7C",
                "departure_at": "2026-10-07T09:30:00",
                "return_at": "2026-10-09T18:00:00",
                "price": 185000,
                "destination": "FUK",
                "origin": "ICN",
                "transfers": 0,
                "gate": "Jetradar",
                "link": "/dup",
                "flight_number": "201",
                "duration": 90,
                "duration_to": 90,
                "duration_back": 85,
                "return_transfers": 0,
            }
        ],
        "currency": "KRW",
    }
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=dup_prices)
        )
        result = await _adapter().fetch(_req())

    ext_ids = [o.external_id for o in result.offers]
    assert len(ext_ids) == len(set(ext_ids)), "external_id 중복이 있다"
