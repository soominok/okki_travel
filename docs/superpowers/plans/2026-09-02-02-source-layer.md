# 계획 2: 소스 계층(Source Layer) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Travelpayouts(SCAN), Bright Data(SAMPLE+VERIFY), Hotellook(호텔 SCAN) 세 어댑터와 예산 선점 로직을 구현한다. Plan 3(collector)이 이 레이어를 소비한다.

**Architecture:** `SourceAdapter` Protocol로 통합 계약 정의 → 어댑터는 `FetchRequest → SourceResult` 순수 변환만 담당(DB 접근 없음) → `cost_per_call > 0` 어댑터를 부르기 전 collector가 `budget.py`에서 크레딧을 선점한다. 예산 선점은 caller(collector)의 일이므로 어댑터는 budget을 모른다.

**Tech Stack:** Python 3.12, httpx (async), respx 0.21 (HTTP mock), pytest-asyncio, SQLAlchemy 2.0 async (budget 테스트에서만)

**Spec:** `docs/superpowers/specs/2026-09-01-source-layer-design.md` §1–6, `docs/03-DATA-SOURCES.md` §2–5

## Global Constraints

- Postgres 전용 — SQLite 없음 (CLAUDE.md §1)
- 가격은 KRW `int` — `float` 금지 (CLAUDE.md §5)
- 모든 timestamp는 UTC (CLAUDE.md §4)
- 어댑터는 예외를 던지지 않는다 → `SourceResult(ok=False, error=str(e))` (CLAUDE.md §7)
- 어댑터는 DB를 모른다 → `FetchRequest → SourceResult[Offer]` 변환만 (CLAUDE.md §8)
- `cost_per_call > 0` 어댑터: 호출 전 budget.py에서 크레딧 선점 — 부족하면 "건너뜀" (CLAUDE.md §11)
- 어댑터 내부 기간 fan-out 금지 (CLAUDE.md §12)
- 어댑터 테스트는 fixture + respx 목킹만 — 실제 API 호출 없음 (CLAUDE.md 작업방식)
- 크롤 우회 없음 (CLAUDE.md §9)
- 설정은 `app/config.py` 경유 (CLAUDE.md §3)
- 명령어는 `backend/` 디렉터리에서 실행

---

## 파일 맵

**신규:**
```
backend/app/sources/__init__.py
backend/app/sources/base.py                   SourceCapability, FetchRequest, Offer, SourceResult, SourceAdapter
backend/app/sources/http.py                   RateLimitedClient
backend/app/sources/budget.py                 ensure_budget_row, reserve_sample, reserve_verify
backend/app/sources/registry.py              SourceRegistry, build_registry
backend/app/sources/policy.py               CrawlPolicy (최소 구현)
backend/app/sources/flight/__init__.py
backend/app/sources/flight/travelpayouts.py  TravelpayoutsAdapter
backend/app/sources/flight/brightdata.py     BrightDataAdapter
backend/app/sources/stay/__init__.py
backend/app/sources/stay/hotellook.py        HotellookAdapter
backend/tests/fixtures/travelpayouts/grouped_prices.json
backend/tests/fixtures/travelpayouts/prices_for_dates.json
backend/tests/fixtures/brightdata/google_flights.json
backend/tests/fixtures/hotellook/cache.json
backend/tests/test_source_contracts.py
backend/tests/test_budget.py
backend/tests/test_adapter_travelpayouts.py
backend/tests/test_adapter_brightdata.py
backend/tests/test_adapter_hotellook.py
backend/tests/test_registry.py
```

**수정:**
```
backend/tests/conftest.py        db_session 픽스처 추가
backend/app/config.py            brightdata_monthly_credits: int = 5000 필드 추가 (없으면)
```

---

## Task 1: `sources/base.py` — 계약 정의 + 계약 테스트

`SourceCapability`, `FetchRequest`, `Offer`, `SourceResult`, `SourceAdapter` Protocol을 정의한다.
어댑터가 이 계약을 지키는지 검증하는 단위 테스트를 먼저 작성한다(DB 불필요).

**Files:**
- Create: `backend/app/sources/__init__.py`
- Create: `backend/app/sources/base.py`
- Create: `backend/tests/test_source_contracts.py`

**Interfaces:**
- Produces: `SourceCapability`, `FetchRequest`, `Offer`, `SourceResult`, `SourceAdapter` — 이후 모든 Task가 이 이름을 그대로 사용한다

---

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_source_contracts.py`:
```python
"""sources/base.py 계약 검증 — DB 불필요."""
from __future__ import annotations

import pytest
from datetime import date, datetime, timezone
from pydantic import ValidationError

from app.sources.base import FetchRequest, Offer, SourceResult


def _offer(**kw) -> dict:
    defaults = dict(
        source="test",
        external_id="ext-1",
        kind="flight",
        price_krw=220000,
        price_original=220000.0,
        currency_original="KRW",
        depart_date=date(2026, 10, 7),
        return_date=date(2026, 10, 9),
        carrier="7C",
        deep_link="https://example.com",
        raw={},
        collected_at=datetime.now(tz=timezone.utc),
        freshness="cached",
        cache_age_days=1,
        observed_at=None,
    )
    defaults.update(kw)
    return defaults


class TestFetchRequest:
    def test_valid_request(self):
        req = FetchRequest(
            origin="ICN",
            destination="FUK",
            depart_from=date(2026, 10, 1),
            depart_to=date(2026, 10, 31),
            nights_min=2,
            nights_max=3,
        )
        assert req.origin == "ICN"
        assert req.adults == 1
        assert req.currency == "KRW"

    def test_date_order_rejected(self):
        with pytest.raises(ValidationError, match="depart_to"):
            FetchRequest(
                origin="ICN",
                destination="FUK",
                depart_from=date(2026, 10, 10),
                depart_to=date(2026, 10, 9),
            )

    def test_equal_dates_allowed(self):
        req = FetchRequest(
            origin="ICN",
            destination="FUK",
            depart_from=date(2026, 10, 7),
            depart_to=date(2026, 10, 7),
        )
        assert req.depart_from == req.depart_to


class TestOffer:
    def test_price_must_be_int(self):
        with pytest.raises(ValidationError):
            Offer(**_offer(price_krw=220000.5))  # float 거부

    def test_valid_offer(self):
        o = Offer(**_offer())
        assert o.price_krw == 220000
        assert isinstance(o.price_krw, int)

    def test_live_offer_no_cache_age(self):
        o = Offer(**_offer(freshness="live", cache_age_days=None))
        assert o.freshness == "live"
        assert o.cache_age_days is None


