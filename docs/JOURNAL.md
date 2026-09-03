# 작업 일지

> 시간순 기록. **왜 그렇게 했는지**를 남긴다. 무엇을 했는지는 git log에 있다.
> 새 항목은 맨 위에 추가한다 (최신순).
>
> - 지금 상태와 다음 할 일 → [../STATUS.md](../STATUS.md)
> - 문제와 해결책 → [ISSUES.md](ISSUES.md)

---

## 2026-09-03 · 계획 2(소스 계층) Task 7 — SourceRegistry + CrawlPolicy

### sample_cap_ratio 권위: config.py (Plan 2) → app_settings DB (Plan 4 이후)

`brightdata_sample_cap_ratio`는 지금 `config.py`의 `float` 필드로 관리된다.
스펙 §6이 "재배포 없이 수정"을 요구하므로 장기적으로는 `app_settings` DB가 권위여야 한다.
Plan 4에서 collector가 `app_settings`를 읽기 시작할 때 이관한다.
Plan 2에서는 재배포가 허용되고 DB 레이어가 아직 없으므로 `config.py`에 두는 것이 맞다.

### CrawlPolicy.require_enabled() — os.environ 직접 읽기 (CLAUDE.md §3 예외 처리)

`policy.py`는 `os.environ.get("CRAWL_ENABLED")` 를 직접 읽는다.
CLAUDE.md §3은 "시크릿은 config.py 경유"이지만 `CRAWL_ENABLED`는 시크릿이 아닌
기능 플래그다. 더 중요한 이유: `get_settings()`는 `lru_cache`로 묶여 있어
`monkeypatch.setenv`가 통하지 않는다. 테스트 가능성을 희생하면서까지 config.py를
경유할 실익이 없다. Plan 4에서 crawl 어댑터 구현 시 이 구조가 바뀌면 그때 재검토.

### Bright Data API URL 검증

`BD_SERP_URL = "https://api.brightdata.com/serp"` — 대시보드 직접 확인 완료.
Task 5 구현 당시 ISSUES.md에 "미확인" 으로 남겼으나, 실제 .env 키와 테스트로
`BrightDataAdapter`가 정상 동작함을 확인 (test_adapter_brightdata.py 4개 PASS).

### 레지스트리 설계: 단순 리스트

`SourceRegistry._adapters: list[SourceAdapter]` — dict 인덱스(name→adapter, kind→adapters)
대신 단순 리스트를 선택했다. Plan 2 어댑터는 3개뿐이고 O(n) 탐색 비용이 무시 가능하다.
Plan 3 collector가 `get(kind, role)`을 반복 호출하기 시작하면 그때 최적화한다.

---

## 2026-09-01~02 · 계획 1(기반) 실행 — Task 1~7의 판단 기록

> Task 8 항목은 아래에 따로 있다. 이 항목은 **Task 1~7에서 내린 결정과 그 근거**를 담는다.
> 원본은 서브에이전트 작업 ledger(`.superpowers/`, gitignore 대상)에 있었고,
> 병합하면 사라지므로 여기로 옮긴다.

### 실행 방식

superpowers의 subagent-driven-development로 8개 태스크를 돌렸다. 태스크마다
`impl`(Sonnet)이 구현하고 `reviewer`(Opus/Sonnet)가 검토했으며, 지적이 나오면
수정 라운드를 돌고 범위를 좁힌 재리뷰로 확인했다. 커밋 31개.

### 되돌리기 어려웠던 결정들

**호스트 DB 포트를 5434로.** 이 머신의 5432·5433을 무관한 다른 프로젝트 컨테이너
(`stock_ai_db`, `budongsan_ai-db-1`)가 점유하고 있었다. 컨테이너 내부는 `db:5432`
그대로고, `.env`의 `DATABASE_URL`만 `localhost:5434`를 가리킨다. compose가
api/worker에 `environment:`로 컨테이너용 값을 따로 주입하므로 둘이 공존한다.

