# 아키텍처 설계서

---

## 1. 기술 스택 (확정)

### 백엔드 — Python 3.12

| 영역 | 선택 | 비고 |
|---|---|---|
| 웹 프레임워크 | FastAPI | 자동 OpenAPI → 프론트 타입 생성에 활용 |
| ORM | SQLAlchemy 2.0 (async) + Alembic | 마이그레이션 필수 |
| 검증 | Pydantic v2 / pydantic-settings | 설정도 Pydantic으로 |
| HTTP 클라이언트 | httpx (async) + tenacity | 재시도/백오프 |
| 스케줄러 | APScheduler 3.x (SQLAlchemyJobStore) | 잡 상태를 Postgres에 저장 → 재시작 내성 |
| 크롤링(보조) | Playwright (Python) | 정책 게이트 통과 시에만 |
| 로깅 | structlog (JSON) | 클라우드 이전 대비 |
| 테스트 | pytest + pytest-asyncio + respx | respx로 HTTP 목킹 |
| 린트/포맷 | ruff | black+isort+flake8 대체 |

### 프론트엔드 — Next.js 15 (App Router)

| 영역 | 선택 |
|---|---|
| 언어 | TypeScript (strict) |
| 스타일 | Tailwind CSS v4 |
| 컴포넌트 | shadcn/ui |
| 서버 상태 | TanStack Query v5 |
| 폼 | react-hook-form + zod |
| 차트 | Recharts (가격 히스토리) |
| 지도 (Phase 3) | MapLibre GL + VWorld 타일 |
| API 타입 | `openapi-typescript`로 FastAPI 스키마에서 자동 생성 |

### 인프라

- **Postgres 16** (SQLite 쓰지 않음 — 클라우드 이전 대비)
- docker-compose 4 서비스: `db`, `api`, `worker`, `web`
- 클라우드 이전 시: `db` → 관리형 Postgres, `worker` → 동일 이미지 그대로 배포

---

## 2. 시스템 구성

```
┌──────────────┐        ┌──────────────────────────────────────┐
│   web        │ HTTP   │  api (FastAPI)                        │
│  Next.js     │──────▶ │  - REST /api/*                        │
│  :3000       │        │  - Watch CRUD, 조회, 설정             │
└──────────────┘        └────────────┬─────────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   Postgres :5432    │
                          │  watches, snapshots,│
                          │  offers, alerts,    │
                          │  apscheduler_jobs   │
                          └──────────▲──────────┘
                                     │
┌────────────────────────────────────┴─────────────────────────┐
│  worker (같은 코드베이스, 다른 엔트리포인트)                  │
│                                                               │
│  APScheduler ──▶ CollectJob(watch_id)                         │
│                      │                                        │
│                      ├─▶ SourceRegistry  ──▶ [travelpayouts]  │
│                      │      (SCAN)            [hotellook]     │
│                      │                        [tourapi]       │
│                      │                        [crawler*]      │
│                      ├─▶ CallBudget     ──▶ Postgres          │
│                      ├─▶ Sampler        ──▶ [brightdata]      │
│                      │      (SAMPLE)          coverage 보강    │
│                      ├─▶ VerifyStage    ──▶ [brightdata]      │
│                      ├─▶ SnapshotStore  ──▶ Postgres          │
│                      ├─▶ RuleEngine     ──▶ Alert 생성        │
│                      └─▶ NotifyDispatcher ─▶ [slack][inapp]   │
│                                                 [telegram*]   │
└───────────────────────────────────────────────────────────────┘
                                                   * = 나중에 켤 것
```

### 왜 `api`와 `worker`를 분리하나

- API 재시작(코드 수정)이 수집 스케줄을 끊지 않는다
- 클라우드 이전 시 worker만 별도 스케일/스케줄 서비스로 옮길 수 있다
- 수집이 CPU/네트워크를 오래 잡아도 API 응답성이 유지된다

---

## 3. 디렉터리 구조

