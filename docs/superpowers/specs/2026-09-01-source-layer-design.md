# 소스 계층 재설계 — 설계 스펙

- 날짜: 2026-09-01
- 상태: 승인됨 (A1 브레인스토밍 산출물)
- 대상: TripPick Phase 1의 데이터 수집 계층
- 이 문서는 `docs/02-ARCHITECTURE.md`와 `docs/03-DATA-SOURCES.md`에 대한 **델타**다.
  두 문서의 나머지 부분은 유효하다.

---

## 1. 왜 이 문서가 필요한가

`docs/03-DATA-SOURCES.md`는 두 소스를 전제로 쓰였다. 둘 다 이 프로젝트에서 쓸 수 없다.

| 소스 | 상태 (2026-09-01 확인) |
|---|---|
| **Amadeus Self-Service** | **2026-07-17 완전 폐쇄.** 신규 가입·기존 키 모두 불가. Enterprise만 잔존 |
| Travelpayouts **Flight Search** API | **50,000 MAU 요건.** 개인 프로젝트 불가 |
| Kiwi Tequila | 2024-05부터 초대제 B2B 전용 |

따라서 기존 설계의 **VERIFY 단계는 구현할 소스가 없는 상태**였다.

살아 있는 것:

| 소스 | 역할 | 조건 |
|---|---|---|
| Travelpayouts **Data** API | SCAN (광역 탐색) | 가입만 하면 제한 없음. 무료 |
| Bright Data (Google Flights) | VERIFY + SAMPLE | 월 5,000 크레딧 매월 갱신, 카드 불필요, **하드 스톱** |

Travelpayouts Data API의 성질 — 이 설계 전체를 규정한다:

> 캐시는 **실제 사용자들의 검색 이력**에서 만들어지고, 쿼리 종류에 따라 **2~7일** 보관된다.

즉 **(a)** 가격이 최대 7일 묵었을 수 있고, **(b)** 아무도 검색하지 않은 날짜 조합은 데이터가 아예 없다.
(b)가 이 서비스의 차별점인 "유연한 날짜 감시"를 직접 위협한다.

### 입장 변경 명시

`docs/03` §1은 "직접 스크래핑하지 않는다"고 선언한다. Bright Data는 Google Flights를
스크래핑하는 상용 서비스이므로, 이 결정은 **그 원칙을 외주로 완화한 것**이다.
빠져나갈 구멍이 아니라 명시적 입장 변경으로 기록한다. 직접 크롤러를 만들지 않는다는
규칙(`CLAUDE.md` 9번)은 그대로 유지된다.

---

## 2. 소스 계층 계약

**핵심 변경 하나: fan-out을 어댑터에서 collector로 옮긴다.**

기존 계약은 `search_flight(FlightQuery) -> list[Offer]`로, 어댑터가 기간 범위를 통째로
받아 내부에서 처리했다. 호출 횟수가 어댑터 안에 숨어 예산을 강제할 수 없었다.

```python
# app/sources/base.py

class SourceCapability(BaseModel):
    """어댑터가 자기 능력을 선언한다.
    미검증 가정(§8)의 결과는 코드 구조가 아니라 이 값들로 흡수된다."""
    role:               Literal["scan", "verify"]
    date_range_native:  bool          # 기간 범위를 1회 호출로 받는가
    max_span_days:      int           # 1회 호출이 커버하는 최대 일수
    trip_length_filter: bool          # 체류일수를 서버가 걸러주는가
    cost_per_call:      int           # 예산 단위. travelpayouts=0, brightdata=1
    freshness:          Literal["live", "cached"]
    max_cache_age_days: int | None    # travelpayouts=7, brightdata=None
    # role은 어댑터의 *성질*이지 사용 목적이 아니다.
    #   scan   = 무료·광역·캐시    (travelpayouts)
    #   verify = 유료·정밀·실시간  (brightdata)
    # SAMPLE과 VERIFY는 둘 다 role="verify" 어댑터를 쓰는 collector 쪽 *목적*이며,
    # 구분은 예산 원장(call_budgets의 used_sample / used_verify)에서만 이뤄진다.
    # 어댑터는 자기가 어떤 목적으로 불렸는지 알 필요가 없다.

class FetchRequest(BaseModel):
    """호출 1회분의 일감. 어댑터가 '1회에 이만큼 된다'고 선언한 그 단위."""
    origin: str
    destination: str
    depart_from: date
    depart_to: date                   # max_span_days 이내
    nights_min: int | None
    nights_max: int | None
    adults: int
    cabin: str
    currency: str = "KRW"

class SourceAdapter(Protocol):
    name: str
    capability: SourceCapability
    async def health(self) -> bool: ...
    async def fetch(self, req: FetchRequest) -> SourceResult: ...
```

