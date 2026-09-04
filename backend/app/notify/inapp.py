"""inapp 채널 — AlertDelivery 기록만 한다. Alert는 collector가 사전 저장."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertDelivery
from app.notify.base import DeliveryResult, NotificationMessage

log = structlog.get_logger()


class InAppNotifier:
    channel = "inapp"

    def __init__(self, alert_id: uuid.UUID, session: AsyncSession) -> None:
        self._alert_id = alert_id
        self._session = session

    async def send(self, msg: NotificationMessage) -> DeliveryResult:
        try:
            delivery = AlertDelivery(
                alert_id=self._alert_id,
                channel=self.channel,
                status="sent",
                sent_at=datetime.now(tz=UTC),
            )
            self._session.add(delivery)
            await self._session.flush()
            return DeliveryResult(channel=self.channel, status="sent")
        except Exception as exc:  # noqa: BLE001
            log.warning("inapp.send_failed", error=str(exc))
            return DeliveryResult(channel=self.channel, status="failed", error=str(exc))
