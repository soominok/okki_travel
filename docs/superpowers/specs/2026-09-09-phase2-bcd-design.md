# Phase 2 B+C+D 확장 설계

> 작성일: 2026-09-09  
> 범위: 딥링크(B) + 가격 추세 통계(C) + 항공사 공식 이벤트 크롤러(D)  
> 접근법: 절충 — EventAdapter 패턴 + on-the-fly 통계 + 딥링크 유틸

---

## 1. 배경과 목적

Phase 1에서 Travelpayouts JetRadar 메타검색 오퍼를 수집하고 슬랙으로 최저가 알림을 보내는 기반을 완성했다. Phase 2는 세 방향으로 실용성을 확장한다.

**B — 딥링크:** 오퍼를 발견했을 때 스카이스캐너·구글항공·네이버항공·트립닷컴에서 같은 구간을 바로 비교할 수 있도록 사전 입력 URL을 제공한다.

**C — 가격 추세 통계:** "이 노선은 몇 월이 역대 가장 쌌는가"를 월별 최저가 집계로 보여준다. 데이터가 쌓일수록 "언제 사야 할까" 판단 근거가 생긴다.

**D — 항공사 공식 이벤트 크롤러:** 한국 LCC·FSC 공식 이벤트 페이지를 주기적으로 수집해 Travelpayouts 캐시에 잡히지 않는 단기 특가를 보완한다. 공식 이벤트 페이지를 우선하고 Telegram은 후순위로 미룬다.

---

## 2. 범위 제약

- **크롤링 금지 대상:** 야놀자·여기어때·스카이스캐너·아고다 (CLAUDE.md Rule 9)
- **봇 차단 우회 금지:** Cloudflare Bot Management·DataDome 우회 코드 작성 금지
- **정식 API 없는 사이트:** robots.txt 허용 + 공개 HTML만 파싱. `policy.py` 게이트 필수
- **수집 대상 항공사 4곳 + 1사이트:**
  - 에어부산 `https://www.airbusan.com/ko/flyNEvent/`
  - 티웨이항공 `https://www.twayair.com/app/promotion/event/being`
  - 제주항공 `https://www.jejuair.net/ko/event/event.do`
  - 대한항공 `https://www.koreanair.com/kr/ko/promotion/list`
  - flightdeal.kr (여러 항공사 특가 집계 사이트)

---

## 3. 데이터 모델

### 3.1 신규 테이블: `airline_events`

```sql
CREATE TABLE airline_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source       VARCHAR(32) NOT NULL,          -- "airbusan" | "tway" | "jejuair" | "koreanair" | "flightdeal"
    external_id  VARCHAR(255) NOT NULL,          -- 항공사 이벤트 번호 or SHA256(url)[:16]
    title        VARCHAR(512) NOT NULL,
    url          VARCHAR(1024) NOT NULL,
    origin       VARCHAR(3),                     -- IATA 코드, 불명확하면 NULL
    destination  VARCHAR(3),
    valid_from   DATE,
    valid_to     DATE,
    discount_info VARCHAR(512),                  -- "최대 30% 할인" 등 자유 텍스트
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_airline_events ON airline_events (source, external_id);
```

기존 `offers`·`price_snapshots`·`watches` 테이블 변경 없음.

### 3.2 스키마 변경 없는 기능 (B, C)

- **B(딥링크):** 기존 `offers` 필드(`depart_time`, `return_time`, Watch params)로 URL 생성. DB 변경 없음.
- **C(가격 통계):** 기존 `price_snapshots.min_price_krw`를 월별 GROUP BY. DB 변경 없음.

---

## 4. 백엔드 설계

### 4.1 B — 딥링크 유틸 (`backend/app/utils/deep_links.py`)

순수 함수 모듈. DB·네트워크 없음.

```python
def build_deep_links(
    origin: str,
    destination: str,
    dep_date: str,        # "YYYY-MM-DD"
    ret_date: str | None, # None이면 편도
) -> dict[str, str]:
    """Watch params로 4개 사이트 사전입력 URL을 반환한다."""
```

반환 키: `"skyscanner"`, `"google"`, `"naver"`, `"tripdotcom"`

