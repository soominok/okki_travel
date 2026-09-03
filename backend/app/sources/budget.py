from __future__ import annotations

import math
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import CallBudget  # noqa: F401 — ORM import to ensure mapper is loaded


async def ensure_budget_row(
    session: AsyncSession,
    source: str,
    total: int,
    sample_cap_ratio: float = 0.70,
) -> None:
    """이번 달 call_budgets 행이 없으면 삽입한다. 이미 있으면 no-op."""
    sample_cap = math.floor(total * sample_cap_ratio)
    await session.execute(
        text(
            """
            INSERT INTO call_budgets (source, period_start, total, sample_cap)
            VALUES (:src, date_trunc('month', current_date)::date, :total, :cap)
            ON CONFLICT (source, period_start) DO NOTHING
            """
        ),
        {"src": source, "total": total, "cap": sample_cap},
    )
    await session.commit()


async def reserve_verify(
    session: AsyncSession,
    source: str,
    n: int = 1,
) -> bool:
    """VERIFY 크레딧 n개 선점. True = 성공, False = 예산 부족(건너뜀)."""
    result = await session.execute(
        text(
            """
            UPDATE call_budgets
            SET used_verify = used_verify + :n,
                updated_at  = now()
            WHERE source       = :src
              AND period_start = date_trunc('month', current_date)::date
              AND used_verify + used_sample + :n <= total
            RETURNING used_verify
            """
        ),
        {"src": source, "n": n},
    )
    updated = result.fetchone()
    if updated:
        await session.commit()
        return True
    return False


async def reserve_sample(
    session: AsyncSession,
    source: str,
    n: int = 1,
    days_left: int | None = None,
) -> bool:
    """SAMPLE 크레딧 n개 선점. 자기보정 일일 페이싱 포함.

    True = 성공, False = 예산 부족 또는 오늘 할당량 초과(건너뜀).
    days_left: 남은 일수 (기본값: 오늘 포함 이번 달 잔여일).
    """
    if days_left is None:
        import calendar

        today = date.today()
        days_left = calendar.monthrange(today.year, today.month)[1] - today.day + 1

    result = await session.execute(
        text(
            """
            UPDATE call_budgets
            SET used_sample     = used_sample + :n,
                used_sample_day = CASE
                                      WHEN sample_day = current_date
                                      THEN used_sample_day + :n
                                      ELSE :n
                                  END,
                sample_day      = current_date,
                updated_at      = now()
            WHERE source       = :src
              AND period_start = date_trunc('month', current_date)::date
              AND used_verify + used_sample + :n <= total
              AND used_sample + :n              <= sample_cap
              AND (CASE WHEN sample_day = current_date
                        THEN used_sample_day ELSE 0 END) + :n
                  <= CEIL(
                       (sample_cap - (used_sample - CASE WHEN sample_day = current_date
                                                         THEN used_sample_day ELSE 0 END)) * 1.0
                       / GREATEST(:days_left, 1)
                     )
            RETURNING used_sample
            """
        ),
        {"src": source, "n": n, "days_left": days_left},
    )
    updated = result.fetchone()
    if updated:
        await session.commit()
        return True
    return False
