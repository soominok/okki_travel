# 수집 엔진 설계 (Plan 3)

> 브랜치: `feat/plan3-collector`  
> 선행: Plan 1(기반) + Plan 2(소스 계층) 완료  
> 목표: Watch 수동 실행 → 스냅샷 생성. 알림·자동 스케줄은 Plan 4.

---

## §1 범위

Plan 3가 만드는 것:

| 컴포넌트 | 산출물 |
|---|---|
| `engine/collector.py` | `collect_watch()` — SCAN→SAMPLE→VERIFY→DB 저장 |
| `api/deps.py` | 토큰 인증 + DB 세션 의존성 |
| `api/routes/watches.py` | Watch CRUD 8개 엔드포인트 |
| `worker.py` 수정 | APScheduler 60초 틱 (§7 선점 SQL) |
| `main.py` 수정 | 라우터 등록 |

Plan 3가 **만들지 않는** 것:

- `engine/rules.py` (알림 규칙) — Plan 4
- `notify/` (슬랙/텔레그램) — Plan 4
- `engine/coverage.py` / `coverage_cells` 추적 — Plan 4 (coverage_pct는 NULL로 저장)
- 자동 스케줄 틱 (APScheduler 잡 구동) — Plan 4 (worker는 틱 SQL만 준비)
- 프론트엔드 화면 — Plan 5

---

## §2 디렉터리 레이아웃 변경

```
backend/app/
├── engine/
│   ├── __init__.py          # 신규
│   └── collector.py         # 신규
├── api/
│   ├── __init__.py          # 신규
│   ├── deps.py              # 신규
│   └── routes/
│       ├── __init__.py      # 신규
│       └── watches.py       # 신규
├── schemas/
│   ├── __init__.py          # 신규 (또는 기존)
│   └── watch.py             # 신규 — Pydantic DTO
├── main.py                  # 수정 — 라우터 등록
└── worker.py                # 수정 — 틱 잡 추가
```

---

## §3 `engine/collector.py` — 수집 파이프라인

### 3-1 공개 인터페이스

```python
async def collect_watch(
    watch_id: UUID,
    *,
    session: AsyncSession,
    registry: SourceRegistry,
    settings: Settings,
) -> WatchRun:
    """Watch 1개를 SCAN → SAMPLE → VERIFY → 저장까지 처리한다.

    반환: 완료된 WatchRun (ok | partial | failed).
    예외를 밖으로 던지지 않는다. 실패는 WatchRun.status='failed'로 기록.
    """
```

### 3-2 실행 순서

```
1. Watch 로드 + 존재/active 확인
2. WatchRun 생성 (status='running', started_at=now())
3. params → FetchRequest 목록 변환 (§3-3)
4. SCAN 단계 (§3-4)
5. SAMPLE 단계 (§3-5)
6. VERIFY 단계 (§3-6)
7. Offers DB 저장 (§3-7)
8. PriceSnapshot 생성 (§3-8)
9. WatchRun 완료 (§3-9)
10. Watch.last_run_at 갱신
```

### 3-3 params → FetchRequest 목록 변환 (월별 청크)

Travelpayouts는 같은 달 내 창만 허용한다 (Ruling R7). Collector가 책임진다 (CLAUDE.md §12).

```python
def _build_requests(watch: Watch) -> list[FetchRequest]:
    p = watch.params
    depart_from = date.fromisoformat(p["depart_from"])
    depart_to   = date.fromisoformat(p["depart_to"])
    
    # 달 경계로 청크 분할
    chunks: list[tuple[date, date]] = []
    cur = depart_from
    while cur <= depart_to:
        last_day = date(cur.year, cur.month,
                        calendar.monthrange(cur.year, cur.month)[1])
        chunks.append((cur, min(last_day, depart_to)))
        cur = min(last_day, depart_to) + timedelta(days=1)
    
    return [
        FetchRequest(
            origin=p.get("origin", ""),
            destination=p["destination"],
            depart_from=start,
            depart_to=end,
            nights_min=p.get("nights_min"),
            nights_max=p.get("nights_max"),
            adults=p.get("adults", 1),
            cabin=p.get("cabin", "economy"),
            currency="KRW",
        )
        for start, end in chunks
    ]
```

stay Watch는 chunking 불필요 (HotellookAdapter는 단일 날짜 처리).

### 3-4 SCAN 단계

```python
scan_adapters = registry.get(kind=watch.kind, role="scan")
all_offers: list[SourceOffer] = []
sources_ok: list[str] = []
sources_failed: dict[str, str] = {}

for req in requests:
    for adapter in scan_adapters:
        result = await adapter.fetch(req)
        if result.ok:
            all_offers.extend(result.offers)
            sources_ok.append(adapter.name)
        else:
            sources_failed[adapter.name] = result.error or "unknown"
```

### 3-5 SAMPLE 단계

SCAN 결과가 0건이고, `cost_per_call > 0` SAMPLE 어댑터가 있을 때만 실행.

