# 로드맵 — Phase 2 / Phase 3

> Phase 1(MVP)에서 만든 **어댑터 레이어 · 알림 추상화 · 스냅샷 시계열**이
> 아래 두 단계의 기반이 된다. Phase 1을 대충 만들면 여기서 값을 치른다.

---

## Phase 1.5 — 텔레그램 전환 (알림이 많아지면)

작업량: 파일 1개 + env 1줄.

1. `backend/app/notify/telegram.py` — `NotificationMessage` → MarkdownV2 + inline keyboard
2. `.env`: `NOTIFY_CHANNELS=telegram,inapp`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. 봇 생성: 텔레그램에서 `@BotFather` → `/newbot` → 토큰 → 봇과 대화 시작 후
   `https://api.telegram.org/bot<TOKEN>/getUpdates`로 `chat_id` 확인

추가 이점: 텔레그램은 inline 버튼 콜백을 받을 수 있으므로
`[일시중지]` `[목표가 -10%]` 버튼으로 **알림에서 바로 조작**이 가능하다.
이걸 하려면 웹훅 수신 엔드포인트 `POST /api/telegram/webhook` 추가 (+ 시크릿 토큰 검증).

---

## Phase 2 — 취향 파악 & 추천

### 2.1 취향 프로필

**온보딩 설문 (12~15문항, A/B 선택형)**

축 예시:
| 축 | 한쪽 | 반대쪽 |
|---|---|---|
| pace | 빡빡한 일정 | 느긋한 휴식 |
| nature | 도시 | 자연 |
| food | 미식 탐방 | 끼니 해결 |
| budget | 가성비 | 경험 우선 |
| crowd | 유명 명소 | 숨은 장소 |
| activity | 액티비티 | 감상·산책 |
| culture | 역사·박물관 | 쇼핑·트렌드 |
| night | 야간 활동 | 이른 취침 |

→ `preference_profiles(user_id, vector jsonb, updated_at)` 에 8차원 [0,1] 벡터로 저장

**암묵 피드백으로 갱신** (설문보다 이쪽이 더 정확해진다)
- 알림 클릭 / 무시
- Watch로 등록한 목적지 성향
- 추천 카드의 `좋아요 / 관심없음`
→ 각 이벤트마다 벡터를 소폭 이동 (learning rate 0.05, 지수 감쇠)

### 2.2 장소 스코어링

TourAPI 관광지에 태그를 붙이고 동일 8차원 벡터를 부여한다.

```
score(place) = cosine(user_vec, place_vec) * 0.6
             + 계절_적합도 * 0.15
             + 날씨_적합도 * 0.10       # 기상청 API
             + 혼잡도_역수 * 0.10
             + 신선도(안 본 곳) * 0.05
```

place 벡터 생성 방법 (선택):
- (a) 규칙 기반: `contentTypeId` + `cat1/cat2/cat3` 코드 → 벡터 매핑 테이블. 비용 0, 결정적
- (b) LLM 기반: 장소 설명문을 Claude API로 8축 스코어링, 결과를 `places.tags`에 캐시.
  → **최초 1회만 호출하고 DB에 영구 캐시.** 매 요청마다 LLM 호출 금지
- 권장: (a)로 시작해서 애매한 것만 (b)로 보정

### 2.3 결합 알림 — 이 프로젝트의 진짜 목표

> "🔥 **당신 취향 92% 일치**한 가고시마, 지금 항공권 역대 최저 ₩198,000"

취향 스코어 상위 목적지에 대해 **자동으로 shadow watch**를 만들어 가격만 조용히 추적하다가,
`취향점수 × 가격매력도`가 임계를 넘으면 알림. 사용자가 등록하지 않은 여행을 제안하는 기능.

**새 테이블**: `preference_profiles`, `place_scores`, `recommendations`, `feedback_events`

---

## Phase 3 — 여행 루트

### 3.1 루트 만들기 (수동 편집)

- 좌: 후보 장소 리스트(취향 스코어 순) / 우: 지도(MapLibre + VWorld 타일)
- 일자별 레인에 드래그&드롭 → `routes(id, title, start_date, days)`,
  `route_items(route_id, day, order, place_id, arrive_at, stay_min)`
- 각 아이템 사이 **이동시간 자동 계산**
  - 국내: 카카오모빌리티 길찾기 API 또는 ODsay 대중교통 API
  - 해외: OSRM 자체 호스팅 또는 직선거리 × 계수 근사

### 3.2 동선 최적화

- 하루 단위 TSP. 장소 6~10개 수준이면 **완전탐색 + 2-opt**로 충분 (외부 솔버 불필요)
- 제약: 영업시간(TourAPI `restdate`/`usetime`), 식사 시간대, 하루 최대 이동시간
- "이 순서면 이동 3시간 → 재배치하면 1시간 20분" 형태로 **개선폭을 보여준다**

### 3.3 루트 → Watch 역생성

루트를 확정하면 필요한 항공/숙소 Watch를 자동 생성:
```
루트: 11/14~11/16 후쿠오카
  → flight watch: ICN→FUK, 11/14 out / 11/16 in
  → stay watch: 후쿠오카 하카타역 인근, 11/14 체크인 2박
```
Phase 1의 Watch 시스템을 그대로 재사용한다. **그래서 Phase 1 스키마를 잘 짜야 한다.**

### 3.4 여행 중 실시간 (선택)

- 당일 아침 슬랙: "오늘 일정 3곳 · 첫 이동 09:20 지하철 · 강수확률 60%, 우산 챙기세요"
- 일정 변경 감지: 휴관일/기상특보 → "2번 일정 휴관입니다. 대안 3곳 제안"

---

## 우선순위 근거

```
Phase 1  가격 알림      ← 매일 가치를 만든다. 데이터도 여기서 쌓인다
Phase 2  취향 추천      ← Phase 1의 데이터가 있어야 의미가 생긴다
Phase 3  루트           ← 여행이 확정된 후에만 쓰는 기능. 사용 빈도 가장 낮음
```

**Phase 1을 3~4주 돌려서 데이터를 쌓기 전에는 Phase 2로 넘어가지 말 것.**
기준선 데이터 없이는 추천도 알림도 다 감(感)이다.