URL 패턴:
- 스카이스캐너: `https://www.skyscanner.co.kr/transport/flights/{origin}/{destination}/{dep_yymmdd}/{ret_yymmdd}/?adults=1&currency=KRW`
- 구글항공: `https://www.google.com/travel/flights/search?q=flights+from+{origin}+to+{destination}+on+{dep_date}`
- 네이버항공: `https://flight.naver.com/flights/{origin}-{destination}-{dep_date_nodash}/?adult=1&returnDate={ret_date_nodash}`
- 트립닷컴: `https://kr.trip.com/flights/show?dcity={origin}&acity={destination}&ddate={dep_date}&rdate={ret_date}&flightway={RT|OW}`

**슬랙 알림 연동:** `notify/slack.py` Block Kit 섹션에 딥링크 버튼 4개 추가.

**API 연동:** `GET /api/watches/{id}/offers` 응답 스키마 `OfferOut`에 `deep_links: dict[str, str]` 필드 추가. 오퍼의 `depart_time`/`return_time`이 있으면 그 날짜, 없으면 Watch `params`의 날짜 범위 첫날을 사용.

### 4.2 C — 가격 통계 엔드포인트

**새 엔드포인트:** `GET /api/watches/{id}/stats`

```python
# 월별 최저가 집계
SELECT
    date_trunc('month', captured_at) AS month,
    MIN(min_price_krw) AS min_krw
FROM price_snapshots
WHERE watch_id = :watch_id
GROUP BY 1
ORDER BY 1
```

**응답 스키마:**
```python
class WatchStats(BaseModel):
    monthly_min: list[MonthlyMin]  # [{month: "2026-07", min_krw: 238000}, ...]
    overall_min: int | None
    overall_min_month: str | None  # "2026-07"
    data_months: int               # 데이터 있는 월 수 (3 미만이면 프론트에서 안내)
```

on-the-fly 집계. pre-computation 잡 없음 (Phase 2 초기에는 데이터가 적어 불필요).

### 4.3 D — EventAdapter 패턴

#### 4.3.1 추상 기반 클래스 (`backend/app/sources/events/base.py`)

```python
from dataclasses import dataclass
from datetime import date
from abc import ABC, abstractmethod

@dataclass
class AirlineEvent:
    source: str
    external_id: str
    title: str
    url: str
    origin: str | None
    destination: str | None
    valid_from: date | None
    valid_to: date | None
    discount_info: str | None

class EventAdapter(ABC):
    source: str  # 서브클래스에서 선언

    def __init__(self, client: RateLimitedClient):
        self._client = client

    async def fetch_events(self) -> list[AirlineEvent]:
        """policy.py 게이트 → HTTP → 파싱. 예외는 빈 리스트로 흡수."""
        ...

    @abstractmethod
    async def _parse(self, html: str) -> list[AirlineEvent]: ...
```

`fetch_events()`는 반드시 `sources/policy.py`의 robots.txt 체크 → rate limit → honest User-Agent 순서를 거친다. CLAUDE.md Rule 9: 봇 차단 우회 코드 작성 금지.

#### 4.3.2 항공사별 파서

```
backend/app/sources/events/
├── __init__.py
├── base.py           # EventAdapter, AirlineEvent
├── airbusan.py       # 에어부산: /ko/flyNEvent/ 목록 파싱
├── tway.py           # 티웨이항공: /app/promotion/event/being 파싱
├── jejuair.py        # 제주항공: /ko/event/event.do?eventNo=... 파싱
├── koreanair.py      # 대한항공: /kr/ko/promotion/list 파싱
└── flightdeal.py     # flightdeal.kr 파싱
```

각 파서는 BeautifulSoup으로 HTML 파싱. `external_id`는 이벤트 번호가 있으면 그것, 없으면 `SHA256(url)[:16]`.

#### 4.3.3 Worker 통합 (`backend/app/worker.py`)

기존 `_tick()` 함수(60초 주기)와 별개로 `_event_tick()` 추가:
- 주기: 6시간 (21600초)
- 동작: 5개 어댑터 순차 실행 → `(source, external_id)` dedup → 신규 이벤트 DB 저장 → 슬랙 알림

슬랙 알림 형식: "✈ 새 이벤트: [에어부산] 항공권 특가 30% 할인 (탑승 ~10/31)" + 원본 URL 버튼.