```python
if not all_offers:
    sample_adapters = registry.get(kind=watch.kind, role="verify")  # BrightData
    for adapter in sample_adapters:
        if adapter.capability.cost_per_call > 0:
            ok = await reserve_sample(
                budget_session, adapter.name,
                n=1, days_left=_days_left_in_month(),
            )
            if not ok:
                continue  # 예산 부족 = 건너뜀. 실패가 아님 (CLAUDE.md §11)
        # 첫 번째 청크 날짜 하나만 샘플
        req = requests[0] if requests else None
        if req:
            result = await adapter.fetch(req)
            if result.ok:
                all_offers.extend(result.offers)
                credits_used += adapter.capability.cost_per_call
```

`budget_session`은 collector 내부에서 별도 세션으로 생성한다 (budget.py 함수가 자기 세션을 커밋하므로, 메인 세션과 분리해야 한다).

### 3-6 VERIFY 단계

`settings.verify_threshold_ratio` (기본 1.15). Watch.rules에 `threshold` 타입 규칙이 있으면 그 가격 기준, 없으면 스킵.

```python
target_price = _target_price_from_rules(watch.rules)
if target_price and all_offers:
    best = min(all_offers, key=lambda o: o.price_krw)
    if best.price_krw <= target_price * settings.verify_threshold_ratio:
        verify_adapters = registry.get(kind=watch.kind, role="verify")
        for adapter in verify_adapters:
            ok = await reserve_verify(budget_session, adapter.name)
            if not ok:
                continue
            req = FetchRequest(
                origin=..., destination=...,
                depart_from=best.depart_date, depart_to=best.depart_date,
                nights_min=watch.params.get("nights_min"),
                currency="KRW",
            )
            result = await adapter.fetch(req)
            if result.ok and result.offers:
                # verified offer로 교체
                ...
                credits_used += adapter.capability.cost_per_call
```

### 3-7 Offers DB 저장

`INSERT ... ON CONFLICT (watch_id, run_id, source, external_id) DO NOTHING`

```python
for o in all_offers:
    session.add(DbOffer(
        watch_id=watch_id,
        run_id=run.id,
        source=o.source,
        external_id=o.external_id,
        kind=o.kind,
        price_krw=o.price_krw,
        price_original=o.price_original,
        currency_original=o.currency_original,
        depart_date=o.depart_date,
        return_date=o.return_date,
        carrier=o.carrier,
        deep_link=o.deep_link,
        raw=o.raw,
        collected_at=o.collected_at,
        freshness=o.freshness,
        cache_age_days=o.cache_age_days,
        observed_at=o.observed_at,
    ))
await session.flush()
```

### 3-8 PriceSnapshot 생성

```python
if all_offers:
    prices = sorted(o.price_krw for o in all_offers)
    best_offer = min(all_offers, key=lambda o: o.price_krw)
    snapshot = PriceSnapshot(
        watch_id=watch_id,
        min_price_krw=prices[0],
        median_price_krw=prices[len(prices) // 2],
        offer_count=len(prices),
        best_offer_id=best_offer_db_id,   # flush 후 알 수 있음
        coverage_pct=None,   # Plan 4에서 채움
        live_pct=None,
        credits_used=credits_used,
    )
    session.add(snapshot)
```

### 3-9 WatchRun 완료

```python
run.finished_at = datetime.now(UTC)
run.status = "ok" if not sources_failed else ("partial" if all_offers else "failed")
run.sources_ok = list(set(sources_ok))
run.sources_failed = sources_failed or None
run.offers_found = len(all_offers)
run.best_price_krw = prices[0] if all_offers else None
run.credits_used = credits_used
```

---

## §4 `api/deps.py` — 의존성

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer()