class TestSourceResult:
    def test_ok_result(self):
        r = SourceResult(ok=True, offers=[Offer(**_offer())])
        assert r.ok
        assert len(r.offers) == 1
        assert r.error is None

    def test_error_result_has_no_offers(self):
        r = SourceResult(ok=False, error="timeout")
        assert not r.ok
        assert r.offers == []
        assert r.credits_used == 0
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
uv run pytest tests/test_source_contracts.py -v
```
기대: `ModuleNotFoundError: app.sources.base`

- [ ] **Step 3: `sources/__init__.py` 와 `sources/base.py` 구현**

`backend/app/sources/__init__.py`:
```python
```
(빈 파일)

`backend/app/sources/base.py`:
```python
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

    @field_validator("price_krw")
    @classmethod
    def _price_must_be_int(cls, v: int) -> int:
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("price_krw must be a plain int, not float or bool")
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
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
uv run pytest tests/test_source_contracts.py -v
```
기대: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/sources/__init__.py app/sources/base.py tests/test_source_contracts.py
git commit -m "feat: sources/base.py — SourceCapability, FetchRequest, Offer, SourceResult, SourceAdapter"
```

---

## Task 2: `sources/http.py` — Rate-limited httpx 래퍼

도메인별 최소 호출 간격을 강제하는 비동기 HTTP 클라이언트. 어댑터는 이 클라이언트만 쓴다.

**Files:**
- Create: `backend/app/sources/http.py`

**Interfaces:**
- Consumes: `httpx` (외부 패키지)
- Produces: `RateLimitedClient` — `Task 4/5/6`의 어댑터가 `__init__`에서 주입받는다

---

- [ ] **Step 1: `http.py` 작성**

`backend/app/sources/http.py`:
```python
from __future__ import annotations

import asyncio
import time

import httpx


class RateLimitedClient:
    """도메인별 최소 간격을 강제하는 httpx 래퍼.

    테스트에서는 respx.mock 컨텍스트 안에서 사용하면 httpx가 자동으로 목킹된다.
    """

    def __init__(self, min_interval_sec: float = 1.0, timeout: float = 30.0) -> None:
        self._min_interval = min_interval_sec
        self._timeout = timeout
        self._last_call: dict[str, float] = {}

    async def _wait(self, domain: str) -> None:
        last = self._last_call.get(domain, 0.0)
        gap = self._min_interval - (time.monotonic() - last)
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_call[domain] = time.monotonic()

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        domain = str(httpx.URL(url).host)
        await self._wait(domain)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(url, headers=headers or {}, params=params)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        domain = str(httpx.URL(url).host)
        await self._wait(domain)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(url, headers=headers or {}, json=json)
```

- [ ] **Step 2: http 래퍼 임포트 확인**

```bash
uv run python -c "from app.sources.http import RateLimitedClient; print('ok')"
```
기대: `ok`

- [ ] **Step 3: 커밋**

```bash
git add app/sources/http.py
git commit -m "feat: sources/http.py — RateLimitedClient (도메인별 rate limit)"
```

---

## Task 3: `sources/budget.py` + `conftest.py` 픽스처 추가

`call_budgets` 테이블에 대한 원자적 크레딧 선점 로직. SAMPLE은 일일 페이싱 포함.

**Files:**
- Create: `backend/app/sources/budget.py`
- Create: `backend/tests/test_budget.py`
- Modify: `backend/tests/conftest.py` (db_session 픽스처 추가)

**Interfaces:**
- Consumes: `CallBudget` ORM (app.models.source), SQLAlchemy `AsyncSession`
- Produces:
  - `ensure_budget_row(session, source, total, sample_cap_ratio) -> None`
  - `reserve_verify(session, source, n=1) -> bool`
  - `reserve_sample(session, source, n=1, days_left=None) -> bool`

---

- [ ] **Step 1: `conftest.py`에 `db_session` 픽스처 추가**

`backend/tests/conftest.py` 파일 끝에 추가:
```python
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session(migrated_engine):
    """함수 스코프 async 세션. 테스트 후 롤백한다."""
    async with AsyncSession(migrated_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_budget.py`:
```python
"""call_budgets 예산 선점 로직 테스트 — 실제 Postgres 사용."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.sources.budget import ensure_budget_row, reserve_sample, reserve_verify


@pytest.mark.asyncio
async def test_ensure_budget_row_creates_row(db_session: AsyncSession):
    await ensure_budget_row(db_session, source="brightdata_test_a", total=100)
    ok = await reserve_verify(db_session, source="brightdata_test_a")
    assert ok


@pytest.mark.asyncio
async def test_reserve_verify_decrements_budget(db_session: AsyncSession):
    await ensure_budget_row(db_session, source="brightdata_test_b", total=3)
    assert await reserve_verify(db_session, source="brightdata_test_b")
    assert await reserve_verify(db_session, source="brightdata_test_b")
    assert await reserve_verify(db_session, source="brightdata_test_b")
    # 4번째는 예산 초과 → False
    assert not await reserve_verify(db_session, source="brightdata_test_b")


@pytest.mark.asyncio
async def test_reserve_sample_respects_cap(db_session: AsyncSession):
    # total=10, sample_cap=7 (ratio 0.70)
    await ensure_budget_row(
        db_session, source="brightdata_test_c", total=10, sample_cap_ratio=0.70
    )
    # sample_cap = 7, 8번 시도 → 7번만 성공
    results = [
        await reserve_sample(db_session, source="brightdata_test_c", days_left=30)
        for _ in range(8)
    ]
    assert results.count(True) == 7
    assert results.count(False) == 1


@pytest.mark.asyncio
async def test_ensure_idempotent(db_session: AsyncSession):
    await ensure_budget_row(db_session, source="brightdata_test_d", total=5)
    await ensure_budget_row(db_session, source="brightdata_test_d", total=5)  # 중복 호출
    # 두 번 호출해도 total이 두 배가 되면 안 된다
    ok_count = 0
    for _ in range(6):
        if await reserve_verify(db_session, source="brightdata_test_d"):
            ok_count += 1
    assert ok_count == 5
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인**

```bash
uv run pytest tests/test_budget.py -v
```
기대: `ModuleNotFoundError: app.sources.budget`

- [ ] **Step 4: `budget.py` 구현**

`backend/app/sources/budget.py`:
```python
from __future__ import annotations

import math
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import CallBudget  # noqa: F401 — ORM import to ensure mapper is loaded


async def ensure_budget_row(
    session: AsyncSession,
    source: str,
    total: int,
    sample_cap_ratio: float = 0.70,
) -> None:
    """이번 달 call_budgets 행이 없으면 삽입한다. 이미 있으면 no-op."""
    sample_cap = math.floor(total * sample_cap_ratio)
    await session.execute(
        text(
            """
            INSERT INTO call_budgets (source, period_start, total, sample_cap)
            VALUES (:src, date_trunc('month', current_date)::date, :total, :cap)
            ON CONFLICT (source, period_start) DO NOTHING
            """
        ),
        {"src": source, "total": total, "cap": sample_cap},
    )
    await session.commit()


