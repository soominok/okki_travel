# 이슈와 해결

> **이미 밟은 지뢰의 목록.** 같은 데 두 번 빠지지 않기 위해 남긴다.
> 새 이슈는 맨 위에 추가한다 (최신순).

각 항목 형식: **증상 → 원인 → 해결 → 교훈**

---

## I-007 · 컨테이너 안에서 pytest 를 돌리면 39개 전부 실패한다 (오탐)

- **날짜** 2026-09-02
- **증상** `docker compose exec api uv run pytest` 가 테스트 39개 전부 DB 접속 실패로 죽는다.
  호스트에서 돌리면 전부 통과한다
- **원인** `.env` 의 `DATABASE_URL` 은 **호스트 전용**(`localhost:5434`)이다. compose 가
  api/worker 컨테이너에는 `environment:` 로 `db:5432` 를 따로 주입하는데, `pytest` 는
  `conftest.py` 의 `pytest_configure` 가 `DATABASE_URL` 을 테스트 DB URL(역시 localhost)로
  덮어쓰므로 컨테이너 안에서는 그 호스트명을 해석할 수 없다
- **해결** 테스트는 **호스트에서** 돌린다 (`cd backend && uv run pytest`). CLAUDE.md 의
  명령어 절이 이미 그렇게 문서화하고 있다
- **교훈**
  1. 이 프로젝트에서 `DATABASE_URL` 은 **소비자에 따라 값이 다르다** — 호스트 명령은
     `localhost:5434`, 컨테이너는 compose 가 주입하는 `db:5432`. 의도된 설계다(I-010 참조 불필요)
  2. "전부 실패"는 코드 결함보다 **환경 오배치**를 먼저 의심한다. 39개가 한꺼번에
     같은 이유로 죽으면 그건 테스트가 아니라 연결 문제다

---

## I-011 · alembic autogenerate 는 생성 칼럼(Computed)을 diff 하지 못한다

- **날짜** 2026-09-02
- **증상** `alembic revision --autogenerate` 실행 시 경고:
  `Computed default on watches.destination cannot be modified`
- **원인** alembic 은 `GENERATED ALWAYS AS (...) STORED` 칼럼의 **식(expression)을 비교하지
  못한다.** 최초 생성은 정상 반영되지만, 이후 식을 바꾸면 **감지하지 못하고 조용히 넘어간다**
- **해결** 지금은 조치 불필요(최초 생성은 정상). 다만 **식을 바꿀 때는 수동 마이그레이션**을
  써야 한다
- **교훈**
  1. **Phase 2 에서 이걸 밟는다.** 취향 추천이 `watches.destination` 을 쓰는데,
     `StayParams` 에는 `destination` 이 없어 stay watch 는 이 칼럼이 항상 NULL 이다.
     숙소 목적지도 인덱싱하려면 생성 칼럼 식을 `kind` 별로 분기해야 하고,
     **그때 autogenerate 는 아무것도 만들어주지 않는다**
  2. 생성 칼럼·확장(EXTENSION)·트리거처럼 autogenerate 가 못 보는 것들은
     마이그레이션을 손으로 쓴다는 것을 전제로 설계한다

---

## I-010 · compose up 직후 pytest 를 돌리면 전부 에러난다 (거짓 빨간불)

- **날짜** 2026-09-02
- **증상** `docker compose up -d --build` 직후 `uv run pytest` → **39 errors**.
  실행 시간이 평소 5초에서 **40초**로 늘어난 것이 단서였다. 잠시 후 재실행하니 39 passed
- **원인** db 컨테이너가 아직 기동 중인데 호스트 측 pytest 가 바로 붙었다.
  compose 의 healthcheck 는 api/worker 의 `depends_on` 만 막아주고,
  **호스트에서 도는 pytest 는 그 게이트를 통과하지 않는다**
- **해결** db 가 준비될 때까지 기다렸다가 재실행. 근본 해결은 `_ensure_test_database`
  픽스처에 접속 재시도를 넣는 것 (deferred)
