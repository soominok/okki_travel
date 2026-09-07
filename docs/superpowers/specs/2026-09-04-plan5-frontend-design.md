# Plan 5 — 프론트엔드 5화면 설계

> 참조: `docs/04-SCREENS.md` (화면 상세 스펙), `docs/02-ARCHITECTURE.md` §5(API)

---

## 목표

Next.js 16 기반 웹 앱으로 TripPick의 5개 관리·분석 화면을 구현한다.
슬랙이 주 소비 채널이므로 웹은 **밀도 높은 정보와 빠른 조작**을 우선한다.
성공 기준: 백엔드 API 실제 연동 상태에서 Watch 등록 → 수집 → 알림 확인 동선이 동작함.

---

## 확정된 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 차트 | SVG 스파크라인 + CSS 히트맵 + Recharts 상세 차트 | 각 컴포넌트에 맞는 최적 방식 |
| API 연동 | 실제 백엔드 바로 연동 (Mock 없음) | 빠른 피드백 루프 |
| 인증 | `NEXT_PUBLIC_API_TOKEN` 환경변수 | 개인 도구, 단순함이 우선 |
| 데이터 페칭 | TanStack Query | mutation 상태 관리가 편함 |
| 컴포넌트 전략 | Client-heavy (대부분 `"use client"`) | 대시보드 특성상 어차피 클라이언트 |

---

## 스택

- **Next.js 16.3.4** + **React 19** + **TypeScript** + **Tailwind CSS 4**
- **@tanstack/react-query** — 데이터 페칭·캐싱
- **recharts** — S3 가격 히스토리 ComposedChart 전용
- **date-fns** — 날짜 계산·KST 변환 (`date-fns-tz` 포함)

추가 UI 라이브러리 없음. 컴포넌트는 전부 직접 작성.

---

## 폴더 구조

```
web/src/
├── app/
│   ├── layout.tsx                  # RootLayout — QueryProvider + ThemeProvider + Nav
│   ├── providers.tsx               # "use client" — QueryClient 설정
│   ├── page.tsx                    # S1 대시보드 /
│   ├── watches/
│   │   ├── new/page.tsx            # S2 감시 등록
│   │   └── [id]/page.tsx           # S3 감시 상세
│   ├── alerts/page.tsx             # S4 알림함
│   └── settings/page.tsx           # S5 설정
├── components/
│   ├── layout/
│   │   ├── Nav.tsx                 # 상단 네비 (대시보드/알림함/설정) + 워커 상태 점
│   │   └── WorkerDot.tsx           # 초록/주황/빨강 점 + 15초 폴링
│   ├── dashboard/
│   │   ├── WatchCard.tsx           # 감시 카드 (스파크라인, 커버리지, 신선도, 목표가)
│   │   ├── Sparkline.tsx           # SVG polyline 스파크라인 (순수 SVG, Recharts 없음)
│   │   └── RecentAlerts.tsx        # 최근 알림 2~3줄
│   ├── watch-detail/
│   │   ├── PriceChart.tsx          # Recharts ComposedChart — 최저가 + 중앙값 + 목표가 + 알림마커
│   │   ├── OfferList.tsx           # 오퍼 테이블 (가격, 날짜, 항공사, 신선도, 소스 뱃지)
│   │   ├── CoverageHeatmap.tsx     # CSS grid 히트맵 (filled/empty/cold)
│   │   └── RunLog.tsx              # 실행 로그 (접힘/펼침)
│   ├── alerts/
│   │   ├── AlertList.tsx           # 알림 목록 (미읽음 굵게 + 좌측 색 바)
│   │   └── AlertFilter.tsx         # 전체/미읽음 + Watch별 필터
│   └── settings/
│       ├── SlackPanel.tsx          # webhook 입력 + 테스트 발송
│       ├── SourceStatus.tsx        # 소스 상태 테이블
│       ├── BudgetBar.tsx           # Bright Data 크레딧 바
│       └── SamplingPolicy.tsx      # app_settings 편집 테이블
├── lib/
│   ├── api.ts                      # apiFetch() — Authorization 헤더 자동 주입
│   ├── types.gen.ts                # npm run gen:api 로 자동 생성 (FastAPI OpenAPI)
│   └── format.ts                   # formatKRW(), formatKST(), formatRelative()
└── hooks/
    ├── useWatches.ts               # useWatches, useWatch, useRunNow, usePauseWatch
    ├── useAlerts.ts                # useAlerts, useMarkRead
    ├── useWorkerStatus.ts          # 15초 폴링 (refetchInterval)
    └── useSettings.ts             # useSourceStatus, useBudget, useSlackTest
```

---

## API 연동 패턴

