"""Slack Block Kit 렌더러 + webhook POST."""

from __future__ import annotations

import structlog
from httpx import AsyncClient, HTTPStatusError, TimeoutException

from app.notify.base import DeliveryResult, NotificationMessage

log = structlog.get_logger()

_SEVERITY_EMOJI = {"info": "ℹ️", "good": "✅", "great": "🔥"}


def _build_blocks(msg: NotificationMessage) -> list[dict]:
    emoji = _SEVERITY_EMOJI.get(msg.severity, "")
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {msg.title}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": msg.summary},
        },
    ]
    if msg.fields:
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{f.label}*\n{f.value}"} for f in msg.fields
                ],
            }
        )
    freshness_text = f"_{msg.confidence.age_label}_"
    if msg.confidence.verified:
        freshness_text += " ✓ 실가격 확인"
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": freshness_text}]})
    if msg.link:
        label = msg.link_label or "예약 바로가기"
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": label},
                        "url": msg.link,
                        "style": "primary",
                    }
                ],
            }
        )
    return blocks


class SlackNotifier:
    channel = "slack"

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def send(self, msg: NotificationMessage) -> DeliveryResult:
        payload = {"blocks": _build_blocks(msg)}
        try:
            async with AsyncClient(timeout=10) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
            return DeliveryResult(channel=self.channel, status="sent")
        except (HTTPStatusError, TimeoutException, Exception) as exc:  # noqa: BLE001
            log.warning("slack.send_failed", error=str(exc))
            return DeliveryResult(channel=self.channel, status="failed", error=str(exc))