- **교훈**
  1. **거짓 빨간불도 비용이다.** 코드를 의심하며 시간을 쓰게 만든다
  2. I-007 과 같은 신호: **전부 한꺼번에 같은 이유로 죽으면 환경을 먼저 본다.**
     여기에 더해 **실행 시간이 비정상적으로 길면 타임아웃/재시도를 의심**한다
  3. `docker compose up` 과 `pytest` 사이에는 db 준비 대기가 필요하다

---

## I-009 · 안전장치 검증이 조용히 통과했다 — Next.js private route 때문

- **날짜** 2026-09-02
- **증상** `import "server-only"` 가드가 실제로 빌드를 막는지 확인하려고 `"use client"`
  컴포넌트에서 `serverFetch` 를 import 하는 임시 라우트를 만들었는데, **빌드가 그냥 통과했다**
- **원인** 폴더명을 `_guard-test` 로 지었다. Next.js 는 `_` 로 시작하는 폴더를
  **private route** 로 취급해 라우팅에서 제외하므로, 그 파일이 아예 빌드 대상이 아니었다
- **해결** `guard-test` 로 바꿔 재시도 → `Error: 'server-only' cannot be imported from a
  Client Component module` 로 정상 실패 확인
- **교훈**
  1. **I-006 과 같은 실패 모드다.** "검증했는데 통과했다"가 곧 "안전하다"는 아니다.
     검증 코드가 **실행되기는 했는지**를 먼저 의심해야 한다
  2. 안전장치를 넣었으면 **일부러 깨서 정말 막히는지** 본다. 이번엔 그 확인 지시가
     있었기 때문에 두 번째 시도까지 갔고, 없었다면 "가드 넣었습니다"로 끝났을 것이다
  3. Next.js 에서 `_` 접두사 폴더는 빌드에서 빠진다. 테스트용 라우트를 만들 때 주의

---

## I-008 · docker compose up --build 가 메모리 부족으로 worker 를 죽인다

- **날짜** 2026-09-02
- **증상** `docker compose up -d --build` 중 worker 가 `OSError: Cannot allocate memory`
  로 종료. 그리고 호스트에 남은 stray `node.exe` 가 포트 3000 을 점유해 web 이 못 뜸
- **원인** 4서비스를 동시에 빌드하면 메모리 경합이 난다. 이전 세션의 dev 서버 프로세스가
  살아남아 포트를 잡고 있는 것은 별개 문제
- **해결** 잔여 프로세스를 죽이고 `docker compose down -v && up -d --build` 재시도
- **교훈** 4서비스 동시 빌드가 실패하면 **코드 문제로 오해하지 말 것.** 잔여 프로세스
  확인(`netstat`/`Get-Process node`) 후 `down -v` 로 완전 초기화하고 재시도한다

---

## I-006 · 중복 FK 경로 때문에 CASCADE 테스트가 아무것도 검증하지 않았다

- **날짜** 2026-09-01
- **증상** `watches → watch_runs → offers` 3단 CASCADE 를 검증한다고 만든 테스트가,
  `offers.run_id` 의 `ondelete` 를 `NO ACTION` 으로 바꿔도 **그대로 초록**이었다
- **원인** `offers` 는 `watches` 로 가는 FK 를 **두 개** 갖는다 — `run_id`(watch_runs 경유)와
  `watch_id`(직접). `DELETE FROM watches` 는 `watch_id` 경로만으로 offers 를 지워버리므로
  `run_id` 의 설정은 검사 대상조차 되지 않는다.
  (Postgres 의 NOT DEFERRABLE 제약은 행이 아니라 **문장 단위**로 검사된다)
- **실측 확인**
  ```
  run_id=NO ACTION + DELETE FROM watches     -> 성공, offers 0행   (테스트 초록 = 거짓)
  run_id=NO ACTION + DELETE FROM watch_runs  -> FK violation       (테스트 빨간불 = 참)
  run_id=CASCADE   + DELETE FROM watch_runs  -> 성공, offers 0행   (테스트 초록 = 참)
  ```
