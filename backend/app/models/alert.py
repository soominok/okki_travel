import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, nullable_ts_col


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watches.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)  # info | good | great
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    read_at: Mapped[datetime | None] = nullable_ts_col()

    # ⚠️ date_trunc('hour', created_at) 로 unique 인덱스를 만들려 하지 말 것.
    #    created_at 이 timestamptz 라 date_trunc 는 STABLE 이고 Postgres 가 거부한다.
    #    게다가 1시간 버킷은 ALERT_COOLDOWN_HOURS(12)와 어긋난다.
    #    dedup 은 engine/dedup.py 단일 경로로만 강제하고 여기서는 조회 인덱스만 둔다.
    __table_args__ = (
        Index("ix_alerts_dedup_created", "dedup_key", "created_at"),
        Index("ix_alerts_watch_created", "watch_id", "created_at"),
    )


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # slack | telegram | inapp
    # deferred = QUIET_HOURS 로 미뤄짐. 버린 게 아니라 아침에 다이제스트로 나간다 (스펙 §7)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = nullable_ts_col()

    __table_args__ = (Index("ix_deliveries_alert", "alert_id"),)