**시크릿을 `SecretStr`로.** `APP_API_TOKEN`이 짧으면 pydantic이 ValidationError에
**토큰 값을 평문으로** 찍고 그게 `docker compose logs`로 흘러간다. Plan 2에서 어댑터
6개가 `settings.<token>`을 `str`로 소비하기 시작하면 `.get_secret_value()`를 전부
따라다녀야 하므로 되돌리기 비용이 태스크마다 커진다 — 그래서 지금 넣었다.

**컨테이너 TZ를 UTC로.** `.env`의 `TZ=Asia/Seoul`이 api/worker에 주입돼 APScheduler가
KST로 돌고 있었다(로그에 `next run at: ... KST`). structlog는 이미 UTC라 로그와
스케줄러가 갈라진 상태였다. compose에서 `TZ: UTC`로 덮고 `AsyncIOScheduler(timezone="UTC")`를
명시했다. KST는 표시 계층에서만 붙인다(절대 규칙 4).

**`Base.metadata`에 naming convention.** 없으면 PK/FK/UNIQUE/CHECK가 Postgres 서버
생성 이름을 받고, autogenerate가 만드는 `op.drop_constraint(None, ...)` 때문에
downgrade가 실패한다. 테이블 13개가 얹히기 전이 가장 쌌다 — 나중이면 전 제약을
개명하는 마이그레이션을 따로 써야 한다.

**`live_ratio` → `live_pct`, 둘 다 0~100.** `coverage_pct`(0~100 암시)와
`live_ratio`(0~1 암시)가 인접한 숫자 칼럼인데 스케일이 갈렸다. Plan 3의 수집기가
`live/total`로 계산하면 자연히 0~1이 나오고 UI가 옆 칼럼을 보고 퍼센트로 취급하면
"0.4%"를 표시하게 된다. 이름이 그렇게 유도한다. 소비자가 없는 지금이 가장 쌌다.

**`WatchCreate.kind`에서 `package` 제거.** `WatchParams`에 `PackageParams` variant가
없어 `kind="package"`는 항상 검증 실패했다. 문제는 실패가 아니라 **실패하는 방식**이다 —
API가 만들 수 없는 값을 받아들이는 척하면 사용자는 "미지원" 대신 discriminator
에러를 받는다. Phase 2에서 `PackageParams`를 만들 때 되돌린다.

**`import "server-only"` 가드.** `web/lib/api.ts`의 `serverFetch`를 클라이언트
컴포넌트가 import하면 `APP_API_TOKEN`이 번들에 박힌다. 지금은 소비자가 0개라 안전한
것뿐이고, Plan 5가 이 파일을 쓰게 된다. 가드는 그 실수를 **빌드 타임 에러**로 만든다.

### 내가 틀렸던 판단 4건

기록해두는 이유는 같은 방식으로 또 틀리지 않기 위해서다.

1. **이벤트 루프 충돌 표면을 작다고 봤다.** "Task 3~6은 별도 세션 스코프 엔진을 쓰니
   충돌이 작다"고 판단했는데 정반대였다 — 세션 스코프 엔진이 문제를 **키운다**.
   리뷰어가 재현해서 반박했고 `poolclass=NullPool`로 해결했다.
2. **lint 면제로 덮으려 했다.** autogenerate 산출물이 ruff에 걸리자 per-file-ignores를
   지시했는데, 측정해보니 `CLAUDE.md`의 표준 명령(`ruff check --fix && ruff format`)이
   위반 7건을 전부 없앴다. 설정 예외를 만들 이유가 없었다.
3. **CASCADE 테스트 근거가 틀렸다.** "`run_id`가 CASCADE가 아니면 watches 삭제가
   FK violation으로 죽는다"고 적었는데, `offers`는 `watches`로 가는 FK가 두 개라
   `watch_id` 경로가 결과를 만들어냈다. **아무것도 검증하지 않는 테스트**를 만들게 했다
   (I-006). psql 롤백 트랜잭션으로 실측해 확인하고 고쳤다.
4. **지시문에 항목을 빠뜨렸다.** 죽은 픽스처(`anyio_backend`) 제거를 승격하기로 해놓고
   실제 지시에는 안 넣어서, 계획서에서만 지워지고 코드에는 남았다. ledger를 다시 읽다
   발견했다.