- **해결** 중간 테이블(`watch_runs`)을 **직접** 삭제해 검증 대상 경로를 고립시킨다
- **교훈**
  1. **CASCADE 테스트는 검증하려는 FK 경로를 고립시켜야 한다.** 최상위 부모를 지우면
     중복 경로가 결과를 만들어내고, 테스트는 통과하지만 아무것도 보장하지 않는다
  2. 테스트를 만들 때 **"이 제약을 깨면 정말 빨간불이 되는가"를 실제로 깨봐야 한다.**
     롤백 트랜잭션 안에서 `ALTER TABLE ... DROP/ADD CONSTRAINT` 로 안전하게 확인할 수 있다
  3. 이 프로젝트의 여러 테이블이 `watches` 를 직접 참조하므로(`offers`, `alerts`,
     `coverage_cells`) 같은 함정이 반복된다. 중간 테이블 경유 FK 를 검증할 때 특히 주의

---

## I-005 · 마이그레이션 파일을 직접 고치면 테스트가 옛 스키마로 통과한다

- **날짜** 2026-09-01
- **증상** 마이그레이션 파일을 수정했는데 `alembic upgrade head` 가 아무것도 하지 않고,
  테스트는 **옛 스키마 위에서 초록으로 통과**했다
- **원인** alembic 은 `alembic_version` 테이블의 리비전 ID 로만 적용 여부를 판단한다.
  리비전 ID 를 바꾸지 않고 파일 내용만 고치면 이미 스탬프된 DB 에는 no-op 이다.
  개발 DB 뿐 아니라 **테스트 DB(`trippick_test`)도 따로 스탬프를 갖는다**
- **해결** `migrated_engine` 픽스처가 매 세션 `alembic downgrade base && upgrade head`
  왕복을 돌게 바꿨다. 파일과 스키마가 항상 일치하고, 부수적으로 downgrade 경로가
  매번 실행돼 `op.drop_constraint(None, ...)` 류의 결함이 즉시 드러난다
- **교훈**
  1. **초기 개발 중 마이그레이션 파일 직접 수정은 유효한 선택이지만**(아직 공유 전이라
     새 ALTER 마이그레이션을 쌓는 것보다 깨끗하다), **스탬프된 DB 를 되감아야 한다**
  2. 더 나쁜 건 "고쳤는데 테스트가 통과한다"는 상태다. 실패보다 **조용한 거짓 초록**이
     위험하다 — 그래서 사람 절차(잊기 쉬움)가 아니라 픽스처(항상 실행)로 막았다
  3. 공유된 뒤에는 절대 직접 수정하지 않는다. 그때는 새 마이그레이션이 유일한 답이다

---

## I-004 · Bash 도구에서 PowerShell here-string이 그대로 커밋 메시지에 들어감

- **날짜** 2026-09-01
- **증상** `git log`에 커밋 제목이 `@ docs: ...`로 찍힘
- **원인** Bash 도구를 쓰면서 PowerShell 문법 `@'...'@`을 사용. 이 환경은 Bash와 PowerShell
  두 도구가 **각각 다른 문법**을 쓰는데 이를 혼동함
- **해결** `git commit --amend -F - <<'MSG' ... MSG` heredoc으로 재작성
- **교훈** Bash 도구 = heredoc(`<<'EOF'`), PowerShell 도구 = here-string(`@'...'@`).
  섞으면 조용히 잘못된 결과가 남는다. 커밋 메시지처럼 나중에 고치기 번거로운 곳에서 특히 주의

---

## I-003 · 작업 디렉터리가 `cd` 이후 유지되어 상대 경로가 깨짐

- **날짜** 2026-09-01
- **증상** `cd docs/superpowers/specs` 후 다음 Bash 호출에서 같은 상대 경로를 쓰자
  `No such file or directory`
