"""Alert 응답 DTO."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    watch_id: uuid.UUID
    rule_id: str
    severity: str
    title: str
    body: str
    payload: dict[str, Any] | None = None
    dedup_key: str
    created_at: datetime
    read_at: datetime | None = None