### 반복해서 드러난 실패 모드

`docs/ISSUES.md` 11건 중 절반 이상이 **"통과했지만 아무것도 확인하지 않은"** 부류다
(I-005 옛 스키마로 통과, I-006 중복 FK 경로, I-009 private route로 빌드 제외,
I-010 거짓 빨간불). 그래서 이 프로젝트에서는 **안전장치를 넣으면 일부러 깨서
정말 막히는지 확인**하는 것을 관행으로 삼았다. 롤백 트랜잭션 안에서
`ALTER TABLE ... DROP/ADD CONSTRAINT`로 안전하게 할 수 있다.

### 아직 안 정한 것 — Plan 2~4가 부딪힌다

- **`sample_cap_ratio`의 진실의 원천이 둘이다.** `config.py`(env)와 스펙 §6의
  `app_settings['sampling_policy']`(DB). 스펙은 "재배포 없이 설정 화면에서 수정"을
  요구하므로 **DB가 권위**여야 하고 env는 seed 값이다. `brightdata_monthly_credits`
  ↔ `call_budgets.total`도 같은 구조. **Plan 2 계획서에서 못 박아야 한다.**
- **`QUIET_HOURS`가 어느 시간대인지 코드가 모른다.** `.env.example` 주석은 KST라는데
  컨테이너는 UTC로 돌고 `config.py`의 `quiet_hours_start/end`는 tz 없는 naive `time`이다.
  Plan 4 디스패처가 `datetime.now(UTC).time()`과 비교하면 9시간 어긋난다.
  절대 규칙 4("KST 변환은 표시 계층에서만")는 이 경우에 답을 주지 않는다 —
  quiet hours는 표시가 아니라 **판정 로직**이다. **Plan 4 전에 정해야 한다.**
- **`app/db.py`가 임포트 시점에 엔진을 만든다.** Plan 3의 collector가 `SessionLocal`을
  직접 import하면 테스트 이음매가 없어진다. 그 전에 `get_engine()` lru_cache로 바꾸거나,
  collector가 sessionmaker를 인자로 받는 형태를 Plan 3 계획 시점에 정한다.

---

## 2026-09-01 · 계획 1(기반) 완료 — Task 8 웹 스캐폴딩

### 한 일

1. `npx create-next-app@latest` 로 `web/` 초기화 (Next 16.3.4, React 19.2.8)
2. `web/lib/api.ts` 의 `serverFetch` 와 `web/app/api/health/route.ts` 프록시로
   브라우저가 백엔드 토큰을 직접 다루지 않게 함 (A1에서 지적된 오류 4)
3. `docker-compose.yml` 의 `web` 서비스를 **처음으로** 실제 기동해 4서비스 전체 확인
4. `README.md`/`docs/02-ARCHITECTURE.md`/계획서의 "Next.js 15" 표기를 16으로 정정

### 왜 이렇게 정했나

**Next 15 → 16을 그대로 수용한 이유.** 계획서와 스펙은 작성 시점 기준 최신인 15를
전제했지만, `create-next-app@latest` 가 실제로 설치한 건 16.3.4였다. 그린필드
프로젝트에서 이미 존재하는 코드가 없으니 굳이 구버전으로 핀할 이유가 없었고,
Route Handler 컨벤션은 15→16 사이 breaking change가 없어 브리프의 코드를 그대로
쓸 수 있었다(`node_modules/next/dist/docs`로 실제 확인). "훈련 데이터 기준으로
단정하지 않는다"(I-002의 교훈)를 프론트 스택에도 그대로 적용한 것.

**검증에 curl을 쓴 이유.** 이 세션엔 브라우저 도구가 없어 브리프 Step 6의
스크린샷 요구를 curl 기반 확인으로 대체했다. `grep -o "백엔드 [^<]*"` 로
단순 매칭했더니 React 하이드레이션 주석(`<!-- -->`)이 텍스트 노드를 쪼개면서
정규식이 RSC payload까지 그리디하게 삼켜 지저분한 결과가 나왔다 — 실제 렌더링은
정상이었고(`<span class="text-sm">백엔드 <!-- -->연결됨<!-- --> · DB <!-- -->ok</span>`),
grep 패턴의 한계였을 뿐이다. 이후 세션에서 같은 패턴으로 확인할 때는
`<span class="text-sm">.*</span>` 처럼 태그 경계로 잘라야 오독하지 않는다.

