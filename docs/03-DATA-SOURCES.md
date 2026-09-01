# 데이터 소스 전략

> **가장 중요한 문서.** 이 프로젝트가 성공하냐 실패하냐는 대부분 여기서 갈린다.

---

## 0. 결론 먼저

**"크롤링 우선"에서 "공식 API 우선"으로 방향을 바꿨다.** 이유는 아래와 같다.

원래 후보였던 스카이스캐너·아고다·야놀자·여기어때는 공통적으로:

1. **이용약관에서 자동 수집을 명시적으로 금지**한다. 개인용이라도 위반이다.
2. Cloudflare Bot Management / DataDome / Akamai 급 방어가 걸려 있다.
   Playwright로 뚫으려면 TLS 지문·캔버스 지문·행동 패턴까지 위조해야 하는데,
   이건 **봇 차단 우회**이고 이 프로젝트의 범위 밖이다.
3. 가격이 SPA 내부 API의 서명된 요청으로 오간다. 서명 로직이 수시로 바뀐다.
   → 셀렉터가 아니라 **암호화 스킴**을 계속 따라가야 한다. 유지보수 불가능.

### ⚠️ 2026년 현실 — 공식 API 생태계가 개인 개발자에게 닫혔다

이 문서의 초안은 Amadeus와 Travelpayouts를 전제로 썼다. **2026-09-01 실측 확인 결과
둘 다 원래 계획대로는 쓸 수 없었다.**

| 소스 | 상태 |
|---|---|
| ~~Amadeus Self-Service~~ | **2026-07-17 완전 폐쇄.** 신규 가입·기존 키 모두 불가. Enterprise만 잔존 |
| ~~Travelpayouts Flight **Search** API~~ | **50,000 MAU 요건.** 개인 프로젝트 불가 |
| ~~Kiwi Tequila~~ | 2024-05부터 초대제 B2B 전용 |

따라서 현재 구성은 아래와 같다. **소스를 추가·교체할 때는 반드시 실제로 확인하고 적을 것.**
"무료 티어가 있다"는 기억은 2026년 기준으로 틀린 경우가 많다.

| 소스 | 역할 | 발급 | 비용 |
|---|---|---|---|
| **Travelpayouts — Aviasales _Data_ API** | SCAN (광역 탐색) | 이메일 가입 → 즉시 토큰, **제한 없음** | 무료 |
| **Bright Data — Google Flights** | SAMPLE + VERIFY | 가입 → API 키, 카드 불필요 | 월 5,000 크레딧 무료·매월 갱신·**하드 스톱** |
| **공공데이터포털 (data.go.kr)** | 관광·숙박·날씨 | 회원가입 → 활용신청 (대부분 자동승인) | 무료 |

크롤링은 **버리지 않는다.** 다만 3순위 보조 어댑터로 내리고,
robots.txt가 허용하고 봇 방어가 없는 대상에만 적용한다.

> 상세 설계는 [`docs/superpowers/specs/2026-09-01-source-layer-design.md`](superpowers/specs/2026-09-01-source-layer-design.md) 참조.

---

## 1. 소스 우선순위 정책

```
1순위  공식 API (무료 티어)      → 가격 데이터의 주력
2순위  공공데이터 API            → 국내 관광/숙박/부가정보의 주력
3순위  공개 피드 (RSS/JSON/오픈데이터 덤프)
4순위  정중한 크롤링             → robots.txt 허용 + 봇방어 없음 + 개인용 한정
금지   봇차단 우회 / 캡차 우회 / 로그인 세션 재사용 / 회원 전용 데이터 수집
```

**4순위를 코드로 강제한다.** 크롤링 어댑터는 반드시 `CrawlPolicy` 게이트를 통과해야 하고,
게이트는 다음을 자동 검사한다.