기존 규칙은 유지된다: 어댑터는 예외를 밖으로 던지지 않고 `SourceResult(ok=False, error=...)`를
반환하며, DB를 모른다.

### 이 변경으로 얻는 것

collector가 `max_span_days`를 읽고 3개월 범위를 몇 조각으로 쪼갤지 **실행 전에** 안다.
따라서 예산을 선점할 수 있고, 소스의 실제 능력이 무엇으로 판명되든 collector 코드는 같다.

| 판명된 능력 | capability | collector 동작 |
|---|---|---|
| 월 단위 1회 호출 가능 | `max_span_days=31` | 3개월 → 3회 |
| 커버리지 얇음 | `max_span_days=31` + 샘플링 예산↑ | 3회 + 빈칸 보강 |
| 날짜별 호출만 가능 | `max_span_days=1` | 90회 필요함을 미리 인지 → 전수조사 대신 샘플링 |

---

## 3. Collector 흐름

```
1. PLAN      capability로 필요한 FetchRequest 목록 산출
2. SCAN      Travelpayouts로 전체 실행 (cost_per_call=0, 예산 무관)
3. RECONCILE 결과를 coverage_cells에 반영
4. BUDGET    이번 실행의 SAMPLE 몫 선점 (§4). 0행이면 SAMPLE 건너뜀 — 실패 아님
5. SAMPLE    3티어 정책으로 빈칸 탐색 (§5, Bright Data)
6. VERIFY    목표가 근처 후보 실가격 확인 (Bright Data)
             ★ 여기서 별도로 used_verify를 선점한다. 페이싱 조건이 없으므로
               4단계와 같은 문장을 쓸 수 없다. SAMPLE이 예산 부족으로 건너뛰어도
               VERIFY는 독립적으로 시도한다
7. STORE     offers 저장 + price_snapshots 1행 (coverage 포함)
8. EVALUATE  engine/rules.py 평가 → dedup → 알림
9. RECORD    watch_runs 기록 (credits_used 포함)
```

소스 하나가 실패해도 나머지로 진행한다. 실패는 `watch_runs.sources_failed`와
`source_health`에 기록한다. collector는 실행 시작 시 watch가 여전히 존재하고
`active`인지 재확인한다.

---

## 4. 호출 예산

**원칙: 예산은 쓰고 나서 세는 게 아니라 쓰기 전에 확보한다.**

### 두 소비자

| | VERIFY | SAMPLE |
|---|---|---|
| 성격 | 수요 기반 · 긴급 | 탄력적 · 안 급함 |
| 페이싱 | **없음** | 있음 |
| 분배 | 수요 순 | 활성 Watch 라운드로빈 |

VERIFY를 페이싱하지 않는 이유: 진짜 최저가가 떴는데 "오늘 할당량 소진"으로 내일 확인하는 것은
이 서비스의 존재 이유를 부정한다. 대신 SAMPLE에 상한(기본 70%)을 걸어 VERIFY 몫을 남긴다.

```
월 5,000 크레딧
├─ SAMPLE 상한  3,500  (sample_cap_ratio = 0.70)
└─ 실질 예비    1,500  VERIFY 전용으로 남는 몫
```

### 스키마

```sql
create table call_budgets (
  source           text not null,
  period_start     date not null,          -- 매월 1일 (Bright Data 갱신 주기)
  total            int  not null,
  sample_cap       int  not null,
  used_verify      int  not null default 0,
  used_sample      int  not null default 0,
  sample_day       date,
  used_sample_day  int  not null default 0,
  updated_at       timestamptz default now(),
  primary key (source, period_start)
);
```

### 선점 (멀티워커 안전)

```sql
UPDATE call_budgets
SET used_sample     = used_sample + :n,
    used_sample_day = CASE WHEN sample_day = current_date
                           THEN used_sample_day + :n ELSE :n END,
    sample_day      = current_date,
    updated_at      = now()
WHERE source = :src
  AND period_start = date_trunc('month', current_date)::date
  AND used_sample + :n <= sample_cap
  AND used_verify + used_sample + :n <= total
  AND (CASE WHEN sample_day = current_date THEN used_sample_day ELSE 0 END) + :n
      <= (sample_cap - used_sample) / GREATEST(:days_left_in_month, 1)
RETURNING used_sample;
```

0행 반환 = 예산 부족 → collector가 요청량을 줄여 재시도하거나 SAMPLE을 건너뛴다. 실패가 아니다.

