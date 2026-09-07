"""채널 중립 알림 모델 + Notifier 프로토콜."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel


class Field(BaseModel):
    label: str
    value: str


class Confidence(BaseModel):
    verified: bool
    freshness: Literal["live", "cached"]
    age_label: str  # "12분 전 실측" | "최대 7일 전 캐시"
    source: str
    coverage_pct: int | None = None


class NotificationMessage(BaseModel):
    severity: Literal["info", "good", "great"]
    confidence: Confidence
    title: str
    summary: str
    fields: list[Field]
    link: str | None = None
    link_label: str | None = None
    dashboard_url: str | None = None
    dedup_key: str


class DeliveryResult(BaseModel):
    channel: str
    status: Literal["sent", "failed", "skipped", "deferred"]
    error: str | None = None


class Notifier(Protocol):
    channel: str

    async def send(self, msg: NotificationMessage) -> DeliveryResult: ...