async def reserve_verify(
    session: AsyncSession,
    source: str,
    n: int = 1,
) -> bool:
    """VERIFY 크레딧 n개 선점. True = 성공, False = 예산 부족(건너뜀)."""
    result = await session.execute(
        text(
            """
            UPDATE call_budgets
            SET used_verify = used_verify + :n,
                updated_at  = now()
            WHERE source       = :src
              AND period_start = date_trunc('month', current_date)::date
              AND used_verify + used_sample + :n <= total
            RETURNING used_verify
            """
        ),
        {"src": source, "n": n},
    )
    updated = result.fetchone()
    if updated:
        await session.commit()
        return True
    return False


async def reserve_sample(
    session: AsyncSession,
    source: str,
    n: int = 1,
    days_left: int | None = None,
) -> bool:
    """SAMPLE 크레딧 n개 선점. 자기보정 일일 페이싱 포함.

    True = 성공, False = 예산 부족 또는 오늘 할당량 초과(건너뜀).
    days_left: 남은 일수 (기본값: 오늘 포함 이번 달 잔여일).
    """
    if days_left is None:
        import calendar

        today = date.today()
        days_left = calendar.monthrange(today.year, today.month)[1] - today.day + 1

    result = await session.execute(
        text(
            """
            UPDATE call_budgets
            SET used_sample     = used_sample + :n,
                used_sample_day = CASE
                                      WHEN sample_day = current_date
                                      THEN used_sample_day + :n
                                      ELSE :n
                                  END,
                sample_day      = current_date,
                updated_at      = now()
            WHERE source       = :src
              AND period_start = date_trunc('month', current_date)::date
              AND used_verify + used_sample + :n <= total
              AND used_sample + :n              <= sample_cap
              AND (CASE WHEN sample_day = current_date
                        THEN used_sample_day ELSE 0 END) + :n
                  <= CEIL(
                       (sample_cap - used_sample)::float
                       / GREATEST(:days_left::float, 1)
                     )
            RETURNING used_sample
            """
        ),
        {"src": source, "n": n, "days_left": days_left},
    )
    updated = result.fetchone()
    if updated:
        await session.commit()
        return True
    return False
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
uv run pytest tests/test_budget.py -v
```
기대: 4개 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add app/sources/budget.py tests/test_budget.py tests/conftest.py
git commit -m "feat: sources/budget.py — VERIFY/SAMPLE 원자적 크레딧 선점 + db_session 픽스처"
```

---

## Task 4: Travelpayouts 어댑터 + 픽스처 + 테스트

SCAN 어댑터. `grouped_prices`(1차) + `prices_for_dates`(2차) 두 엔드포인트를 1회 fetch에서 호출해 결과를 병합한다. cost_per_call=0이므로 budget 선점 불필요.

**Files:**
- Create: `backend/app/sources/flight/__init__.py`
- Create: `backend/app/sources/flight/travelpayouts.py`
- Create: `backend/tests/fixtures/travelpayouts/grouped_prices.json`
- Create: `backend/tests/fixtures/travelpayouts/prices_for_dates.json`
- Create: `backend/tests/test_adapter_travelpayouts.py`

**Interfaces:**
- Consumes: `SourceCapability`, `FetchRequest`, `Offer`, `SourceResult`, `SourceAdapter` (Task 1), `RateLimitedClient` (Task 2)
- Produces: `TravelpayoutsAdapter` — `Task 7` 레지스트리에서 등록

---

- [ ] **Step 1: 픽스처 작성**

`backend/tests/fixtures/travelpayouts/grouped_prices.json`:
```json
{
  "data": {
    "2026-10-04": {
      "flight_number": "271",
      "link": "/search/ICN0410FUK09101?marker=test",
      "departure_at": "2026-10-04T07:05:00",
      "return_at": "2026-10-06T18:30:00",
      "airline": "LJ",
      "price": 220000,
      "transfers": 0,
      "duration": 80,
      "duration_to": 80,
      "duration_back": 75,
      "origin": "ICN",
      "destination": "FUK",
      "origin_airport": "ICN",
      "destination_airport": "FUK"
    },
    "2026-10-07": {
      "flight_number": "201",
      "link": "/search/ICN0710FUK09101?marker=test",
      "departure_at": "2026-10-07T09:30:00",
      "return_at": "2026-10-09T18:00:00",
      "airline": "7C",
      "price": 185000,
      "transfers": 0,
      "duration": 90,
      "duration_to": 90,
      "duration_back": 85,
      "origin": "ICN",
      "destination": "FUK",
      "origin_airport": "ICN",
      "destination_airport": "FUK"
    },
    "2026-10-14": {
      "flight_number": "301",
      "link": "/search/ICN1410FUK09101?marker=test",
      "departure_at": "2026-10-14T11:00:00",
      "return_at": "2026-10-17T19:00:00",
      "airline": "TW",
      "price": 198000,
      "transfers": 0,
      "duration": 85,
      "duration_to": 85,
      "duration_back": 80,
      "origin": "ICN",
      "destination": "FUK",
      "origin_airport": "ICN",
      "destination_airport": "FUK"
    },
    "2026-10-21": {
      "flight_number": "401",
      "link": "/search/ICN2110FUK09101?marker=test",
      "departure_at": "2026-10-21T06:00:00",
      "return_at": "2026-10-22T20:00:00",
      "airline": "LJ",
      "price": 210000,
      "transfers": 0,
      "duration": 80,
      "duration_to": 80,
      "duration_back": 75,
      "origin": "ICN",
      "destination": "FUK",
      "origin_airport": "ICN",
      "destination_airport": "FUK"
    }
  },
  "currency": "KRW"
}
```

설명:
- Oct 4: 2박 → `nights_min=2, nights_max=3` 범위 **포함**
- Oct 7: 2박 → **포함**
- Oct 14: 3박 → **포함**
- Oct 21: 1박 → **제외** (nights < 2)

`backend/tests/fixtures/travelpayouts/prices_for_dates.json`:
```json
{
  "data": [
    {
      "airline": "ZE",
      "departure_at": "2026-10-10T08:00:00",
      "return_at": "2026-10-12T19:30:00",
      "price": 232000,
      "destination": "FUK",
      "origin": "ICN",
      "transfers": 0,
      "gate": "Jetradar",
      "link": "/search/ICN1010FUK09101?marker=test",
      "flight_number": "ZE201",
      "duration": 90,
      "duration_to": 90,
      "duration_back": 85,
      "return_transfers": 0
    },
    {
      "airline": "ZE",
      "departure_at": "2026-10-10T08:00:00",
      "return_at": "2026-10-11T19:30:00",
      "price": 215000,
      "destination": "FUK",
      "origin": "ICN",
      "transfers": 0,
      "gate": "Jetradar",
      "link": "/search/ICN1010FUK0911?marker=test",
      "flight_number": "ZE201-1n",
      "duration": 90,
      "duration_to": 90,
      "duration_back": 85,
      "return_transfers": 0
    }
  ],
  "currency": "KRW"
}
```

