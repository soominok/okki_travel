from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, field_validator


class SourceCapability(BaseModel):
    role: Literal["scan", "verify"]
    date_range_native: bool
    max_span_days: int
    trip_length_filter: bool
    cost_per_call: int
    freshness: Literal["live", "cached"]
    max_cache_age_days: int | None


class FetchRequest(BaseModel):
    origin: str
    destination: str
    depart_from: date
    depart_to: date
    nights_min: int | None = None
    nights_max: int | None = None
    adults: int = 1
    cabin: Literal["economy", "premium", "business", "first"] = "economy"
    currency: str = "KRW"

    @field_validator("depart_to")
    @classmethod
    def _to_not_before_from(cls, v: date, info) -> date:
        if "depart_from" in info.data and v < info.data["depart_from"]:
            raise ValueError("depart_to must be >= depart_from")
        return v


class Offer(BaseModel):
    source: str
    external_id: str
    kind: Literal["flight", "stay", "place"]
    price_krw: int
    price_original: float
    currency_original: str
    depart_date: date | None = None
    return_date: date | None = None
    carrier: str | None = None
    deep_link: str | None = None
    raw: dict = {}
    collected_at: datetime
    freshness: Literal["live", "cached"]
    cache_age_days: int | None = None
    observed_at: datetime | None = None

    @field_validator("price_krw", mode="before")
    @classmethod
    def _price_must_be_int(cls, v: object) -> object:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"price_krw must be a plain int, got {type(v).__name__}")
        return v

    @field_validator("collected_at", "observed_at", mode="after")
    @classmethod
    def _must_be_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware (UTC)")
        return v


class SourceResult(BaseModel):
    ok: bool
    offers: list[Offer] = []
    error: str | None = None
    credits_used: int = 0


@runtime_checkable
class SourceAdapter(Protocol):
    name: str
    kind: Literal["flight", "stay", "place"]
    capability: SourceCapability

    async def health(self) -> bool: ...
    async def fetch(self, req: FetchRequest) -> SourceResult: ...
