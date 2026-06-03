// ── Build Wizard types ────────────────────────────────────────────────────────

export interface WizardPlaybook {
  id: number;
  name: string;
  emoji: string;
  description: string;
  target_use_case: string;
  status: string;
  profit_strategy: Record<string, unknown>;
}

export interface RefinedIntent {
  playbook_name: string;
  playbook_emoji: string;
  budget_max: number;
  target_use_case: string;
  priorities: string[];
  constraints: string[];
  user_notes: string;
}

export interface BuildUpgrade {
  role: string;
  item: string;
  cost_estimate: number;
  source: string;
  required: boolean;
}

export interface WizardBuild {
  id: string;
  name: string;
  base_spec: string;
  base_cost: number;
  upgrades: BuildUpgrade[];
  total_cost: number;
  estimated_resale: number;
  estimated_profit: number;
  profit_margin_pct: number;
  risk: "low" | "medium" | "high";
  risk_score?: number; // 0-10 for scatter graph visualization
  demand_fit: "excellent" | "good" | "moderate" | "poor";
  demand_score?: number; // 0-10 for scatter graph visualization
  why: string;
  sell_platform: string;
  sell_price_target: number;
  valid: boolean;
  validation_score: number;
  rejection_reason: string;
  compatibility_confidence?: number;
  compatibility_warnings?: string[];
  rank: number;
  gem_id?: number;
  playbook_id?: number;
  playbook_name?: string;
  seller_type?: "shop" | "refurb_shop" | "flipper" | "private" | null;
  seller_label?: string;
  sourcing_lane?: string;
  listing_url?: string;
}

export interface GenerateRequest {
  playbook_id: number;
  budget: number;
  user_notes: string;
  priorities: string[];
  constraints: string[];
}

export interface GenerateResult {
  intent: RefinedIntent;
  builds: WizardBuild[];
  rejected_count: number;
  attempts: number;
  matrix_meta?: {
    gem_count: number;
    playbook_count: number;
    coverage: string;
  };
}

export interface PlanStep {
  step: number;
  action: string;
  detail: string;
  estimated_time: string;
}

export interface PurchasePlan {
  build: WizardBuild;
  steps: PlanStep[];
  ebay_searches: string[];
  facebook_searches: string[];
  total_budget: number;
  contingency_buffer: number;
  expected_net_profit: number;
  expected_roi_pct: number;
  timeline_days: number;
  tips: string[];
}

// ─────────────────────────────────────────────────────────────────────────────

export interface ScanSite {
  name: string;
  url: string;
  status: "pending" | "scanning" | "done" | "error";
  found: number;
  gems: number;
  error: string | null;
}

export interface ScanStatus {
  running: boolean;
  total: number;
  completed: number;
  current_sites: string[];
  sites: ScanSite[];
  started_at: string | null;
  finished_at: string | null;
  total_found: number;
  total_gems: number;
}

export interface ScheduleRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: "success" | "running" | "failed" | "skipped";
  message: string;
  duration_ms: number | null;
}

export interface ScheduleJob {
  id: string;
  name: string;
  description: string;
  cron: string;
  cron_label: string;
  enabled: boolean;
  last_run_at: string | null;
  last_status: "success" | "running" | "failed" | "skipped" | null;
  next_run_at: string | null;
  category: "scraping" | "analysis" | "selling" | "maintenance";
}

export interface SearchTelemetryItem {
  ts: string;
  run_id: string | null;
  source: string | null;
  term: string;
  found: number;
  new: number;
  error: string | null;
}

export interface SearchTelemetrySourceSummary {
  terms: number;
  found_total: number;
  new_total: number;
  errors: number;
}

export interface AntiBotPreflightStatus {
  enabled: boolean;
  show_scraper_browser: string;
  has_display: boolean;
  interactive_mode: boolean;
  chromium_available: boolean;
  running: boolean;
  last_result: string;
  last_message: string;
  last_run_at: string | null;
  urls: string[];
  wait_seconds: number;
  browser_cdp_url?: string;
  browser_cdp_host?: string;
}