```python
# backend/app/sources/policy.py 가 강제하는 것
- robots.txt 를 fetch 해서 해당 User-Agent/경로가 허용되는지 확인 (결과 24h 캐시)
- 도메인별 최소 요청 간격 (기본 5초), 동시성 1
- 정직한 User-Agent (봇임을 숨기지 않음) + 연락 가능한 식별자
- 429/403 수신 시 해당 도메인 지수 백오프 후 자동 비활성화
- 응답은 TTL 캐시에 저장하여 동일 요청 재발사 금지
```

정책을 통과하지 못하면 어댑터는 `SourceDisabled` 를 던지고 **조용히 건너뛴다.**
이건 선택이 아니라 아키텍처 제약이다.

### 입장 변경 — 제3자 스크래퍼 API 위탁 (2026-09-01)

위 정책은 "직접 스크래핑하지 않는다"를 뜻한다. **Bright Data는 Google Flights를 스크래핑하는
상용 서비스이므로, 이를 채택한 것은 그 원칙을 외주로 완화한 것이다.**

빠져나갈 구멍이 아니라 명시적 입장 변경으로 기록한다. 근거는 다음과 같다.

- 공식 API가 전부 닫혀 실가격 검증 수단이 남지 않았다 (§0)
- 스크래핑의 법적·기술적 부담은 해당 업체가 자기 사업으로 진다
- 우리 코드는 여전히 봇 차단 우회·캡차 우회·로그인 세션 재사용을 하지 않는다

**`CLAUDE.md` 9번 규칙(직접 크롤러를 만들지 않는다)은 그대로 유효하다.**
야놀자·여기어때·스카이스캐너·아고다 어댑터는 계속 만들지 않는다.

---

## 2. 소스 카탈로그

### 2.1 항공권 가격 (Phase 1 주력)

#### A. Travelpayouts — Aviasales Data API ⭐ 1순위

- 가입: <https://www.travelpayouts.com> → 파트너 가입 → 대시보드에서 API 토큰
- 핵심 엔드포인트 (`api.travelpayouts.com`):
  - `/aviasales/v3/prices_for_dates` — 출발/도착/기간별 최저가 목록
  - `/aviasales/v3/grouped_prices` — 월별/일별 그룹 최저가 (유연한 날짜 감시에 최적)
  - `/v1/prices/cheap` — 캐시된 최저가
- 접근 조건: **제한 없음.** 가입 후 Profile → API token 에서 바로 받는다
  (50,000 MAU 요건은 별개인 *Flight Search* API 이야기다. 혼동하지 말 것)
- ⚠️ **캐시의 성질이 이 프로젝트 설계 전체를 규정한다:**
  - 캐시는 **실제 사용자들의 검색 이력**에서 만들어진다
  - 보관 기간은 **쿼리 종류에 따라 2~7일**
  - 즉 **(a)** 가격이 최대 7일 묵었을 수 있고,
    **(b)** 아무도 검색하지 않은 날짜 조합은 **데이터가 아예 없다**
  - (b)가 "유연한 날짜 감시"라는 차별점을 직접 위협한다 → §4의 SAMPLE 단계가 이걸 메운다
- 주의: 응답 가격은 편도/통화 파라미터에 좌우된다. `currency=krw` 고정.

#### B. Bright Data — Google Flights ⭐ 검증·보강용

- 가입: <https://brightdata.com> → API 키. **카드 등록 불필요**
- 무료 티어: **월 5,000 크레딧, 매월 1일 갱신, 1요청 = 1크레딧**
- 소진 시 **하드 스톱** — 초과 청구가 구조적으로 발생하지 않는다 (개인 프로젝트에 중요)
- 제품: SERP API 또는 Web Scraper API 의 Google Flights
- ⚠️ 개인 이메일 + 카드 미등록이면 *Web Unlocker*·프록시는 막힌다.
  SERP/Web Scraper API는 해당 없음 — **가입 시 확인 필요** (스펙 §8 가정 A5)
- 두 가지 목적으로 쓴다. 어댑터는 하나이고, 구분은 예산 원장에서만 이뤄진다:
  - **VERIFY** — 목표가 근처 후보의 실가격 확인. 페이싱 없음
  - **SAMPLE** — Travelpayouts가 비운 날짜 구간 탐색. 페이싱 + 라운드로빈

