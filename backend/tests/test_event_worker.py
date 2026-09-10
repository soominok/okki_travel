"""event_tick 단위 테스트 — 실제 HTTP 없음."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.sources.events.base import AirlineEventData


def _mock_settings(crawl_enabled: bool = True) -> MagicMock:
    m = MagicMock()
    m.crawl_enabled = crawl_enabled
    return m


@pytest.mark.asyncio
async def test_event_tick_inserts_new_event(db_session: AsyncSession):
    """신규 이벤트가 DB에 삽입되는지 확인."""
    from app.worker import event_tick

    fake_event = AirlineEventData(
        source="airbusan",
        external_id="EVT_TEST_001",
        title="테스트 특가",
        url="https://www.airbusan.com/ko/flyNEvent/detail?eventId=EVT_TEST_001",
        valid_to=date(2026, 12, 31),
    )

    adapter_mock = AsyncMock()
    adapter_mock.fetch_events = AsyncMock(return_value=[fake_event])

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.worker.get_settings", return_value=_mock_settings()),
        patch("app.worker.build_event_adapters", return_value=[adapter_mock]),
        patch("app.worker.SessionLocal", return_value=mock_session_ctx),
    ):
        await event_tick()

    # DB에 이벤트가 생성됐는지 확인
    from sqlalchemy import select

    from app.models.event import AirlineEvent

    result = await db_session.execute(
        select(AirlineEvent).where(AirlineEvent.external_id == "EVT_TEST_001")
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.title == "테스트 특가"
    assert row.source == "airbusan"


@pytest.mark.asyncio
async def test_event_tick_dedup_same_event(db_session: AsyncSession):
    """동일 (source, external_id)는 중복 저장 안 됨."""
    from app.worker import event_tick

    fake_event = AirlineEventData(
        source="tway",
        external_id="TW_DEDUP_001",
        title="중복 테스트",
        url="https://www.twayair.com/app/promotion/event/detail?eventId=TW_DEDUP_001",
    )

    for _ in range(2):
        adapter_mock = AsyncMock()
        adapter_mock.fetch_events = AsyncMock(return_value=[fake_event])

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.worker.get_settings", return_value=_mock_settings()),
            patch("app.worker.build_event_adapters", return_value=[adapter_mock]),
            patch("app.worker.SessionLocal", return_value=mock_session_ctx),
        ):
            await event_tick()

    from sqlalchemy import func, select

    from app.models.event import AirlineEvent

    result = await db_session.execute(
        select(func.count()).where(
            AirlineEvent.source == "tway",
            AirlineEvent.external_id == "TW_DEDUP_001",
        )
    )
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_event_tick_skips_when_crawl_disabled(db_session: AsyncSession):
    """crawl_enabled=False 이면 어댑터를 호출하지 않는다."""
    from app.worker import event_tick

    with (
        patch("app.worker.get_settings", return_value=_mock_settings(crawl_enabled=False)),
        patch("app.worker.build_event_adapters") as mock_adapters,
    ):
        await event_tick()
        mock_adapters.assert_not_called()


@pytest.mark.asyncio
async def test_event_tick_continues_on_adapter_error(db_session: AsyncSession):
    """어댑터 하나가 실패해도 나머지가 실행된다."""
    from app.worker import event_tick

    # 첫 번째 어댑터는 예외 발생
    failing = AsyncMock()
    failing.fetch_events = AsyncMock(side_effect=Exception("parse error"))
    failing.source = "airbusan"

    # 두 번째 어댑터는 정상 반환
    ok_event = AirlineEventData(
        source="tway",
        external_id="TW_RESILIENCE_001",
        title="회복 테스트",
        url="https://www.twayair.com/app/promotion/event/detail?eventId=TW_RESILIENCE_001",
        valid_to=date(2026, 12, 31),
    )
    working = AsyncMock()
    working.fetch_events = AsyncMock(return_value=[ok_event])
    working.source = "tway"

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.worker.get_settings", return_value=_mock_settings()),
        patch("app.worker.build_event_adapters", return_value=[failing, working]),
        patch("app.worker.SessionLocal", return_value=mock_session_ctx),
    ):
        await event_tick()

    # working 어댑터의 이벤트는 저장됐어야 함
    from sqlalchemy import select

    from app.models.event import AirlineEvent

    result = await db_session.execute(
        select(AirlineEvent).where(AirlineEvent.external_id == "TW_RESILIENCE_001")
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.source == "tway"
    assert saved.title == "회복 테스트"
