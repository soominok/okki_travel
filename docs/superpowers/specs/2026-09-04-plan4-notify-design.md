# Plan 4 — 규칙 엔진 + 알림 스택 설계

> 참조: `docs/02-ARCHITECTURE.md` §4(데이터 모델) §6(알림 추상화) §7(스케줄러)

---

## 목표

Watch 수집이 완료된 뒤 규칙을 평가하고, 조건 충족 시 Slack 알림을 발송한다.
성공 기준: Watch를 등록 → 수집 실행 → 규칙 발화 → Slack DM/채널에 알림 도착.

---

## 현재 상태 (Plan 3 완료 기준)

- **있는 것**: `alerts`, `alert_deliveries` 테이블(마이그레이션 완료), `config.py`에 알림 관련 설정 전부 완비, `collect_watch`가 `PriceSnapshot`까지 저장함
- **없는 것**: 규칙 평가, dedup, NotificationMessage 구성, 발송 코드, collector 통합

---

## 파일 구조 (신규/변경)

```
backend/app/
├── engine/
│   ├── collector.py        MODIFY  — 스냅샷 저장 후 rules→dedup→alert→dispatch 호출
│   ├── rules.py            CREATE  — 순수 함수 규칙 평가기 4종
│   ├── baseline.py         CREATE  — median_14d / median_30d DB 조회
│   └── dedup.py            CREATE  — dedup_key 생성 + cooldown DB 체크
├── notify/
│   ├── __init__.py         CREATE
│   ├── base.py             CREATE  — NotificationMessage, Notifier Protocol, DeliveryResult
│   ├── inapp.py            CREATE  — alerts 테이블 저장
│   ├── slack.py            CREATE  — Block Kit 렌더러 + webhook POST
│   └── dispatcher.py       CREATE  — 채널 라우팅, QUIET_HOURS, 재시도, alert_deliveries 기록
├── api/routes/
│   └── alerts.py           CREATE  — GET /api/alerts, POST /api/alerts/{id}/read, POST /api/notify/test
├── schemas/
│   └── alert.py            CREATE  — AlertOut DTO
└── worker.py               MODIFY  — cleanup_old_offers(cron 4am) + source_health_check(15min) 추가
```

---

## 핵심 타입

### `engine/rules.py`

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

@dataclass(frozen=True)
class AlertCandidate:
    rule_id: str
    severity: str          # "info" | "good" | "great"
    title: str             # "ICN→FUK 238,000원 — 목표가 달성"
    body: str              # "목표가 250,000원 대비 -12,000원 (4.8% 할인)"
    best_price_krw: int
    depart_date: date | None
    deep_link: str | None

# 각 함수 시그니처
def eval_threshold(snapshot, rule: dict) -> AlertCandidate | None: ...
def eval_drop_pct(snapshot, history: list, rule: dict) -> AlertCandidate | None: ...
def eval_all_time_low(snapshot, history: list, rule: dict) -> AlertCandidate | None: ...
def eval_new_best(snapshot, history: list, rule: dict) -> AlertCandidate | None: ...
def evaluate_rules(snapshot, history: list, rules: list[dict]) -> list[AlertCandidate]: ...
```

`snapshot`은 `PriceSnapshot` ORM 인스턴스. `history`는 동일 watch의 과거 snapshots 리스트.
`rules.py`는 DB·네트워크를 전혀 건드리지 않는다 (CLAUDE.md §10).

### `engine/baseline.py`

```python
async def get_history(watch_id: UUID, days: int, session: AsyncSession) -> list[PriceSnapshot]:
    """최근 N일간 스냅샷을 시간 역순으로 반환."""
```

### `engine/dedup.py`

```python
def make_dedup_key(watch_id: UUID, rule_id: str, price_krw: int, depart_date: date | None) -> str:
    """SHA1('{watch_id}:{rule_id}:{price_krw//5000}:{depart_date}') — 5천원 버킷"""

async def is_suppressed(key: str, severity: str, cooldown_hours: int, session: AsyncSession) -> bool:
    """동일 dedup_key + cooldown 내 더 높은 severity 알림이 없으면 True(발송 금지)."""