설명:
- Oct 10→12: 2박 → **포함**
- Oct 10→11: 1박 → **제외**

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_adapter_travelpayouts.py`:
```python
"""TravelpayoutsAdapter 테스트 — respx로 HTTP 목킹."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.base import FetchRequest
from app.sources.flight.travelpayouts import TravelpayoutsAdapter
from app.sources.http import RateLimitedClient

FIXTURES = Path(__file__).parent / "fixtures" / "travelpayouts"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> TravelpayoutsAdapter:
    return TravelpayoutsAdapter(token="test-token", client=RateLimitedClient(min_interval_sec=0))


def _req(**kw) -> FetchRequest:
    defaults = dict(
        origin="ICN",
        destination="FUK",
        depart_from=date(2026, 10, 1),
        depart_to=date(2026, 10, 31),
        nights_min=2,
        nights_max=3,
    )
    defaults.update(kw)
    return FetchRequest(**defaults)


@pytest.mark.asyncio
async def test_fetch_returns_ok_and_offers():
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=_load("prices_for_dates.json"))
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_prices_are_krw_int():
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=_load("prices_for_dates.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(isinstance(o.price_krw, int) for o in result.offers)
    assert all(o.price_krw > 0 for o in result.offers)


@pytest.mark.asyncio
async def test_nights_filter_applied():
    """nights_min=2, nights_max=3 → 1박 항목은 제외된다."""
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=_load("prices_for_dates.json"))
        )
        result = await _adapter().fetch(_req(nights_min=2, nights_max=3))

    # Oct21(1박)과 ZE Oct10→11(1박)은 제외 → grouped 3 + prices 1 = 4
    assert len(result.offers) == 4
    for o in result.offers:
        if o.depart_date and o.return_date:
            nights = (o.return_date - o.depart_date).days
            assert 2 <= nights <= 3


@pytest.mark.asyncio
async def test_http_error_returns_ok_false():
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(401)
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(401)
        )
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
    assert result.offers == []


@pytest.mark.asyncio
async def test_dedup_same_external_id():
    """grouped와 prices_for_dates가 같은 항공편을 반환해도 중복 제거된다."""
    # grouped에는 Oct7 항목이 있다; prices에도 같은 external_id가 나오면 1개만.
    dup_prices = {
        "data": [
            {
                "airline": "7C",
                "departure_at": "2026-10-07T09:30:00",
                "return_at": "2026-10-09T18:00:00",
                "price": 185000,
                "destination": "FUK",
                "origin": "ICN",
                "transfers": 0,
                "gate": "Jetradar",
                "link": "/dup",
                "flight_number": "201",
                "duration": 90,
                "duration_to": 90,
                "duration_back": 85,
                "return_transfers": 0,
            }
        ],
        "currency": "KRW",
    }
    with respx.mock:
        respx.get("https://api.travelpayouts.com/aviasales/v3/grouped_prices").mock(
            return_value=httpx.Response(200, json=_load("grouped_prices.json"))
        )
        respx.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates").mock(
            return_value=httpx.Response(200, json=dup_prices)
        )
        result = await _adapter().fetch(_req())

    ext_ids = [o.external_id for o in result.offers]
    assert len(ext_ids) == len(set(ext_ids)), "external_id 중복이 있다"
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인**

```bash
uv run pytest tests/test_adapter_travelpayouts.py -v
```
기대: `ModuleNotFoundError: app.sources.flight.travelpayouts`

- [ ] **Step 4: 어댑터 구현**

`backend/app/sources/flight/__init__.py`: (빈 파일)

`backend/app/sources/flight/travelpayouts.py`:
```python
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.sources.base import FetchRequest, Offer, SourceCapability, SourceResult

if TYPE_CHECKING:
    from app.sources.http import RateLimitedClient

_BASE = "https://api.travelpayouts.com"
_GROUPED = f"{_BASE}/aviasales/v3/grouped_prices"
_PRICES = f"{_BASE}/aviasales/v3/prices_for_dates"


def _parse_dt(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _nights(dep: date | None, ret: date | None) -> int | None:
    if dep and ret:
        return (ret - dep).days
    return None


def _in_range(dep: date | None, ret: date | None, req: FetchRequest) -> bool:
    if dep is None:
        return False
    if not (req.depart_from <= dep <= req.depart_to):
        return False
    if req.nights_min is not None or req.nights_max is not None:
        n = _nights(dep, ret)
        if n is None:
            return False
        if req.nights_min is not None and n < req.nights_min:
            return False
        if req.nights_max is not None and n > req.nights_max:
            return False
    return True


def _grouped_to_offer(key: str, item: dict) -> Offer | None:
    dep = _parse_dt(item.get("departure_at") or key)
    ret = _parse_dt(item.get("return_at"))
    price = item.get("price")
    if price is None:
        return None
    airline = item.get("airline", "")
    fn = item.get("flight_number", "")
    ext_id = f"tp_g_{item.get('origin','')}{item.get('destination','')}_{key}_{airline}{fn}"
    return Offer(
        source="travelpayouts",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original="KRW",
        depart_date=dep,
        return_date=ret,
        carrier=airline or None,
        deep_link=item.get("link"),
        raw=item,
        collected_at=datetime.now(tz=timezone.utc),
        freshness="cached",
        cache_age_days=None,
        observed_at=None,
    )


def _prices_to_offer(item: dict) -> Offer | None:
    dep = _parse_dt(item.get("departure_at"))
    ret = _parse_dt(item.get("return_at"))
    price = item.get("price")
    if price is None or dep is None:
        return None
    airline = item.get("airline", "")
    fn = item.get("flight_number", "")
    dep_s = dep.isoformat() if dep else ""
    ret_s = ret.isoformat() if ret else ""
    ext_id = f"tp_p_{item.get('origin','')}{item.get('destination','')}_{dep_s}_{ret_s}_{airline}{fn}"
    return Offer(
        source="travelpayouts",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original="KRW",
        depart_date=dep,
        return_date=ret,
        carrier=airline or None,
        deep_link=item.get("link"),
        raw=item,
        collected_at=datetime.now(tz=timezone.utc),
        freshness="cached",
        cache_age_days=None,
        observed_at=None,
    )


class TravelpayoutsAdapter:
    name = "travelpayouts"
    kind = "flight"
    capability = SourceCapability(
        role="scan",
        date_range_native=True,
        max_span_days=31,
        trip_length_filter=False,  # A2 확인: 클라이언트 필터링 필요
        cost_per_call=0,
        freshness="cached",
        max_cache_age_days=7,
    )

    def __init__(self, token: str, client: RateLimitedClient) -> None:
        self._token = token
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {
            "X-Access-Token": self._token,
            "Accept": "application/json",
            "User-Agent": "TripPick/0.1",
        }

    async def health(self) -> bool:
        try:
            resp = await self._client.get(
                _GROUPED,
                headers=self._headers(),
                params={"origin": "ICN", "destination": "FUK",
                        "departure_at": "2026-10", "currency": "krw",
                        "group_by": "departure_at"},
            )
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def fetch(self, req: FetchRequest) -> SourceResult:
        try:
            month = req.depart_from.strftime("%Y-%m")
            ret_month = req.depart_to.strftime("%Y-%m")

            grouped_resp = await self._client.get(
                _GROUPED,
                headers=self._headers(),
                params={
                    "origin": req.origin,
                    "destination": req.destination,
                    "departure_at": month,
                    "return_at": ret_month,
                    "currency": "krw",
                    "direct": "false",
                    "group_by": "departure_at",
                },
            )
            grouped_resp.raise_for_status()

            prices_resp = await self._client.get(
                _PRICES,
                headers=self._headers(),
                params={
                    "origin": req.origin,
                    "destination": req.destination,
                    "departure_at": month,
                    "return_at": ret_month,
                    "currency": "krw",
                    "sorting": "price",
                    "direct": "false",
                    "one_way": "false",
                    "limit": 1000,
                    "page": 1,
                },
            )
            prices_resp.raise_for_status()

            grouped_data: dict = grouped_resp.json().get("data") or {}
            prices_data: list = prices_resp.json().get("data") or []

            offers_by_id: dict[str, Offer] = {}

            for key, item in grouped_data.items():
                if not isinstance(item, dict):
                    continue
                dep = _parse_dt(item.get("departure_at") or key)
                ret = _parse_dt(item.get("return_at"))
                if not _in_range(dep, ret, req):
                    continue
                o = _grouped_to_offer(key, item)
                if o:
                    offers_by_id[o.external_id] = o

            for item in prices_data:
                if not isinstance(item, dict):
                    continue
                dep = _parse_dt(item.get("departure_at"))
                ret = _parse_dt(item.get("return_at"))
                if not _in_range(dep, ret, req):
                    continue
                o = _prices_to_offer(item)
                if o and o.external_id not in offers_by_id:
                    offers_by_id[o.external_id] = o

            return SourceResult(ok=True, offers=list(offers_by_id.values()))

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
uv run pytest tests/test_adapter_travelpayouts.py -v
```
기대: 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add app/sources/flight/__init__.py app/sources/flight/travelpayouts.py \
        tests/fixtures/travelpayouts/ tests/test_adapter_travelpayouts.py
git commit -m "feat: TravelpayoutsAdapter — grouped_prices + prices_for_dates SCAN"
```

---

## Task 5: Bright Data 어댑터 + 픽스처 + 테스트

VERIFY / SAMPLE 어댑터. Google Flights SERP를 Bright Data로 조회한다. `cost_per_call=1` → collector가 호출 전 `reserve_verify()` 또는 `reserve_sample()`을 반드시 실행해야 한다(어댑터는 이를 강제하지 않는다).

> ⚠️ **Bright Data API URL 확인 필요**: 아래 구현은 Bright Data SERP API v1 포맷을 사용한다.
> 대시보드 → API reference → Google Flights 섹션에서 정확한 엔드포인트와 파라미터를 검증할 것.
> 픽스처 테스트는 URL과 무관하게 통과하므로, 어댑터 파라미터만 조정하면 된다.

**Files:**
- Create: `backend/app/sources/flight/brightdata.py`
- Create: `backend/tests/fixtures/brightdata/google_flights.json`
- Create: `backend/tests/test_adapter_brightdata.py`

**Interfaces:**
- Consumes: `SourceCapability`, `FetchRequest`, `Offer`, `SourceResult` (Task 1), `RateLimitedClient` (Task 2)
- Produces: `BrightDataAdapter`

---

- [ ] **Step 1: 픽스처 작성**

`backend/tests/fixtures/brightdata/google_flights.json`:
```json
{
  "best_flights": [
    {
      "flights": [
        {
          "departure_airport": {"id": "ICN", "name": "Incheon International"},
          "arrival_airport": {"id": "FUK", "name": "Fukuoka"},
          "departure_time": "2026-10-07 09:30",
          "arrival_time": "2026-10-07 11:00",
          "airline": "Jeju Air",
          "airline_logo": "https://example.com/logo.png",
          "travel_class": "Economy",
          "flight_number": "7C 1201",
          "legroom": "30 in",
          "extensions": ["Below average legroom"]
        }
      ],
      "return_flights": [
        {
          "departure_airport": {"id": "FUK", "name": "Fukuoka"},
          "arrival_airport": {"id": "ICN", "name": "Incheon International"},
          "departure_time": "2026-10-09 18:00",
          "arrival_time": "2026-10-09 19:30",
          "airline": "Jeju Air",
          "airline_logo": "https://example.com/logo.png",
          "travel_class": "Economy",
          "flight_number": "7C 1202",
          "legroom": "30 in"
        }
      ],
      "price": 215000,
      "type": "Round trip",
      "airline_logo": "https://example.com/logo.png",
      "booking_token": "abc123",
      "total_duration": 90,
      "carbon_emissions": {"this_flight": 120000}
    }
  ],
  "other_flights": [],
  "price_insights": {
    "lowest_price": 215000,
    "price_level": "typical",
    "typical_price_range": [180000, 280000]
  }
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_adapter_brightdata.py`:
```python
"""BrightDataAdapter 테스트 — respx로 HTTP 목킹."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.base import FetchRequest
from app.sources.flight.brightdata import BrightDataAdapter, BD_SERP_URL
from app.sources.http import RateLimitedClient