마지막 조건이 **자기 보정 일일 페이싱**이다. 고정 숫자가 아니라 `남은 예산 ÷ 남은 날짜`이므로
며칠 적게 쓰면 내일 한도가 저절로 오르고, 월초 폭주가 있어도 월말까지 굶지 않는다.
Watch가 중간에 늘어도 자연히 나눠 쓴다.

VERIFY 선점은 같은 문장에서 `used_verify`만 올리고 페이싱 조건을 뺀다.

### 소진 시 동작

- **VERIFY 불가** → 알림은 계속 나가되 `unverified`로 표시 (§7)
- **SAMPLE 중단** → 조용히 멈춤. 커버리지만 얇아짐
- `source_health`에 기록, 설정 화면에 잔여 크레딧·소진 예상일 표시
- 우리 카운터가 실제보다 뒤처져 402/429를 받으면 → `used_verify = total`로 맞추고
  `disabled_until = 다음 달 1일`. 자기 치유된다

---

## 5. 커버리지 샘플링

### 탐색 공간을 명시적으로 만든다

항공 감시 하나의 공간은 `(출발일 × 체류일수)`다. 3개월 × 2~3박 = 180칸.

```sql
create table coverage_cells (
  watch_id       uuid not null references watches(id) on delete cascade,
  depart_date    date not null,
  nights         int  not null,
  last_seen_at   timestamptz,                       -- NULL = 한 번도 못 봄
  last_price_krw int,
  source         text,
  probe_count    int  not null default 0,
  last_probe_at  timestamptz,
  state          text not null default 'unknown',   -- unknown | known | cold
  primary key (watch_id, depart_date, nights)
);
create index on coverage_cells (watch_id, state, last_probe_at);
```

Watch 생성·수정 시 미리 채운다(감시당 ~180행). 범위가 바뀌면 재생성한다.

이 테이블이 있어야 **"안 찾아봤다"와 "찾아봤는데 없다"를 구분**할 수 있다.
`offers`만으로는 영원히 구분되지 않는다.

### 3티어 정책

실행당 배정받은 몫(`per_run_sample_budget`, 기본 5)을 위에서부터 쓴다.
예산이 중간에 떨어지면 남은 티어는 그냥 건너뛴다.

1. **경계 탐색** — 값이 있는 칸 바로 옆의 빈칸. 단 인접 가격이 목표가의
   `boundary_price_ratio`(기본 1.30) 이내일 때만. 싼 구간의 가장자리를 넓히는 것이
   수익률이 가장 높다. 인접이 목표가의 2배면 어차피 알림이 안 나갈 구간이므로 건너뛴다.
2. **블록 정찰** — 연속으로 빈 구간은 전부 찍지 않고 **중앙 1개만** 찍는다.
   값이 나왔고 싸면 다음 실행에서 주변으로 좁혀 들어간다. 안 나오면 해당 블록 칸들의
   `probe_count`를 올리고 뒤로 미룬다. 21칸을 21회가 아니라 1회로 정찰한다.
3. **유휴 순회** — 예산이 남으면 `last_probe_at`이 오래된 칸부터.

### 포기 규칙

`probe_count >= cold_after_probes`(기본 3)인데 계속 값이 없으면 `state='cold'`로 내리고
`cold_retry_days`(기본 7)마다만 재시도한다. 항공편 자체가 없는 날일 수 있다.

### 부수 효과

SAMPLE 결과는 Bright Data에서 오므로 `freshness='live'`다. 즉 샘플링은 커버리지를 메우면서
**신선한 가격도 함께 가져온다.** §7에서 이를 활용한다.

---

## 6. 데이터 모델 델타

`docs/02-ARCHITECTURE.md` §4 대비 변경 전체.

| 테이블 | 변경 |
|---|---|
| `call_budgets` | 신규 (§4) |
| `coverage_cells` | 신규 (§5) |
| `probe_log` | 신규 (아래) |
| `app_settings` | 신규 (아래) |
| `offers` | `freshness` `cache_age_days` `observed_at` `verified` `verify_run_id` 추가 |
| `price_snapshots` | `coverage_pct` `live_ratio` `credits_used` 추가 |
| `watches` | `last_sampled_at timestamptz` 추가 (샘플링 라운드로빈) |
| `watch_runs` | `credits_used int` 추가 |

기존 결정(Postgres 전용, UTC `timestamptz`, 원화 정수, `next_run_at` 폴링 스케줄러,
`fx_rates` 영업일 폴백)은 모두 그대로 유효하다.

### 차트가 거짓말하는 문제