#### C. 국내 공공데이터 (보조)

- 한국공항공사 `항공기 운항 현황` — 실제 운항 여부/지연 (알림 부가정보)
- 국토교통부 `항공운임 통계` — 노선별 평균 운임 기준선 (비쌈/쌈 판단 baseline)

### 2.2 숙소 (Phase 1)

#### A. Travelpayouts — Hotellook API ⭐ 1순위

- `engine.hotellook.com/api/v2/cache.json` — 도시/날짜별 캐시 최저가
- `engine.hotellook.com/api/v2/lookup.json` — 도시/호텔 ID 조회
- 무료, 토큰은 Travelpayouts와 동일.

#### B. 한국관광공사 TourAPI 4.0 ⭐ 국내 숙소 정보

- 공공데이터포털에서 `한국관광공사_국문 관광정보 서비스_GW` 활용신청
- `searchStay` — 숙박업소 목록 (contentTypeId=32)
- `detailCommon` / `detailIntro` / `detailImage` — 상세·이미지
- **가격은 없다.** 숙소 "정보"의 소스이고, 가격은 Hotellook과 결합한다.

#### C. 고캠핑 API (`GoCamping`)

- 캠핑장 정보. Phase 3 루트 기능에서 유용.

#### ❌ 야놀자 / 여기어때

- 두 곳 다 약관상 자동 수집 금지 + 봇 방어 존재. **어댑터를 만들지 않는다.**
- 대안: 딥링크만 생성해서 "이 조건으로 야놀자에서 보기" 버튼을 제공한다.
  (사용자가 직접 클릭 → 합법·안정적. 가격 비교의 마지막 1cm는 사람이 한다.)

### 2.3 부가 정보 (Phase 2~3, 전부 공공데이터)

| 데이터 | API | 용도 |
|---|---|---|
| 관광지/음식점/축제 | 한국관광공사 TourAPI 4.0 | 취향 추천, 루트 |
| 단기/중기예보 | 기상청 동네예보 API | "여행일 날씨" 알림 |
| 공연/전시 | 문화체육관광부 공연전시정보 | 루트 |
| 대기질 | 한국환경공단 에어코리아 | 여행 적합도 |
| 여행경보 | 외교부 국가별 여행경보 | 해외 목적지 경고 |

### 환율 — Phase 1에 **준비**하되 필수 여부는 P4에서 판명

초안은 "Amadeus가 EUR/USD로 응답하므로 Phase 1 필수"라고 적었으나, Amadeus가 사라져
그 근거는 소멸했다. 현재 두 소스는 통화를 지정할 수 있는 것으로 **보인다**:

- Travelpayouts: `currency=krw` 파라미터 존재
- Bright Data Google Flights: 지역·통화 설정 가능한 것으로 보이나 **확인하지 않았다**

따라서 `fx_rates` 테이블과 폴백 로직은 **만들어두되**, 두 소스가 실제로 KRW를 반환하면
경로를 타지 않는다. 테이블 유지 비용은 거의 없고, 하나라도 외화로 응답하면 즉시 필요해진다.
(스펙 §8 가정 A6)

- 소스: 한국수출입은행 환율 API (`data.go.kr` 아님, 별도 발급) 또는 한국은행 ECOS
- **주말·공휴일에는 데이터가 없다.** 반드시 다음을 구현한다:
  - 일 1회 조회 → `fx_rates(currency, rate_krw, rate_date, fetched_at)` 테이블에 저장
  - 조회 실패/휴일이면 **가장 최근 영업일 환율로 폴백** (없으면 어댑터를 disabled 처리)
  - `Offer.price_krw` 환산에 사용한 `rate_date`를 `raw`에 함께 남겨 재현 가능하게 한다
- 환산은 어댑터가 아니라 `engine/collector.py`에서 일괄 처리한다 (어댑터는 원본 통화 그대로 반환)

---

