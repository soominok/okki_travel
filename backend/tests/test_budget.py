"""call_budgets 예산 선점 로직 테스트 — 실제 Postgres 사용."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.sources.budget import ensure_budget_row, reserve_sample, reserve_verify


@pytest.mark.asyncio
async def test_ensure_budget_row_creates_row(db_session: AsyncSession):
    await ensure_budget_row(db_session, source="brightdata_test_a", total=100)
    ok = await reserve_verify(db_session, source="brightdata_test_a")
    assert ok


@pytest.mark.asyncio
async def test_reserve_verify_decrements_budget(db_session: AsyncSession):
    await ensure_budget_row(db_session, source="brightdata_test_b", total=3)
    assert await reserve_verify(db_session, source="brightdata_test_b")
    assert await reserve_verify(db_session, source="brightdata_test_b")
    assert await reserve_verify(db_session, source="brightdata_test_b")
    # 4번째는 예산 초과 → False
    assert not await reserve_verify(db_session, source="brightdata_test_b")


@pytest.mark.asyncio
async def test_reserve_sample_respects_cap(db_session: AsyncSession):
    """sample_cap을 월 내에 다 써도 cap을 초과하지 않는다."""
    # total=10, sample_cap=7 (ratio 0.70), days_left=1 → 하루 허용 7개
    await ensure_budget_row(db_session, source="brightdata_test_c", total=10, sample_cap_ratio=0.70)
    results = [
        await reserve_sample(db_session, source="brightdata_test_c", days_left=1) for _ in range(8)
    ]
    assert results.count(True) == 7
    assert results.count(False) == 1


@pytest.mark.asyncio
async def test_ensure_idempotent(db_session: AsyncSession):
    await ensure_budget_row(db_session, source="brightdata_test_d", total=5)
    await ensure_budget_row(db_session, source="brightdata_test_d", total=5)  # 중복 호출
    # 두 번 호출해도 total이 두 배가 되면 안 된다
    ok_count = 0
    for _ in range(6):
        if await reserve_verify(db_session, source="brightdata_test_d"):
            ok_count += 1
    assert ok_count == 5


@pytest.mark.asyncio
async def test_reserve_sample_pacing_limits_daily(db_session: AsyncSession):
    """같은 날 두 번째 호출은 일일 허용량 초과 시 False."""
    # sample_cap=7, days_left=7 → 하루 허용 = ceil(7/7) = 1
    await ensure_budget_row(db_session, source="brightdata_test_e", total=20, sample_cap_ratio=0.35)
    first = await reserve_sample(db_session, source="brightdata_test_e", days_left=7)
    second = await reserve_sample(db_session, source="brightdata_test_e", days_left=7)
    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_missing_budget_row_returns_false(db_session: AsyncSession):
    """예산 행이 없으면 False — 예외 아님."""
    ok = await reserve_verify(db_session, source="brightdata_nonexistent")
    assert ok is False


@pytest.mark.asyncio
async def test_verify_consumes_total_blocking_sample(db_session: AsyncSession):
    """verify로 total을 모두 쓰면 sample도 막힌다 (total 제약)."""
    await ensure_budget_row(db_session, source="brightdata_test_f", total=2, sample_cap_ratio=0.90)
    await reserve_verify(db_session, source="brightdata_test_f")
    await reserve_verify(db_session, source="brightdata_test_f")
    ok = await reserve_sample(db_session, source="brightdata_test_f", days_left=1)
    assert ok is False