```

### `notify/base.py`

```python
class Confidence(BaseModel):
    verified: bool
    freshness: Literal["live", "cached"]
    age_label: str        # "12분 전 실측" | "최대 7일 전 캐시"
    source: str
    coverage_pct: int | None

class NotificationMessage(BaseModel):
    severity: Literal["info", "good", "great"]
    confidence: Confidence
    title: str
    summary: str
    fields: list[Field]   # 날짜 / 항공사 / 직전가 / 최저기록
    link: str | None
    link_label: str | None
    dashboard_url: str | None
    dedup_key: str

class DeliveryResult(BaseModel):
    channel: str
    status: Literal["sent", "failed", "skipped", "deferred"]
    error: str | None = None

class Notifier(Protocol):
    channel: str
    async def send(self, msg: NotificationMessage) -> DeliveryResult: ...
```

---

## QUIET_HOURS 처리 규칙

| 채널 | 판단 | 동작 |
|---|---|---|
| inapp | 무관 | 항상 alerts 테이블에 저장 |
| slack (+ telegram 미래) | quiet_hours 내, severity ≠ great | deferred → alert_deliveries.status='deferred'. 지금은 아침 다이제스트 없음(Plan 5) |
| slack | quiet_hours 내, severity = great | 즉시 발송 |
| slack | quiet_hours 밖 | 즉시 발송 |

quiet_hours: 서버 UTC 기준. QUIET_HOURS env가 KST를 의미하므로 비교 시 +9h 오프셋 적용.

---

## collector.py 통합 포인트

`collect_watch`의 스냅샷 저장(`session.flush()`) 직후, commit 전:

```python
# 10. 규칙 평가 + 알림 (snapshot이 있을 때만)
if snap is not None:
    history = await get_history(watch_id, days=30, session=session)
    candidates = evaluate_rules(snap, history, watch.rules)
    for candidate in candidates:
        key = make_dedup_key(watch_id, candidate.rule_id, candidate.best_price_krw, candidate.depart_date)
        if await is_suppressed(key, candidate.severity, settings.alert_cooldown_hours, session):
            continue
        alert = Alert(watch_id=watch_id, rule_id=candidate.rule_id, ...)
        session.add(alert)
        await session.flush()
        msg = build_notification_message(candidate, alert, snap, watch)
        await dispatcher.dispatch(msg, alert, session=session, settings=settings)
```

commit은 기존 step 9(watch.last_run_at)와 통합해 한 번만 한다.

---

## Watch 생성 시 즉시 수집

`POST /api/watches`의 `create_watch`에서:
```python
watch.next_run_at = datetime.now(tz=UTC)  # 다음 60초 틱에 첫 수집
```

---

## Alert API

| Method | Path | 동작 |
|---|---|---|
| GET | `/api/alerts` | `?unread=true&limit=50`. unread 필터는 `read_at IS NULL` |
| POST | `/api/alerts/{id}/read` | `read_at = now()`, 204 반환 |
| POST | `/api/notify/test` | SlackNotifier로 테스트 메시지 발송. 설정 없으면 422 |

---

## Worker 추가 잡

```python
scheduler.add_job(cleanup_old_offers, "cron", hour=4, minute=0, max_instances=1)
scheduler.add_job(source_health_check, "interval", minutes=15, max_instances=1)
```

- `cleanup_old_offers`: `DELETE FROM offers WHERE collected_at < now() - interval '{OFFER_RETENTION_DAYS} days'`
- `source_health_check`: 현재는 log만 출력하는 stub (실제 헬스 체크 로직은 Plan 5)

---

## 절대 규칙 (CLAUDE.md) 재확인

- §6: 도메인 로직은 슬랙을 모른다. `AlertCandidate`는 채널 중립. 변환은 `slack.py`에서만.
- §10: `engine/rules.py`는 순수 함수만. DB·네트워크 접근 금지.
- §3: `slack_webhook_url`은 `settings.slack_webhook_url.get_secret_value()`로만 접근.
- §4: 모든 DB 시각은 UTC.

---

## 미포함 (Plan 5 이후)

- 아침 deferred 다이제스트 (묶음 발송)
- FX 환율 API 연동
- coverage heatmap / budget / sources API
- 텔레그램 Notifier
