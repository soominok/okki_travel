# Claude Code 실행 프롬프트 모음

superpowers **v6.3.0** 기준. 스킬 이름은 실제 설치본에서 확인한 것이다.

---

## 0. 시작 전 준비

### 0-1. superpowers 활성화 확인

이 프로젝트에는 `.claude/settings.json`이 이미 들어 있다:

```json
{ "enabledPlugins": { "superpowers@claude-plugins-official": true } }
```

플러그인 활성화는 **세션 시작 시점에 읽힌다.** 이 파일이 추가된 뒤 Claude Code를 껐다 켜야
스킬이 잡힌다. 확인 방법 — 새 세션에서:

```
/superpowers:using-superpowers
```

이게 실행되면 준비 완료다. `Unknown skill` 이 뜨면 `/plugin` 으로 설치 상태를 다시 본다.

> 주의: superpowers는 **작업 폴더(cwd) 기준**으로 활성화된다. `trip_pick` 안에서
> `claude`를 실행해야 한다. 상위 폴더에서 실행하면 이 설정이 적용되지 않는다.

### 0-2. 이 프로젝트에서 쓸 스킬 (전체 14개 중)

| 스킬 | 언제 |
|---|---|
| `superpowers:brainstorming` | 설계 검토·의사결정. **코드 쓰기 전 필수** |
| `superpowers:writing-plans` | 스펙 → 실행 계획 문서화 |
| `superpowers:executing-plans` | 계획을 별도 세션에서 체크포인트 두고 실행 |
| `superpowers:subagent-driven-development` | 계획을 현재 세션에서 서브에이전트로 실행 |
| `superpowers:test-driven-development` | 구현 전 테스트 먼저 (P4·P5의 핵심) |
| `superpowers:dispatching-parallel-agents` | 독립 작업 2개 이상 병렬 (어댑터·화면) |
| `superpowers:systematic-debugging` | 버그·테스트 실패 시. 추측 수정 방지 |
| `superpowers:verification-before-completion` | "됐다"고 말하기 전. **증거 없이 완료 선언 금지** |
| `superpowers:requesting-code-review` | 기능 완료 후 |
| `superpowers:receiving-code-review` | 리뷰 지적을 맹목 수용하지 않고 검증 |
| `superpowers:using-git-worktrees` | 격리 작업공간 (Phase 2/3 병행 시) |
| `superpowers:finishing-a-development-branch` | 브랜치 통합 판단 |

나머지 2개(`writing-skills`, `using-superpowers`)는 이 프로젝트에서 직접 쓸 일이 없다.

### 0-3. API 키 발급 (약 20분, 전부 무료·카드 불필요)

`docs/03-DATA-SOURCES.md` §5 체크리스트대로. **P7 전까지만** 준비하면 된다.

### 0-4. Docker Desktop 실행 확인 (`docker version`)

### 0-5. 🔴 스파이크 — 코드 한 줄 쓰기 전에 반드시

설계 검토에서 나온 **가장 큰 미검증 리스크**: Travelpayouts가 "기간 범위 + 체류일수"
검색을 적은 호출로 커버하지 못하면, 이 서비스의 차별점인 유연 날짜 감시가 성립하지 않는다.
P4까지 가서 발견하면 설계를 되돌려야 한다.

토큰을 받은 뒤 30분만 투자한다. 의존성 없이 바로 돌아간다:

```bash
python spikes/travelpayouts_probe.py
```

출력 마지막의 판정이 🟢이면 설계대로 진행, 🟠이면 2단계 수집이 필수, 🔴이면 설계 변경이다.
**결과를 그대로 Claude Code에 붙여넣고** 이렇게 말한다:

```
spikes/travelpayouts_probe.py 실행 결과야. (출력 붙여넣기)

이 결과를 근거로 docs/03-DATA-SOURCES.md 의 어댑터 설계가 실현 가능한지 판단해줘.
- 그대로 가도 되면 그렇다고 말해줘
- 호출 수나 커버리지가 부족하면 어떻게 바꿔야 하는지 대안을 비교해줘
- 유연 날짜 검색을 MVP에서 빼야 한다면 솔직히 그렇게 말해줘

추측하지 말고 이 실측 데이터만 근거로.
```

---

