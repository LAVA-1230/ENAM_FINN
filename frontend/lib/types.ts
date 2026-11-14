// Mirrors the backend payloads (backend/app/api). Optional fields are absent on some event kinds.
export type Tier = "P0" | "P1" | "P2" | "P3";

export interface Decision { id: number; action: string; note: string | null; date: string; event_id: number | null; symbol?: string; company?: string }

export interface EventCard {
  id: number; symbol: string | null; company: string | null; kind: string; category: string; category_label: string;
  tier: Tier; score: number; reasons: string[]; title: string; metric_line: string | null; impact_line: string | null;
  summary: string | null; status: string; thesis_tag: string | null; verify_ok: boolean; event_date: string;
  time_ist: string; date_ist: string; quote: string | null; last_decision: Decision | null;
}

export interface Move { date: string; ret: number; close: number; index: string; index_ret: number | null;
  nifty_ret: number | null; specific: number | null; vol_ratio: number | null }

export interface Exposure { held: boolean; weight: number | null; value: number | null; qty: number | null;
  avg_cost: number | null; move?: Move; day_rs?: number; pnl_rs?: number; pnl_pct?: number }

export interface Fact { k: string; v: string; src?: string; quote?: boolean }

export interface EventDetail extends EventCard {
  facts: Fact[]; context: string[]; enrichment: Record<string, any>; sector: string | null;
  source: { exchange: string; category: string; subject: string; url: string | null; page: number | null;
            published_at: string; filing_id: number } | null;
  exposure: Exposure | null; decisions: Decision[]; suggested: string[];
  related_filing?: { id: number; subject: string; url: string | null; published_at: string };
}

export interface Brief {
  window: { name: string; from: string; to: string };
  header: { ret: number; rs: number; value: number; nifty_ret: number; from_date: string; to_date: string;
            sentence: string; contributors: { symbol: string | null; name: string; rs: number; ret: number | null }[];
            freshness: string } | null;
  attention: EventCard[]; good_to_know: EventCard[];
  routine: { count: number; groups: { label: string; count: number; companies: number;
             items: { id: number; company: string; title: string; symbol: string | null; date_ist: string }[] }[] };
  coming_up: { symbol: string; company: string; date: string; label: string; purpose: string }[];
  tripwires: { id: number; symbol: string; company: string; label: string; status: string; value: number | null;
               threshold: number; op: string }[];
  counts: { attention: number; good_to_know: number; routine: number; p0: number };
  freshness: { filings_checked: string | null; eod_date: string | null; eod_label: string | null };
  last_seen: string | null;
}

export interface Holding { symbol: string; name: string; sector: string | null; weight: number | null; value: number | null;
  qty: number; avg_cost: number | null; move?: Move; day_rs?: number; pnl_rs?: number; pnl_pct?: number;
  health: "green" | "amber" | "red"; thesis: string | null; thesis_source: string | null; muted_until: string | null;
  only_p0: boolean; note: { text: string; tier: Tier; event_id: number } | null }

export interface ProgressStep { key: string; label: string; state: "todo" | "running" | "done" | "warn"; note?: string }

export interface Scorecard { sentence: string; counts: Record<string, number>; total: number; due: number; delivered: number; open: number }

export interface Company {
  symbol: string; name: string; sector: string | null; exchange: string; is_holding: boolean; is_research: boolean;
  price: { close: number; date: string; label: string } | null; exposure: Exposure | null;
  research: { status: string; updated_at: string | null; error: string | null };
  scorecard: Scorecard | null; thesis: string | null; thesis_source: string | null; health: string | null;
  coming_up: { date: string; purpose: string }[]; prep_due: boolean; decisions: Decision[];
}

export interface PromiseRow {
  id: number; metric: string; metric_key: string; headline?: boolean; made_in: string; horizon: string | null; target_text: string;
  quote: string; speaker: string | null; page: number | null; extractor: string;
  source: { label: string; url: string | null; document_id: number | null };
  status: string; actual_text: string | null; method: string | null;
  evidence: { label: string; url?: string | null; chunk_id?: number }[];
  repeats: string[]; revisions: { made_in: string; target_text: string }[];
}

export interface Citation { n: number; label: string; kind: string; url: string | null; page?: number | null;
  chunk_id?: number | null; document_id?: number | null; filing_id?: number | null; event_id?: number; excerpt: string }

export interface AskAnswer { answer: string; found: boolean; citations: Citation[]; context: string; suggested: string[];
  method: string; needs_research?: boolean }

export interface Tripwire { id: number; kind: string; metric_key: string; op: string; threshold: number; label: string;
  source: string; enabled: boolean; status: string; value: number | null; value_label: string; threshold_label: string }

export interface Settings {
  price_pct: number; volume_x: number; impact_pct: number; push_p0_only: boolean; show_routine: boolean;
  quiet_start: string; quiet_end: string; p0_in_quiet: boolean; brief_times: string[]; replay: boolean;
  tier_overrides: Record<string, string>; tripwire_defaults: Record<string, boolean>; tripwire_labels: Record<string, string>;
  categories: { key: string; label: string; default: Tier; tier: Tier }[];
  preview: { alerts: number; price: number; volume: number; sessions: number };
}
