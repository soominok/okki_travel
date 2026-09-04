// 수동 관리. 백엔드 스키마 변경 시 함께 갱신.
// 자동 생성: npm run gen:api (백엔드 실행 중일 때)

export type WatchStatus = 'active' | 'paused' | 'error';
export type WatchType = 'flight' | 'stay';
export type Freshness = 'live' | 'cached';
export type Severity = 'info' | 'good' | 'great';
export type RunStatus = 'ok' | 'partial' | 'failed';

export interface WatchRule {
  id: string;
  type: 'threshold' | 'drop_pct' | 'all_time_low' | 'new_best';
  threshold?: number;  // KRW 목표가 (threshold 타입)
  pct?: number;        // 하락 % (drop_pct 타입)
}

export interface WatchOut {
  id: string;
  name: string;
  type: WatchType;
  status: WatchStatus;
  query: Record<string, unknown>;
  rules: WatchRule[];
  interval_hours: number;
  next_run_at: string | null;  // ISO UTC
  last_run_at: string | null;
  created_at: string;
}

export interface WatchCreate {
  name: string;
  type: WatchType;
  query: Record<string, unknown>;
  rules: WatchRule[];
  interval_hours: number;
}

export interface PriceSnapshotOut {
  id: string;
  watch_id: string;
  min_price_krw: number | null;
  median_price_krw: number | null;
  coverage_pct: number | null;
  freshness: Freshness;
  source: string;
  offer_count: number;
  captured_at: string;  // ISO UTC
}

export interface OfferOut {
  id: string;
  watch_id: string;
  price_krw: number;
  price_original: number | null;
  currency: string | null;
  depart_date: string | null;   // ISO date "2024-11-14"
  return_date: string | null;
  airline: string | null;
  deep_link: string | null;
  freshness: Freshness;
  source: string;
  collected_at: string;
}

export interface AlertOut {
  id: string;
  watch_id: string;
  rule_id: string;
  severity: Severity;
  title: string;
  body: string;
  dedup_key: string;
  read_at: string | null;
  created_at: string;
}

export interface WorkerRunOut {
  id: string;
  watch_id: string;
  status: RunStatus;
  sources_ok: number;
  sources_failed: number;
  duration_ms: number | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface HealthOut {
  status: string;
  db: string;
  worker?: string;
}
