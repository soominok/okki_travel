"""sources/base.py 계약 검증 — DB 불필요."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.sources.base import FetchRequest, Offer, SourceResult


def _offer(**kw) -> dict:
    defaults = dict(
        source="test",
        external_id="ext-1",
        kind="flight",
        price_krw=220000,
        price_original=220000.0,
        currency_original="KRW",
        depart_date=date(2026, 10, 7),
        return_date=date(2026, 10, 9),
        carrier="7C",
        deep_link="https://example.com",
        raw={},
        collected_at=datetime.now(tz=UTC),
        freshness="cached",
        cache_age_days=1,
        observed_at=None,
    )
    defaults.update(kw)
    return defaults


class TestFetchRequest:
    def test_valid_request(self):
        req = FetchRequest(
            origin="ICN",
            destination="FUK",
            depart_from=date(2026, 10, 1),
            depart_to=date(2026, 10, 31),
            nights_min=2,
            nights_max=3,
        )
        assert req.origin == "ICN"
        assert req.adults == 1
        assert req.currency == "KRW"

    def test_date_order_rejected(self):
        with pytest.raises(ValidationError, match="depart_to"):
            FetchRequest(
                origin="ICN",
                destination="FUK",
                depart_from=date(2026, 10, 10),
                depart_to=date(2026, 10, 9),
            )

    def test_equal_dates_allowed(self):
        req = FetchRequest(
            origin="ICN",
            destination="FUK",
            depart_from=date(2026, 10, 7),
            depart_to=date(2026, 10, 7),
        )
        assert req.depart_from == req.depart_to


class TestOffer:
    def test_price_must_be_int(self):
        with pytest.raises(ValidationError):
            Offer(**_offer(price_krw=220000.5))  # float 거부

    def test_valid_offer(self):
        o = Offer(**_offer())
        assert o.price_krw == 220000
        assert isinstance(o.price_krw, int)

    def test_live_offer_no_cache_age(self):
        o = Offer(**_offer(freshness="live", cache_age_days=None))
        assert o.freshness == "live"
        assert o.cache_age_days is None


class TestSourceResult:
    def test_ok_result(self):
        r = SourceResult(ok=True, offers=[Offer(**_offer())])
        assert r.ok
        assert len(r.offers) == 1
        assert r.error is None

    def test_error_result_has_no_offers(self):
        r = SourceResult(ok=False, error="timeout")
        assert not r.ok
        assert r.offers == []
        assert r.credits_used == 0
