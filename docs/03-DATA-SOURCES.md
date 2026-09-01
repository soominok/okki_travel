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

반면 **"해외 API 발급이 번거롭다"는 걱정은 실제로는 기우**다.
아래 두 곳은 카드 등록 없이, 5~10분이면 키가 나오고, 무료 티어로 이 프로젝트에 충분하다.

| 소스 | 발급 난이도 | 비용 | 얻는 것 |
|---|---|---|---|
| **Travelpayouts (Aviasales/Hotellook)** | 이메일 가입 → 즉시 토큰 | 무료 | 노선별 최저가, 월별 최저가 캘린더, 호텔 가격 |
| **Amadeus for Developers (Self-Service)** | 가입 → 앱 생성 → 즉시 키 | 무료 티어 (월 호출 제한) | 실시간 항공 오퍼, 최저 날짜 검색, 공항/도시 코드 |
| **공공데이터포털 (data.go.kr)** | 회원가입 → 활용신청 → 대부분 자동승인 | 무료 | 관광정보, 숙박, 캠핑장, 축제, 운항정보, 날씨 |

크롤링은 **버리지 않는다.** 다만 3순위 보조 어댑터로 내리고,
robots.txt가 허용하고 봇 방어가 없는 대상에만 적용한다.

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

---

## 2. 소스 카탈로그

### 2.1 항공권 가격 (Phase 1 주력)

#### A. Travelpayouts — Aviasales Data API ⭐ 1순위

- 가입: <https://www.travelpayouts.com> → 파트너 가입 → 대시보드에서 API 토큰
- 핵심 엔드포인트 (`api.travelpayouts.com`):
  - `/aviasales/v3/prices_for_dates` — 출발/도착/기간별 최저가 목록
  - `/aviasales/v3/grouped_prices` — 월별/일별 그룹 최저가 (유연한 날짜 감시에 최적)
  - `/v1/prices/cheap` — 캐시된 최저가
- 특징: **캐시된 가격**이라 실시간성은 떨어지지만, 트렌드 추적·급락 감지에는 충분하고
  호출 제한이 관대하다. → **정기 폴링의 기본 소스로 삼는다.**
- 주의: 응답 가격은 보통 편도/통화 파라미터에 좌우된다. `currency=krw` 고정.

#### B. Amadeus Self-Service ⭐ 2순위 (검증용)

- 가입: <https://developers.amadeus.com> → My Self-Service Workspace → API Key/Secret
- 인증: OAuth2 client_credentials → `access_token` (30분) 캐싱 필수
- 핵심 엔드포인트:
  - `GET /v2/shopping/flight-offers` — 실시간 오퍼 (정확하지만 쿼터 소모 큼)
  - `GET /v1/shopping/flight-dates` — 최저가 날짜 검색
  - `GET /v1/reference-data/locations` — 공항/도시 IATA 코드 (자동완성용)
- 전략: **Travelpayouts가 "싸다"고 신호를 준 후보에 대해서만** Amadeus로 실가격 검증.
  이러면 무료 쿼터 안에서 정확도를 얻는다. (2단계 수집: `scan → verify`)

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

### ⚠️ 환율은 Phase 2가 아니라 **Phase 1 필수**다

원래 이 표에 넣어뒀는데 잘못된 분류였다. **Amadeus는 EUR/USD로 응답**하므로
P4(어댑터) 시점에 이미 환율이 필요하다. `price_krw`를 채울 수 없으면 비교 자체가 불가능하다.

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

class FlightQuery(BaseModel):
    origin: str                  # IATA, 예: "ICN"
    destination: str
    depart_from: date            # 유연 검색의 시작일
    depart_to: date              # 유연 검색의 종료일
    trip_length_min: int | None  # 왕복 최소 박수 (None이면 편도)
    trip_length_max: int | None
    adults: int = 1
    cabin: Literal["economy", "premium", "business", "first"] = "economy"
    currency: str = "KRW"

class Offer(BaseModel):
    """모든 소스의 결과가 이 형태로 정규화된다."""
    source: str                  # "travelpayouts", "amadeus", ...
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

class SourceAdapter(Protocol):
    name: str
    kind: Literal["flight", "stay", "place"]
    priority: int                # 낮을수록 먼저

    async def health(self) -> bool: ...
    async def search_flight(self, q: FlightQuery) -> list[Offer]: ...
```

### 어댑터 구현 규칙 (반드시 지킬 것)

1. **어댑터는 절대 예외를 밖으로 던지지 않는다.** 실패는 `SourceResult(ok=False, error=...)`로 반환.
   한 소스의 장애가 전체 수집을 죽이면 안 된다.
2. **어댑터는 DB를 모른다.** 순수 함수처럼 `Query → list[Offer]` 만 한다. 저장은 엔진 책임.
3. **모든 어댑터는 fixture 기반 테스트를 가진다.** `tests/fixtures/<source>/*.json` 에
   실제 응답을 한 번 저장해두고, 정규화 로직을 네트워크 없이 검증한다.
   → 소스가 응답 포맷을 바꾸면 테스트가 먼저 깨진다.
4. **레이트리밋은 어댑터가 아니라 `HttpClient` 래퍼가 담당한다.** 도메인별 토큰 버킷.
5. 신규 소스 추가 = `sources/flight/newsource.py` 1개 + fixture + registry 한 줄. 그 외 수정 금지.

---

## 4. 2단계 수집 전략 (쿼터 절약)

```
[SCAN]  Travelpayouts 로 넓게 훑는다 (무료·관대·캐시가격)
          ↓ 목표가 근처 or 급락 후보만 통과
[VERIFY] Amadeus 로 해당 날짜만 실가격 조회 (정확·쿼터 소모)
          ↓
[ALERT] 검증된 가격으로만 알림 발송
```

이 구조 덕분에 무료 쿼터로도 정확한 알림을 보낼 수 있다.
`VERIFY` 단계는 어댑터 `priority` 와 엔진의 `verify_threshold_ratio` 설정으로 제어한다.

---

## 5. 키 발급 체크리스트 (사용자가 직접 해야 하는 일)

구현 전에 아래를 받아 `.env`에 넣어둔다. **전부 무료, 카드 등록 불필요.**

- [ ] `TRAVELPAYOUTS_TOKEN` — travelpayouts.com 가입 후 대시보드
- [ ] `TRAVELPAYOUTS_MARKER` — 동일 대시보드 (딥링크용 파트너 ID)
- [ ] `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET` — developers.amadeus.com
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
