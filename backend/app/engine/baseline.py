"""스냅샷 히스토리 DB 조회 — rules.py에 넘길 history 리스트를 준비."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import PriceSnapshot


async def get_history(
    watch_id: UUID,
    days: int,
    session: AsyncSession,
) -> list[PriceSnapshot]:
    """최근 N일간 price_snapshots를 오래된 순으로 반환."""
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    result = await session.execute(
        select(PriceSnapshot)
        .where(
            PriceSnapshot.watch_id == watch_id,
            PriceSnapshot.captured_at >= cutoff,
        )
        .order_by(PriceSnapshot.captured_at)
    )
    return list(result.scalars().all())
