"""Watch 요청/응답 DTO.

params 는 kind 에 따라 완전히 다른 필드를 가지므로 discriminated union 으로 정의한다.
이러면 잘못된 조합이 DB 까지 가지 않고 API 레벨에서 걸린다.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

# ---------- params ----------


class FlightParams(BaseModel):
    kind: Literal["flight"]
    origin: str = Field(min_length=3, max_length=3)  # IATA
    destination: str = Field(min_length=3, max_length=3)
    depart_from: date
    depart_to: date
    nights_min: int | None = Field(default=None, ge=0)
    nights_max: int | None = Field(default=None, ge=0)
    weekday_preference: list[str] = Field(default_factory=list)
    adults: int = Field(default=1, ge=1, le=9)
    cabin: Literal["economy", "premium", "business", "first"] = "economy"
    direct_only: bool = False

    @model_validator(mode="after")
    def _check_ranges(self) -> "FlightParams":
        if self.depart_to < self.depart_from:
            raise ValueError("depart_to must be on or after depart_from")
        if (
            self.nights_min is not None
            and self.nights_max is not None
            and self.nights_max < self.nights_min
        ):
            raise ValueError("nights_max must be >= nights_min")
        return self


class StayParams(BaseModel):
    kind: Literal["stay"]
    city_code: str
    checkin_from: date
    checkin_to: date
    nights: int = Field(ge=1)
    guests: int = Field(default=2, ge=1)
    min_stars: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def _check_ranges(self) -> "StayParams":
        if self.checkin_to < self.checkin_from:
            raise ValueError("checkin_to must be on or after checkin_from")
        return self


WatchParams = Annotated[FlightParams | StayParams, Field(discriminator="kind")]


# ---------- rules ----------


class ThresholdRule(BaseModel):
    id: str
    type: Literal["threshold"]
    price_krw: int = Field(gt=0)


class DropPctRule(BaseModel):
    id: str
    type: Literal["drop_pct"]
    pct: float = Field(gt=0, le=100)
    baseline: Literal["median_14d", "median_30d"] = "median_14d"


class AllTimeLowRule(BaseModel):
    id: str
    type: Literal["all_time_low"]
    min_samples: int = Field(default=10, ge=1)


class NewBestRule(BaseModel):
    id: str
    type: Literal["new_best"]
    improve_krw: int = Field(default=10000, gt=0)


Rule = Annotated[
    ThresholdRule | DropPctRule | AllTimeLowRule | NewBestRule,
    Field(discriminator="type"),
]


# ---------- watch ----------


class WatchCreate(BaseModel):
    kind: Literal["flight", "stay", "package"]
    title: str = Field(min_length=1, max_length=200)
    params: WatchParams
    rules: list[Rule] = Field(default_factory=list)
    interval_min: int = Field(default=360, ge=30, le=1440)

    @model_validator(mode="after")
    def _kind_matches_params(self) -> "WatchCreate":
        if self.params.kind != self.kind:
            raise ValueError(f"params.kind({self.params.kind}) != kind({self.kind})")
        return self


class WatchRead(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    params: WatchParams
    rules: list[Rule]
    interval_min: int
    status: str
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