# 두 가지 진행 방식

**Track A** — superpowers 워크플로에 맡긴다. 프롬프트 4개. 빠르지만 중간 개입이 적다.
**Track B** — 단계별로 직접 통제한다. 프롬프트 10개. 느리지만 각 단계를 검수할 수 있다.

처음이라면 **Track A로 시작해서, 계획이 마음에 안 들면 Track B의 해당 프롬프트로 갈아타는 것**을 권한다.
docs/ 가 이미 상세 스펙이라 Track A로도 정보가 부족하지 않다.

---

# Track A — superpowers 워크플로 (권장)

## A1. 설계 검토

```
/superpowers:brainstorming

docs/ 아래 5개 설계 문서와 CLAUDE.md를 전부 읽고, TripPick Phase 1 구현에 들어가기 전에
설계 검토부터 같이 하자. 내가 놓쳤을 만한 것들:

- watches.params/rules 를 jsonb로 둔 게 맞나, 정규화 테이블 대비 트레이드오프는
- 유연 날짜 검색(기간 범위 + 체류일수)을 Travelpayouts grouped_prices 로 실제로 커버 가능한가
- API와 worker 가 APScheduler 잡을 60초 폴링으로 동기화하는 방식의 취약점
- price_snapshots 와 offers 를 둘 다 두는 게 중복인가

아직 코드도 계획도 쓰지 마. 검토와 합의만.
```

> `brainstorming` 은 질문을 한 번에 하나씩 던지며 대화로 진행한다.
> 답을 대충 하지 말 것 — 여기서 정한 게 그대로 계획이 된다.

## A2. 계획 수립

```
/superpowers:writing-plans

방금 합의한 내용과 docs/ 의 스펙을 근거로 Phase 1 전체 구현 계획을 써줘.
plans/phase1.md 에 저장.

계획의 각 단계마다 반드시 포함할 것:
- 만들 파일 목록
- 그 단계가 끝났다는 걸 증명하는 실행 가능한 검증 명령
  (테스트 통과가 아니라, 실제로 돌려서 눈으로 확인하는 것)

단계 경계는 docs/02-ARCHITECTURE.md 의 레이어를 따라줘:
스캐폴딩 → 데이터모델 → 소스어댑터 → 수집엔진 → 알림 → API/스케줄러 → 프론트 → E2E
```

## A3. 실행

```
/superpowers:executing-plans

plans/phase1.md 를 실행해줘.

전제 조건:
- CLAUDE.md 의 절대 규칙 10개를 매 단계 지킬 것
- 소스 어댑터(3단계)와 수집엔진·규칙(4단계)은 superpowers:test-driven-development 로
  반드시 테스트 먼저. 이 두 단계에서 TDD를 건너뛰면 나중에 전부 다시 짜야 한다
- 각 단계 완료 선언 전에 superpowers:verification-before-completion 을 적용할 것
- 막히면 superpowers:systematic-debugging. 증상만 고치지 말 것

체크포인트마다 멈추고 나한테 보여줘.
```

> 어댑터가 여러 개라 병렬화 이득이 크다. 3단계에 진입하면 이렇게 덧붙여도 좋다:
> `이 단계의 어댑터들은 서로 독립적이니 superpowers:dispatching-parallel-agents 로 병렬 진행해줘.`

## A4. 마무리

```
/superpowers:requesting-code-review
```
그다음 리뷰 결과를 받아서:
```
/superpowers:receiving-code-review

리뷰 지적을 하나씩 검증해줘. 동의하는 것만 고치고,
동의하지 않는 건 왜 아닌지 근거를 대줘. 맹목적으로 다 반영하지 마.
```
마지막으로 Track B의 **P9(E2E 검증)** 과 **P10(보안 점검)** 을 그대로 실행한다.

---

# Track B — 단계별 수동 진행

Track A의 A3가 너무 큰 덩어리로 느껴지거나, 특정 단계만 다시 하고 싶을 때 쓴다.

## P1 — 설계 검토 & 계획

Track A의 A1 + A2와 동일. 위를 사용한다.

## P2 — 스캐폴딩 & 실행 가능한 뼈대

