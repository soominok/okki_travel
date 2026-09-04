"""Alert API — 알림함 조회·읽음 처리·테스트 발송."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_token
from app.config import get_settings
from app.models.alert import Alert
from app.notify.dispatcher import Dispatcher
from app.schemas.alert import AlertOut

log = structlog.get_logger()

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
notify_router = APIRouter(prefix="/api/notify", tags=["notify"])
_auth = Depends(require_token)


@router.get("", response_model=list[AlertOut], dependencies=[_auth])
async def list_alerts(
    unread: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if unread:
        q = q.where(Alert.read_at.is_(None))
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/{alert_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_auth],
)
async def mark_read(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    if alert.read_at is None:
        alert.read_at = datetime.now(tz=UTC)
        await db.commit()


@notify_router.post("/test", status_code=status.HTTP_200_OK, dependencies=[_auth])
async def notify_test():
    """Slack webhook 연동 테스트. quiet_hours 무시하고 직접 발송."""
    settings = get_settings()
    dispatcher = Dispatcher(settings=settings)
    try:
        result = await dispatcher.test_send()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.status == "failed":
        raise HTTPException(status_code=502, detail=f"slack send failed: {result.error}")
    return {"status": "sent"}