```sql
alter table price_snapshots
  add column coverage_pct numeric,   -- 값이 있는 셀 비율
  add column live_ratio   numeric,   -- 그중 live 비율
  add column credits_used int;
```

`coverage_pct`가 없으면 **커버리지 하락을 가격 상승으로 오독한다.** 차트만이 아니라
규칙 엔진도 똑같이 속아 `all_time_low`가 오발동하거나 진짜 급락을 놓친다.

따라서 **규칙 평가에 커버리지 게이트**를 건다: `coverage_pct`가 직전 스냅샷 대비
`coverage_drop_gate`(기본 0.5배) 이하로 급락한 실행은 `min_price`를 신뢰하지 않고 알림을 보류한다.
`engine/rules.py`는 순수 함수 원칙을 유지한다 — 스냅샷에 값이 실려 오기만 하면 된다.

보류 사실은 `watch_runs`에 남겨 실행 로그에 표시한다. 그러지 않으면
"왜 알림이 안 왔지?"에 답할 수 없다.

### 튜닝 상수는 DB에

```sql
create table app_settings (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz default now()
);
```

```jsonc
// key = 'sampling_policy'
{
  "boundary_price_ratio":  1.30,
  "cold_after_probes":     3,
  "cold_retry_days":       7,
  "per_run_sample_budget": 5,
  "sample_cap_ratio":      0.70,
  "coverage_drop_gate":    0.5
}
```

**이 값들은 전부 추측이다.** 실데이터로 고칠 계획이므로 재배포 없이 설정 화면에서
수정 가능해야 한다.

### 고칠 근거 — `probe_log`

```sql
create table probe_log (
  id          bigserial primary key,
  watch_id    uuid not null,
  depart_date date not null,
  nights      int  not null,
  tier        text not null,          -- boundary | block | idle
  hit         bool not null,
  price_krw   int,
  credits     int  not null,
  created_at  timestamptz default now()
);
```

90일 보관. 이것이 있어야 다음 질문에 **데이터로** 답할 수 있다:

- 경계 탐색의 적중률은? → `boundary_price_ratio` 1.30이 맞는 숫자인가
- 블록 정찰이 실제로 싼 것을 찾았나, 예산만 태웠나
- `cold` 판정한 칸에 나중에 값이 생기던가 → 3회가 성급한가

probe_log 없이는 튜닝이 감이 된다.

---

## 7. 알림·화면

목적 하나: **사용자가 가격을 얼마나 믿어야 하는지 알 수 있게 한다.**

### 채널 중립 유지

`CLAUDE.md` 6번(도메인은 슬랙을 모른다)을 지키려면 신선도도 채널 중립으로 실어야 한다.

```python
class Confidence(BaseModel):
    verified:     bool
    freshness:    Literal["live", "cached"]
    age_label:    str        # "12분 전 실측" / "최대 7일 전 캐시"
    source:       str
    coverage_pct: int

class NotificationMessage(BaseModel):
    ...                      # 기존 필드 유지
    confidence: Confidence
```

슬랙은 context block, 텔레그램은 이탤릭 한 줄, 인앱은 뱃지로 렌더링한다.
도메인 코드는 어느 쪽인지 모른다.

### 슬랙 메시지

```
🔥 ICN → FUK  ₩238,000
목표가 250,000원 대비 -12,000원 · 90일 최저

출발      11/14(금) ~ 11/16(일)
항공사    JJA 진에어 · 직항
직전가    ₩251,000  ▼5.2%
커버리지  180칸 중 112칸 (62%)

[ 예약하기 ]   [ 대시보드 ]

✅ 12분 전 실측 확인 · Bright Data
```

미검증이면 마지막 줄만 바뀐다:

```
⚠️ 참고가 · 최대 7일 전 캐시 · Travelpayouts
   실제 가격은 다를 수 있습니다. 링크에서 확인하세요.
```

미검증 알림을 막지 않고 정직하게 표시하는 쪽을 택했다.

### 대시보드 카드

`docs/04-SCREENS.md` S1에 추가:

- 최저가 옆 **신선도 점** — 초록(live) / 회색(cached)
- 하단 **커버리지 미터** — `112/180칸 (62%)`
- 빈 상태 문구 변경: ~~"조건에 맞는 항공권이 없습니다"~~ →
  **"아직 데이터를 못 찾았습니다 (0/180칸)"**

전자는 사실이 아니다. 항공권이 없는 게 아니라 우리가 못 본 것이다.

### 감시 상세

`docs/04-SCREENS.md` S3에 추가:

