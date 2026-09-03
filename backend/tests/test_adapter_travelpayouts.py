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


# Mod 7: 실제로 dedup이 작동하는지 검증하는 테스트로 재작성
@pytest.mark.asyncio
async def test_dedup_within_grouped_endpoint():
    """grouped 응답에 서로 다른 dict 키지만 같은 ext_id를 생성하는 항목이 두 개여도 1개만 반환된다.

    두 항목이 departure_at/return_at/airline/flight_number가 동일하면 ext_id가 같으므로
    offers_by_id에 1개만 들어간다.
    """
    dup_grouped = {
        "data": {
            "2026-10-04": {
                "departure_at": "2026-10-04T07:05:00",
                "return_at": "2026-10-06T18:30:00",
                "airline": "LJ",
                "flight_number": "271",
                "price": 220000,
                "origin": "ICN",
                "destination": "FUK",
            },
            # 다른 dict 키지만 departure_at이 같아서 ext_id 동일
            "2026-10-05": {
                "departure_at": "2026-10-04T07:05:00",
                "return_at": "2026-10-06T18:30:00",
                "airline": "LJ",
                "flight_number": "271",
                "price": 218000,
                "origin": "ICN",
                "destination": "FUK",
            },
        },
        "currency": "KRW",
    }
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=dup_grouped)
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json={"data": [], "currency": "KRW"})
        )
        result = await _adapter().fetch(_req())

    # grouped에 항목 2개지만 ext_id가 같으므로 1개만
    assert result.ok is True
    assert len(result.offers) == 1
    ext_ids = [o.external_id for o in result.offers]
    assert len(ext_ids) == len(set(ext_ids)), "external_id 중복이 있다"


# Mod 8: 누락 edge-case 테스트 4개 추가

@pytest.mark.asyncio
async def test_empty_grouped_response():
    """grouped가 빈 결과를 줘도 ok=True, offers=[]."""
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json={"data": {}, "currency": "KRW"})
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json={"data": [], "currency": "KRW"})
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert result.offers == []


@pytest.mark.asyncio
async def test_cross_month_range_rejected():
    """depart_from과 depart_to가 다른 달이면 ok=False, 에러에 'same calendar month' 포함."""
    result = await _adapter().fetch(
        _req(depart_from=date(2026, 10, 20), depart_to=date(2026, 11, 19))
    )

    assert result.ok is False
    assert result.error is not None
    assert "same calendar month" in result.error


@pytest.mark.asyncio
async def test_non_krw_currency_rejected():
    """응답 통화가 KRW가 아니면 ok=False, 에러에 'non-KRW' 포함."""
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json={"data": {}, "currency": "usd"})
        )
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
    assert "non-KRW" in result.error


@pytest.mark.asyncio
async def test_prices_for_dates_error_does_not_kill_grouped():
    """prices_for_dates가 500 오류여도 grouped 결과를 반환한다."""
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(500)
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) > 0