```
plans/phase1.md 의 1단계를 구현해줘. 목표는 "docker compose up 한 번으로 전부 뜨고,
/healthz 가 200을 반환하는 상태"야.

만들 것:
- docker-compose.yml : db(postgres:16) / api / worker / web.
  db는 healthcheck 걸고 api·worker는 db가 healthy 된 뒤 시작. 코드는 볼륨 마운트로 핫리로드.
- backend/ : uv 기반 pyproject.toml, Dockerfile,
  app/main.py (FastAPI + /healthz + CORS),
  app/config.py (pydantic-settings로 docs/02 §8 의 모든 env를 타입 있게.
                 키 없는 소스는 예외 없이 None → 나중에 disabled 처리),
  app/db.py (async engine + session dependency),
  app/worker.py (지금은 30초 하트비트 로그만 찍는 빈 스케줄러),
  structlog JSON 로깅, ruff 설정
- web/ : Next.js 15 App Router + TS strict + Tailwind v4 + shadcn/ui 초기화.
  루트 페이지는 백엔드 /healthz 를 호출해 연결 상태만 표시.
- .gitignore, git init + 첫 커밋

완료 판정은 superpowers:verification-before-completion 을 적용해줘.
docker compose up -d --build 후 curl localhost:8000/healthz 200,
localhost:3000 연결 성공 표시, worker 로그에 하트비트 —
셋 다 실제 출력을 보여주기 전까지 완료라고 하지 마.
```

## P3 — 데이터 모델 & 마이그레이션

```
docs/02-ARCHITECTURE.md §4 의 데이터 모델을 SQLAlchemy 2.0 모델 + Alembic 마이그레이션으로.

- app/models/ 에 테이블별 파일 분리 (watch, run, offer, snapshot, alert, delivery,
  source_health, place)
- 문서의 인덱스·unique 제약 빠짐없이. 모든 시각은 timestamptz, 서버사이드 now()
- price_krw 는 반드시 Integer. params/rules/raw 는 JSONB
- alerts 의 dedup unique index 는 표현식 인덱스라 Alembic 자동생성이 안 되니 직접 작성
- app/schemas/ 에 Pydantic v2 DTO. watches.params 는 kind에 따라
  FlightParams | StayParams 로 갈리는 discriminated union 으로 정의해서
  잘못된 조합이 API 레벨에서 걸러지게

검증: 컨테이너에서 alembic upgrade head 를 실제로 돌리고 psql \d watches 출력을 보여줘.
downgrade 도 동작하는지 확인.
```

## P4 — 소스 어댑터 레이어

> 이 프로젝트의 심장. 급하게 가지 말 것.

```
/superpowers:test-driven-development

docs/03-DATA-SOURCES.md 를 다시 읽고 소스 어댑터 레이어를 구현해줘.
어댑터들은 서로 독립적이니 superpowers:dispatching-parallel-agents 로 병렬 진행해도 좋아.

1. app/sources/base.py — 문서 §3 의 Protocol, FlightQuery, StayQuery, Offer, SourceResult.
   "어댑터는 절대 예외를 던지지 않고 SourceResult(ok=False, error=...) 를 반환한다"를
   docstring 에 계약으로 명시.
2. app/sources/http.py — httpx.AsyncClient 래퍼. 도메인별 토큰버킷 레이트리밋,
   tenacity 재시도(429/5xx만, 지수 백오프, 3회), 타임아웃, UA 주입, 응답 TTL 캐시.
3. app/sources/policy.py — 문서 §1 크롤 정책 게이트.
   robots.txt 파싱 후 24h 캐시, 도메인별 최소 간격, 403/429 시 자동 비활성화.
   CRAWL_ENABLED=false 면 무조건 SourceDisabled.
4. app/sources/registry.py — 등록/조회, kind 필터, priority 정렬, 키 미설정 시 auto-disabled.
5. app/sources/flight/travelpayouts.py — grouped_prices / prices_for_dates 로
   기간범위+체류일수를 최소 호출로 커버. deep_link 는 marker 포함 생성.
6. app/sources/flight/amadeus.py — OAuth2 토큰 30분 캐시, flight-offers 로 특정 날짜만
   정밀 조회 (VERIFY 단계용).
7. app/sources/stay/hotellook.py, app/sources/stay/tourapi_stay.py

테스트: tests/fixtures/<source>/*.json 에 샘플을 두고 respx 로 목킹. 네트워크 호출 없이.
반드시 커버 — 정상 / 빈결과 / 401 / 429 / 500 / 타임아웃 / 스키마가 깨진 응답.
전부 예외 없이 SourceResult 로 나와야 함. KRW 아닌 통화의 원화 정수 환산.
policy.py 가 robots.txt disallow 를 실제로 차단하는지.

fixture 는 지어내지 말고 각 API 공식 문서의 응답 예시를 근거로 만들어줘. 웹 검색해도 좋아.
야놀자/여기어때/스카이스캐너/아고다 어댑터는 만들지 마 (CLAUDE.md 9번).
```

