"""중복 억제 — dedup_key 생성 + cooldown DB 체크."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert

_SEVERITY_RANK = {"info": 0, "good": 1, "great": 2}


def make_dedup_key(
    watch_id: UUID,
    rule_id: str,
    price_krw: int,
    depart_date: date_type | None,
) -> str:
    bucket = price_krw // 5000
    raw = f"{watch_id}:{rule_id}:{bucket}:{depart_date}"
    return hashlib.sha1(raw.encode()).hexdigest()


async def is_suppressed(
    key: str,
    severity: str,
    cooldown_hours: int,
    session: AsyncSession,
) -> bool:
    """cooldown 내 동일 key의 알림이 있고, severity가 낮거나 같으면 True(발송 금지)."""
    cutoff = datetime.now(tz=UTC) - timedelta(hours=cooldown_hours)
    result = await session.execute(
        select(Alert.severity)
        .where(Alert.dedup_key == key, Alert.created_at >= cutoff)
        .order_by(Alert.created_at.desc())
        .limit(1)
    )
    existing_severity = result.scalar_one_or_none()
    if existing_severity is None:
        return False
    return _SEVERITY_RANK.get(severity, 0) <= _SEVERITY_RANK.get(existing_severity, 0)