## 3. 어댑터 계약 (핵심 추상화)

모든 소스는 아래 인터페이스 하나만 만족하면 된다.
**엔진은 소스가 API인지 크롤러인지 절대 알지 못한다.**

```python
# backend/app/sources/base.py

from typing import Protocol, Literal
from datetime import date
from pydantic import BaseModel

class SourceCapability(BaseModel):
    """★ 어댑터가 자기 능력을 선언한다. fan-out은 collector가 한다.
    미검증 가정(스펙 §8)의 결과는 코드 구조가 아니라 이 값들로 흡수된다."""
    role:               Literal["scan", "verify"]
    date_range_native:  bool          # 기간 범위를 1회 호출로 받는가
    max_span_days:      int           # 1회 호출이 커버하는 최대 일수
    trip_length_filter: bool          # 체류일수를 서버가 걸러주는가
    cost_per_call:      int           # 예산 단위. travelpayouts=0, brightdata=1
    freshness:          Literal["live", "cached"]
    max_cache_age_days: int | None    # travelpayouts=7, brightdata=None
    # role은 어댑터의 *성질*이지 사용 목적이 아니다.
    # SAMPLE과 VERIFY는 둘 다 role="verify" 어댑터를 쓰는 collector 쪽 목적이며,
    # 구분은 call_budgets 의 used_sample / used_verify 에서만 이뤄진다.

class FetchRequest(BaseModel):
    """★ 호출 1회분의 일감. 어댑터가 '1회에 이만큼 된다'고 선언한 그 단위.
    3개월 범위를 몇 조각으로 쪼갤지는 collector 가 max_span_days 를 보고 정한다."""
    origin: str                  # IATA, 예: "ICN"
    destination: str
    depart_from: date
    depart_to: date              # max_span_days 이내
    nights_min: int | None       # 왕복 최소 박수 (None이면 편도)
    nights_max: int | None
    adults: int = 1
    cabin: Literal["economy", "premium", "business", "first"] = "economy"
    currency: str = "KRW"

class Offer(BaseModel):
    """모든 소스의 결과가 이 형태로 정규화된다."""
    source: str                  # "travelpayouts", "brightdata", ...
    external_id: str             # 소스 내 고유 키 (dedup 용)
    kind: Literal["flight", "stay", "package"]
    price_krw: int               # 정규화된 원화 정수
    price_original: float
    currency_original: str
    depart_date: date | None
    return_date: date | None
    carrier: str | None          # 항공사 코드 / 숙소명
    deep_link: str | None        # 예약 페이지 URL
    raw: dict                    # 원본 응답 (디버깅·재해석용, JSONB 저장)
    collected_at: datetime
    # 신선도 — 사용자에게 신뢰도를 보여주기 위해 필요 (스펙 §7)
    freshness: Literal["live", "cached"]
    cache_age_days: int | None
    observed_at: datetime | None # 소스가 관측한 시각. 안 주면 None (스펙 §8 가정 A3)

class SourceAdapter(Protocol):
    name: str
    kind: Literal["flight", "stay", "place"]
    capability: SourceCapability

    async def health(self) -> bool: ...
    async def fetch(self, req: FetchRequest) -> SourceResult: ...
```

### 어댑터 구현 규칙 (반드시 지킬 것)

1. **어댑터는 절대 예외를 밖으로 던지지 않는다.** 실패는 `SourceResult(ok=False, error=...)`로 반환.
   한 소스의 장애가 전체 수집을 죽이면 안 된다.
2. **어댑터는 DB를 모른다.** 순수 함수처럼 `FetchRequest → SourceResult` 만 한다. 저장은 엔진 책임.
   어댑터는 자기가 SCAN·SAMPLE·VERIFY 중 무엇으로 불렸는지도 알지 못한다.
3. **모든 어댑터는 fixture 기반 테스트를 가진다.** `tests/fixtures/<source>/*.json` 에
   실제 응답을 한 번 저장해두고, 정규화 로직을 네트워크 없이 검증한다.
   → 소스가 응답 포맷을 바꾸면 테스트가 먼저 깨진다.
