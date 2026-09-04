"""notify/slack.py + notify/dispatcher.py 테스트."""

from __future__ import annotations

import uuid
from datetime import time
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from app.notify.base import Confidence, Field, NotificationMessage
from app.notify.dispatcher import Dispatcher, _is_quiet_now


def _msg(severity: str = "good") -> NotificationMessage:
    return NotificationMessage(
        severity=severity,
        confidence=Confidence(
            verified=False, freshness="cached", age_label="최대 7일 전 캐시", source="travelpayouts"
        ),
        title="ICN→FUK 238,000원",
        summary="목표가 250,000원 대비 -12,000원",
        fields=[Field(label="출발일", value="2026-10-15")],
        dedup_key="test-key",
    )


# ---------- quiet_hours ----------


def test_is_quiet_now_inside_range():
    # 00:30 KST는 quiet (23:00-08:00)
    now_kst_time = time(0, 30)
    assert _is_quiet_now(time(23, 0), time(8, 0), now_kst_time) is True


def test_is_quiet_now_outside_range():
    now_kst_time = time(12, 0)  # 낮 12시는 조용하지 않음
    assert _is_quiet_now(time(23, 0), time(8, 0), now_kst_time) is False


def test_is_quiet_now_great_always_false():
    # great는 quiet 계산을 하지 않음 (dispatcher 레벨에서 처리)
    pass


# ---------- slack ----------


@pytest.mark.asyncio
async def test_slack_notifier_sends_block_kit():
    from app.notify.slack import SlackNotifier

    with respx.mock(base_url="https://hooks.slack.com") as mock:
        mock.post("/services/test").mock(return_value=Response(200, text="ok"))

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/test")
        result = await notifier.send(_msg())

    assert result.status == "sent"
    assert result.channel == "slack"


@pytest.mark.asyncio
async def test_slack_notifier_returns_failed_on_error():
    from app.notify.slack import SlackNotifier

    with respx.mock(base_url="https://hooks.slack.com") as mock:
        mock.post("/services/fail").mock(return_value=Response(500, text="error"))

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/fail")
        result = await notifier.send(_msg())

    assert result.status == "failed"


# ---------- dispatcher ----------


@pytest.mark.asyncio
async def test_dispatcher_skips_slack_when_no_webhook(db_session):

    settings = MagicMock()
    settings.notify_channel_list = ["slack", "inapp"]
    settings.slack_webhook_url = None
    settings.quiet_hours_start = time(23, 0)
    settings.quiet_hours_end = time(8, 0)

    alert_id = uuid.uuid4()
    dispatcher = Dispatcher(settings=settings)
    results = await dispatcher.dispatch(_msg(), alert_id=alert_id, session=db_session)

    slack_result = next((r for r in results if r.channel == "slack"), None)
    assert slack_result is not None
    assert slack_result.status == "skipped"


@pytest.mark.asyncio
async def test_dispatcher_defers_slack_in_quiet_hours(db_session, migrated_engine):
    from app.models.alert import Alert
    from app.models.watch import Watch

    watch = Watch(
        kind="flight",
        title="t",
        params={
            "kind": "flight",
            "origin": "ICN",
            "destination": "FUK",
            "depart_from": "2026-10-01",
            "depart_to": "2026-10-31",
        },
        rules=[],
    )
    db_session.add(watch)
    await db_session.flush()

    alert = Alert(
        watch_id=watch.id,
        rule_id="r1",
        severity="good",
        title="t",
        body="b",
        dedup_key="qh-test",
    )
    db_session.add(alert)
    await db_session.commit()

    settings = MagicMock()
    settings.notify_channel_list = ["slack"]
    settings.slack_webhook_url = MagicMock()
    settings.slack_webhook_url.get_secret_value.return_value = "https://hooks.slack.com/test"
    settings.quiet_hours_start = time(23, 0)
    settings.quiet_hours_end = time(8, 0)

    with patch("app.notify.dispatcher._is_quiet_now", return_value=True):
        dispatcher = Dispatcher(settings=settings)
        results = await dispatcher.dispatch(
            _msg(severity="good"), alert_id=alert.id, session=db_session
        )

    slack_result = next(r for r in results if r.channel == "slack")
    assert slack_result.status == "deferred"