```
trip_pick/
├── CLAUDE.md                    # Claude Code 상시 규칙
├── docker-compose.yml
├── .env.example
├── docs/                        # 이 설계서들
├── PROMPTS.md
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py              # FastAPI 엔트리
│   │   ├── worker.py            # 스케줄러 엔트리
│   │   ├── config.py            # pydantic-settings, 모든 env
│   │   ├── db.py                # async engine/session
│   │   ├── models/              # SQLAlchemy 모델
│   │   │   ├── watch.py  snapshot.py  offer.py  alert.py
│   │   │   ├── source_health.py  place.py
│   │   ├── schemas/             # Pydantic DTO (요청/응답)
│   │   ├── api/
│   │   │   ├── deps.py          # 인증, DB 세션
│   │   │   └── routes/
│   │   │       ├── watches.py  prices.py  alerts.py
│   │   │       ├── settings.py  sources.py  health.py
│   │   ├── sources/             # ★ 어댑터 레이어
│   │   │   ├── base.py          # Protocol, Offer, Query 모델
│   │   │   ├── registry.py      # 등록/조회/우선순위
│   │   │   ├── http.py          # 레이트리밋 httpx 래퍼
│   │   │   ├── policy.py        # robots.txt / 크롤 정책 게이트
│   │   │   ├── budget.py        # call_budgets 선점 (cost_per_call>0 소스용)
│   │   │   ├── flight/
│   │   │   │   ├── travelpayouts.py
│   │   │   │   └── brightdata.py
│   │   │   ├── stay/
│   │   │   │   ├── hotellook.py
│   │   │   │   └── tourapi_stay.py
│   │   │   └── place/
│   │   │       ├── tourapi.py
│   │   │       └── kma_weather.py
│   │   ├── engine/              # ★ 도메인 로직
│   │   │   ├── collector.py     # SCAN → SAMPLE → VERIFY → 저장
│   │   │   ├── sampler.py       # 커버리지 3티어 샘플링 정책
│   │   │   ├── coverage.py      # coverage_cells 갱신·통계
│   │   │   ├── rules.py         # 알림 규칙 평가 (순수 함수)
│   │   │   ├── baseline.py      # 기준선(중앙값/최저가) 계산
│   │   │   └── dedup.py         # 중복 억제 + 쿨다운
│   │   ├── notify/              # ★ 알림 추상화
│   │   │   ├── base.py          # Notifier Protocol, Message 모델
│   │   │   ├── dispatcher.py    # 채널 라우팅 + 재시도
│   │   │   ├── slack.py         # Block Kit 렌더러
│   │   │   ├── telegram.py      # (Phase 1.5)
│   │   │   └── inapp.py         # DB 저장
│   │   └── scheduler/
│   │       ├── jobs.py
│   │       └── setup.py
│   └── tests/
│       ├── fixtures/<source>/*.json
│       ├── test_rules.py  test_adapters.py  test_notify.py
│       └── test_api.py
│
└── web/
    ├── app/
    │   ├── page.tsx                    # 대시보드
    │   ├── watches/new/page.tsx        # 감시 등록
    │   ├── watches/[id]/page.tsx       # 감시 상세 + 차트
    │   ├── alerts/page.tsx             # 알림함
    │   └── settings/page.tsx           # 설정 + 소스 상태
    ├── components/
    │   ├── watch-card.tsx  price-chart.tsx  offer-table.tsx
    │   └── ui/                          # shadcn
    └── lib/
        ├── api.ts                       # fetch 래퍼
        └── types.gen.ts                 # OpenAPI 생성 타입
```

---

## 4. 데이터 모델

