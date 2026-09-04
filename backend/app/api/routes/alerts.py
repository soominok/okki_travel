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
from app.notify.base import Confidence, Field, NotificationMessage
from app.schemas.alert import AlertOut

log = structlog.get_logger()
router = APIRouter(prefix="/api/alerts", tags=["alerts"])
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


@router.post("/test", status_code=status.HTTP_200_OK, dependencies=[_auth])
async def notify_test(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if settings.slack_webhook_url is None:
        raise HTTPException(status_code=422, detail="SLACK_WEBHOOK_URL not configured")

    msg = NotificationMessage(
        severity="info",
        confidence=Confidence(
            verified=False, freshness="live", age_label="테스트 메시지", source="system"
        ),
        title="TripPick 알림 테스트",
        summary="이 메시지가 보이면 슬랙 연동이 정상입니다.",
        fields=[
            Field(
                label="발송 시각",
                value=datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC"),
            )
        ],
        dedup_key="test-message",
    )

    # 테스트는 quiet_hours 무시하고 직접 slack만 발송
    from app.notify.slack import SlackNotifier

    notifier = SlackNotifier(webhook_url=settings.slack_webhook_url.get_secret_value())
    result = await notifier.send(msg)
    if result.status == "failed":
        raise HTTPException(status_code=502, detail=f"slack send failed: {result.error}")
    return {"status": "sent"}