FIXTURES = Path(__file__).parent / "fixtures" / "brightdata"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> BrightDataAdapter:
    return BrightDataAdapter(api_key="test-key", client=RateLimitedClient(min_interval_sec=0))


def _req(**kw) -> FetchRequest:
    defaults = dict(
        origin="ICN",
        destination="FUK",
        depart_from=date(2026, 10, 7),
        depart_to=date(2026, 10, 7),
        nights_min=2,
        nights_max=2,
    )
    defaults.update(kw)
    return FetchRequest(**defaults)


@pytest.mark.asyncio
async def test_fetch_returns_ok_and_offers():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(
            return_value=httpx.Response(200, json=_load("google_flights.json"))
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) > 0
    assert result.credits_used == 1


@pytest.mark.asyncio
async def test_price_is_int():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(
            return_value=httpx.Response(200, json=_load("google_flights.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(isinstance(o.price_krw, int) for o in result.offers)
    assert all(o.price_krw > 0 for o in result.offers)


@pytest.mark.asyncio
async def test_freshness_is_live():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(
            return_value=httpx.Response(200, json=_load("google_flights.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(o.freshness == "live" for o in result.offers)
    assert all(o.cache_age_days is None for o in result.offers)


@pytest.mark.asyncio
async def test_http_401_returns_ok_false():
    with respx.mock:
        respx.post(BD_SERP_URL).mock(return_value=httpx.Response(401))
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
    assert result.offers == []
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인**

```bash
uv run pytest tests/test_adapter_brightdata.py -v
```

- [ ] **Step 4: 어댑터 구현**

`backend/app/sources/flight/brightdata.py`:
```python
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.sources.base import FetchRequest, Offer, SourceCapability, SourceResult

if TYPE_CHECKING:
    from app.sources.http import RateLimitedClient

# ⚠️ 대시보드 → API reference → Google Flights 에서 정확한 URL 확인 필요
# https://brightdata.com/cp/serp_api → Docs → Google Flights
BD_SERP_URL = "https://api.brightdata.com/serp"


def _parse_dt_str(v: str | None) -> date | None:
    """'YYYY-MM-DD HH:MM' 형태 파싱."""
    if not v:
        return None
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _flight_to_offer(flight_group: dict, api_key_prefix: str) -> Offer | None:
    price = flight_group.get("price")
    if price is None:
        return None

    flights = flight_group.get("flights", [])
    returns = flight_group.get("return_flights", [])

    dep_date = _parse_dt_str(flights[0].get("departure_time") if flights else None)
    ret_date = _parse_dt_str(returns[0].get("departure_time") if returns else None)

    airline = (flights[0].get("airline") or "") if flights else ""
    flight_no = (flights[0].get("flight_number") or "") if flights else ""

    dep_s = dep_date.isoformat() if dep_date else "?"
    ret_s = ret_date.isoformat() if ret_date else "?"
    ext_id = f"bd_{dep_s}_{ret_s}_{airline.replace(' ', '')}_{flight_no.replace(' ', '')}"

    return Offer(
        source="brightdata",
        external_id=ext_id,
        kind="flight",
        price_krw=int(price),
        price_original=float(price),
        currency_original="KRW",
        depart_date=dep_date,
        return_date=ret_date,
        carrier=airline or None,
        deep_link=None,
        raw=flight_group,
        collected_at=datetime.now(tz=timezone.utc),
        freshness="live",
        cache_age_days=None,
        observed_at=datetime.now(tz=timezone.utc),
    )


class BrightDataAdapter:
    name = "brightdata"
    kind = "flight"
    capability = SourceCapability(
        role="verify",
        date_range_native=False,
        max_span_days=1,
        trip_length_filter=False,
        cost_per_call=1,
        freshness="live",
        max_cache_age_days=None,
    )

    def __init__(self, api_key: str, client: RateLimitedClient) -> None:
        self._api_key = api_key
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> bool:
        return bool(self._api_key)

    async def fetch(self, req: FetchRequest) -> SourceResult:
        return_date: date | None = None
        if req.nights_min is not None and req.depart_from:
            from datetime import timedelta
            return_date = req.depart_from + timedelta(days=req.nights_min)

        payload: dict = {
            "engine": "google_flights",
            "hl": "en",
            "gl": "kr",
            "departure_id": req.origin,
            "arrival_id": req.destination,
            "outbound_date": req.depart_from.isoformat(),
            "currency": req.currency,
        }
        if return_date:
            payload["return_date"] = return_date.isoformat()
            payload["type"] = "1"  # round trip
        else:
            payload["type"] = "2"  # one way

        try:
            resp = await self._client.post(
                BD_SERP_URL,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()

            body = resp.json()
            best = body.get("best_flights") or []
            other = body.get("other_flights") or []
            all_groups = best + other

            offers: list[Offer] = []
            seen: set[str] = set()
            for group in all_groups:
                o = _flight_to_offer(group, self._api_key[:4])
                if o and o.external_id not in seen:
                    offers.append(o)
                    seen.add(o.external_id)

            return SourceResult(ok=True, offers=offers, credits_used=1)

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
uv run pytest tests/test_adapter_brightdata.py -v
```

- [ ] **Step 6: 커밋**

```bash
git add app/sources/flight/brightdata.py \
        tests/fixtures/brightdata/ tests/test_adapter_brightdata.py
git commit -m "feat: BrightDataAdapter — Google Flights SERP VERIFY/SAMPLE"
```

---

## Task 6: Hotellook 어댑터 + 픽스처 + 테스트

호텔 SCAN 어댑터. Travelpayouts 토큰 사용. `cost_per_call=0`.

**Files:**
- Create: `backend/app/sources/stay/__init__.py`
- Create: `backend/app/sources/stay/hotellook.py`
- Create: `backend/tests/fixtures/hotellook/cache.json`
- Create: `backend/tests/test_adapter_hotellook.py`

**Interfaces:**
- Consumes: `SourceCapability`, `FetchRequest`, `Offer`, `SourceResult` (Task 1), `RateLimitedClient` (Task 2)
- Produces: `HotellookAdapter`

---

- [ ] **Step 1: 픽스처 작성**

`backend/tests/fixtures/hotellook/cache.json`:
```json
[
  {
    "hotelId": 788613,
    "priceFrom": 75000,
    "priceAvg": 82000,
    "stars": 4,
    "locationName": "Fukuoka",
    "location": {"name": "Fukuoka", "geo": "FUK"},
    "hotelName": "Hakata Excel Hotel Tokyu",
    "deeplink": "https://tp.media/r?marker=test&id=1",
    "photoUrl": "https://photos.hotellook.com/image_v2/..."
  },
  {
    "hotelId": 123456,
    "priceFrom": 55000,
    "priceAvg": 60000,
    "stars": 3,
    "locationName": "Fukuoka",
    "location": {"name": "Fukuoka", "geo": "FUK"},
    "hotelName": "Toyoko Inn Fukuoka Tenjin",
    "deeplink": "https://tp.media/r?marker=test&id=2",
    "photoUrl": "https://photos.hotellook.com/image_v2/..."
  }
]
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_adapter_hotellook.py`:
```python
"""HotellookAdapter 테스트 — respx로 HTTP 목킹."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.base import FetchRequest
from app.sources.stay.hotellook import HotellookAdapter, HL_CACHE_URL
from app.sources.http import RateLimitedClient

FIXTURES = Path(__file__).parent / "fixtures" / "hotellook"


def _load(name: str) -> list:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> HotellookAdapter:
    return HotellookAdapter(token="test-token", client=RateLimitedClient(min_interval_sec=0))


def _req(**kw) -> FetchRequest:
    defaults = dict(
        origin="ICN",
        destination="FUK",
        depart_from=date(2026, 10, 7),
        depart_to=date(2026, 10, 9),
        nights_min=2,
        nights_max=2,
    )
    defaults.update(kw)
    return FetchRequest(**defaults)


@pytest.mark.asyncio
async def test_fetch_returns_ok_and_offers():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(
            return_value=httpx.Response(200, json=_load("cache.json"))
        )
        result = await _adapter().fetch(_req())

    assert result.ok is True
    assert len(result.offers) == 2


@pytest.mark.asyncio
async def test_prices_are_krw_int():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(
            return_value=httpx.Response(200, json=_load("cache.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(isinstance(o.price_krw, int) for o in result.offers)
    assert all(o.price_krw > 0 for o in result.offers)


@pytest.mark.asyncio
async def test_offer_kind_is_stay():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(
            return_value=httpx.Response(200, json=_load("cache.json"))
        )
        result = await _adapter().fetch(_req())

    assert all(o.kind == "stay" for o in result.offers)


@pytest.mark.asyncio
async def test_http_error_returns_ok_false():
    with respx.mock:
        respx.get(HL_CACHE_URL).mock(return_value=httpx.Response(403))
        result = await _adapter().fetch(_req())

    assert result.ok is False
    assert result.error is not None
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인**

```bash
uv run pytest tests/test_adapter_hotellook.py -v
```

- [ ] **Step 4: 어댑터 구현**

`backend/app/sources/stay/__init__.py`: (빈 파일)

`backend/app/sources/stay/hotellook.py`:
```python
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.sources.base import FetchRequest, Offer, SourceCapability, SourceResult

if TYPE_CHECKING:
    from app.sources.http import RateLimitedClient

HL_CACHE_URL = "https://engine.hotellook.com/api/v2/cache.json"


class HotellookAdapter:
    name = "hotellook"
    kind = "stay"
    capability = SourceCapability(
        role="scan",
        date_range_native=False,
        max_span_days=1,
        trip_length_filter=False,
        cost_per_call=0,
        freshness="cached",
        max_cache_age_days=7,
    )

    def __init__(self, token: str, client: RateLimitedClient) -> None:
        self._token = token
        self._client = client

    async def health(self) -> bool:
        return bool(self._token)

    async def fetch(self, req: FetchRequest) -> SourceResult:
        check_in = req.depart_from
        nights = req.nights_min if req.nights_min is not None else (req.depart_to - req.depart_from).days
        check_out = check_in + timedelta(days=max(nights, 1))

        try:
            resp = await self._client.get(
                HL_CACHE_URL,
                headers={"User-Agent": "TripPick/0.1"},
                params={
                    "location": req.destination,
                    "checkIn": check_in.isoformat(),
                    "checkOut": check_out.isoformat(),
                    "currency": req.currency.lower(),
                    "token": self._token,
                    "limit": 100,
                    "adults": req.adults,
                },
            )
            resp.raise_for_status()

            data = resp.json()
            if not isinstance(data, list):
                return SourceResult(ok=False, error=f"unexpected response shape: {type(data)}")

            offers: list[Offer] = []
            for hotel in data:
                price = hotel.get("priceFrom")
                hotel_id = hotel.get("hotelId")
                if price is None or hotel_id is None:
                    continue
                ext_id = f"hl_{hotel_id}_{check_in.isoformat()}_{check_out.isoformat()}"
                offers.append(
                    Offer(
                        source="hotellook",
                        external_id=ext_id,
                        kind="stay",
                        price_krw=int(price),
                        price_original=float(price),
                        currency_original=req.currency,
                        depart_date=check_in,
                        return_date=check_out,
                        carrier=None,
                        deep_link=hotel.get("deeplink"),
                        raw=hotel,
                        collected_at=datetime.now(tz=timezone.utc),
                        freshness="cached",
                        cache_age_days=None,
                        observed_at=None,
                    )
                )

            return SourceResult(ok=True, offers=offers)

        except Exception as e:  # noqa: BLE001
            return SourceResult(ok=False, error=str(e))
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
uv run pytest tests/test_adapter_hotellook.py -v
```

- [ ] **Step 6: 커밋**

```bash
git add app/sources/stay/__init__.py app/sources/stay/hotellook.py \
        tests/fixtures/hotellook/ tests/test_adapter_hotellook.py
git commit -m "feat: HotellookAdapter — 호텔 캐시 SCAN"
```

---

## Task 7: `registry.py` + `policy.py` + 레지스트리 테스트

어댑터 등록/조회 레지스트리와 크롤 정책 게이트(Plan 2 범위: 최소 구현).

**Files:**
- Create: `backend/app/sources/registry.py`
- Create: `backend/app/sources/policy.py`
- Create: `backend/tests/test_registry.py`

**Interfaces:**
- Consumes: `TravelpayoutsAdapter` (Task 4), `BrightDataAdapter` (Task 5), `HotellookAdapter` (Task 6)
- Produces:
  - `SourceRegistry` — Plan 3 collector가 `get(kind, role)` 로 어댑터를 조회
  - `build_registry(settings) -> SourceRegistry` — API 키가 있는 어댑터만 등록
  - `CrawlPolicy` — Plan 4+ 크롤 어댑터가 `require_enabled()` 호출

---

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_registry.py`:
```python
"""SourceRegistry, build_registry, CrawlPolicy 테스트."""
from __future__ import annotations

import pytest

from app.sources.base import SourceAdapter
from app.sources.flight.travelpayouts import TravelpayoutsAdapter
from app.sources.http import RateLimitedClient
from app.sources.registry import SourceRegistry, build_registry
from app.sources.policy import CrawlPolicy


def _tp() -> TravelpayoutsAdapter:
    return TravelpayoutsAdapter(token="tok", client=RateLimitedClient(min_interval_sec=0))


class TestSourceRegistry:
    def test_register_and_get_by_role(self):
        reg = SourceRegistry()
        reg.register(_tp())
        adapters = reg.get(kind="flight", role="scan")
        assert len(adapters) == 1
        assert adapters[0].name == "travelpayouts"

    def test_get_wrong_role_returns_empty(self):
        reg = SourceRegistry()
        reg.register(_tp())
        assert reg.get(kind="flight", role="verify") == []

    def test_get_by_name(self):
        reg = SourceRegistry()
        reg.register(_tp())
        a = reg.get_by_name("travelpayouts")
        assert a is not None
        assert isinstance(a, SourceAdapter)

    def test_get_by_name_missing_returns_none(self):
        reg = SourceRegistry()
        assert reg.get_by_name("nonexistent") is None

    def test_adapter_protocol_satisfied(self):
        a = _tp()
        assert isinstance(a, SourceAdapter)


class TestBuildRegistry:
    def test_no_keys_empty_registry(self, monkeypatch):
        monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "")
        from app.config import Settings
        settings = Settings(
            app_api_token="x" * 32,
            database_url="postgresql+asyncpg://trip:trip@localhost:5434/trippick_test",
            travelpayouts_token=None,
            brightdata_api_key=None,
        )
        reg = build_registry(settings)
        assert reg.get(kind="flight", role="scan") == []
        assert reg.get(kind="flight", role="verify") == []

    def test_tp_token_registers_tp_and_hl(self, monkeypatch):
        from pydantic import SecretStr
        from app.config import Settings
        settings = Settings(
            app_api_token="x" * 32,
            database_url="postgresql+asyncpg://trip:trip@localhost:5434/trippick_test",
            travelpayouts_token=SecretStr("tp-test"),
            brightdata_api_key=None,
        )
        reg = build_registry(settings)
        flight_scan = reg.get(kind="flight", role="scan")
        stay_scan = reg.get(kind="stay", role="scan")
        assert any(a.name == "travelpayouts" for a in flight_scan)
        assert any(a.name == "hotellook" for a in stay_scan)


class TestCrawlPolicy:
    def test_require_enabled_raises_when_disabled(self, monkeypatch):
        monkeypatch.setenv("CRAWL_ENABLED", "false")
        with pytest.raises(RuntimeError, match="CRAWL_ENABLED"):
            CrawlPolicy.require_enabled()

    def test_check_allowed_returns_false(self):
        assert CrawlPolicy.check_allowed("example.com") is False
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
uv run pytest tests/test_registry.py -v
```

- [ ] **Step 3: `registry.py` 구현**

`backend/app/sources/registry.py`:
```python
from __future__ import annotations

from app.sources.base import SourceAdapter


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: list[SourceAdapter] = []

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters.append(adapter)

    def get(self, kind: str, role: str) -> list[SourceAdapter]:
        return [
            a for a in self._adapters
            if a.kind == kind and a.capability.role == role
        ]

    def get_by_name(self, name: str) -> SourceAdapter | None:
        return next((a for a in self._adapters if a.name == name), None)

    def all(self) -> list[SourceAdapter]:
        return list(self._adapters)


def build_registry(settings) -> SourceRegistry:
    """API 키가 있는 어댑터만 등록한다."""
    from app.sources.flight.brightdata import BrightDataAdapter
    from app.sources.flight.travelpayouts import TravelpayoutsAdapter
    from app.sources.http import RateLimitedClient
    from app.sources.stay.hotellook import HotellookAdapter

    registry = SourceRegistry()
    client = RateLimitedClient(min_interval_sec=1.0)

    if settings.travelpayouts_token:
        tp_token = settings.travelpayouts_token.get_secret_value()
        registry.register(TravelpayoutsAdapter(token=tp_token, client=client))
        registry.register(HotellookAdapter(token=tp_token, client=client))

    if settings.brightdata_api_key:
        bd_key = settings.brightdata_api_key.get_secret_value()
        registry.register(BrightDataAdapter(api_key=bd_key, client=client))

    return registry
```

- [ ] **Step 4: `policy.py` 구현**

`backend/app/sources/policy.py`:
```python
from __future__ import annotations


class CrawlPolicy:
    """크롤러 활성화 게이트.

    공식 API 어댑터는 이 클래스를 사용하지 않는다.
    Plan 4+ 크롤 어댑터는 fetch() 진입 시 require_enabled()를 호출해야 한다.
    """

    @staticmethod
    def require_enabled() -> None:
        """CRAWL_ENABLED=false 면 RuntimeError. 크롤 어댑터 시작 시 호출."""
        import os
        if os.environ.get("CRAWL_ENABLED", "false").lower() != "true":
            raise RuntimeError(
                "CRAWL_ENABLED is false — crawl adapters are disabled. "
                "Set CRAWL_ENABLED=true in .env to enable."
            )

    @staticmethod
    def check_allowed(domain: str, path: str = "/") -> bool:
        """robots.txt 파싱은 Plan 4+에서 구현. 지금은 항상 False."""
        return False
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
uv run pytest tests/test_registry.py -v
```

- [ ] **Step 6: 전체 소스 계층 테스트 통과 확인**

```bash
uv run pytest tests/ -v --tb=short
```
기대: 기존 44개 + 신규 약 25개 = 전부 PASS. 실패 0개.

- [ ] **Step 7: 타입체크**

```bash
uv run ruff check . && uv run ruff format --check .
```

- [ ] **Step 8: 커밋**

```bash
git add app/sources/registry.py app/sources/policy.py tests/test_registry.py
git commit -m "feat: SourceRegistry + CrawlPolicy — 어댑터 등록/조회"
```

---

## 완료 기준

아래를 전부 만족해야 Plan 2가 완료다:

1. `uv run pytest tests/ -q` → 실패 0개
2. `uv run python -c "from app.sources.registry import build_registry; from app.config import get_settings; r = build_registry(get_settings()); print(r.all())"` → 어댑터 리스트 출력 (키가 없으면 `[]`)
3. `uv run ruff check . && uv run ruff format --check .` → 오류 없음
4. `STATUS.md` / `docs/JOURNAL.md` 갱신 완료

---

## 완료 후 갱신 항목

| 파일 | 내용 |
|---|---|
| `STATUS.md` | "계획 2(소스 계층) 완료", 다음 할 일을 "계획 3(수집 엔진)"으로 변경 |
| `docs/JOURNAL.md` | `sample_cap_ratio` 권위 결정(Plan 2 = config.py, Plan 4에서 app_settings로 이관), Bright Data API URL 검증 여부 |
| `docs/ISSUES.md` | Bright Data 엔드포인트가 맞지 않아 수정했다면 증상·원인·교훈 기록 |

---

## 미결 사항 (Plan 2 범위 밖)

| 항목 | 언제 |
|---|---|
| `sample_cap_ratio` 권위를 `app_settings` DB로 이관 | Plan 4 |
| `QUIET_HOURS` 시간대 정책 (KST vs UTC) | Plan 4 디스패처 전 |
| `db.py` 임포트 시점 엔진 생성 → `get_engine()` lru_cache | Plan 3 collector 전 |
| `coverage_cells` 초기화·갱신 (`engine/coverage.py`) | Plan 3 |
| Bright Data API URL 검증 (대시보드 → API reference) | Task 5 구현 시 |
| `policy.py` robots.txt 파싱 | Plan 4 크롤 어댑터 시 |
