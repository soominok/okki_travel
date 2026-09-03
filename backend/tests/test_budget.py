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
    # total=10, sample_cap=7 (ratio 0.70)
    await ensure_budget_row(
        db_session, source="brightdata_test_c", total=10, sample_cap_ratio=0.70
    )
    # sample_cap = 7, 8번 시도 → 7번만 성공
    results = [
        await reserve_sample(db_session, source="brightdata_test_c", days_left=30)
        for _ in range(8)
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