- **원인** Bash 도구는 **호출 간 작업 디렉터리가 유지된다.** 이전 `cd`가 살아 있었음
- **해결** 절대 경로 사용. 또는 매 호출 시작에 `cd <프로젝트 루트>`
- **교훈** 상대 경로를 쓰려면 매번 루트로 이동부터 한다. `SendUserFile`도 같은 함정을 밟았다

---

## I-002 · 설계에 넣은 API가 이미 폐쇄돼 있었음 ★ 가장 비싼 실수

- **날짜** 2026-09-01
- **증상** 설계서가 **가입 자체가 불가능한 서비스**로 사용자를 안내하고 있었음.
  VERIFY 단계 전체가 구현 불가능한 상태
- **원인** 훈련 데이터 기준의 기억("Amadeus Self-Service는 무료 티어가 있다")으로 설계.
  **확인하지 않고 단정함**
- **실제 확인 결과** (2026-09-01 웹 검색·브라우저 확인)
  | 소스 | 상태 |
  |---|---|
  | Amadeus Self-Service | **2026-07-17 완전 폐쇄.** 신규 가입·기존 키 모두 불가 |
  | Travelpayouts Flight **Search** API | **50,000 MAU 요건.** 개인 프로젝트 불가 |
  | Travelpayouts **Data** API | ✅ 가입만 하면 제한 없음. 우리가 쓸 것 |
  | Kiwi Tequila | 2024-05부터 초대제 B2B 전용 |
  | SearchAPI.io | 100회 일회성. 부적합 |
  | Bright Data | ✅ 월 5,000 크레딧 갱신, 카드 불필요, 하드 스톱 |
- **해결** VERIFY를 Bright Data로 교체. 소스 계층을 capability 선언 기반으로 재설계해
  **다음 폐쇄 때는 파일 1개 교체로 끝나도록** 함
- **교훈**
  1. **외부 서비스는 반드시 실제로 확인하고 적는다.** 여행 API 생태계는 2024~2026년에
     개인 개발자에게 빠르게 닫히는 중이다. 기억은 거의 틀린다
  2. 같은 벤더 안에서도 **API 종류마다 접근 조건이 다르다** (Travelpayouts Search vs Data).
     벤더 이름만 보고 판단하지 말 것
  3. 소스 교체 비용을 낮추는 설계가 선택이 아니라 **필수**다

---

## I-001 · superpowers 플러그인이 하위 폴더에서 로드되지 않음

- **날짜** 2026-09-01
- **증상** 플러그인을 설치했는데도 `/superpowers:*` 스킬이 목록에 안 뜸.
  `Unknown skill: superpowers:using-superpowers`
- **원인** 플러그인이 **project 스코프**로 상위 폴더(`.../vibecoding`)에 묶여 설치됨.
  작업 디렉터리인 `trip_pick`에서는 "미설치"로 취급됨.
  플러그인 활성화는 **cwd 기준**이다
- **해결** user 스코프로 재설치 + `~/.claude/settings.json`의 `enabledPlugins`에 추가.
  프로젝트 의존성 명시를 위해 `trip_pick/.claude/settings.json`도 유지
- **교훈**
  1. 플러그인 활성화는 **세션 시작 시점에 한 번** 읽힌다. 설정을 고쳤으면 **재시작 필수**
  2. `installed_plugins.json`의 `scope`와 `projectPath`를 확인하면 원인이 바로 보인다
  3. **설정 파일을 읽는 것으로는 "이 세션에서 되는지"를 알 수 없다.**
     실제로 스킬을 호출해봐야 한다

---

## 템플릿

새 이슈는 아래 형식으로 맨 위에 추가한다.

```markdown
## I-00N · 한 줄 요약

- **날짜** YYYY-MM-DD
- **증상** 무엇이 잘못 보였나 (에러 메시지 그대로)
- **원인** 실제 원인. 추측이면 추측이라고 적을 것
- **해결** 무엇을 했나
- **교훈** 다음에 어떻게 피하나. 이게 이 문서의 존재 이유다
```
