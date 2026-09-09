// 수동 관리. 백엔드 스키마 변경 시 함께 갱신.
// 자동 생성: npm run gen:api (백엔드 실행 중일 때)

export type WatchStatus = 'active' | 'paused' | 'error';
export type WatchKind = 'flight' | 'stay';
export type Freshness = 'live' | 'cached';
export type Severity = 'info' | 'good' | 'great';
export type RunStatus = 'ok' | 'partial' | 'failed';

// ---------- params ----------

export interface FlightParams {
  kind: 'flight';
  origin: string;
  destination: string;
  depart_from: string;   // ISO date "2024-09-01"
  depart_to: string;
  nights_min?: number | null;
  nights_max?: number | null;
  weekday_preference?: string[];
  adults?: number;
  cabin?: 'economy' | 'premium' | 'business' | 'first';
  direct_only?: boolean;
}

export type WatchParams = FlightParams;

// ---------- rules ----------

export interface ThresholdRule {
  id: string;
  type: 'threshold';
  price_krw: number;
}

export interface DropPctRule {
  id: string;
  type: 'drop_pct';
  pct: number;
  baseline?: 'median_14d' | 'median_30d';
}

export interface AllTimeLowRule {
  id: string;
  type: 'all_time_low';
  min_samples?: number;
}

export interface NewBestRule {
  id: string;
  type: 'new_best';
  improve_krw?: number;
}

export type WatchRule = ThresholdRule | DropPctRule | AllTimeLowRule | NewBestRule;

// ---------- watch ----------

export interface WatchOut {
  id: string;
  kind: WatchKind;
  title: string;
  params: WatchParams;
  rules: WatchRule[];
  interval_min: number;
  status: WatchStatus;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

export interface WatchCreate {
  kind: WatchKind;
  title: string;
  params: WatchParams;
  rules: WatchRule[];
  interval_min: number;
}

// ---------- snapshots / offers / alerts ----------

export interface PriceSnapshotOut {
  id: number;
  watch_id: string;
  min_price_krw: number | null;
  median_price_krw: number | null;
  coverage_pct: number | null;
  offer_count: number | null;
  captured_at: string;
}

export interface OfferOut {
  id: string;
  watch_id: string;
  price_krw: number;
  price_original: number | null;
  currency: string | null;
  depart_date: string | null;
  return_date: string | null;
  depart_time: string | null;
  return_time: string | null;
  airline: string | null;
  deep_link: string | null;
  deep_links: Record<string, string> | null;
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
  started_at: string;
  finished_at: string | null;
  offers_found: number | null;
  best_price_krw: number | null;
  credits_used: number | null;
  error: string | null;
}

export interface HealthOut {
  status: string;
  db: string;
  worker?: string;
}

// ---------- events ----------

export interface EventOut {
  id: string;
  source: string;
  external_id: string;
  title: string;
  url: string;
  origin: string | null;
  destination: string | null;
  valid_from: string | null;   // "YYYY-MM-DD"
  valid_to: string | null;
  discount_info: string | null;
  is_active: boolean;
  fetched_at: string;
}

// ---------- stats ----------

export interface MonthlyMin {
  month: string;   // "2026-07"
  min_krw: number;
}

export interface WatchStats {
  monthly_min: MonthlyMin[];
  overall_min: number | null;
  overall_min_month: string | null;
  data_months: number;
}