## P5 — 수집 엔진 & 알림 규칙

```
/superpowers:test-driven-development

app/engine/ 을 구현해줘.

1. engine/rules.py — 순수 함수. DB·네트워크 금지.
   evaluate(current, history, rules) -> list[AlertCandidate]
   규칙 4종: threshold / drop_pct / all_time_low / new_best (docs/02 §4)

   테스트로 반드시 검증:
   - history 가 비었을 때 all_time_low 가 오발동하지 않는가 (min_samples 미만이면 침묵)
   - drop_pct 의 baseline(median_14d) 계산 정확성
   - 가격이 오를 때 아무 규칙도 발동하지 않는가
   - 여러 규칙 동시 만족 시 가장 높은 severity 하나로 합쳐지는가

2. engine/baseline.py — 중앙값/최저/평균. 상위 5% 이상치 제외.
3. engine/dedup.py — docs/02 §6 의 dedup_key + 쿨다운. severity 상승 시 쿨다운 무시.
   테스트: 같은 가격대 반복 → 1회만 / 5000원 버킷 경계 / 쿨다운 만료 후 재발송 /
          good→great 승격 시 즉시 발송
4. engine/collector.py — SCAN(병렬 gather) → 목표가×VERIFY_THRESHOLD_RATIO 이내면
   VERIFY(amadeus) → offers 저장 → price_snapshots 1행 → rules 평가 →
   dedup 통과분만 알림 생성 → watch_runs 기록.
   소스 하나가 실패해도 나머지로 계속 진행. 실패는 watch_runs.sources_failed 와
   source_health 에 기록. 전체를 죽이지 마.

engine 테스트는 실제 DB(트랜잭션 롤백)를 쓰고, 소스는 fake adapter 주입으로 결정적으로.
```

## P6 — 알림 채널 & 슬랙

```
app/notify/ 를 구현해줘. 핵심 목표는 "나중에 텔레그램으로 바꿀 때 도메인 코드 수정이 0인 것".

1. notify/base.py — docs/02 §6 의 NotificationMessage, Field, Notifier, DeliveryResult
2. notify/inapp.py — alerts 테이블 저장
3. notify/slack.py — Block Kit 변환. header + section(summary) + fields(2열) +
   actions(예약하기/대시보드) + context(수집시각, 소스). severity 별 이모지·색
4. notify/dispatcher.py — NOTIFY_CHANNELS 로 채널 결정, 채널별 3회 재시도,
   결과를 alert_deliveries 에 기록, QUIET_HOURS 에는 severity=great 만 통과
5. POST /api/notify/test 엔드포인트

테스트:
- 동일 NotificationMessage 하나로 slack/inapp 두 렌더러 출력 스냅샷
- Slack 이 500 을 반환해도 inapp 저장은 성공하는지 (채널 격리)
- QUIET_HOURS 경계

notify/telegram.py 는 아직 만들지 마. 대신 base.py docstring 에 전환 절차를 남겨줘.

마지막에 실제 SLACK_WEBHOOK_URL 을 .env 에 넣고 POST /api/notify/test 를 호출해서
슬랙에 메시지가 진짜 도착하는지 확인해줘 (verification-before-completion).
```

## P7 — API 라우트 & 스케줄러

