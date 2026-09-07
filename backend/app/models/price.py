import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, nullable_ts_col


class Offer(Base):
    """개별 상품. 매 수집마다 append 된다.
    OFFER_RETENTION_DAYS(90일) 후 정리되므로, 장기 히스토리는 PriceSnapshot 이 담당한다.
    """

    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watches.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watch_runs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)

    # CLAUDE.md 5번: 원화 정수. 원본 통화·금액은 별도 보존
    price_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    price_original: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency_original: Mapped[str | None] = mapped_column(Text)

    depart_date: Mapped[date | None] = mapped_column(Date)
    return_date: Mapped[date | None] = mapped_column(Date)
    carrier: Mapped[str | None] = mapped_column(Text)
    deep_link: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    collected_at: Mapped[datetime] = created_at_col()

    # --- 신선도 (스펙 §6). 사용자에게 신뢰도를 보여주기 위해 필요 ---
    freshness: Mapped[str] = mapped_column(Text, nullable=False)  # live | cached
    cache_age_days: Mapped[int | None] = mapped_column(Integer)
    # 소스가 관측 시각을 주지 않으면 NULL (스펙 §8 가정 A3)
    observed_at: Mapped[datetime | None] = nullable_ts_col()
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    verify_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        # ★ collected_at 이 아니라 run_id 를 쓴다.
        #   collected_at 은 행마다 now() 라 튜플이 항상 달라져 중복을 못 막는다.
        UniqueConstraint(
            "watch_id", "run_id", "source", "external_id", name="uq_offers_watch_run_source_ext"
        ),
        Index("ix_offers_watch_collected", "watch_id", "collected_at"),
        Index("ix_offers_watch_price", "watch_id", "price_krw"),
    )


class PriceSnapshot(Base):
    """차트용 시계열 요약. 실행당 1행.

    offers 와 중복처럼 보이지만 아니다: offers 는 90일 후 정리되고 snapshots 는
    영구 보관한다. 이 비대칭이 존재 이유다. "GROUP BY 로 대체 가능"하다고 지우지 말 것.
    """

    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    watch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watches.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = created_at_col()
    min_price_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    median_price_krw: Mapped[int | None] = mapped_column(Integer)
    offer_count: Mapped[int | None] = mapped_column(Integer)
    best_offer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # --- 커버리지 (스펙 §6) ---
    # ★ 이게 없으면 커버리지 하락을 가격 상승으로 오독한다.
    #   차트만이 아니라 rules.py 도 똑같이 속아 all_time_low 가 오발동한다.
    # ★ 단위는 둘 다 0~100 퍼센트로 통일한다.
    #   인접한 두 숫자 칼럼의 스케일이 다르면(하나는 0~1, 하나는 0~100)
    #   수집기와 UI 사이에서 단위 혼동 버그가 난다.
    coverage_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    live_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    credits_used: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_snapshots_watch_captured", "watch_id", "captured_at"),)
