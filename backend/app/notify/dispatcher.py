"""채널 라우팅 + QUIET_HOURS 판단 + alert_deliveries 기록."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.alert import AlertDelivery
from app.notify.base import DeliveryResult, NotificationMessage
from app.notify.inapp import InAppNotifier
from app.notify.slack import SlackNotifier

log = structlog.get_logger()


def _is_quiet_now(start: time, end: time, now_kst: time | None = None) -> bool:
    """KST 기준 방해금지 시간인지 확인. 자정을 넘는 범위(23:00-08:00) 지원."""
    if now_kst is None:
        now_kst = (datetime.now(tz=UTC) + timedelta(hours=9)).time()
    if start <= end:
        return start <= now_kst < end
    # 자정 넘김: e.g. 23:00-08:00
    return now_kst >= start or now_kst < end


class Dispatcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def dispatch(
        self,
        msg: NotificationMessage,
        alert_id: uuid.UUID,
        session: AsyncSession,
    ) -> list[DeliveryResult]:
        results: list[DeliveryResult] = []
        quiet = _is_quiet_now(self._settings.quiet_hours_start, self._settings.quiet_hours_end)

        for channel in self._settings.notify_channel_list:
            result = await self._send_channel(channel, msg, alert_id, quiet, session)
            results.append(result)
            await self._record_delivery(alert_id, result, session)

        return results

    async def _send_channel(
        self,
        channel: str,
        msg: NotificationMessage,
        alert_id: uuid.UUID,
        quiet: bool,
        session: AsyncSession,
    ) -> DeliveryResult:
        if channel == "inapp":
            notifier = InAppNotifier(alert_id=alert_id, session=session)
            return await notifier.send(msg)

        if channel == "slack":
            webhook = self._settings.slack_webhook_url
            if webhook is None:
                return DeliveryResult(channel="slack", status="skipped", error="no webhook url")
            if quiet and msg.severity != "great":
                return DeliveryResult(channel="slack", status="deferred")
            notifier = SlackNotifier(webhook_url=webhook.get_secret_value())
            return await notifier.send(msg)

        log.warning("dispatcher.unknown_channel", channel=channel)
        return DeliveryResult(channel=channel, status="skipped", error="unknown channel")

    async def _record_delivery(
        self,
        alert_id: uuid.UUID,
        result: DeliveryResult,
        session: AsyncSession,
    ) -> None:
        if result.channel == "inapp":
            return  # InAppNotifier가 자체 flush함
        try:
            delivery = AlertDelivery(
                alert_id=alert_id,
                channel=result.channel,
                status=result.status,
                error=result.error,
                sent_at=datetime.now(tz=UTC) if result.status == "sent" else None,
            )
            session.add(delivery)
            await session.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning("dispatcher.record_failed", error=str(exc))
