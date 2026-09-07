"""모든 모델의 공통 기반.

CLAUDE.md 4번: DB 시각은 전부 UTC timestamptz. 여기서 강제한다.
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 제약에 결정적인 이름을 부여한다. 이게 없으면 Postgres가 서버 생성 이름(예: 임의
# 해시가 섞인 이름)을 붙이고, alembic autogenerate가 이름 없는 제약을 다룰 때
# `op.drop_constraint(None, ...)`처럼 이름을 못 채운 downgrade를 만들어 왕복
# (`alembic downgrade -1 && upgrade head`)이 실패한다.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def created_at_col() -> Mapped[datetime]:
    """생성 시각. 서버 사이드 now(). 애플리케이션이 시각을 만들지 않는다."""
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def nullable_ts_col() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True)