```
docs/02-ARCHITECTURE.md §5 REST API 전체와 §7 스케줄러를 구현해줘.

API (app/api/routes/):
- 명세의 모든 엔드포인트. Bearer 인증은 deps.py 공통 의존성으로
- GET /api/watches 는 N+1 없이 최신 스냅샷과 24h 변동률을 한 쿼리로 조인
- POST /api/watches 는 생성 후 즉시 1회 수집을 백그라운드 트리거
- 에러는 전부 { error: { code, message, detail } }. 전역 exception handler 로 처리하고
  라우트마다 try/except 흩뿌리지 마

스케줄러 (app/scheduler/, app/worker.py) — docs/02 §7 을 그대로 따라줘:
- **job store 를 쓰지 마.** Watch당 잡을 만들지도 마. 진실의 원천은 watches.next_run_at 하나다
- APScheduler 는 60초 틱 1개 + source_health_check(15분) + cleanup_old_offers(일1회) 뿐
- 틱은 문서 §7 의 SQL 한 문장(CTE + FOR UPDATE SKIP LOCKED + next_run_at 밀기)으로.
  선점과 다음 예약이 한 트랜잭션에서 원자적으로 끝나야 해
- 지터는 random() * interval '3 minutes' 로 SQL 안에서
- Watch 생성 / 수동 실행 / 재개 는 전부 next_run_at = now() 로 통일. 경로를 늘리지 마
- collector 는 실행 시작 시 watch 가 아직 존재하고 active 인지 재확인
- 그레이스풀 셧다운

검증 — 실제로 돌려서:
1. Watch 생성 → 60초 안에 첫 수집이 도는지
2. worker 재시작 → 스케줄이 유지되는지 (DB가 진실이므로 당연히 유지돼야 함)
3. interval 1분으로 바꿔 2~3회 수집이 돌고 price_snapshots 에 행이 쌓이는지
4. worker 를 2개로 띄워도 같은 watch 가 중복 수집되지 않는지 (SKIP LOCKED 확인)
5. worker 를 10분간 정지 후 재시작 → 밀린 실행이 폭주하지 않고 1회만 도는지
   (PC 절전 복귀 시나리오. 이게 예전 설계의 coalesce 를 대체하는 부분)
6. 잘못된 API 키를 일부러 넣고 → 다른 소스로 수집이 계속되고 source_health 에 기록되는지
```

## P8 — 프론트엔드

```
docs/04-SCREENS.md 를 읽고 웹 화면을 구현해줘.
화면들은 서로 독립적이니 superpowers:dispatching-parallel-agents 를 써도 좋아.

먼저 openapi-typescript 로 web/lib/types.gen.ts 를 생성하고 npm run gen:api 로 등록.
프론트에서 API 타입을 손으로 쓰지 마.

1. S1 대시보드 — 감시 카드 그리드. 문서에 적힌 6가지가 카드에 전부 들어가야 함.
   스파크라인은 Recharts 미니차트. TanStack Query 30초 폴링
2. S3 감시 상세 — ComposedChart: 최저가 라인 + 중앙값 점선 + 목표가 ReferenceLine +
   알림 시점 마커. 30/90/전체 토글. 오퍼 테이블(소스 뱃지 포함)
3. S2 등록 3스텝 위저드 — react-hook-form + zod.
   백엔드 discriminated union 과 zod 스키마가 어긋나지 않게 주의.
   **날짜 "범위" 입력이 기본**이라는 게 이 화면의 핵심
4. S4 알림함, S5 설정(소스 상태 패널 + 슬랙 테스트 발송)

정보 밀도 우선. 다크/라이트 둘 다. 모바일 카드 1열.
로딩은 스켈레톤, 에러는 재시도 버튼 있는 인라인 배너, 빈 상태는 "첫 감시 만들기" CTA.

브라우저로 직접 열어서 렌더링과 콘솔 에러 없음을 확인하고 스크린샷 보여줘.
```

## P9 — 엔드투엔드 검증

