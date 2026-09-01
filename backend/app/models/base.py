"""모든 모델의 공통 기반.

CLAUDE.md 4번: DB 시각은 전부 UTC timestamptz. 여기서 강제한다.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def created_at_col() -> Mapped[datetime]:
    """생성 시각. 서버 사이드 now(). 애플리케이션이 시각을 만들지 않는다."""
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def nullable_ts_col() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True)
