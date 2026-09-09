"""항공사 이벤트 CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_token
from app.models.event import AirlineEvent
from app.schemas.event import EventOut

router = APIRouter(prefix="/api/events", tags=["events"])
_auth = Depends(require_token)


@router.get("", response_model=list[EventOut], dependencies=[_auth])
async def list_events(
    source: str | None = None,
    active_only: bool = True,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    q = select(AirlineEvent).order_by(desc(AirlineEvent.fetched_at)).limit(limit)
    if active_only:
        q = q.where(AirlineEvent.is_active.is_(True))
    if source:
        q = q.where(AirlineEvent.source == source)
    result = await db.execute(q)
    return result.scalars().all()