### `lib/api.ts`

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? '';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`,
      ...init?.headers,
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
```

### TanStack Query 훅 패턴

```typescript
// 조회
export function useWatches() {
  return useQuery({
    queryKey: ['watches'],
    queryFn: () => apiFetch<WatchOut[]>('/api/watches'),
  });
}

// mutation
export function useRunNow(watchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch(`/api/watches/${watchId}/run`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watches', watchId] }),
  });
}
```

### 타입 생성

`npm run gen:api` (기존 스크립트): FastAPI OpenAPI → `lib/types.gen.ts` 자동 생성.
생성된 타입을 훅에서 그대로 사용. 수동 인터페이스 정의 금지.

---

## 환경변수

`.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TOKEN=<백엔드 API_TOKEN과 동일한 값>
```

`.env.example`에 빈 값으로 추가.

---

## 5화면 상세

### S1. 대시보드 `/`

- `useWatches()` + `useAlerts({ limit: 3 })`
- WatchCard: 현재 최저가(크게) + SVG 스파크라인 + 커버리지 바 + 신선도 점 + 목표가 상태
- 빈 상태: "아직 데이터를 못 찾았습니다 (0/180칸)" — "항공권이 없음"으로 오해 금지
- `paused` 카드: 회색 + `일시중지` 뱃지
- `failed` 마지막 실행: 카드 상단 주황 스트립 + 실패 소스명

### S2. 감시 등록 `/watches/new`

3스텝 위저드. 한 화면에 다 넣지 않는다.
- Step 1: 큰 버튼 2개 (✈ 항공권 / 🏨 숙소, 패키지는 비활성)
- Step 2: 조건 입력 (출발지·도착지 자동완성, 날짜 범위 피커, 체류 기간 슬라이더, 요일 칩)
  - 공항 자동완성: `GET /api/meta/airports?q=후쿠` — 아직 없으면 하드코딩 상위 50개 공항 fallback
- Step 3: 알림 규칙 (목표가 입력, 체크박스 3개, 주기 셀렉트, 미리보기)
- 저장 → `POST /api/watches` + `POST /api/watches/{id}/run` → 상세 화면 이동

### S3. 감시 상세 `/watches/[id]`

- `useWatch(id)` + `useWatchRuns(id)` + `useWatchSnapshots(id)`
- PriceChart: Recharts ComposedChart
  - 최저가 Area (연두 fill) + 중앙값 점선 + 목표가 참조선 (파랑) + 🔔 알림 마커
  - 커버리지 낮은 구간: 회색 점선으로 처리
  - 기간 탭: 30일 / 90일 / 전체
- OfferList: 가격순 정렬, 소스 뱃지, 신선도 점 (● live / ○ cached), 예약하기 링크
- CoverageHeatmap: CSS grid 30열, filled(green) / empty(gray) / cold(red-muted)
- RunLog: 기본 접힘, 펼치면 실행별 상태·소요시간

### S4. 알림함 `/alerts`

- `useAlerts({ unread?: boolean, watchId?: string })`
- AlertRow: 심각도 색 바(info 회색/good 파랑/great 주황) + 굵은 미읽음 + 발송 채널 아이콘
- 행 클릭 → `/watches/{watchId}` 이동
- 읽음 처리: 행 호버 시 "읽음" 버튼, `useMarkRead` mutation

### S5. 설정 `/settings`

- SlackPanel: webhook URL 입력 + `[테스트 발송]` → `POST /api/notify/test` → 결과 인라인
- SourceStatus: `GET /api/health` 또는 내부 소스 상태 폴링 테이블
- BudgetBar: Bright Data 크레딧 진행 바 + 소진 예상일
- SamplingPolicy: `app_settings` 테이블 편집 + 저장

---

## 공통 규칙

- **가격 표시**: 항상 `₩238,000` (천 단위 구분, 원 단위 정수)
- **가격 변동**: `▼ 12,000 (-4.8%)` 초록 / `▲ 8,000 (+3.3%)` 빨강
- **시각 표시**: KST (`date-fns-tz`) + `2시간 전` 상대시간 병기
- **신선도**: `● 실측` 초록 / `○ 캐시 (최대 7일 전)` 회색
- **반응형**: `< 768px` 카드 1열, 차트 높이 축소, 오퍼 테이블 → 카드 리스트
- **다크/라이트**: `prefers-color-scheme` + 토글. `NEXT_PUBLIC_THEME` 불필요, CSS 변수로 처리

---

## 미포함 (Phase 2 이후)

- 아침 deferred 다이제스트 화면
- 텔레그램 채널 설정
- 패키지 여행 감시
- 소스 커스텀 추가
