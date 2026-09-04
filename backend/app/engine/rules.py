"""규칙 평가기 — 순수 함수만. DB·네트워크 접근 금지 (CLAUDE.md §10)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AlertCandidate:
    rule_id: str
    severity: str  # "info" | "good" | "great"
    title: str
    body: str
    best_price_krw: int
    depart_date: date | None = None
    deep_link: str | None = None


def _fmt(price: int) -> str:
    return f"{price:,}원"


def _median_min(history: list) -> int | None:
    """history의 min_price_krw 중앙값. 빈 리스트면 None."""
    prices = [s.min_price_krw for s in history]
    if not prices:
        return None
    return int(statistics.median(prices))


def eval_threshold(snapshot, rule: dict) -> AlertCandidate | None:
    target = int(rule["price_krw"])
    price = snapshot.min_price_krw
    if price > target:
        return None
    diff = target - price
    return AlertCandidate(
        rule_id=rule["id"],
        severity="great",
        title=f"목표가 달성 — {_fmt(price)}",
        body=f"목표가 {_fmt(target)} 대비 -{_fmt(diff)} ({diff * 100 // target}% 절약)",
        best_price_krw=price,
    )


def eval_drop_pct(snapshot, history: list, rule: dict) -> AlertCandidate | None:
    baseline_key = rule.get("baseline", "median_14d")  # noqa: F841  # baseline.py가 이미 필터함
    baseline = _median_min(history)
    if baseline is None:
        return None
    threshold_pct = float(rule["pct"])
    price = snapshot.min_price_krw
    drop_pct = (baseline - price) / baseline * 100
    if drop_pct < threshold_pct:
        return None
    return AlertCandidate(
        rule_id=rule["id"],
        severity="good",
        title=f"{threshold_pct:.0f}% 이상 하락 — {_fmt(price)}",
        body=f"기준가 {_fmt(baseline)} 대비 -{drop_pct:.1f}% 하락",
        best_price_krw=price,
    )


def eval_all_time_low(snapshot, history: list, rule: dict) -> AlertCandidate | None:
    min_samples = int(rule.get("min_samples", 10))
    if len(history) < min_samples:
        return None
    price = snapshot.min_price_krw
    prev_min = min(s.min_price_krw for s in history)
    if price >= prev_min:
        return None
    return AlertCandidate(
        rule_id=rule["id"],
        severity="great",
        title=f"역대 최저가 경신 — {_fmt(price)}",
        body=f"직전 최저 {_fmt(prev_min)} 대비 -{_fmt(prev_min - price)} 하락",
        best_price_krw=price,
    )


def eval_new_best(snapshot, history: list, rule: dict) -> AlertCandidate | None:
    if not history:
        return None
    improve_krw = int(rule.get("improve_krw", 10000))
    price = snapshot.min_price_krw
    prev_best = min(s.min_price_krw for s in history)
    improvement = prev_best - price
    if improvement < improve_krw:
        return None
    return AlertCandidate(
        rule_id=rule["id"],
        severity="good",
        title=f"최저가 갱신 — {_fmt(price)}",
        body=f"직전 최저 {_fmt(prev_best)} 대비 -{_fmt(improvement)} 개선",
        best_price_krw=price,
    )


_EVALUATORS = {
    "threshold": lambda snap, hist, rule: eval_threshold(snap, rule),
    "drop_pct": eval_drop_pct,
    "all_time_low": eval_all_time_low,
    "new_best": eval_new_best,
}


def evaluate_rules(snapshot, history: list, rules: list[dict]) -> list[AlertCandidate]:
    """모든 규칙을 평가하고 발화한 것들을 반환."""
    results: list[AlertCandidate] = []
    for rule in rules:
        rule_type = rule.get("type", "")
        evaluator = _EVALUATORS.get(rule_type)
        if evaluator is None:
            continue
        candidate = evaluator(snapshot, history, rule)
        if candidate is not None:
            results.append(candidate)
    return results
