import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, nullable_ts_col


class CallBudget(Base):
    """유료 소스의 월 예산. 스펙 §4.

    VERIFY 는 페이싱하지 않고 SAMPLE 만 sample_cap 으로 제한한다.
    실질적으로 total - sample_cap 만큼이 VERIFY 예비분이 된다.
    """

    __tablename__ = "call_budgets"

    source: Mapped[str] = mapped_column(Text, primary_key=True)
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)  # 매월 1일
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    used_verify: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    used_sample: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # 자기 보정 일일 페이싱용 (스펙 §4)
    sample_day: Mapped[date | None] = mapped_column(Date)
    used_sample_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = created_at_col()


class CoverageCell(Base):
    """탐색 공간의 한 칸. 스펙 §5.

    이 테이블이 있어야 "안 찾아봤다"와 "찾아봤는데 없다"를 구분할 수 있다.
    offers 만으로는 영원히 구분되지 않는다.
    """

    __tablename__ = "coverage_cells"

    watch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watches.id", ondelete="CASCADE"), primary_key=True
    )
    depart_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nights: Mapped[int] = mapped_column(Integer, primary_key=True)

    last_seen_at: Mapped[datetime | None] = nullable_ts_col()  # NULL = 한 번도 못 봄
    last_price_krw: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(Text)
    probe_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_probe_at: Mapped[datetime | None] = nullable_ts_col()
    state: Mapped[str] = mapped_column(
        Text, nullable=False, default="unknown", server_default=text("'unknown'")
    )

    __table_args__ = (Index("ix_cells_watch_state_probe", "watch_id", "state", "last_probe_at"),)


class ProbeLog(Base):
    """샘플링 시도 기록. 스펙 §6.

    이게 없으면 튜닝이 감이 된다. 경계 탐색 적중률 같은 질문에
    데이터로 답하기 위해 존재한다. 90일 보관.
    """

    __tablename__ = "probe_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # ★ watch_id 에 FK 를 걸지 않는 것은 의도된 선택이다. 결함이 아니다.
    #   (a) 고볼륨 append 로그라 매 INSERT 마다 FK 검사를 치르고 싶지 않다
    #   (b) 90일 보관 정리 잡이 어차피 오래된 행을 지우므로 고아 행이 쌓이지 않는다
    #   (c) Watch 를 지워도 "그 감시에서 샘플링이 어땠는지"는 튜닝 근거로 남을 가치가 있다
    #   → 따라서 이 테이블에는 CASCADE 삭제 테스트가 없는 것이 맞다
    watch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    depart_date: Mapped[date] = mapped_column(Date, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)  # boundary | block | idle
    hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    price_krw: Mapped[int | None] = mapped_column(Integer)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (Index("ix_probe_log_created", "created_at"),)


class AppSetting(Base):
    """재배포 없이 바꿔야 하는 튜닝 상수. 스펙 §6.

    key='sampling_policy' 가 boundary_price_ratio, cold_after_probes 등을 담는다.
    이 값들은 전부 추측이므로 probe_log 를 보고 실데이터로 고친다.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = created_at_col()


class SourceHealth(Base):
    __tablename__ = "source_health"

    source: Mapped[str] = mapped_column(Text, primary_key=True)
    ok: Mapped[bool | None] = mapped_column(Boolean)
    last_ok_at: Mapped[datetime | None] = nullable_ts_col()
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    disabled_until: Mapped[datetime | None] = nullable_ts_col()


class FxRate(Base):
    """환율. 소스가 KRW 를 못 주는 경우의 폴백 (docs/03).

    수출입은행 API 는 주말·공휴일에 데이터가 없다. 조회는 항상
    "해당 일자 이하의 가장 최근 영업일" 로 한다.
    """

    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(Text, primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    rate_krw: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    fetched_at: Mapped[datetime] = created_at_col()


class Place(Base):
    """관광 장소 캐시 (TourAPI). Phase 2~3 에서 쓰지만 테이블은 지금 만들어둔다.
    나중에 마이그레이션을 하나 더 만드느니 지금 넣는 게 싸다 (docs/02 §4).
    """

    __tablename__ = "places"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    area_code: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_places_source_ext"),)
