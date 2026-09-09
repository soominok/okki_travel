"""이벤트 응답 DTO."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    title: str
    url: str
    origin: str | None = None
    destination: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    discount_info: str | None = None
    is_active: bool
    fetched_at: datetime