1. 가격 차트에 **커버리지 영역**을 옅게 깔고, 커버리지가 낮았던 구간은 라인을 회색 점선으로
2. **180칸 달력 히트맵** — 값 있음 / 빈칸 / cold를 색으로. 어디가 비었는지, 샘플링이
   제대로 도는지 한눈에 보인다

히트맵 구현 시 `dataviz` 스킬을 로드해 색·접근성을 맞춘다.

### 설정 화면

```
Bright Data 크레딧
████████░░░░░░░░░░  1,847 / 5,000

이번 달 말까지 하루 약 105회 여유
검증 1,203 · 샘플링 644 · 소진 예상 없음
```

소진 임박 시 경고, 소진 시 "검증 없이 알림 발송 중" 배너.

---

## 8. 미검증 가정

**이 설계는 아래를 확인하지 않은 채 세워졌다.** `spikes/travelpayouts_probe.py`가 답한다.
P4(어댑터 구현) 착수 전에 반드시 실행한다.

| # | 가정 | 틀렸을 때 |
|---|---|---|
| A1 | Travelpayouts가 기간 범위를 1회 호출로 받는다 | `max_span_days` 하향 → 호출 수 급증 → SAMPLE 비중 상승 |
| A2 | 체류일수 필터를 서버가 해준다 | 클라이언트 필터링 → 결과 수 대비 유효 후보 감소 |
| A3 | 응답에 가격 관측 시각이 있다 | `observed_at`을 NULL로 두고 "최대 7일"로만 표기 |
| A4 | 3개월 범위에서 유효 후보가 실제로 나온다 | 유연 날짜 자체를 MVP에서 재검토 |
| A5 | Bright Data Google Flights를 개인 이메일 + 카드 없이 쓸 수 있다 | VERIFY 소스 재선정 |

A5는 가입 시점에 확인된다. A1~A4는 스파이크 출력의 판정 섹션이 답한다.

---

## 9. 변경 비용 — 나중에 무엇을 바꾸기 쉬운가

| 바꾸고 싶을 것 | 비용 |
|---|---|
| 샘플링 상수 | 설정 화면에서 즉시. 재배포 없음 |
| 감시 주기·목표가·알림 규칙 | 화면에서 즉시 |
| 소스 교체 | 파일 1개 + env |
| 샘플링 티어 정책 | `engine/sampler.py` 한 파일 |
| SCAN/VERIFY 역할 뒤집기 | capability `role` + 예산 비율 |
| **`coverage_cells` 제거** | **비쌈** — 규칙 엔진·차트·알림이 모두 참조 |
| **채널 중립 구조 포기** | **비쌈** — 텔레그램 전환 비용이 0에서 크게 오름 |

아래 둘만 되돌리기 어렵다. 나머지는 실데이터를 보고 편하게 조정한다.

---

## 10. 기존 문서에 반영할 변경

A2(계획 수립) 전에 아래를 갱신한다.

- `docs/03-DATA-SOURCES.md`
  - §2.1 Amadeus 항목 제거 → Bright Data로 교체
  - §1 정책에 "제3자 스크래퍼 API 위탁" 입장 명시
  - §3 어댑터 계약을 §2의 capability 기반으로 교체
  - §4 2단계 수집 → 3단계(SCAN/SAMPLE/VERIFY)로 갱신
  - §5 키 체크리스트에서 Amadeus 제거, Bright Data 추가
- `docs/02-ARCHITECTURE.md`
  - §2 구성도의 `[amadeus]` → `[brightdata]`
  - §4 데이터 모델에 §6의 델타 반영
  - §6 `NotificationMessage`에 `Confidence` 추가
  - §8 env에서 `AMADEUS_*` 제거, `BRIGHTDATA_API_KEY` 추가
- `docs/04-SCREENS.md` — §7의 화면 변경 반영
- `docs/01-PRD.md` §6 성공 기준에 커버리지 항목 추가
- `.env.example` — 위와 동일
- `PROMPTS.md` — P4에서 `amadeus.py` 제거, 샘플러·예산 단계 추가
- `CLAUDE.md` — 절대 규칙에 "예산 없이 유료 소스를 호출하지 않는다" 추가

---

## 11. 열린 항목

- 숙소(stay) 쪽 커버리지 모델은 이 스펙 범위 밖이다. 항공이 안정된 뒤 같은 패턴을 적용한다.
- Bright Data 초과 단가는 확인하지 않았다. 카드 미등록 시 하드 스톱이므로 현재는 무의미하다.
- Phase 2 shadow watch가 생기면 예산 경쟁이 커진다. 그때 `call_budgets`에 우선순위 개념이 필요할 수 있다.