```
/superpowers:verification-before-completion

전체가 실제로 동작하는지 처음부터 끝까지 확인해줘. 테스트 통과 말고 진짜 시나리오로.

1. docker compose down -v 로 완전 초기화 → up --build → 마이그레이션
2. 웹에서 Watch 생성: ICN→FUK, 3개월 범위, 2~3박,
   목표가는 일부러 아주 높게(900,000원) 잡아 알림이 확실히 터지게
3. 즉시 수집이 돌고 실제 항공권 가격이 들어오는지
4. 슬랙에 알림이 실제로 도착하는지 (스크린샷)
5. 알림함과 대시보드 카드에 반영되는지
6. interval 1분으로 5분간 두고 → 차트에 점이 여러 개 찍히는지
7. 같은 가격 반복 시 알림이 한 번만 오는지 (dedup)
8. worker 를 죽였다 살려도 스케줄이 유지되는지

실패하면 superpowers:systematic-debugging 으로 원인을 특정해서 고치고 다시 돌려줘.
추측으로 고치지 말고 로그/DB 를 실제로 확인해.

마지막에 docs/01-PRD.md §6 성공 기준 체크리스트를 하나씩 대조해 표로 보고.
미충족은 솔직히 미충족이라고 적어줘.
```

## P10 — 리뷰 & 하드닝

```
/superpowers:requesting-code-review
```
그다음 (내장 리뷰도 병행하면 커버리지가 넓어진다):
```
/security-review
```
받은 지적 처리:
```
/superpowers:receiving-code-review

리뷰 지적을 우선순위대로 정리해서 보여주고, 하나씩 검증해줘.
동의하는 것만 고치고 동의하지 않는 건 왜 아닌지 근거를 대줘.

추가 점검:
- .env 가 커밋에 없는지, 로그에 API 키가 찍히지 않는지
- APP_API_TOKEN 없이 /api/* 호출 시 401 인지
- 소스 응답 raw jsonb 에 개인정보가 들어가지 않는지
- offers 테이블이 무한 증가하지 않도록 정리 잡이 실제로 도는지
- README.md 의 "처음부터 세팅하는 법"이 실제 순서대로 정확한지
```

브랜치를 따로 팠다면 마무리:
```
/superpowers:finishing-a-development-branch
```

---

# 이후 (Phase 1.5 / 2 / 3)

## 텔레그램 전환

```
docs/05-ROADMAP.md 의 Phase 1.5 대로 텔레그램 알림을 추가해줘.
notify/telegram.py 하나만 만들고 기존 도메인 코드는 한 줄도 고치지 마.
고쳐야 한다면 그건 P6 의 추상화가 잘못된 거니까 먼저 그걸 알려줘.
```

## 취향 추천

```
/superpowers:brainstorming

docs/05-ROADMAP.md Phase 2 를 시작하기 전에, 먼저 지금까지 쌓인 데이터를 확인하자.
price_snapshots 가 Watch당 최소 30개 이상 쌓였는지, 기준선이 의미 있는지.
데이터가 부족하면 그렇다고 말해주고 Phase 2 는 보류하자.

충분하다면 2.1 취향 프로필 설계부터 같이 이야기하자.
place 벡터는 (a) 규칙 기반으로 먼저 갈 생각이야 — LLM 스코어링은 규칙 기반의 한계가
실제로 드러난 다음에.
```

## 여행 루트

```
/superpowers:writing-plans

docs/05-ROADMAP.md Phase 3 구현 계획을 세워줘.
특히 3.3 "루트 → Watch 역생성"이 Phase 1 스키마로 무리 없이 되는지 확인하고,
안 되면 어떤 스키마 변경이 필요한지 마이그레이션 계획까지 포함해줘.
```

Phase 2와 3을 동시에 진행하고 싶다면 격리 작업공간을 쓴다:
```
/superpowers:using-git-worktrees
```

---

# 막혔을 때

| 상황 | 이렇게 |
|---|---|
| 결과가 그럴듯한데 미심쩍다 | `/superpowers:verification-before-completion` — 실제 출력을 요구한다 |
| 버그가 반복된다 | `/superpowers:systematic-debugging` — 증상이 아니라 근본 원인 |
| 리뷰 지적을 다 받아들이는 것 같다 | `/superpowers:receiving-code-review` — 검증 후 선별 수용 |
| 코드가 비대해진다 | `/simplify` 또는 "이 파일에서 지울 수 있는 걸 찾아줘. 추가 말고 제거만" |
| 설계를 벗어난다 | "CLAUDE.md 규칙 N번을 위반했어. 다시 봐줘" |
| 범위가 번진다 | "지금은 X만. 나머지는 TODO 로 적어두고 건드리지 마" |
| 완료 판정 | "docs/01-PRD.md §6 체크리스트로 대조해서 표로 보고해줘" |
