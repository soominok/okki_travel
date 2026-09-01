# 현재 상태

> **프로젝트를 다시 시작한다면 이 파일부터 읽는다.**
> 마지막 갱신: 2026-09-01

---

## 한눈에

```
단계       설계 완료 · 구현 시작 전
코드       0줄 (스파이크 스크립트 제외)
블로커     API 토큰 미발급 → 스파이크 실행 불가
다음 할 일 ① 토큰 2개 발급  ② 스파이크 실행  ③ A2 계획 수립
```

## 지금 당장 할 일

### 1. API 토큰 2개 발급 (약 15분, 무료, 카드 불필요)

- [ ] **Travelpayouts** — <https://www.travelpayouts.com> 가입 → Profile → API token
      - 이게 가장 급하다. 이것만 있으면 스파이크를 돌릴 수 있다
- [ ] **Bright Data** — <https://brightdata.com> 가입 → API 키
      - 가입 시 **SERP / Web Scraper API의 Google Flights가 카드 없이 되는지 확인**할 것
      - 안 되면 스펙 §8 가정 A5가 깨진 것 → VERIFY 소스 재선정 필요

나머지 키(`DATA_GO_KR_KEY`, `EXIM_API_KEY`, `SLACK_WEBHOOK_URL`)는 P6~P7 전까지 하면 된다.

### 2. 스파이크 실행 — **코드 쓰기 전에 반드시**

```bash
python spikes/travelpayouts_probe.py
```

이 프로젝트의 핵심 차별점("유연한 날짜 감시")이 실제로 가능한지 아직 **아무도 확인하지 않았다.**
스펙 §8의 가정 5개 중 A1~A4가 여기서 판명된다.

출력 판정에 따라:

| 판정 | 의미 | 대응 |
|---|---|---|
| 🟢 | 월 1회 호출로 충분 | 설계대로. 샘플링 예산 낮게 |
| 🟠 | 커버리지 얇음 | 설계대로. 샘플링이 제 역할 |
| 🔴 | 날짜별 호출만 가능 | `max_span_days=1`로 두고 샘플링 주력. **코드 구조는 안 바뀐다** |

결과를 그대로 붙여넣고 `PROMPTS.md` §0-5의 프롬프트를 실행한다.

### 3. A2 — 구현 계획 수립

```
/superpowers:writing-plans
```

`PROMPTS.md`의 Track A → A2 프롬프트 사용.

---

## 완료된 것

| 날짜 | 내용 |
|---|---|
| 2026-09-01 | 설계 문서 5종 작성 (`docs/01`~`05`) |
| 2026-09-01 | Claude Code 작업 규칙(`CLAUDE.md`), 구현 프롬프트(`PROMPTS.md`) |
| 2026-09-01 | superpowers v6.3.0 활성화 (user 스코프) |
| 2026-09-01 | **A1 설계 검토** — 오류 8건 발견·수정, 스케줄러 재설계 |
| 2026-09-01 | **소스 계층 재설계 스펙** — Amadeus 폐쇄 대응 |
| 2026-09-01 | 스펙 내용을 기존 문서 전체에 반영 |
| 2026-09-01 | git 초기화, 기록 체계 구축 |

## 미완료 — 큰 것부터

- [ ] **P0** 스파이크 실행 (블로커: 토큰)
- [ ] **A2** 구현 계획 수립 → `plans/phase1.md`
- [ ] **P2** 스캐폴딩 — docker-compose, FastAPI, Next.js, `/healthz`
- [ ] **P3** 데이터 모델 + Alembic 마이그레이션
- [ ] **P4** 소스 어댑터 (TDD) — travelpayouts, brightdata, budget, policy
- [ ] **P5** 수집 엔진 + 샘플러 + 규칙 (TDD)
- [ ] **P6** 알림 채널 + 슬랙
- [ ] **P7** API 라우트 + 스케줄러
- [ ] **P8** 프론트엔드 5화면
- [ ] **P9** E2E 검증
- [ ] **P10** 리뷰·하드닝

---

## 이 프로젝트를 이해하는 최단 경로

처음 보거나 오래 쉬었다 돌아왔다면 이 순서로 읽는다.

1. **[README.md](README.md)** — 이게 뭐 하는 물건인지 (3분)
2. **이 파일** — 어디까지 왔는지
3. **[docs/ISSUES.md](docs/ISSUES.md)** — 이미 밟은 지뢰. **다시 밟지 말 것** (5분)
4. **[docs/superpowers/specs/2026-09-01-source-layer-design.md](docs/superpowers/specs/2026-09-01-source-layer-design.md)**
   — 수집 계층이 왜 이렇게 생겼는지 (15분)
5. **[CLAUDE.md](CLAUDE.md)** — 절대 규칙 10개
6. **[PROMPTS.md](PROMPTS.md)** — 다음 작업을 어떻게 시작하는지

시간이 없다면 **1 → 2 → 3**만 읽어도 재개는 가능하다.

---

## 지금 알고 있는 위험

| 위험 | 상태 | 대응 |
|---|---|---|
| 유연 날짜 검색이 불가능할 수 있음 | **미확인** | 스파이크가 답한다. capability 값으로 흡수되도록 설계됨 |
| Bright Data가 카드를 요구할 수 있음 | **미확인** | 가입 시 판명. 안 되면 VERIFY 소스 재선정 |
| 여행 API가 또 닫힐 수 있음 | 진행형 | 어댑터 교체가 파일 1개. `source_health`가 죽은 소스를 자동 비활성화 |
| 상수들이 전부 추측 | 의도됨 | `app_settings`에서 재배포 없이 수정. `probe_log`가 근거 제공 |

---

## 갱신 규칙

- **이 파일은 작업 단위가 끝날 때마다 갱신한다.** 오래되면 존재 이유가 없어진다
- 시간순 상세 기록은 [docs/JOURNAL.md](docs/JOURNAL.md)
- 문제와 해결책은 [docs/ISSUES.md](docs/ISSUES.md)
- 이 파일은 **"지금 어디이고 다음에 뭘 하나"만** 담는다. 히스토리를 여기 쌓지 않는다