```sql
-- 감시 조건
watches (
  id             uuid pk,
  kind           text not null,          -- flight | stay | package
  title          text not null,          -- "가을 후쿠오카"
  params         jsonb not null,         -- 아래 스키마 참조
  rules          jsonb not null,         -- 알림 규칙 배열
  interval_min   int not null default 360,
  status         text not null default 'active',  -- active|paused|error
  last_run_at    timestamptz,
  next_run_at    timestamptz,          -- ★ 스케줄의 유일한 진실의 원천 (§7 참조)
  created_at     timestamptz default now(),
  updated_at     timestamptz,
  -- params 는 jsonb 로 두되, 조회가 필요한 소수 필드만 생성 칼럼으로 꺼내 인덱싱한다.
  -- (Phase 2 추천이 "이 사용자가 어느 목적지를 감시하나"를 물어야 하는데,
  --  그때 jsonb path 쿼리를 하게 되면 늦다. 쓰기 로직 중복은 없다.)
  destination    text generated always as (params->>'destination') stored
)
create index on watches (status, next_run_at);
create index on watches (destination);

-- 매 수집 실행 기록 (관측성)
watch_runs (
  id             uuid pk,
  watch_id       uuid fk,
  started_at     timestamptz,
  finished_at    timestamptz,
  status         text,                   -- ok|partial|failed
  sources_ok     text[],
  sources_failed jsonb,                  -- {source: error}
  offers_found   int,
  best_price_krw int,
  error          text
)

-- 개별 상품 (매 수집마다 append)
offers (
  id             uuid pk,
  watch_id       uuid fk,
  run_id         uuid fk,
  source         text not null,
  external_id    text not null,
  kind           text not null,
  price_krw      int not null,
  price_original numeric,
  currency_original text,
  depart_date    date,
  return_date    date,
  carrier        text,
  deep_link      text,
  raw            jsonb,
  collected_at   timestamptz not null,
  -- run_id 를 쓴다. collected_at 을 넣으면 행마다 now() 라 튜플이 항상 달라져서
  -- 중복을 전혀 막지 못한다 (재시도 시 이중 삽입 방지가 이 제약의 목적).
  unique (watch_id, run_id, source, external_id)
)
create index on offers (watch_id, collected_at desc);
create index on offers (watch_id, price_krw);

-- 시계열 요약 (차트용, 실행당 1행)
-- offers 와 중복처럼 보이지만 아니다: offers 는 OFFER_RETENTION_DAYS(90일) 후 정리되고
-- snapshots 는 영구 보관한다. 즉 snapshots 가 장기 히스토리의 유일한 원천이다.
-- 이 비대칭이 존재 이유이므로 "GROUP BY 로 대체 가능"하다고 판단해 지우지 말 것.
price_snapshots (
  id             bigserial pk,
  watch_id       uuid fk,
  captured_at    timestamptz not null,
  min_price_krw  int not null,
  median_price_krw int,
  offer_count    int,
  best_offer_id  uuid
)
create index on price_snapshots (watch_id, captured_at desc);

-- 알림
alerts (
  id             uuid pk,
  watch_id       uuid fk,
  rule_id        text not null,          -- 어떤 규칙이 발화했나
  severity       text not null,          -- info | good | great
  title          text not null,
  body           text not null,
  payload        jsonb,                  -- 렌더링용 구조화 데이터
  dedup_key      text not null,          -- 중복 억제 키
  created_at     timestamptz default now(),
  read_at        timestamptz
)
-- ⚠️ date_trunc('hour', created_at) 로 unique 인덱스를 만들려 하지 말 것.
-- created_at 이 timestamptz 라 date_trunc 는 STABLE(IMMUTABLE 아님)이고,
-- Postgres 는 이런 표현식으로 인덱스를 만들지 못한다 (must be marked IMMUTABLE 에러).
-- 게다가 1시간 버킷은 ALERT_COOLDOWN_HOURS(12) 와 어긋난다.
-- dedup 은 engine/dedup.py 단일 경로로만 강제하고, 여기서는 조회 인덱스만 둔다.
create index on alerts (dedup_key, created_at desc);

-- 채널별 발송 결과
alert_deliveries (
  id         uuid pk,
  alert_id   uuid fk,
  channel    text,                       -- slack | telegram | inapp
  status     text,                       -- sent | failed | skipped
  error      text,
  sent_at    timestamptz
)

-- 소스 헬스 (설정 화면에 표시)
source_health (
  source        text pk,
  ok            bool,
  last_ok_at    timestamptz,
  last_error    text,
  consecutive_failures int default 0,
  disabled_until timestamptz
)

-- 환율 (소스가 KRW 를 못 주는 경우의 폴백. P4에서 필요 여부 판명)
fx_rates (
  currency    text not null,           -- USD, EUR, JPY ...
  rate_date   date not null,           -- 고시 영업일
  rate_krw    numeric not null,        -- 1단위당 원화
  fetched_at  timestamptz default now(),
  primary key (currency, rate_date)
)
-- 조회는 항상 "해당 일자 이하의 가장 최근 영업일" 로 한다 (주말·공휴일 폴백):
--   select rate_krw from fx_rates
--   where currency = $1 and rate_date <= $2
--   order by rate_date desc limit 1

-- ───────────────────────────────────────────────────────────────
-- 소스 계층 재설계로 추가된 것들 (2026-09-01)
-- 전체 DDL과 근거는 docs/superpowers/specs/2026-09-01-source-layer-design.md §4~§6
-- ───────────────────────────────────────────────────────────────

call_budgets (source, period_start) -- 유료 소스 월 예산. SAMPLE 상한 + 자기보정 일일 페이싱
coverage_cells (watch_id, depart_date, nights) -- 탐색 공간 180칸. "안 봤다" vs "봤는데 없다"
probe_log (id)                      -- 샘플링 적중률 기록. 상수 튜닝의 근거. 90일 보관
app_settings (key, value jsonb)     -- sampling_policy 등 재배포 없이 바꿀 상수

-- 기존 테이블 칼럼 추가
alter table offers          add column freshness text not null,      -- live | cached
                            add column cache_age_days int,
                            add column observed_at timestamptz,      -- 소스가 안 주면 NULL
                            add column verified bool not null default false,
                            add column verify_run_id uuid;
alter table price_snapshots add column coverage_pct numeric,         -- ★ 아래 주의
                            add column live_ratio numeric,
                            add column credits_used int;
alter table watches         add column last_sampled_at timestamptz;  -- 샘플링 라운드로빈
alter table watch_runs      add column credits_used int;

-- ★ coverage_pct 가 없으면 커버리지 하락을 가격 상승으로 오독한다.
--   차트만이 아니라 rules.py 도 똑같이 속아 all_time_low 가 오발동한다.
--   따라서 규칙 평가에 커버리지 게이트를 건다 (스펙 §6).

-- 관광 장소 캐시 (Phase 2~3 대비, Phase 1에서 테이블만 만들어둠)
places (
  id           uuid pk,
  source       text,                     -- tourapi
  external_id  text,
  name         text,
  content_type text,
  area_code    text,
  lat          double precision,
  lng          double precision,
  tags         text[],
  raw          jsonb,
  unique (source, external_id)
)
```

