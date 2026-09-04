"""engine/rules.py 순수 함수 테스트.

DB·네트워크 없음. PriceSnapshot mock을 직접 만들어 사용.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.engine.rules import (
    AlertCandidate,  # noqa: F401
    eval_all_time_low,
    eval_drop_pct,
    eval_new_best,
    eval_threshold,
    evaluate_rules,
)


def _snap(min_price: int, offer_count: int = 5) -> MagicMock:
    s = MagicMock()
    s.min_price_krw = min_price
    s.median_price_krw = min_price + 10000
    s.offer_count = offer_count
    s.captured_at = datetime.now(tz=UTC)
    return s


def _history(prices: list[int]) -> list[MagicMock]:
    return [_snap(p) for p in prices]


# ---------- threshold ----------


def test_threshold_fires_when_below():
    snap = _snap(230000)
    rule = {"id": "r1", "type": "threshold", "price_krw": 250000}
    c = eval_threshold(snap, rule)
    assert c is not None
    assert c.rule_id == "r1"
    assert c.severity == "great"
    assert "230,000" in c.title or "230000" in c.title


def test_threshold_silent_when_above():
    snap = _snap(260000)
    rule = {"id": "r1", "type": "threshold", "price_krw": 250000}
    assert eval_threshold(snap, rule) is None


def test_threshold_fires_at_exact_price():
    snap = _snap(250000)
    rule = {"id": "r1", "type": "threshold", "price_krw": 250000}
    assert eval_threshold(snap, rule) is not None


# ---------- drop_pct ----------


def test_drop_pct_fires_when_dropped_enough():
    # median_14d = median of last 14 days
    history = _history([300000, 310000, 290000, 305000])  # median ~302500
    snap = _snap(230000)  # 23% 하락
    rule = {"id": "r2", "type": "drop_pct", "pct": 20, "baseline": "median_14d"}
    c = eval_drop_pct(snap, history, rule)
    assert c is not None
    assert c.severity == "good"


def test_drop_pct_silent_when_small_drop():
    history = _history([250000, 248000])
    snap = _snap(240000)  # ~4% 하락
    rule = {"id": "r2", "type": "drop_pct", "pct": 20, "baseline": "median_14d"}
    assert eval_drop_pct(snap, history, rule) is None


def test_drop_pct_silent_when_no_history():
    rule = {"id": "r2", "type": "drop_pct", "pct": 20, "baseline": "median_14d"}
    assert eval_drop_pct(_snap(200000), [], rule) is None


# ---------- all_time_low ----------


def test_all_time_low_fires_on_new_record():
    history = _history([300000, 280000, 270000])
    snap = _snap(250000)  # 역대 최저
    rule = {"id": "r3", "type": "all_time_low", "min_samples": 3}
    c = eval_all_time_low(snap, history, rule)
    assert c is not None
    assert c.severity == "great"


def test_all_time_low_silent_when_not_record():
    history = _history([300000, 240000, 270000])  # 240000이 기존 최저
    snap = _snap(250000)
    rule = {"id": "r3", "type": "all_time_low", "min_samples": 3}
    assert eval_all_time_low(snap, history, rule) is None


def test_all_time_low_silent_when_insufficient_samples():
    history = _history([300000])  # 1개뿐, min_samples=3 미달
    snap = _snap(200000)
    rule = {"id": "r3", "type": "all_time_low", "min_samples": 3}
    assert eval_all_time_low(snap, history, rule) is None


# ---------- new_best ----------


def test_new_best_fires_when_improved():
    history = _history([300000, 290000, 285000])
    snap = _snap(270000)  # 15000원 개선 (improve_krw=10000 초과)
    rule = {"id": "r4", "type": "new_best", "improve_krw": 10000}
    c = eval_new_best(snap, history, rule)
    assert c is not None
    assert c.severity == "good"


def test_new_best_silent_when_small_improvement():
    history = _history([300000, 280000])
    snap = _snap(276000)  # 4000원 개선, improve_krw=10000 미달
    rule = {"id": "r4", "type": "new_best", "improve_krw": 10000}
    assert eval_new_best(snap, history, rule) is None


def test_new_best_silent_when_no_history():
    rule = {"id": "r4", "type": "new_best", "improve_krw": 10000}
    assert eval_new_best(_snap(200000), [], rule) is None


# ---------- evaluate_rules ----------


def test_evaluate_rules_returns_all_fired():
    snap = _snap(230000)
    history = _history([300000, 280000, 270000])
    rules = [
        {"id": "t1", "type": "threshold", "price_krw": 250000},
        {"id": "a1", "type": "all_time_low", "min_samples": 3},
    ]
    results = evaluate_rules(snap, history, rules)
    assert len(results) == 2


def test_evaluate_rules_ignores_unknown_type():
    snap = _snap(100000)
    rules = [{"id": "x1", "type": "unknown_rule_type", "price_krw": 200000}]
    results = evaluate_rules(snap, [], rules)
    assert results == []