**세션 중단 후 재개.** Rate limit으로 작업이 중간에 끊겼는데, 코디네이터가
"처음부터 다시 하지 마라"며 현재 상태를 정확히 짚어줘서 `web/lib/api.ts` 이후
스텝부터 이어갈 수 있었다. 재개 시점에 포트 3000을 잔여 `node.exe` 프로세스가
점유하고 있었고 첫 `up -d --build` 에서 worker가 메모리 부족으로 죽었는데,
둘 다 코드 문제가 아니라 이전 시도의 잔여 리소스 경합이었다 — 죽이고 재시도로 해결.

**pytest를 컨테이너 안에서 먼저 돌려서 헛짚었던 것.** `docker compose exec api
uv run pytest` 를 시도했다가 39개 전부 `OSError: Connect call failed`로 실패했다.
`.env`의 `DATABASE_URL`이 호스트 전용(`localhost:5434`)인데 컨테이너 안에서는
그 주소가 무의미하기 때문 — `CLAUDE.md` 명령어 목록이 애초에 `uv run pytest`를
호스트 명령으로 적어둔 걸 놓쳤다. 호스트에서 재실행해 39개 전부 통과 확인.

### 다음

계획 1(기반) 완료. `docker compose up` 한 번으로 4서비스가 뜨고, `/healthz` 프록시가
동작하고, 토큰이 클라이언트 번들에 없다는 것까지 확인됐다. 다음은 계획 2(소스 계층) —
스파이크(`python spikes/travelpayouts_probe.py`) 결과가 선행 조건이다.

---

## 2026-09-01 · A1 설계 검토와 소스 계층 재설계

### 한 일

1. superpowers v6.3.0 활성화 (I-001)
2. A1 설계 검토 — 기존 설계의 오류 8건 발견·수정
3. Amadeus 폐쇄 발견 → 소스 계층 전면 재설계
4. 스펙 작성 후 기존 문서 전체에 반영
5. git 초기화, 기록 체계 구축

### 왜 이렇게 정했나

**설계 검토를 코딩보다 먼저 한 이유.** 설계 구멍을 코드 3천 줄 쓴 다음에 발견하면
되돌리는 비용이 훨씬 크다. 실제로 이 판단이 맞았다 — Amadeus 폐쇄를 P4에서 발견했다면
어댑터 한 벌을 통째로 버렸을 것이다.

**A1에서 고친 오류 8건** (전부 `docs/02`에 반영됨)

| # | 문제 | 왜 문제인가 |
|---|---|---|
| 1 | `alerts`의 `date_trunc('hour', created_at)` unique 인덱스 | `timestamptz` 기반이라 STABLE → **Postgres가 인덱스를 못 만든다.** P3에서 즉시 실패했을 것 |
| 2 | `offers` unique에 `collected_at` 포함 | 행마다 `now()`라 튜플이 항상 달라져 **중복을 전혀 못 막음** |
| 3 | 환율을 Phase 2로 분류 | Amadeus가 EUR/USD 응답이라 P4부터 필요했음 (※ Amadeus 폐쇄로 근거는 소멸, 폴백으로만 유지) |
| 4 | 웹이 API 토큰을 직접 사용 | Next.js 클라이언트 번들에 토큰이 박힘. 로컬에선 안 보이지만 클라우드에선 사고 |
| 5 | QUIET_HOURS 억제 알림의 처리 미정 | 버리면 밤사이 최저가를 놓침 → inapp은 항상 기록 + 아침 다이제스트 |
| 6 | APScheduler job store + 60초 동기화 | **진실의 원천이 둘.** pickle 역직렬화가 깨지면 store 전체 오염 |
| 7 | `params` jsonb를 그대로 조회 | Phase 2 추천이 jsonb path 쿼리를 하게 됨 → 생성 칼럼으로 `destination` 인덱싱 |
| 8 | `snapshots`/`offers` 중복 이유 미기재 | 보관 기간 비대칭(90일 vs 영구)이 존재 이유인데 안 적혀 있어 누군가 지울 위험 |

