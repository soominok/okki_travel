"""Collector 파이프라인 테스트."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
import respx

from app.config import get_settings
from app.engine.collector import _monthly_chunks, collect_watch
from app.models.price import Offer as DbOffer
from app.models.price import PriceSnapshot
from app.models.watch import Watch
from app.sources.flight.travelpayouts import _BASE, TravelpayoutsAdapter
from app.sources.http import RateLimitedClient
from app.sources.registry import SourceRegistry

FIXTURES = Path(__file__).parent / "fixtures"

_GROUPED = f"{_BASE}/aviasales/v3/grouped_prices"
_PRICES = f"{_BASE}/aviasales/v3/prices_for_dates"


def _tp_fixture() -> dict:
    return json.loads((FIXTURES / "travelpayouts" / "grouped_prices.json").read_text())


def _registry_with_tp() -> SourceRegistry:
    r = SourceRegistry()
    r.register(TravelpayoutsAdapter(token="tok", client=RateLimitedClient(min_interval_sec=0)))
    return r


def _make_watch_kwargs(depart_from="2026-10-01", depart_to="2026-10-31") -> dict:
    return dict(
        kind="flight",
        title="테스트",
        params={
            "kind": "flight",
            "origin": "ICN",
            "destination": "FUK",
            "depart_from": depart_from,
            "depart_to": depart_to,
            "nights_min": 2,
            "nights_max": 3,
            "adults": 1,
            "cabin": "economy",
            "direct_only": False,
            "weekday_preference": [],
        },
        rules=[{"id": "t1", "type": "threshold", "price_krw": 250000}],
        interval_min=360,
        status="active",
    )


# ── 순수 함수 테스트 ──────────────────────────────────────────────


def test_monthly_chunks_same_month():
    chunks = _monthly_chunks(date(2026, 10, 1), date(2026, 10, 31))
    assert chunks == [(date(2026, 10, 1), date(2026, 10, 31))]


def test_monthly_chunks_two_months():
    chunks = _monthly_chunks(date(2026, 10, 15), date(2026, 11, 10))
    assert len(chunks) == 2
    assert chunks[0] == (date(2026, 10, 15), date(2026, 10, 31))
    assert chunks[1] == (date(2026, 11, 1), date(2026, 11, 10))


def test_monthly_chunks_three_months():
    chunks = _monthly_chunks(date(2026, 10, 1), date(2026, 12, 31))
    assert len(chunks) == 3


# ── DB 테스트 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_watch_scan_saves_offers(db_session):
    """SCAN 결과가 DB에 저장되고 WatchRun.status='ok'."""
    from sqlalchemy import select

    w = Watch(**_make_watch_kwargs())
    db_session.add(w)
    await db_session.flush()
    watch_id = w.id

    _empty: dict = {"data": [], "currency": "krw"}
    with respx.mock:
        respx.get(_GROUPED).mock(return_value=httpx.Response(200, json=_tp_fixture()))
        respx.get(_PRICES).mock(return_value=httpx.Response(200, json=_empty))

        run = await collect_watch(
            watch_id,
            session=db_session,
            registry=_registry_with_tp(),
            settings=get_settings(),
        )

    assert run.status == "ok"
    assert run.offers_found is not None and run.offers_found > 0

    offers = (
        (await db_session.execute(select(DbOffer).where(DbOffer.watch_id == watch_id)))
        .scalars()
        .all()
    )
    assert len(offers) > 0
    assert all(isinstance(o.price_krw, int) for o in offers)


@pytest.mark.asyncio
async def test_collect_watch_creates_snapshot(db_session):
    """수집 후 PriceSnapshot 1행 생성."""
    from sqlalchemy import select

    w = Watch(**_make_watch_kwargs())
    db_session.add(w)
    await db_session.flush()

    _empty: dict = {"data": [], "currency": "krw"}
    with respx.mock:
        respx.get(_GROUPED).mock(return_value=httpx.Response(200, json=_tp_fixture()))
        respx.get(_PRICES).mock(return_value=httpx.Response(200, json=_empty))

        await collect_watch(
            w.id,
            session=db_session,
            registry=_registry_with_tp(),
            settings=get_settings(),
        )

    snaps = (
        (await db_session.execute(select(PriceSnapshot).where(PriceSnapshot.watch_id == w.id)))
        .scalars()
        .all()
    )
    assert len(snaps) == 1
    assert snaps[0].min_price_krw > 0


@pytest.mark.asyncio
async def test_collect_watch_all_fail_returns_failed(db_session):
    """SCAN 어댑터 전부 실패 → WatchRun.status='failed'."""
    w = Watch(**_make_watch_kwargs())
    db_session.add(w)
    await db_session.flush()

    with respx.mock:
        respx.get(_GROUPED).mock(return_value=httpx.Response(500))
        respx.get(_PRICES).mock(return_value=httpx.Response(500))
        run = await collect_watch(
            w.id,
            session=db_session,
            registry=_registry_with_tp(),
            settings=get_settings(),
        )

    assert run.status == "failed"
    assert run.offers_found == 0


@pytest.mark.asyncio
async def test_collect_watch_paused_returns_failed(db_session):
    """paused Watch → WatchRun.status='failed'."""
    w = Watch(**{**_make_watch_kwargs(), "status": "paused"})
    db_session.add(w)
    await db_session.flush()

    run = await collect_watch(
        w.id,
        session=db_session,
        registry=_registry_with_tp(),
        settings=get_settings(),
    )
    assert run.status == "failed"


@pytest.mark.asyncio
async def test_collect_watch_creates_alert_when_rule_fires(db_session, migrated_engine):
    """규칙 평가 → dedup pass → Alert DB 저장 검증."""
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy import select

    from app.engine.collector import collect_watch
    from app.models.alert import Alert
    from app.models.watch import Watch as WatchModel
    from app.sources.base import Offer, SourceResult

    # threshold 250000원 규칙이 있는 Watch 생성
    watch = WatchModel(
        kind="flight",
        title="alert-test",
        status="active",
        params={
            "kind": "flight",
            "origin": "ICN",
            "destination": "FUK",
            "depart_from": "2026-10-01",
            "depart_to": "2026-10-31",
        },
        rules=[{"id": "r1", "type": "threshold", "price_krw": 250000}],
        next_run_at=datetime.now(tz=UTC),
    )
    db_session.add(watch)
    await db_session.commit()

    # 230,000원 오퍼를 반환하는 mock registry (threshold 250,000 미만 → 규칙 발화)
    mock_offer = Offer(
        source="travelpayouts",
        external_id="test-001",
        kind="flight",
        price_krw=230000,
        price_original=230000,
        currency_original="KRW",
        depart_date=date(2026, 10, 15),
        freshness="cached",
        cache_age_days=1,
        collected_at=datetime.now(tz=UTC),
        raw={},
    )
    mock_adapter = MagicMock()
    mock_adapter.name = "travelpayouts"
    mock_adapter.capability.cost_per_call = 0
    mock_adapter.capability.roles = ["scan"]
    mock_adapter.fetch = AsyncMock(return_value=SourceResult(ok=True, offers=[mock_offer]))

    mock_registry = MagicMock()
    mock_registry.get.return_value = [mock_adapter]

    settings = get_settings()

    run = await collect_watch(
        watch.id, session=db_session, registry=mock_registry, settings=settings
    )

    assert run.status in ("ok", "partial")
    assert run.offers_found == 1

    # Alert가 생성됐는지 확인
    result = await db_session.execute(select(Alert).where(Alert.watch_id == watch.id))
    alerts = result.scalars().all()
    assert len(alerts) >= 1
    assert alerts[0].rule_id == "r1"
    assert alerts[0].severity == "great"


@pytest.mark.asyncio
async def test_collect_watch_no_alert_when_no_rules(db_session, migrated_engine):
    """watch.rules가 빈 리스트면 Alert가 생성되지 않는다."""
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy import select

    from app.engine.collector import collect_watch
    from app.models.alert import Alert
    from app.models.watch import Watch as WatchModel
    from app.sources.base import Offer, SourceResult

    watch = WatchModel(
        kind="flight",
        title="no-rules",
        status="active",
        params={
            "kind": "flight",
            "origin": "ICN",
            "destination": "FUK",
            "depart_from": "2026-10-01",
            "depart_to": "2026-10-31",
        },
        rules=[],  # 규칙 없음
        next_run_at=datetime.now(tz=UTC),
    )
    db_session.add(watch)
    await db_session.commit()

    mock_offer = Offer(
        source="travelpayouts",
        external_id="test-002",
        kind="flight",
        price_krw=100000,
        price_original=100000,
        currency_original="KRW",
        depart_date=date(2026, 10, 15),
        freshness="cached",
        cache_age_days=1,
        collected_at=datetime.now(tz=UTC),
        raw={},
    )
    mock_adapter = MagicMock()
    mock_adapter.name = "travelpayouts"
    mock_adapter.capability.cost_per_call = 0
    mock_adapter.capability.roles = ["scan"]
    mock_adapter.fetch = AsyncMock(return_value=SourceResult(ok=True, offers=[mock_offer]))

    mock_registry = MagicMock()
    mock_registry.get.return_value = [mock_adapter]

    await collect_watch(
        watch.id, session=db_session, registry=mock_registry, settings=get_settings()
    )

    result = await db_session.execute(select(Alert).where(Alert.watch_id == watch.id))
    assert len(result.scalars().all()) == 0