def require_token(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    if cred.credentials != settings.app_api_token.get_secret_value():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

---

## §5 `api/routes/watches.py` — 엔드포인트 명세

모든 엔드포인트는 `Depends(require_token)`.

### 5-1 Watch CRUD

| Method | Path | 상태코드 | 설명 |
|---|---|---|---|
| GET | `/api/watches` | 200 | 목록. `WatchListItem[]` |
| POST | `/api/watches` | 201 | 생성. `next_run_at=None` (자동 실행 없음, /run으로 명시) |
| GET | `/api/watches/{id}` | 200 | 상세 |
| PATCH | `/api/watches/{id}` | 200 | 부분 수정 (params/rules/interval_min/status) |
| DELETE | `/api/watches/{id}` | 204 | 삭제 |

### 5-2 수동 실행

```
POST /api/watches/{id}/run
→ 202 { "run_id": "<uuid>" }
```

- Watch가 없으면 404
- Watch가 paused면 409 (`{"error": {"code": "WATCH_PAUSED"}}`)
- BackgroundTasks로 `collect_watch()` 비동기 실행
- run_id는 WatchRun을 먼저 DB에 생성(status='running')하고 즉시 반환

### 5-3 조회 엔드포인트

```
GET /api/watches/{id}/snapshots?days=90
→ 200 PriceSnapshot[]  (captured_at DESC)

GET /api/watches/{id}/runs?limit=20
→ 200 WatchRun[]  (started_at DESC)
```

---

## §6 `schemas/watch.py` — Pydantic DTO

```python
class WatchCreate(BaseModel):
    kind: Literal["flight", "stay"]
    title: str
    params: dict        # watches.params jsonb 그대로
    rules: list[dict]   # watches.rules jsonb 그대로
    interval_min: int = 360

class WatchPatch(BaseModel):
    params: dict | None = None
    rules: list[dict] | None = None
    interval_min: int | None = None
    status: Literal["active", "paused"] | None = None

class WatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    title: str
    params: dict
    rules: list[dict]
    interval_min: int
    status: str
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
```

---

## §7 `worker.py` 수정 — 60초 틱

```python
async def tick(registry: SourceRegistry, settings: Settings) -> None:
    """due인 watch를 선점하고 collect_watch를 순차 실행."""
    async with async_session_factory() as session:
        # SELECT FOR UPDATE SKIP LOCKED (docs/02 §7)
        rows = await session.execute(
            text("""
            WITH due AS (
              SELECT id FROM watches
              WHERE status = 'active' AND next_run_at <= now()
              ORDER BY next_run_at
              FOR UPDATE SKIP LOCKED
              LIMIT :batch
            )
            UPDATE watches w
            SET next_run_at = now()
                  + (w.interval_min * interval '1 minute')
                  + (random() * interval '3 minutes'),
                last_run_at = now()
            FROM due WHERE w.id = due.id
            RETURNING w.id
            """),
            {"batch": 5},
        )
        watch_ids = [r[0] for r in rows.fetchall()]
        await session.commit()

    for wid in watch_ids:
        async with async_session_factory() as s:
            await collect_watch(wid, session=s, registry=registry, settings=settings)
```

Plan 3에서는 APScheduler가 틱을 **등록만** 하고 실제 수집 대상이 없으므로 동작은 무해하다.  
Plan 4에서 Watch가 생성되면 자동으로 수집이 돈다.

---

## §8 테스트 전략

### `test_collector.py`

- 실 DB 사용 (respx로 HTTP만 목킹)
- `test_collect_watch_scan_only` — SCAN 결과 저장 → WatchRun.status='ok', offers 삽입 확인
- `test_collect_watch_no_offers_sample` — SCAN 0건 → SAMPLE 호출 → 예산 부족 시 ok
- `test_collect_watch_verify_triggered` — best_price ≤ threshold → VERIFY 호출
- `test_collect_watch_scan_fails` — SCAN adapter 실패 → WatchRun.status='failed'
- `test_monthly_chunks` — 3개월 범위 → 3개 FetchRequest 생성 확인 (순수 함수, DB 불필요)

### `test_api_watches.py`

- httpx AsyncClient + TestClient
- `test_create_watch` — POST 201, DB에 저장 확인
- `test_run_returns_202` — POST /run 202 + run_id 반환
- `test_run_paused_watch_returns_409`
- `test_get_snapshots` — 스냅샷 목록 정상 반환

---

## §9 전제 조건 및 파킹

### 전제 조건

- Plan 2 브랜치 머지 완료 (어댑터 3종 + budget.py + registry.py)
- `call_budgets` 테이블 존재 (Plan 2 마이그레이션 포함)
- `async_session_factory` — `db.py`에 이미 있거나 추가

### 파킹 (Plan 4 이전 수정 필요)

| 항목 | 내용 |
|---|---|
| R4 `_wait()` 동시성 버그 | Plan 3에서는 순차 실행이라 미발현. Plan 4 collector fan-out 전 반드시 수정 |
| `coverage_cells` 추적 | Plan 3 snapshot에 coverage_pct=NULL 저장. Plan 4에서 채움 |
| QUIET_HOURS 시간대 | `config.py`는 naive `time`. Plan 4 알림 디스패처 전 KST 확인 필요 |
| `db.py` 임포트 시 엔진 생성 | Plan 3 collector 첫 소비자. `get_engine()` lru_cache 전환 or sessionmaker 주입 검토 |

---

## §10 글로벌 제약 (CLAUDE.md)

- §3: 시크릿은 `get_settings()` 경유. `os.getenv()` 직접 사용 금지
- §4: 모든 datetime은 UTC (`timestamptz`). KST 변환은 표시 계층에서만
- §5: `price_krw`는 int. float 금지
- §7: 어댑터는 예외를 던지지 않음. collector가 `SourceResult.ok`를 확인
- §8: 어댑터는 DB 모름. DB 저장은 collector만
- §11: `cost_per_call > 0` 어댑터는 예산 선점 후 호출
- §12: fan-out(월별 청크 분할)은 collector. 어댑터 내부 루프 금지