**스케줄러를 `next_run_at` 폴링으로 바꾼 이유.** 6번의 근본 원인은 상태가 두 곳
(`watches` 테이블 + APScheduler job store)에 있다는 것이었다. 동기화를 잘 하는 대신
**동기화가 필요 없게** 만들었다. CTE + `FOR UPDATE SKIP LOCKED` 한 문장이
기존의 `jitter`/`max_instances`/`coalesce`/`misfire_grace_time`/60초 동기화를 전부 대체한다.
부수적으로 멀티워커가 공짜로 안전해지고, 클라우드 이전 시 워커 컨테이너를 없앨 수 있게 됐다.

**Amadeus 폐쇄 대응** (경위는 I-002)

사용자가 "Amadeus 사용이 가능해?"라고 물은 것이 발단이었다. 확인해보니 7주 전에 폐쇄됐고,
연달아 Travelpayouts Search API의 50k MAU 요건과 Kiwi의 초대제 전환까지 드러났다.
**공식 API 생태계가 개인 개발자에게 닫히는 중**이라는 게 이 프로젝트의 구조적 위험이다.

대응으로 세 가지를 정했다:

1. **fan-out을 어댑터에서 collector로 이동.** 어댑터가 `SourceCapability`로 자기 능력을
   선언하고, 기간을 쪼개는 일은 collector가 한다. 이러면 호출 수가 실행 전에 보이고,
   소스의 실제 능력이 무엇으로 판명되든 **capability 값만 바뀌지 코드 구조는 안 바뀐다**
2. **호출 예산 계층 신설.** 유료 소스가 생겼으므로 예산을 쓰기 전에 원자적으로 선점한다.
   VERIFY는 페이싱하지 않고(진짜 최저가를 내일 확인하는 건 서비스 부정), SAMPLE만 페이싱
3. **커버리지를 1급 개념으로.** Travelpayouts 캐시가 사용자 검색 이력 기반이라
   아무도 안 본 날짜는 비어 있다. `coverage_cells`로 "안 봤다"와 "봤는데 없다"를 구분하고,
   예산으로 빈칸을 산다

**"방어적 설계"를 택한 이유.** 스파이크(유연 날짜 검증)를 아직 못 돌렸는데,
결과를 기다리는 대신 **어떤 결과가 나와도 흡수되는 구조**를 먼저 만들기로 했다.
🟢/🟠/🔴 어느 쪽이든 `max_span_days`와 예산 비율만 달라진다.

**제3자 스크래퍼 API 채택 — 입장 변경.** `docs/03`은 "직접 스크래핑하지 않는다"고
선언했었다. Bright Data는 Google Flights를 스크래핑하는 상용 서비스이므로 이 결정은
**그 원칙을 외주로 완화한 것**이다. 빠져나갈 구멍이 아니라 명시적 입장 변경으로 기록한다.
직접 크롤러를 만들지 않는다는 규칙(`CLAUDE.md` 9번)은 그대로 유효하다.

### 남긴 미확인 가정

스펙 §8에 6개를 명시했다. 이번 세션의 교훈이 "확인 없이 단정하지 말 것"이라
**모르는 것을 모른다고 문서에 남기는 것**을 관행으로 만들었다.

### 다음

`STATUS.md`의 "지금 당장 할 일" 참조. 요약하면 토큰 발급 → 스파이크 → A2.

---

## 템플릿

```markdown
## YYYY-MM-DD · 한 줄 요약

### 한 일
1. ...

### 왜 이렇게 정했나
(대안이 있었다면 왜 그걸 안 골랐는지까지. 이게 이 문서의 핵심이다)

### 막힌 것 / 미확인
(해결했으면 ISSUES.md에도 추가)

### 다음
```