### `watches.params` 스키마

```jsonc
// kind = "flight"
{
  "origin": "ICN",
  "destination": "FUK",
  "depart_from": "2026-10-01",
  "depart_to":   "2026-12-31",
  "trip_length_min": 2,
  "trip_length_max": 3,
  "weekday_preference": ["FRI", "SAT"],   // 출발 요일 선호 (빈 배열 = 무관)
  "adults": 2,
  "cabin": "economy",
  "direct_only": false
}

// kind = "stay"
{
  "city_code": "SEL",           // 또는 tourapi area/sigungu 코드
  "checkin_from": "2026-12-24",
  "checkin_to":   "2026-12-26",
  "nights": 2,
  "guests": 2,
  "min_stars": 4
}
```

### `watches.rules` 스키마

```jsonc
[
  { "id": "target",   "type": "threshold",    "price_krw": 250000 },
  { "id": "drop",     "type": "drop_pct",     "pct": 20, "baseline": "median_14d" },
  { "id": "lowest",   "type": "all_time_low", "min_samples": 10 },
  { "id": "newbest",  "type": "new_best",     "improve_krw": 10000 }
]
```

각 규칙은 `engine/rules.py`의 **순수 함수**로 구현한다.
입력: `(현재 스냅샷, 히스토리, 규칙 설정)` → 출력: `AlertCandidate | None`.
**DB도, 네트워크도 건드리지 않는다.** → 테스트가 쉽고 빠르다.

---

## 5. REST API 명세