#### 4.3.4 신규 API 엔드포인트

**`GET /api/events`**
- 쿼리 파라미터: `source` (옵션, 항공사 필터), `active_only` (기본 true)
- 응답: `list[EventOut]`
- 정렬: `fetched_at DESC`, 최대 100건

**`EventOut` 스키마:**
```python
class EventOut(BaseModel):
    id: UUID
    source: str
    title: str
    url: str
    origin: str | None
    destination: str | None
    valid_from: date | None
    valid_to: date | None
    discount_info: str | None
    fetched_at: datetime
    is_active: bool
```

---

## 5. 프론트엔드 설계

### 5.1 B — OfferList 딥링크 버튼

`web/app/components/watch/OfferList.tsx` 수정.

각 오퍼 행 하단에 버튼 그룹 추가:
```
[🔍 스카이스캐너] [✈ 구글항공] [N 네이버항공] [🌐 트립닷컴]
```
클릭 시 `target="_blank" rel="noopener noreferrer"`. API에서 받은 `deep_links` 필드 사용.

### 5.2 C — 월별 최저가 차트

`web/app/watches/[id]/page.tsx`에 `PriceHistoryChart` 컴포넌트 추가 (기존 `PriceChart` 아래).

- 데이터 3개월 이상: 월별 막대그래프 + "X월에 가장 쌌어요 (YYY,000원)" 요약 텍스트
- 데이터 3개월 미만: "최저가 패턴 분석 중 — 데이터가 더 쌓이면 표시됩니다" 안내

`useWatchStats` 훅 신설 (`GET /api/watches/{id}/stats` 호출).

### 5.3 D — 이벤트 페이지

신규 페이지: `web/app/events/page.tsx`

레이아웃:
- 상단: 항공사 필터 탭 (전체 / 에어부산 / 티웨이 / 제주항공 / 대한항공 / flightdeal)
- 본문: `EventCard` 그리드

`EventCard` 컴포넌트 (`web/app/events/components/EventCard.tsx`):
- 항공사명 + 이벤트 제목
- 유효기간 (valid_from ~ valid_to)
- discount_info 텍스트
- "자세히 보기" → 원본 항공사 페이지로 새 탭

Nav (`web/components/layout/Nav.tsx`)에 "이벤트" 항목 추가.

---

## 6. 구현 순서 (권장)

1. **B (딥링크)** — 독립적, DB 변경 없음. 즉시 구현 가능. 슬랙 + UI 동시 반영.
2. **DB 마이그레이션** — `airline_events` 테이블 Alembic revision.
3. **D 백엔드** — EventAdapter + 파서 5개 + Worker `event_tick()` + API.
4. **D 프론트엔드** — Events 페이지 + EventCard + Nav.
5. **C** — Stats 엔드포인트 + PriceHistoryChart.

---

## 7. 테스트 전략

- **B:** `utils/deep_links.py` 순수 함수 단위 테스트. 편도/왕복 각각 검증.
- **C:** `GET /api/watches/{id}/stats` 엔드포인트 통합 테스트. PriceSnapshot fixture로 월별 집계 검증.
- **D 파서:** 각 항공사별 HTML fixture 파일 저장 (`backend/tests/fixtures/events/`) → `_parse()` 단위 테스트. 실제 사이트 호출 없음.
- **D Worker:** `event_tick()` 단위 테스트. dedup 로직 (동일 external_id 재수집 시 DB에 중복 저장 안 됨) 검증.

---

## 8. 미결 사항

| 항목 | 상태 | 비고 |
|---|---|---|
| 각 항공사 robots.txt 실제 확인 | 미확인 | 구현 전 `policy.py`로 체크 |
| 항공사별 HTML 구조 안정성 | 미확인 | 구현 시 fixture 저장 후 파싱 |
| flightdeal.kr robots.txt | 미확인 | 허용 여부 확인 후 포함 결정 |
| 슬랙 이벤트 알림 중복 방지 | 설계됨 | DB `(source, external_id)` UNIQUE 인덱스로 dedup |
| 딥링크 URL 정확도 | 미검증 | 각 사이트에서 실제 동작 확인 필요 |
