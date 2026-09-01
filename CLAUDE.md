# TripPick — Claude Code 작업 규칙

개인용 여행 가격 감시·알림 서비스. 설계서는 `docs/` 에 있다.
**코드를 쓰기 전에 관련 설계 문서를 먼저 읽는다.**

| 문서 | 언제 읽나 |
|---|---|
| `docs/01-PRD.md` | 범위·성공기준이 헷갈릴 때 |
| `docs/02-ARCHITECTURE.md` | 스택·폴더구조·DB스키마·API명세·알림추상화 |
| `docs/03-DATA-SOURCES.md` | **소스/어댑터/크롤링 작업 전 반드시** |
| `docs/04-SCREENS.md` | 프론트 작업 전 |
| `docs/05-ROADMAP.md` | Phase 2/3 관련 판단 |

---

## 절대 규칙

1. **SQLite를 쓰지 않는다.** Postgres 전용. 클라우드 이전이 확정된 프로젝트다.
2. **모든 상태는 DB에.** 로컬 파일·인메모리 전역변수에 상태를 두지 않는다.
3. **시크릿은 `app/config.py`(pydantic-settings) 경유.** 코드에 키 하드코딩 금지.
   `os.getenv()`를 코드 곳곳에 흩뿌리지 않는다.
4. **DB 시각은 전부 UTC (`timestamptz`).** KST 변환은 표시 계층에서만.
5. **가격은 원화 정수(`int`)로 저장.** float 금지. 원본 통화·금액은 별도 컬럼에 보존.
6. **도메인 로직은 슬랙을 모른다.** 알림은 항상 `NotificationMessage`를 만들고,
   채널 변환은 `notify/*.py` 렌더러에서만 한다.
7. **어댑터는 예외를 밖으로 던지지 않는다.** `SourceResult(ok=False, error=...)`로 반환.
   한 소스 장애가 전체 수집을 죽이면 안 된다.
8. **어댑터는 DB를 모른다.** `Query → list[Offer]` 순수 변환만. 저장은 `engine/collector.py`.
9. **봇 차단 우회·캡차 우회·로그인 세션 재사용 코드를 작성하지 않는다.**
   야놀자/여기어때/스카이스캐너/아고다 크롤러를 만들지 않는다. (`docs/03` 참조)
   크롤링 어댑터는 반드시 `sources/policy.py` 게이트를 통과해야 한다.
10. **`engine/rules.py`는 순수 함수만.** DB·네트워크 접근 금지. 그래야 테스트가 빠르다.

## 작업 방식

이 프로젝트는 **superpowers v6.3.0** 을 전제로 한다 (`.claude/settings.json`에서 활성화).
아래 상황에서는 해당 스킬을 반드시 사용한다.

| 상황 | 스킬 |
|---|---|
| 설계·기능 방향을 정할 때 (코드 쓰기 전) | `superpowers:brainstorming` |
| 다단계 작업 착수 전 | `superpowers:writing-plans` |
| 계획 실행 | `superpowers:executing-plans` / `superpowers:subagent-driven-development` |
| 규칙 엔진·어댑터 정규화·dedup 구현 | `superpowers:test-driven-development` |
| 독립 작업 2개 이상 (어댑터 여러 개, 화면 여러 개) | `superpowers:dispatching-parallel-agents` |
| 버그·테스트 실패 | `superpowers:systematic-debugging` |
| "됐다"고 말하기 직전 | `superpowers:verification-before-completion` |
| 기능 완료 후 리뷰 | `superpowers:requesting-code-review` |
| 리뷰 지적 처리 | `superpowers:receiving-code-review` |

그 위에 이 프로젝트 고유의 규칙:

- **계획 먼저.** 파일 3개 이상을 건드리는 작업은 계획을 세우고 승인받은 뒤 착수한다.
- **테스트 먼저.** 규칙 엔진·어댑터 정규화·dedup 로직은 TDD로 간다.
  실패하는 테스트 → 구현 → 통과 순서를 지킨다.
- **어댑터 테스트는 fixture로.** 실제 API를 테스트에서 호출하지 않는다.
  `backend/tests/fixtures/<source>/*.json`에 실제 응답을 한 번 저장해두고 `respx`로 목킹.
- **완료 선언 전에 실제로 돌려본다.** `docker compose up` → 엔드포인트 호출 →
  결과 확인까지 하고 나서 "됐다"고 말한다. 타입체크·테스트 통과만으로는 완료가 아니다.
- 작업이 끝나면 `docs/`에서 달라진 내용(스키마 변경 등)을 함께 갱신한다.

## 명령어

```bash
# 전체 스택
docker compose up -d --build
docker compose logs -f worker

# 백엔드 (backend/)
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run python -m app.worker
uv run pytest -q
uv run ruff check --fix . && uv run ruff format .

# 프론트 (web/)
npm run dev
npm run typecheck
npm run gen:api        # FastAPI OpenAPI → lib/types.gen.ts
```

## 커밋

- 한 커밋 = 한 논리 단위. 백엔드·프론트를 한 커밋에 섞지 않는다.
- 메시지는 한국어 또는 영어 일관되게. `feat: 슬랙 알림 디스패처 추가` 형식.
- `.env`는 절대 커밋하지 않는다. `.env.example`만 갱신한다.

## 자주 하는 실수 (사전 차단)

- APScheduler job store에 Watch당 잡을 만들고 DB와 동기화하는 것
  → 진실의 원천이 둘이 되고 pickle 역직렬화가 깨진다. `watches.next_run_at` 폴링만 쓴다 (`docs/02` §7)
- 환율 변환을 나중 일로 미루는 것 → Amadeus는 EUR/USD로 응답한다. P4부터 이미 필요하다.
  수출입은행 API는 주말·공휴일에 데이터가 없으니 마지막 영업일 환율 폴백이 필수
- 가격 비교 시 통화 정규화를 잊는 것 → USD 300을 KRW 300으로 취급
- `dedup_key`에 가격을 원 단위 그대로 넣는 것 → 1원만 변해도 알림 폭탄.
  반드시 5,000원 단위 버킷으로 뭉갠다
- 유연 날짜 검색에서 날짜 조합을 전부 API 호출하는 것
  → grouped/calendar 엔드포인트를 써서 **1회 호출로 기간 전체**를 받는다