4. **레이트리밋은 어댑터가 아니라 `HttpClient` 래퍼가 담당한다.** 도메인별 토큰 버킷.
5. 신규 소스 추가 = `sources/flight/newsource.py` 1개 + fixture + registry 한 줄. 그 외 수정 금지.
6. **fan-out 을 어댑터 안에서 하지 않는다.** 기간을 쪼개는 것은 collector 의 일이다.
   어댑터가 내부에서 루프를 돌면 호출 수가 숨어 예산을 강제할 수 없게 된다.
7. **`cost_per_call > 0` 인 어댑터는 예산 선점 없이 호출하지 않는다.** collector 가
   `call_budgets` 에서 확보한 뒤에만 부른다.

---

## 4. 3단계 수집 전략

```
[SCAN]   Travelpayouts 로 넓게 훑는다        무료·무제한·캐시가격(2~7일)
           ↓ 결과를 coverage_cells 에 반영
[SAMPLE] Bright Data 로 빈칸을 탐색한다      예산 소모·페이싱·라운드로빈
           ↓ 캐시에 없던 날짜의 실가격을 확보
[VERIFY] Bright Data 로 후보를 확인한다      예산 소모·페이싱 없음
           ↓ 목표가의 VERIFY_THRESHOLD_RATIO 이내 후보만
[ALERT]  검증 여부를 메시지에 명시하고 발송
```

**SAMPLE이 초안에는 없던 단계다.** Travelpayouts 캐시가 사용자 검색 이력 기반이라
아무도 안 본 날짜는 비어 있고, 그걸 메우지 않으면 "유연한 날짜 감시"가 인기 날짜에서만
동작한다. 예산으로 커버리지를 사는 단계다.

- SAMPLE과 VERIFY는 **같은 어댑터**를 쓴다. 구분은 예산 원장(`call_budgets`)에서만 이뤄진다
- 검증되지 않은 가격도 알림은 나간다. 대신 메시지에 "최대 7일 전 캐시"를 명시한다
- 샘플링 정책·티어·포기 규칙은 스펙 §5, 예산 관리는 스펙 §4 참조

---

## 5. 키 발급 체크리스트 (사용자가 직접 해야 하는 일)

구현 전에 아래를 받아 `.env`에 넣어둔다. **전부 무료, 카드 등록 불필요.**

- [ ] `TRAVELPAYOUTS_TOKEN` — travelpayouts.com 가입 → Profile → API token
- [ ] `TRAVELPAYOUTS_MARKER` — 동일 대시보드 (딥링크용 파트너 ID)
- [ ] `BRIGHTDATA_API_KEY` — brightdata.com 가입 → API 키. 카드 불필요
      - 가입 시 **SERP / Web Scraper API 의 Google Flights 가 카드 없이 쓰이는지 확인**할 것
      - 무료 5,000 크레딧/월. 소진 시 하드 스톱이므로 초과 청구는 없다
- [ ] `DATA_GO_KR_KEY` — data.go.kr 가입 후 아래 3개 활용신청
      - 한국관광공사_국문 관광정보 서비스_GW
      - 한국관광공사_고캠핑 정보 조회서비스
      - 기상청_단기예보 조회서비스
- [ ] `EXIM_API_KEY` — koreaexim.go.kr 인증키 신청 (환율. **Phase 1 필수**)
- [ ] `SLACK_WEBHOOK_URL` — Slack 앱 생성 → Incoming Webhooks 활성화 → 채널 선택

> `TRAVELPAYOUTS_TOKEN`은 가장 먼저 받아라. 그것만 있으면
> `python spikes/travelpayouts_probe.py`로 설계의 최대 리스크를 즉시 검증할 수 있다.

> 키가 없어도 앱은 뜬다. 해당 어댑터만 `disabled` 상태로 표시되고,
> 설정 화면의 "소스 상태" 패널에서 무엇이 빠졌는지 보여준다.
