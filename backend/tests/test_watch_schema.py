import pytest
from pydantic import ValidationError

from app.schemas.watch import WatchCreate


def test_flight_watch_parses():
    w = WatchCreate.model_validate(
        {
            "kind": "flight",
            "title": "가을 후쿠오카",
            "params": {
                "kind": "flight",
                "origin": "ICN",
                "destination": "FUK",
                "depart_from": "2026-10-01",
                "depart_to": "2026-12-31",
                "nights_min": 2,
                "nights_max": 3,
                "adults": 2,
                "cabin": "economy",
            },
            "rules": [{"id": "target", "type": "threshold", "price_krw": 250000}],
        }
    )
    assert w.params.origin == "ICN"
    assert w.rules[0].price_krw == 250000


def test_stay_params_rejected_for_flight_kind():
    """discriminated union 이 잘못된 조합을 API 레벨에서 걸러야 한다."""
    with pytest.raises(ValidationError):
        WatchCreate.model_validate(
            {
                "kind": "flight",
                "title": "잘못된 조합",
                "params": {
                    "kind": "stay",
                    "city_code": "SEL",
                    "checkin_from": "2026-12-24",
                    "checkin_to": "2026-12-26",
                    "nights": 2,
                    "guests": 2,
                },
                "rules": [],
            }
        )


def test_nights_max_must_be_ge_min():
    with pytest.raises(ValidationError):
        WatchCreate.model_validate(
            {
                "kind": "flight",
                "title": "역전된 박수",
                "params": {
                    "kind": "flight",
                    "origin": "ICN",
                    "destination": "FUK",
                    "depart_from": "2026-10-01",
                    "depart_to": "2026-12-31",
                    "nights_min": 5,
                    "nights_max": 2,
                },
                "rules": [],
            }
        )


def test_depart_to_must_be_after_depart_from():
    with pytest.raises(ValidationError):
        WatchCreate.model_validate(
            {
                "kind": "flight",
                "title": "역전된 기간",
                "params": {
                    "kind": "flight",
                    "origin": "ICN",
                    "destination": "FUK",
                    "depart_from": "2026-12-31",
                    "depart_to": "2026-10-01",
                },
                "rules": [],
            }
        )


def test_unknown_rule_type_rejected():
    with pytest.raises(ValidationError):
        WatchCreate.model_validate(
            {
                "kind": "flight",
                "title": "모르는 규칙",
                "params": {
                    "kind": "flight",
                    "origin": "ICN",
                    "destination": "FUK",
                    "depart_from": "2026-10-01",
                    "depart_to": "2026-12-31",
                },
                "rules": [{"id": "x", "type": "존재하지_않는_규칙"}],
            }
        )
