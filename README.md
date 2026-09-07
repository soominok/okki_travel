# TripPick

> 가고 싶은 여행의 조건을 등록해두면, 값이 떨어졌을 때 슬랙으로 먼저 알려주는 개인용 서비스.

**현재 상태: 설계 완료, 구현 전.** `PROMPTS.md`의 P1부터 시작하면 된다.

---

## 이게 뭔가

- 항공권/숙소 **감시 조건**을 등록 (날짜를 고정하지 않고 "10~12월 중 아무 주말이나" 식의 범위 지정)
- 워커가 주기적으로 여러 소스에서 가격을 수집 → 시계열로 축적
- 목표가 도달 / 평소 대비 급락 / 역대 최저 등 규칙에 걸리면 **슬랙 알림**
- 웹 대시보드에서 가격 히스토리와 오퍼 비교

---

## 문서

| 파일 | 내용 |
|---|---|
| [docs/01-PRD.md](docs/01-PRD.md) | 범위, 시나리오, 성공 기준 |
| [docs/02-ARCHITECTURE.md](docs/02-ARCHITECTURE.md) | 스택, 구성도, 폴더구조, DB 스키마, API 명세, 알림 추상화, 스케줄러, env |
| [docs/03-DATA-SOURCES.md](docs/03-DATA-SOURCES.md) | **소스 전략 — 가장 중요.** 왜 크롤링 대신 공식 API인지, 어댑터 계약 |
| [docs/04-SCREENS.md](docs/04-SCREENS.md) | 화면 5종 설계 |
| [docs/05-ROADMAP.md](docs/05-ROADMAP.md) | 텔레그램 전환, 취향 추천, 여행 루트 |
| [CLAUDE.md](CLAUDE.md) | Claude Code 상시 규칙 (절대 규칙 10개) |
| [PROMPTS.md](PROMPTS.md) | **구현용 프롬프트** — Track A(superpowers 워크플로) / Track B(단계별 수동) |

---

## 시작하기

### 1. 키 발급 (약 20분, 전부 무료·카드 불필요)

`docs/03-DATA-SOURCES.md` §5 체크리스트 참고.

- [Travelpayouts](https://www.travelpayouts.com) — Aviasales **Data** API. 광역 탐색(SCAN). 무료·제한 없음
- [Bright Data](https://brightdata.com) — Google Flights. 실가격 검증(VERIFY)과 커버리지 보강(SAMPLE).
  월 5,000 크레딧 무료·카드 불필요·소진 시 하드 스톱
- [공공데이터포털](https://www.data.go.kr) — 관광정보, 날씨
- Slack Incoming Webhook — 알림 수신

> ⚠️ 초안에 있던 **Amadeus Self-Service는 2026-07-17 폐쇄**되어 사용할 수 없다.
> Travelpayouts의 *Flight Search* API도 50,000 MAU 요건이 있어 개인 프로젝트는 불가하다
> (우리가 쓰는 *Data* API는 제한 없음). 자세한 경위는
> [소스 계층 재설계 스펙](docs/superpowers/specs/2026-09-01-source-layer-design.md) §1 참조.

### 2. 구현

Docker Desktop을 켜고, **`trip_pick` 폴더 안에서** Claude Code를 실행한다.
(superpowers 플러그인이 이 폴더 기준으로 활성화되어 있다 — `.claude/settings.json`)

`PROMPTS.md`를 열고 **Track A의 A1**부터 붙여넣는다.
A1은 설계 검토, A2는 계획 수립이고 실제 코딩은 A3부터다.
단계를 더 잘게 통제하고 싶으면 같은 문서의 Track B(P2~P10)를 쓴다.

### 3. 실행 (구현 후)

```bash
cp .env.example .env      # 키 채우기
docker compose up -d --build
docker compose exec api alembic upgrade head
```

- 웹: http://localhost:3000
- API 문서: http://localhost:8000/docs

---

## 기술 스택

**백엔드** Python 3.12 · FastAPI · SQLAlchemy 2.0(async) · Alembic · APScheduler · httpx · Postgres 16
**프론트** Next.js 16 · TypeScript · Tailwind v4 · shadcn/ui · TanStack Query · Recharts
**인프라** docker-compose 4서비스 (`db` / `api` / `worker` / `web`)

로컬 실행으로 시작하되, 클라우드 이전을 전제로 설계했다 (Postgres 전용, 상태는 전부 DB,
설정은 전부 env, JSON 로깅). 이전 시 재작성은 없다.

---

## 수집 원칙

이 프로젝트는 **봇 차단 우회·캡차 우회·로그인 세션 재사용을 하지 않는다.**
스카이스캐너·아고다·야놀자·여기어때는 약관상 자동 수집을 금지하고 강한 봇 방어를 두고 있어
어댑터를 만들지 않는다. 대신 딥링크 버튼으로 사용자가 직접 확인하게 한다.

크롤링 어댑터는 `sources/policy.py` 게이트(robots.txt 준수, 도메인별 최소 간격,
정직한 User-Agent, 403/429 시 자동 비활성화)를 통과해야만 동작한다.
이유와 상세는 [docs/03-DATA-SOURCES.md](docs/03-DATA-SOURCES.md) §1 참조.