인증: 모든 `/api/*` 요청에 `Authorization: Bearer ${APP_API_TOKEN}`.

> ⚠️ **웹에서 이 토큰을 직접 쓰지 않는다.** Next.js 클라이언트 컴포넌트가 백엔드를 직접
> 호출하면 토큰이 JS 번들에 박힌다 (`NEXT_PUBLIC_`으로 넣는 순간 공개된다).
> 브라우저는 **Next.js Route Handler(`web/app/api/[...path]/route.ts`)만 호출**하고,
> 그 핸들러가 서버 사이드 env의 토큰을 붙여 백엔드로 프록시한다.
> 지금은 로컬이라 문제가 안 보이지만, 클라우드로 옮기는 순간 사고가 된다.

| Method | Path | 설명 |
|---|---|---|
| GET | `/healthz` | 무인증. DB 연결 확인 |
| GET | `/api/watches` | 목록 (+ 최신 스냅샷, 24h 변동률 조인) |
| POST | `/api/watches` | 생성. 생성 즉시 1회 수집 트리거 |
| GET | `/api/watches/{id}` | 상세 |
| PATCH | `/api/watches/{id}` | 수정 (params/rules/interval/status) |
| DELETE | `/api/watches/{id}` | 삭제 |
| POST | `/api/watches/{id}/run` | 수동 즉시 수집 (202 + run_id) |
| GET | `/api/watches/{id}/snapshots?days=90` | 차트 데이터 |
| GET | `/api/watches/{id}/offers?limit=50&sort=price` | 현재 오퍼 목록 |
| GET | `/api/watches/{id}/runs?limit=20` | 실행 로그 |
| GET | `/api/alerts?unread=true&limit=50` | 알림함 |
| POST | `/api/alerts/{id}/read` | 읽음 처리 |
| GET | `/api/sources` | 소스별 health/enabled/키 설정 여부 |
| POST | `/api/notify/test` | 슬랙 테스트 메시지 발송 |
| GET | `/api/meta/airports?q=후쿠` | 공항 자동완성 (아래 주 참조) |
| GET | `/api/watches/{id}/coverage` | 커버리지 히트맵 데이터 (180칸 상태) |
| GET | `/api/budget` | 소스별 잔여 크레딧·소진 예상일 |

> **공항 자동완성 소스**: 초안은 Amadeus `reference-data/locations`를 썼으나 폐쇄됐다.
> 대신 **정적 IATA 데이터셋을 리포지토리에 동봉**한다 (OpenFlights 등 공개 데이터, ~7천 행).
> 공항 목록은 거의 변하지 않으므로 API를 쓸 이유가 없다. 부팅 시 메모리에 적재하거나
> `places` 와 별개의 `airports` 테이블에 시드한다.

에러 응답은 전부 동일 포맷:

```json
{ "error": { "code": "WATCH_NOT_FOUND", "message": "...", "detail": {} } }
```

---

## 6. 알림 추상화 (슬랙 → 텔레그램 전환 비용을 0으로)

**핵심 원칙: 도메인 로직은 슬랙을 모른다.** 채널 중립 메시지를 만들고, 렌더러가 변환한다.

```python
# backend/app/notify/base.py

class Field(BaseModel):
    label: str
    value: str

class Confidence(BaseModel):
    """이 가격을 얼마나 믿을 수 있는가. 표현 방법은 렌더러가 정한다.
    Travelpayouts 캐시는 최대 7일 묵을 수 있으므로 이걸 숨기면 신뢰가 무너진다."""
    verified: bool                # VERIFY 단계를 통과했나
    freshness: Literal["live", "cached"]
    age_label: str                # "12분 전 실측" / "최대 7일 전 캐시"
    source: str
    coverage_pct: int

class NotificationMessage(BaseModel):
    """채널 중립 메시지. Slack/Telegram/InApp 어디로든 갈 수 있다."""
    severity: Literal["info", "good", "great"]
    confidence: Confidence        # 신선도·검증 여부 (렌더러가 알아서 표현)
    title: str                    # "🔥 ICN→FUK 238,000원"
    summary: str                  # "목표가 250,000원 대비 -12,000원"
    fields: list[Field]           # 날짜/항공사/직전가/최저기록
    link: str | None              # 예약 딥링크
    link_label: str | None
    dashboard_url: str | None
    dedup_key: str

class Notifier(Protocol):
    channel: str
    async def send(self, msg: NotificationMessage) -> DeliveryResult: ...
```

