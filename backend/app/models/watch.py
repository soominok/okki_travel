import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Computed, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, nullable_ts_col


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # flight | stay | package
    title: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rules: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    interval_min: Mapped[int] = mapped_column(
        Integer, nullable=False, default=360, server_default=text("360")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="active", server_default=text("'active'")
    )

    last_run_at: Mapped[datetime | None] = nullable_ts_col()
    # ★ 스케줄의 유일한 진실의 원천. APScheduler job store 를 쓰지 않는다 (docs/02 §7)
    next_run_at: Mapped[datetime | None] = nullable_ts_col()
    # 샘플링 라운드로빈용 (스펙 §4)
    last_sampled_at: Mapped[datetime | None] = nullable_ts_col()

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime | None] = nullable_ts_col()

    # params 는 jsonb 로 두되 조회가 필요한 필드만 생성 칼럼으로 꺼내 인덱싱한다.
    # Phase 2 추천이 "이 사용자가 어느 목적지를 감시하나"를 물을 때 jsonb path 쿼리를
    # 하게 되면 늦다. 쓰기 로직 중복은 없다.
    destination: Mapped[str | None] = mapped_column(
        Text, Computed("params->>'destination'", persisted=True), nullable=True
    )

    __table_args__ = (
        Index("ix_watches_status_next_run", "status", "next_run_at"),
        Index("ix_watches_destination", "destination"),
    )


class WatchRun(Base):
    __tablename__ = "watch_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watches.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = created_at_col()
    finished_at: Mapped[datetime | None] = nullable_ts_col()
    status: Mapped[str | None] = mapped_column(Text)  # ok | partial | failed
    sources_ok: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    sources_failed: Mapped[dict | None] = mapped_column(JSONB)
    offers_found: Mapped[int | None] = mapped_column(Integer)
    best_price_krw: Mapped[int | None] = mapped_column(Integer)
    credits_used: Mapped[int | None] = mapped_column(Integer)  # 스펙 §6
    note: Mapped[str | None] = mapped_column(Text)  # 커버리지 게이트 보류 사유 등
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_watch_runs_watch_started", "watch_id", "started_at"),)