export interface SourceSearchTerm {
  id: number;
  scope: string;
  group_name: string;
  term: string;
  source_names: string[];
  attributes: Record<string, unknown>;
  notes?: string | null;
  enabled: boolean;
  created_at: string;
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Ensure trailing slash to avoid 307 redirect which breaks cross-origin requests
  const url = apiUrl(path).replace(/([^/])(\?|$)/, "$1/$2");
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    signal: AbortSignal.timeout(10_000),
    redirect: "follow",
    ...init,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

function qs(params?: Record<string, string | undefined>): string {
  if (!params) return "";
  const p = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined)) as Record<string, string>;
  return Object.keys(p).length ? "?" + new URLSearchParams(p).toString() : "";
}

export const api = {
  listings: {
    list: (params?: Record<string, string>) => request<unknown[]>(`/listings${qs(params)}`),
    stats: () => request<{ total_listings: number; gems_count: number; avg_profit: number }>("/listings/stats"),
    get: (id: number) => request<unknown>(`/listings/${id}`),
  },

  flips: {
    list: () => request<unknown[]>("/flips"),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/flips", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/flips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    markSold: (id: number, data: { actual_sale_price: number; sale_platform: string }) =>
      request<unknown>(`/flips/${id}/sold`, { method: "POST", body: JSON.stringify(data) }),
    generateListing: (id: number) =>
      request<{ titles: string[]; description: string }>(`/flips/${id}/generate-listing`, { method: "POST" }),
    generateImages: (id: number) =>
      request<{ images: string[] }>(`/flips/${id}/generate-images`, { method: "POST" }),
  },

  parts: {
    list: (category?: string) => request<unknown[]>(`/parts${category ? `?category=${category}` : ""}`),
    grouped: (category?: string) => request<unknown[]>(`/parts/grouped${category ? `?category=${category}` : ""}`),
    cases: (params?: Record<string, string>) => request<unknown[]>(`/parts/cases${qs(params)}`),
    themes: () => request<string[]>("/parts/themes"),
  },

  sources: {
    list: () => request<unknown[]>("/sources"),
    health: () => request<{ avg_health_score: number; items: unknown[] }>("/sources/health"),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/sources", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/sources/${id}`, { method: "DELETE" }),
    trigger: (id: number) => request<unknown>(`/sources/${id}/scrape`, { method: "POST" }),
  },

  searchTelemetry: {
    recent: (limit?: number) => request<{ items: SearchTelemetryItem[] }>(`/search-telemetry/recent${limit ? `?limit=${limit}` : ""}`),
    bySource: (limit?: number) =>
      request<{ summary: Record<string, SearchTelemetrySourceSummary>; items: Record<string, SearchTelemetryItem[]> }>(
        `/search-telemetry/by-source${limit ? `?limit=${limit}` : ""}`,
      ),
  },

  config: {
    get: () => request<unknown>("/config/search"),
    update: (data: Record<string, unknown>) =>
      request<unknown>("/config/search", { method: "PUT", body: JSON.stringify(data) }),
  },

  settings: {
    get: () => request<unknown>("/settings"),
    update: (data: Record<string, unknown>) =>
      request<unknown>("/settings", { method: "PUT", body: JSON.stringify(data) }),
  },

  sourceSearchTerms: {
    list: (scope?: string) =>
      request<{ items: SourceSearchTerm[]; groups: string[]; scopes: string[] }>(
        `/source-search-terms${scope ? `?scope=${encodeURIComponent(scope)}` : ""}`,
      ),
    create: (data: Record<string, unknown>) =>
      request<SourceSearchTerm>("/source-search-terms", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<SourceSearchTerm>(`/source-search-terms/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/source-search-terms/${id}`, { method: "DELETE" }),
  },

  intel: {
    summary: () =>
      request<{
        total_flips: number;
        total_profit: number;
        avg_profit: number;
        avg_roi_pct: number;
        avg_days_to_sell: number;
        best_source: string | null;
        best_cpu_tier: string | null;
      }>("/intel/summary"),
    bySource: () => request<{ source: string; count: number; avg_profit: number; total_profit: number }[]>("/intel/by-source"),
    byCpuTier: () => request<{ cpu_tier: string; count: number; avg_profit: number }[]>("/intel/by-cpu"),
    byPlatform: () => request<{ platform: string; count: number; avg_profit: number }[]>("/intel/by-platform"),
    history: (params?: Record<string, string>) => request<unknown[]>(`/intel/history${qs(params)}`),
    recommendations: () => request<{ insight: string; action: string; confidence: number }[]>("/intel/recommendations"),
    retrainStatus: () =>
      request<{
        checkpoint: string;
        sold_flips_since: number;
        retrain_ready: boolean;
        last_flip_id: number;
        updated_at: string | null;
      }>("/intel/retrain-status"),
    modelVersions: (limit = 20) => request<{ items: unknown[] }>(`/intel/models/versions?limit=${limit}`),
    modelRuns: (limit = 30) => request<{ items: unknown[] }>(`/intel/models/runs?limit=${limit}`),
  },

  chat: {
    send: (message: string, history: { role: string; content: string }[], listing_id?: number) =>
      request<{ response: string; model_used: string }>("/chat", {
        method: "POST",
        body: JSON.stringify({ message, history, listing_id }),
      }),
  },

  swarms: {
    list: () => request<unknown[]>("/swarms"),
    trigger: (id: string) => request<unknown>(`/swarms/${id}/trigger`, { method: "POST" }),
    scanStatus: () => request<ScanStatus>("/swarms/scan/status"),
  },

  schedule: {
    list: () => request<ScheduleJob[]>("/schedule"),
    toggle: (id: string) => request<{ ok: boolean; enabled: boolean }>(`/schedule/${id}/toggle`, { method: "POST" }),
    run: (id: string) => request<{ ok: boolean; status: "success" | "failed"; duration_ms: number }>(`/schedule/${id}/run`, { method: "POST" }),
    runs: (id: string) => request<ScheduleRun[]>(`/schedule/${id}/runs`),
  },

  alerts: {
    list: (limit = 100, includeAcked = false) => request<unknown[]>(`/alerts?limit=${limit}&include_acked=${includeAcked ? "true" : "false"}`),
    ack: (id: number) => request<{ ok: boolean }>(`/alerts/${id}/ack`, { method: "POST" }),
  },

  manual: {
    submitUrl: (url: string, price_override?: number) =>
      request<import("./types").Listing>("/manual-submit/url", {
        method: "POST",
        body: JSON.stringify({ url, price_override: price_override ?? null }),
      }),
    submitImage: (file: File, title?: string, price?: number) => {
      const form = new FormData();
      form.append("file", file);
      if (title) form.append("title", title);
      if (price != null) form.append("price", String(price));
      // Don't set Content-Type — browser sets multipart boundary automatically
      const url = apiUrl("/manual-submit/image/");
      return fetch(url, { method: "POST", body: form, signal: AbortSignal.timeout(45_000) })
        .then(r => { if (!r.ok) return r.json().then(d => { throw new Error(d.detail || `HTTP ${r.status}`); }); return r.json(); }) as Promise<import("./types").Listing>;
    },
  },

  demand: {
    categories: () => request<import("./types").DemandCategory[]>("/demand/categories"),
    auctionIntel: (limit?: number) => request<import("./types").AuctionIntelItem[]>(`/demand/auction-intel${limit ? `?limit=${limit}` : ""}`),
    summary: () => request<import("./types").DemandSummary>("/demand/summary"),
    externalSignals: (limit_per_source?: number) =>
      request<{ summary: Record<string, { count: number; avg_score: number; avg_confidence: number }>; items: Record<string, unknown[]> }>(
        `/demand/external-signals${limit_per_source ? `?limit_per_source=${limit_per_source}` : ""}`,
      ),
    refreshExternalSignals: () => request<{ ok: boolean; inserted: number; topics: number; signals: number }>("/demand/external-signals/refresh", { method: "POST" }),
    pricingMultipliers: () =>
      request<{
        window_days: number;
        external_window_days: number;
        internal_counts: Record<string, number>;
        external_topic_strength: Record<string, number>;
        multipliers: Record<string, number>;
      }>("/demand/pricing-multipliers"),
  },

  facebook: {
    status: () => request<{exists: boolean; valid: boolean; expired: boolean; expiry_warning: boolean; message: string; days_remaining?: number}>("/facebook/status"),
    updateCookies: (cookies_json: string) => request<{ok: boolean; message: string}>("/facebook/cookies", {
      method: "PUT",
      body: JSON.stringify({ cookies_json }),
    }),
  },
  preflight: {
    antibotStatus: () => request<AntiBotPreflightStatus>("/preflight/antibot"),
    triggerAntibot: () => request<{ ok: boolean; started: boolean; reason?: string }>("/preflight/antibot/trigger", {
      method: "POST",
    }),
  },

  buildWizard: {
    playbooks: () => request<WizardPlaybook[]>("/build-wizard/playbooks"),
    generate: (body: GenerateRequest) =>
      request<GenerateResult>("/build-wizard/generate", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    generateGemMatrix: (body: Omit<GenerateRequest, "playbook_id"> & { gem_limit?: number; playbook_limit?: number; listing_id?: number }) =>
      request<GenerateResult>("/build-wizard/generate-gem-matrix", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    plan: (body: { build: WizardBuild; intent: RefinedIntent }) =>
      request<PurchasePlan>("/build-wizard/plan", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  playbooks: {
    list: (status?: string) => request<import("./types").Playbook[]>(`/playbooks${status ? `?status=${status}` : ""}`),
    get: (id: number) => request<import("./types").Playbook>(`/playbooks/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Playbook>("/playbooks", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Playbook>(`/playbooks/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) => request<void>(`/playbooks/${id}`, { method: "DELETE" }),
    activeKeywords: () => request<string[]>("/playbooks/active-keywords"),
    proposals: {
      list: (status?: string) =>
        request<import("./types").PlaybookProposal[]>(`/playbooks/proposals${status ? `?status=${status}` : ""}`),
      create: (data: Record<string, unknown>) =>
        request<import("./types").PlaybookProposal>("/playbooks/proposals", { method: "POST", body: JSON.stringify(data) }),
      approve: (id: number, resolved_by?: string) =>
        request<import("./types").Playbook>(`/playbooks/proposals/${id}/approve`, {
          method: "POST",
          body: JSON.stringify({ approved: true, resolved_by: resolved_by ?? "user" }),
        }),
      reject: (id: number, reason?: string) =>
        request<import("./types").PlaybookProposal>(`/playbooks/proposals/${id}/reject`, {
          method: "POST",
          body: JSON.stringify({ approved: false, rejection_reason: reason }),
        }),
    },
    rollbackLastUpdate: (id: number) =>
      request<import("./types").PlaybookProposal>(`/playbooks/${id}/rollback-last-update`, { method: "POST" }),
    experimentSummary: () => request<{ variants: Record<string, { total: number; pending: number; approved: number; rejected: number; approval_rate: number }> }>("/playbooks/experiments/summary"),
    experimentAttribution: (window_days?: number) =>
      request<{ window_days: number; variants: Record<string, { proposal_windows: number; attributed_flips: number; avg_profit: number; avg_roi_pct: number; sample_quality: "low" | "medium" | "high" }> }>(
        `/playbooks/experiments/attribution${window_days ? `?window_days=${window_days}` : ""}`,
      ),
  },

  reselling: {
    getSellerFees: () => request<{
      insertion_fee: number;
      final_value_fee_pct: number;
      category: string;
      seller_tier: string;
      last_updated: string;
      expires_at: number;
    }>("/reselling/seller-fees"),

    analyzePricing: (flipId: number) => request<{
      flip_id: number;
      total_cost: number;
      estimated_resale: number;
      seller_fees: {
        insertion_fee: number;
        final_value_fee_pct: number;
        seller_tier: string;
        last_updated: string;
      };
      pricing_tiers: {
        walk_away_price: number;
        total_cost_position: number;
        optimal_listing_price: number;
        estimated_profit_at_optimal: number;
        breakeven_price: number;
        margin_pct: number;
        insertion_fee: number;
        final_value_fee_pct: number;
        final_value_fee_at_optimal: number;
        net_proceeds_at_optimal: number;
      };
      analysis_timestamp: string;
    }>(`/reselling/flips/${flipId}/pricing-analysis`, { method: "POST" }),

    getPricingSummary: (flipId: number) => request<{
      flip_id: number;
      total_cost: number;
      estimated_resale: number;
      walk_away_price: number;
      optimal_listing_price: number;
      estimated_profit: number;
      margin_pct: number;
    }>(`/reselling/flips/${flipId}/pricing-summary`),
  },
};