- `slack.py` — `NotificationMessage` → Block Kit(header/section/fields/actions) 변환
- `telegram.py` — 동일 입력 → MarkdownV2 + inline keyboard 변환
- `inapp.py` — `alerts` 테이블에 저장
- `dispatcher.py` — `NOTIFY_CHANNELS=slack,inapp` 환경변수로 활성 채널 결정,
  채널별 재시도 3회(지수 백오프), 결과를 `alert_deliveries`에 기록

> **텔레그램 전환 = `.env`에서 `NOTIFY_CHANNELS=telegram,inapp` + 토큰 추가. 코드 수정 0.**

### 중복 억제

```
dedup_key = sha1(f"{watch_id}:{rule_id}:{best_price_bucket}:{depart_date}")
price_bucket = price_krw // 5000     # 5천원 단위로 뭉갬 → 잔변동 스팸 방지
```

- 동일 `dedup_key`는 `ALERT_COOLDOWN_HOURS`(기본 12) 안에 재발송하지 않는다
- 단, `severity`가 올라가면(good → great) 쿨다운을 무시하고 발송한다

### QUIET_HOURS 처리 — 억제이지 폐기가 아니다

방해금지 시간대에 걸린 알림은 **버리지 않는다.** 밤사이 뜬 최저가를 놓치면 이 서비스의
존재 이유가 없어진다.

- `inapp` 채널은 **항상** 기록한다 (아침에 대시보드/알림함에서 보인다)
- 푸시 채널(slack/telegram)만 억제하고, `alert_deliveries.status='deferred'`로 남긴다
- `severity=great`는 시간대와 무관하게 즉시 푸시한다
- 방해금지 종료 시각에 `deferred` 건을 **묶어서 1건의 다이제스트로** 발송한다
  (개별로 다 쏘면 아침에 알림 폭탄이 된다)

---

## 7. 스케줄러 — `next_run_at` 폴링

> **APScheduler의 job store를 쓰지 않는다.** Watch당 잡을 만들고 DB와 동기화하면
> 진실의 원천이 둘(`watches` 테이블 + job store)이 되어 다음 문제가 전부 생긴다:
> 삭제된 watch의 잡이 폴링 전에 발화, interval 변경 감지의 번거로움, 워커 2개 시 경합,
> 그리고 결정적으로 **job store는 잡을 pickle로 저장하므로 함수를 다른 모듈로 옮기면
> 역직렬화가 깨지고 store 전체가 오염된다.**
>
> 대신 **`watches.next_run_at`을 유일한 진실**로 삼고, APScheduler는 60초 틱 하나만 돌린다.

### 스케줄러 전체

```python
# worker.py — 이게 전부다. jobstore 없음, 메모리 전용.
scheduler = AsyncIOScheduler()
scheduler.add_job(tick, "interval", seconds=60, id="tick",
                  max_instances=1, coalesce=True)
scheduler.add_job(source_health_check, "interval", minutes=15, max_instances=1)
scheduler.add_job(cleanup_old_offers, "cron", hour=4, max_instances=1)
```

### 틱 — 선점과 다음 예약을 한 문장으로

```sql
WITH due AS (
  SELECT id FROM watches
  WHERE status = 'active' AND next_run_at <= now()
  ORDER BY next_run_at
  FOR UPDATE SKIP LOCKED          -- ★ 워커가 여러 개여도 같은 행을 두 번 잡지 않는다
  LIMIT :batch_size
)
UPDATE watches w
SET next_run_at = now()
      + (w.interval_min * interval '1 minute')
      + (random() * interval '3 minutes'),   -- ★ 지터: 동시 폭주 방지
    last_run_at = now()
FROM due
WHERE w.id = due.id
RETURNING w.*;
```

이 한 문장이 예전 설계의 `jitter` / `max_instances` / `coalesce` / `misfire_grace_time` /
`replace_existing` / 60초 동기화 로직을 **전부 대체한다.**

| 예전 옵션 | 지금은 어떻게 되는가 |
|---|---|
| `jitter=180` | `random() * interval '3 minutes'` |
| `max_instances=1` | `FOR UPDATE SKIP LOCKED` + 실행 **전에** next_run_at을 미리 밀어둠 |
| `coalesce=True` | `next_run_at`은 단일 타임스탬프라 밀린 실행이 쌓이지 않는다.<br>PC가 이틀 절전이어도 복귀 시 **1회만** 돈다 |
| `misfire_grace_time` | 불필요. 늦게라도 1회 도는 게 맞는 동작이다 |
| job 동기화 60초 폴링 | 불필요. 테이블이 곧 스케줄이다 |

### 나머지 규칙

- **Watch 생성 시 `next_run_at = now()`** → 다음 틱(최대 60초)에 첫 수집이 돈다.
  별도의 "생성 후 백그라운드 트리거" 코드가 필요 없다.
- **수동 실행**(`POST /api/watches/{id}/run`)도 `next_run_at = now()` 로 끝. 경로가 하나다.
- **일시중지**는 `status='paused'` 하나로. 잡을 지우고 다시 만들 필요가 없다.
- 워커가 수집 도중 죽어도 `next_run_at`은 이미 밀려 있으므로 다음 주기에 자연히 재시도된다.
  (실패한 실행은 `watch_runs.status='failed'`로 남는다)
- `collector`는 실행 시작 시 watch가 아직 존재하고 `active`인지 한 번 더 확인한다.

### 클라우드 이전 시

틱을 `POST /internal/tick`(내부 토큰 인증) 엔드포인트로 노출하면
Cloud Scheduler / EventBridge / cron이 60초마다 호출하는 것으로 **워커 컨테이너 자체를 없앨 수 있다.**
로직은 그대로다.

---

## 8. 설정 (`.env.example`)

```bash
# --- Core ---
APP_ENV=local
APP_API_TOKEN=change-me-to-a-long-random-string
DATABASE_URL=postgresql+asyncpg://trip:trip@db:5432/trippick
TZ=Asia/Seoul
PUBLIC_WEB_URL=http://localhost:3000

# --- Sources (없으면 해당 어댑터만 비활성) ---
TRAVELPAYOUTS_TOKEN=
TRAVELPAYOUTS_MARKER=
BRIGHTDATA_API_KEY=
BRIGHTDATA_MONTHLY_CREDITS=5000
BRIGHTDATA_SAMPLE_CAP_RATIO=0.70
DATA_GO_KR_KEY=

# --- Notify ---
NOTIFY_CHANNELS=slack,inapp
SLACK_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_COOLDOWN_HOURS=12
QUIET_HOURS=23:00-08:00        # 이 시간대는 great 등급만 발송

# --- Collect ---
DEFAULT_INTERVAL_MIN=360
VERIFY_THRESHOLD_RATIO=1.15    # 목표가의 115% 이내면 Bright Data로 실가격 검증
CRAWL_ENABLED=false            # 기본 off. 켜도 policy.py 게이트를 통과해야 함
CRAWL_MIN_INTERVAL_SEC=5
HTTP_USER_AGENT=TripPick/0.1 (personal price watcher; contact: you@example.com)
```

---

## 9. 클라우드 이전 대비 (지금 지켜야 할 것)

| 하지 말 것 | 대신 |
|---|---|
| SQLite | Postgres |
| 로컬 파일에 캐시/상태 저장 | Postgres 테이블 |
| `localhost` 하드코딩 | 전부 env |
| 인메모리 스케줄 상태 | SQLAlchemyJobStore |
| print 로깅 | structlog JSON → stdout |
| 컨테이너 안에서 마이그레이션 자동 실행 | 별도 `alembic upgrade head` 스텝 |

이것만 지키면 클라우드 이전은 **docker-compose → 관리형 Postgres + 컨테이너 2개 배포**로 끝난다.
