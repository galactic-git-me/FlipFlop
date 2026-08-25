import { getAdminToken } from "@/lib/admin-token";

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
  listing_url?: string;
  image_url?: string;
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
  base_listing_url?: string;
  base_image_url?: string;
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
  total_budget: number;
  contingency_buffer: number;
  expected_net_profit: number;
  expected_roi_pct: number;
  timeline_days: number;
  tips: string[];
}

export interface BuildComponent {
  slot: string;
  name: string;
  price_paid: number;
  source: "catalogue" | "manual";
  part_id?: number;
  listing_url?: string;
  image_url?: string;
  purchased?: boolean;
  inventory_item_id?: number;
  condition?: "new" | "new_other" | "refurbished" | "used" | "unknown";
  warranty_expires_at?: string | null;
  proof_of_purchase?: boolean;
  original_packaging?: boolean;
}

export type ManualBuildStatus = "in_progress" | "built" | "listed" | "sold";

export interface BuildPhoto {
  url: string;
  kind: "photo" | "spec_card" | "registration_plate" | "performance_card";
}

export interface ComponentRating {
  component_slot: string;
  component_key: string;
  overall_rating: number;
  reliability_rating?: number | null;
  installation_rating?: number | null;
  aesthetics_rating?: number | null;
  value_rating?: number | null;
  customer_appeal_rating?: number | null;
  notes?: string | null;
}

export interface PriceAlert {
  id: number;
  manual_build_id: number;
  build_name: string;
  build_status: string | null;
  current_price_gbp: number | null;
  user_email: string;
  target_price_gbp: number;
  is_active: boolean;
  triggered_at: string | null;
  triggered_price_gbp: number | null;
  created_at: string;
  updated_at: string;
}

export interface PriceAlertList {
  items: PriceAlert[];
  active_count: number;
  triggered_count: number;
}

export interface ManualBuild {
  id: number;
  name: string;
  components: BuildComponent[];
  total_cost: number | null;
  last_evaluation: ManualBuildEvaluation | null;
  status: ManualBuildStatus;
  generated_title: string | null;
  generated_description: string | null;
  generated_aspects: Record<string, string[]> | null;
  ebay_listing_id: string | null;
  ebay_listing_url: string | null;
  photos: BuildPhoto[];
  // Structured factual data behind the rendered spec card / registration
  // plate / performance card — this is what's actually sent to the LLM for
  // listing generation (as JSON text), not the images themselves.
  evidence_data?: Record<string, unknown>;
  hero_photo_url: string | null;
  model_3d_url?: string | null;
  model_3d_assets?: Record<string, Build3DAsset>;
  selected_faq_ids?: string[] | null;
  selected_faq_answer_overrides?: Record<string, string>;
  storefront_product_id: number | null;
  // eBay Listing Configuration (optional until migration runs)
  ebay_condition?: string | null;
  ebay_price?: number | null;
  allow_offers?: boolean;
  auto_reject_below_price?: number | null;
  auction_start_price?: number | null;
  return_days?: number;
  shipping_method?: string;
  shipping_cost?: number;
  shipping_insurance_cost?: number;
  packaging_cost?: number;
  warranty_reserve_pct?: number;
  handling_time_days?: number;
  delivery_min_days?: number;
  delivery_max_days?: number;
  shipping_damage_cover_confirmed?: boolean;
  ships_to_countries?: string[];
  domestic_only?: boolean;
  fulfillment_policy_id?: string | null;
  package_weight_kg?: number | null;
  package_length_cm?: number | null;
  package_width_cm?: number | null;
  package_height_cm?: number | null;
  deferred_publish_at?: string | null;
  // Real post-sale order/shipment data (see /manual-builds/{id}/sync-ebay-order
  // and /manual-builds/{id}/book-shipment) — null until the build actually sells.
  ebay_order_id?: string | null;
  buyer_name?: string | null;
  buyer_address_json?: BuyerAddress | null;
  sale_price_actual?: number | null;
  marketplace_fees_actual?: number | null;
  promotion_cost_actual?: number | null;
  refund_amount?: number | null;
  warranty_claim_cost?: number | null;
  parcel2go_order_id?: string | null;
  parcel2go_service_slug?: string | null;
  tracking_number?: string | null;
  shipping_label_url?: string | null;
  shipment_booked_at?: string | null;
  // Computed per-channel "is this actually purchasable right now" status —
  // only populated by the single-build GET, null on list/summary views.
  ebay_live?: boolean | null;
  storefront_live?: boolean | null;
  created_at: string;
  updated_at: string;
}

// Real tracked-delivery quotes, cheapest first, for a build's saved package
// dimensions, via Parcel2Go (see /manual-builds/{id}/courier-quote).
export interface CourierQuote {
  courier_name: string;
  service_name: string;
  price_gbp: number;
  tracked: boolean;
  estimated_days: number | null;
  service_slug: string | null;
  protection_scope: "loss_only" | "loss_and_damage" | "unknown";
  full_value_damage_cover: boolean;
  protection_warning: string;
}

export interface Build3DAsset {
  provider: "meshy";
  status: "queued" | "processing" | "succeeded" | "failed";
  source_image_urls: string[];
  task_id?: string;
  glb_url?: string;
  preview_url?: string | null;
  error?: string;
  queued_at?: string;
  completed_at?: string;
}

export interface InsuranceQuote {
  provider: string;
  insured_value_gbp: number;
  price_gbp: number;
  currency: string;
  quote_only: boolean;
}

export interface ProductFaq {
  id: string;
  category: string;
  question: string;
  answer: string;
}

export interface BuildFaqSelection {
  bank: ProductFaq[];
  selected_ids: string[];
  uses_defaults: boolean;
  maximum: number;
  answer_overrides: Record<string, string>;
}

// The buyer's real delivery address, synced from the actual eBay order
// once a build sells — never available before then (see sync-ebay-order).
export interface BuyerAddress {
  contact_name: string;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state_or_province: string | null;
  postal_code: string | null;
  country_code: string;
  phone: string | null;
}

export interface SyncEbayOrderResult {
  ebay_order_id: string;
  buyer_name: string;
  buyer_address: BuyerAddress;
  sale_price_actual: number;
}

export interface BookShipmentResult {
  success: boolean;
  tracking_number: string | null;
  shipping_label_url: string | null;
  parcel2go_order_id: string | null;
  ebay_marked_shipped: boolean;
  warning?: string | null;
  error?: string | null;
}

// A real shipping-destination option, fetched live from the seller's own
// eBay account (see /manual-builds/ebay-fulfillment-policies) — not a
// hardcoded list. Each policy is configured once in eBay's Seller Hub with
// its own shipping services, rates, and destination countries/regions.
export interface FulfillmentPolicy {
  policy_id: string;
  name: string;
  marketplace_id: string;
  ship_to_regions: string[];
  handling_time_days: number | null;
}

// Whole-DB "most up to date view of the market" — same categories as the
// Current Scan Run panel, scoped to every currently-active listing instead
// of just the latest run (see /gem-radar/market-snapshot).
export interface MarketSnapshot {
  ingestedCount: number;
  superGemCount: number;
  gemCount: number;
  avgSuperGemScore: number;
  avgGemScore: number;
  binPricesCount: number;
  soldPricesCount: number;
}

// Real scan cadence derived from actual observation activity — see
// /gem-radar/scan-schedule-status's docstring for why this is a best-effort
// estimate rather than a guaranteed backend-scheduled job.
export interface ScanScheduleStatus {
  scan_started_at: string | null;
  last_scan_at: string | null;
  scan_interval_minutes: number;
  next_scan_at: string | null;
  estimate_only: boolean;
}

export interface ManualBuildSummary {
  id: number;
  name: string;
  total_cost: number | null;
  component_count: number;
  status: ManualBuildStatus;
  updated_at: string;
}

export interface EvaluationSuggestion {
  text: string;
  uplift: number;
}

export interface ManualBuildEvaluation {
  low: number;
  mid: number;
  high: number;
  narrative: string;
  suggestions: EvaluationSuggestion[];
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

// NEXT_PUBLIC_API_URL (when set) is the bare backend origin, used elsewhere for
// direct SSE/websocket connections that can't go through the Next.js rewrite
// proxy — so it never includes "/api". Append it here rather than changing the
// env var itself, since other call sites depend on the bare-origin form.
const backendOrigin = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
export const API_BASE_URL = backendOrigin ? `${backendOrigin}/api` : "/api";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Add trailing slash to path only (not end of query string) — backend handles both
  // NOTE: the old regex /([^/])(\?|$)/ was corrupting query params like status=active → status=active/
  const url = apiUrl(path).replace(/([^/])(\?)/, "$1/$2");
  const token = getAdminToken();
  const res = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    signal: AbortSignal.timeout(120_000),
    redirect: "follow",
    ...init,
  });
  if (!res.ok) {
    const detail = await res
      .clone()
      .json()
      .then((body) => body?.detail)
      .catch(() => undefined);
    throw new Error(detail ? String(detail) : `API ${path} → ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function qs(params?: Record<string, string | undefined>): string {
  if (!params) return "";
  const p = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined)) as Record<string, string>;
  return Object.keys(p).length ? "?" + new URLSearchParams(p).toString() : "";
}

export const api = {
  priceAlerts: {
    list: () => request<PriceAlertList>("/price-alerts"),
    create: (data: { manual_build_id: number; user_email: string; target_price_gbp: number }) =>
      request<PriceAlert>("/price-alerts", { method: "POST", body: JSON.stringify(data) }),
    dismiss: (id: number) => request<{ ok: boolean }>(`/price-alerts/${id}/dismiss`, { method: "POST" }),
    rearm: (id: number) => request<{ ok: boolean }>(`/price-alerts/${id}/re-arm`, { method: "POST" }),
    history: (id: number) => request<{ items: Array<{ id: number; event_type: string; price_gbp: number | null; notes: string | null; created_at: string }> }>(`/price-alerts/${id}/history`),
  },
  listings: {
    // DEPRECATED: Use gemRadar.scoredListings instead
    list: (params?: Record<string, string>) => request<unknown[]>(`/listings/${qs(params)}`),
    stats: () => request<{ total_listings: number; gems_count: number; avg_profit: number }>("/listings/stats"),
    get: (id: number) => request<unknown>(`/listings/${id}`),
  },

  gemRadar: {
    scoredListings: () => request<unknown[]>("/gem-radar/scored-listings"),
    listings: () => request<unknown[]>("/gem-radar/listings"),
    currentGem: () => request<unknown>("/gem-radar/current-gem"),
    // Whole-DB market snapshot (all currently-active listings, not just the
    // latest scan run) — same shape as the Current Scan Run panel's stats.
    marketSnapshot: () => request<MarketSnapshot>("/gem-radar/market-snapshot"),
    // Real scan cadence derived from actual observation activity, since
    // there's no backend-scheduled "next scan" job (scanning happens
    // client-side in the browser extension) — see the endpoint's docstring.
    scanScheduleStatus: () => request<ScanScheduleStatus>("/gem-radar/scan-schedule-status"),
  },

  flips: {
    list: () => request<unknown[]>("/flips"),
    get: (id: number) => request<unknown>(`/flips/${id}`),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/flips", { method: "POST", body: JSON.stringify(data) }),
    patch: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/flips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/flips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    markSold: (id: number, data: { actual_sale_price: number; sale_platform: string }) =>
      request<unknown>(`/flips/${id}/sold`, { method: "POST", body: JSON.stringify(data) }),
    purchasePlan: (id: number) =>
      request<{
        flip_id: number;
        items: {
          category: string;
          label: string;
          name: string;
          specs: string;
          price: number;
          url: string;
          source: string;
          part_id: number | null;
        }[];
        total: number;
      }>(`/flips/${id}/purchase-plan`),
    compatibilityCheck: (id: number) =>
      request<{
        compatible: boolean | null;
        confidence: "high" | "medium" | "low";
        issues: string[];
        warnings: string[];
        summary: string;
        model_used: string;
      }>(`/flips/${id}/compatibility-check`, { method: "POST" }),
    generateListing: (id: number) =>
      request<{ titles: string[]; description: string }>(`/flips/${id}/generate-listing`, { method: "POST" }),
    generateImages: (id: number) =>
      request<{ images: string[] }>(`/flips/${id}/generate-images`, { method: "POST" }),
    uploadVideo: async (id: number, file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE_URL}/flips/${id}/upload-video`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`Video upload failed: ${res.status}`);
      return res.json() as Promise<{ video_url: string; video_ebay_status: string }>;
    },
    demandCheck: (id: number) =>
      request<{
        query: string;
        active_count: number | null;
        sold_count_90d: number | null;
        sold_data_available: boolean;
        ratio_ok: boolean | null;
        note: string | null;
      }>(`/flips/${id}/demand-check`, { method: "POST" }),
    recalculatePricing: (id: number) =>
      request<{
        listing_price: number | null;
        sold_comp_target: number | null;
        active_range_ceiling: number | null;
        price_floor: number | null;
      }>(`/flips/${id}/recalculate-pricing`, { method: "POST" }),
    counterOffer: (id: number, buyer_offer: number) =>
      request<{ action: string; counter_price: number | null; reason: string }>(
        `/flips/${id}/counter-offer`,
        { method: "POST", body: JSON.stringify({ buyer_offer }) }
      ),
    publishNow: (id: number) =>
      request<{ published: boolean; reason?: string; ebay_listing_url?: string }>(
        `/flips/${id}/publish-now`,
        { method: "POST" }
      ),
    pricingSuggestions: (id: number) =>
      request<{
        shipping: { estimated_weight_kg: number; estimated_shipping_cost: number; shipping_inclusive_price: number };
        promoted_listings: { suggested_ad_rate_pct: number; too_thin_to_promote: boolean; max_ad_spend: number; reason: string };
      }>(`/flips/${id}/pricing-suggestions`),
    watcherOfferPlan: (id: number) =>
      request<{ should_send: boolean; discount_pct: number; offer_price: number | null; reason: string }>(
        `/flips/${id}/watcher-offer-plan`
      ),
    profitBreakdown: (id: number) =>
      request<{
        flip_id: number;
        sale_price: number;
        selling_fee: number;
        net_proceeds: number;
        total_landed_cost: number;
        profit: number;
        profit_margin_pct: number;
        allocations: Array<{
          inventory_item_id: number;
          quantity: number;
          cost_per_unit: number;
          total_cost: number;
        }>;
      }>(`/inventory-allocations/flips/${id}/profit-breakdown`),
  },

  parts: {
    list: (category?: string) => request<unknown[]>(`/parts${category ? `?category=${category}` : ""}`),
    grouped: (category?: string) => request<unknown[]>(`/parts/grouped${category ? `?category=${category}` : ""}`),
    cases: (params?: Record<string, string>) => request<unknown[]>(`/parts/cases${qs(params)}`),
    themes: () => request<string[]>("/parts/themes"),
  },

  manualBuilds: {
    list: () => request<ManualBuildSummary[]>("/manual-builds/"),
    get: (id: number) => request<ManualBuild>(`/manual-builds/${id}`),
    getFaqs: (id: number) => request<BuildFaqSelection>(`/manual-builds/${id}/faqs`),
    updateFaqs: (id: number, selectedIds: string[], answerOverrides: Record<string, string>) =>
      request<{ selected_ids: string[]; selected_faqs: ProductFaq[] }>(`/manual-builds/${id}/faqs`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_ids: selectedIds, answer_overrides: answerOverrides }),
      }),
    create: (name: string) =>
      request<ManualBuild>("/manual-builds/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }),
    patch: (id: number, data: { name?: string; components?: BuildComponent[] }) =>
      request<ManualBuild>(`/manual-builds/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      fetch(`${API_BASE_URL}/manual-builds/${id}`, { method: "DELETE" }),
    evaluate: (id: number) =>
      request<ManualBuildEvaluation>(`/manual-builds/${id}/evaluate`, {
        method: "POST",
      }),
    markBuilt: (id: number) =>
      request<ManualBuild>(`/manual-builds/${id}/mark-built`, { method: "POST" }),
    purchaseComponent: (id: number, slot: string, data: { price_paid?: number; source?: string }) =>
      request<ManualBuild>(`/manual-builds/${id}/components/${encodeURIComponent(slot)}/purchase`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    getComponentRatings: (id: number) =>
      request<ComponentRating[]>(`/manual-builds/${id}/component-ratings`),
    saveComponentRatings: (id: number, ratings: ComponentRating[]) =>
      request<{ saved: number; preferred_added: number }>(`/manual-builds/${id}/component-ratings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ratings }),
      }),
    generateListing: (id: number) =>
      request<{ titles: string[]; description: string; aspects: Record<string, string[]> }>(
        `/manual-builds/${id}/generate-listing`,
        { method: "POST" },
      ),
    generateSpecifics: (id: number) =>
      request<{ titles: string[]; description: string; aspects: Record<string, string[]> }>(
        `/manual-builds/${id}/generate-specifics`,
        { method: "POST" },
      ),
    updateAspects: (id: number, aspects: Record<string, string[]>) =>
      request<ManualBuild>(`/manual-builds/${id}/aspects`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aspects }),
      }),
    // Derived from ManualBuild (via Pick) rather than hand-duplicated --
    // the duplicate had silently drifted out of sync with ManualBuild's real
    // nullability (ebay_condition/ebay_price/auto_reject_below_price/
    // auction_start_price/package_*_cm are all `T | null` on ManualBuild,
    // but were declared non-nullable here), which is what caused build/[id]/
    // page.tsx's updateEbayConfig(build as Partial<ManualBuild>) call to fail
    // type-checking.
    updateEbayConfig: (id: number, config: Partial<Pick<ManualBuild,
      | "ebay_condition" | "ebay_price" | "allow_offers" | "auto_reject_below_price"
      | "auction_start_price" | "return_days" | "shipping_method" | "shipping_cost"
      | "handling_time_days" | "ships_to_countries" | "domestic_only"
      | "shipping_damage_cover_confirmed"
      | "fulfillment_policy_id" | "package_weight_kg" | "package_length_cm"
      | "package_width_cm" | "package_height_cm" | "deferred_publish_at"
    >>) =>
      request<ManualBuild>(`/manual-builds/${id}/ebay-config`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      }),
    getFulfillmentPolicies: () =>
      request<FulfillmentPolicy[]>("/manual-builds/ebay-fulfillment-policies"),
    // Omitting deliveryCountry lets the backend default to the real synced
    // buyer address's country (see sync-ebay-order) instead of forcing GBR.
    getCourierQuote: (id: number, deliveryCountry?: string) =>
      request<CourierQuote[]>(
        `/manual-builds/${id}/courier-quote${deliveryCountry ? `?delivery_country=${deliveryCountry}` : ""}`,
        { method: "POST" },
      ),
    // Fetches the build's real eBay order — buyer name, actual delivery
    // address, actual sale price — only possible once it's actually sold.
    syncEbayOrder: (id: number) =>
      request<SyncEbayOrderResult>(`/manual-builds/${id}/sync-ebay-order`, { method: "POST" }),
    // Books and pays for a real Parcel2Go shipment, then pushes tracking to
    // eBay. Spends real money — only call from an explicit user confirmation.
    bookShipment: (id: number, data: { service_slug: string; price_gbp: number }) =>
      request<BookShipmentResult>(`/manual-builds/${id}/book-shipment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    postToEbay: (id: number, data: { price: number; condition: string }) =>
      request<{ success: boolean; listing_id?: string; url?: string; error?: string }>(
        `/manual-builds/${id}/post-to-ebay`,
        { method: "POST", body: JSON.stringify(data) },
      ),
    getInsuranceQuote: (id: number, listingValueGbp: number) =>
      request<InsuranceQuote>(
        `/manual-builds/${id}/insurance-quote?listing_value_gbp=${encodeURIComponent(listingValueGbp)}`,
        { method: "POST" },
      ),
    endEbayListing: (id: number) =>
      request<ManualBuild>(`/manual-builds/${id}/ebay-listing`, { method: "DELETE" }),
    uploadPhotos: async (id: number, files: File[], kind: "photo" | "performance_card" = "photo"): Promise<ManualBuild> => {
      const formData = new FormData();
      for (const f of files) formData.append("files", f);
      formData.append("kind", kind);
      const token = getAdminToken();
      const res = await fetch(`${API_BASE_URL}/manual-builds/${id}/photos`, {
        method: "POST",
        body: formData,
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new Error(`API upload photos → ${res.status}`);
      return res.json();
    },
    updateEvidenceData: (id: number, kind: "spec_card" | "registration_plate" | "performance_card", data: Record<string, unknown>) =>
      request<ManualBuild>(`/manual-builds/${id}/evidence-data`, { method: "PUT", body: JSON.stringify({ kind, data }) }),
    uploadBrandedAsset: async (id: number, kind: "spec_card" | "registration_plate", blob: Blob): Promise<ManualBuild> => {
      const formData = new FormData();
      formData.append("file", blob, `${kind}.png`);
      const token = getAdminToken();
      const res = await fetch(`${API_BASE_URL}/manual-builds/${id}/photos/branded?kind=${kind}`, {
        method: "POST",
        body: formData,
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new Error(`API upload branded asset → ${res.status}`);
      return res.json();
    },
    upload3dModel: async (id: number, file: File): Promise<ManualBuild> => {
      const formData = new FormData();
      formData.append("file", file);
      const token = getAdminToken();
      const res = await fetch(`${API_BASE_URL}/manual-builds/${id}/model-3d`, {
        method: "POST",
        body: formData,
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) {
        const detail = await res.json().then((body) => body?.detail).catch(() => undefined);
        throw new Error(detail ? String(detail) : `3D model upload failed (${res.status})`);
      }
      return res.json();
    },
    generate3dAssets: (id: number, assets: Record<string, string[]>) =>
      request<{ queued: string[]; assets: Record<string, Build3DAsset> }>(`/manual-builds/${id}/model-3d/generate`, {
        method: "POST",
        body: JSON.stringify({ assets }),
      }),
    removePhoto: (id: number, url: string) =>
      request<ManualBuild>(`/manual-builds/${id}/photos`, { method: "DELETE", body: JSON.stringify({ url }) }),
    reorderPhotos: (id: number, urls: string[]) =>
      request<ManualBuild>(`/manual-builds/${id}/photos/order`, { method: "PUT", body: JSON.stringify({ urls }) }),
    setHeroPhoto: (id: number, url: string) =>
      request<ManualBuild>(`/manual-builds/${id}/photos/hero`, { method: "POST", body: JSON.stringify({ url }) }),
    listOnStorefront: (id: number, price: number) =>
      request<{ product_id: number; build_id: number; storefront_url?: string }>(
        `/manual-builds/${id}/list-on-storefront`,
        { method: "POST", body: JSON.stringify({ price }) },
      ),
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

  favourites: {
    list: () => request<{ items: import("./types").Favourite[]; groups: string[] }>("/favourites"),
    search: (q: string) => request<import("./types").FavouriteMatrixRow>(`/favourites/search?q=${encodeURIComponent(q)}`),
    matrix: () => request<Record<number, import("./types").FavouriteMatrixRow>>("/favourites/matrix"),
    create: (term?: string | null, category?: string | null, cpk?: string | null) =>
      request<import("./types").Favourite>("/favourites", {
        method: "POST",
        body: JSON.stringify({ term: term ?? null, category: category ?? null, cpk: cpk ?? null }),
      }),
    update: (id: number, category: string) =>
      request<import("./types").Favourite>(`/favourites/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ category }),
      }),
    remove: (id: number) => request<void>(`/favourites/${id}`, { method: "DELETE" }),
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
    soldMarket: (days = 90) => request<import("./types").SoldMarketDemand>(`/demand/sold-market?days=${days}`),
    soldMarketListings: (category: import("./types").SoldComponentCategory, days = 90, limit = 250) =>
      request<import("./types").SoldMarketListing[]>(`/demand/sold-market/listings?category=${category}&days=${days}&limit=${limit}`),
    soldMarketInsights: (days = 90, refresh = false) =>
      request<import("./types").SoldMarketInsight>(`/demand/sold-market/insights?days=${days}&refresh=${refresh}`),
    externalSignals: (limit_per_source?: number) =>
      request<{ summary: Record<string, { count: number; avg_score: number; avg_confidence: number }>; items: Record<string, unknown[]> }>(
        `/demand/external-signals${limit_per_source ? `?limit_per_source=${limit_per_source}` : ""}`,
      ),
    refreshExternalSignals: () => request<{ ok: boolean; inserted: number; topics: number; signals: number }>("/demand/external-signals/refresh", { method: "POST" }),
    richSignals: () => request<{
      google_trends: {
        queries: string[];
        timeseries: Record<string, { date: string; value: number }[]>;
        geo: Record<string, { region: string; code: string | null; value: number }[]>;
      };
      reddit: {
        posts: {
          reddit_id: string; query: string; topic: string; title: string;
          subreddit: string; score: number; comments: number;
          url: string | null; created_utc: string | null;
        }[];
      };
      steam: {
        stats: { category: string; name: string; percentage: number; change: number | null; collected_at: string | null }[];
      };
    }>("/demand/rich-signals"),
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
    componentCandidates: () => request<{
      generated_at: string | null;
      unavailable_reason?: string;
      builds: Array<{
        rank: number;
        build_cost: number;
        estimated_profit: number;
        compatibility_confidence: "matched" | "unknown";
        super_gem_count: number;
        components: Array<{
          id: number;
          listing_id: string;
          category: string;
          title: string;
          seller: string | null;
          image_url: string | null;
          delivered_price: number;
          classification: string;
          url: string;
        }>;
      }>;
    }>("/pc-builder/ai-generated-builds"),
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
    ranked: () => request<import("./types").Playbook[]>("/playbooks/ranked"),
    seed: () => request<{ ok: boolean; created: number }>("/playbooks/seed", { method: "POST" }),
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

  benchmarks: {
    status: () => request<{
      total_benchmarks: number;
      cpu_count: number;
      gpu_count: number;
      storage_count: number;
      last_run: {
        run_type: string | null;
        status: string | null;
        started_at: string | null;
        completed_at: string | null;
        components_checked: number;
        components_updated: number;
        components_failed: number;
      } | null;
    }>("/benchmarks/status"),
    top: (component_type = "cpu", limit = 20) =>
      request<Array<{
        model: string;
        normalized_model: string;
        overall_score: number;
        gaming_score: number | null;
        last_refreshed_at: string | null;
        confidence_score: number;
      }>>(`/benchmarks/top?component_type=${component_type}&limit=${limit}`),
    refreshRuns: (limit = 10) =>
      request<Array<{
        id: number;
        run_type: string;
        status: string;
        started_at: string;
        completed_at: string | null;
        components_checked: number;
        components_updated: number;
        components_failed: number;
        error_log: string | null;
      }>>(`/benchmarks/refresh-runs?limit=${limit}`),
    triggerRefresh: async (run_type = "manual") => {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const token = getAdminToken();
      const resp = await fetch(`${base}/api/benchmarks/refresh?run_type=${run_type}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      return resp.json();
    },
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

    generateListing: (flipId: number) => request<{
      flip_id: number;
      title_options: string[];
      description: string;
      recommended_title: string;
      specs: string;
    }>(`/reselling/flips/${flipId}/generate-listing`, { method: "POST" }),

    processImages: (flipId: number, imageUrls: string[], addWatermark: boolean = true) =>
      request<{
        flip_id: number;
        images: Array<{
          base64: string;
          size_kb: number;
        }>;
        processed_count: number;
        error_count: number;
        error_urls: string[];
      }>(`/reselling/flips/${flipId}/process-images`, {
        method: "POST",
        body: JSON.stringify({ image_urls: imageUrls, add_watermark: addWatermark }),
      }),

    getListingPreview: (flipId: number) => request<{
      flip_id: number;
      title: string;
      description: string;
      listing_source: "saved" | "generated";
      pricing: {
        listing_price: number;
        walk_away_price: number;
        estimated_profit: number;
        margin_pct: number;
        insertion_fee: number;
        final_value_fee_pct: number;
      };
      images_available: boolean;
      ready_to_post: boolean;
    }>(`/reselling/flips/${flipId}/listing-preview`),
  },

  catalogue: {
    reviewQueue: () => request<unknown[]>("/catalogue/review-queue"),
    approve: (id: number) =>
      request<unknown>(`/catalogue/variants/${id}/approve`, { method: "POST" }),
    reject: (id: number, reason: string) =>
      request<unknown>(`/catalogue/variants/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    approveAll: () =>
      request<unknown>("/catalogue/variants/approve-all", { method: "POST" }),
    variants: (params?: Record<string, string>) =>
      request<unknown[]>(`/catalogue/variants${params ? "?" + new URLSearchParams(params) : ""}`),
    toggleVariantStatus: (id: number) =>
      request<unknown>(`/catalogue/variants/${id}/toggle-status`, { method: "PATCH" }),
    cases: () => request<unknown[]>("/catalogue/cases"),
    createCase: (data: Record<string, unknown>) =>
      request<unknown>("/catalogue/cases", { method: "POST", body: JSON.stringify(data) }),
    updateCase: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/catalogue/cases/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    slots: (playbookId?: number) =>
      request<unknown[]>(`/catalogue/slots${playbookId ? `?playbook_id=${playbookId}` : ""}`),
    updateSlot: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/catalogue/slots/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },

  inventoryAllocations: {
    list: (flipId?: number) =>
      request<unknown[]>(
        `/inventory-allocations${flipId ? `?flip_id=${flipId}` : ""}`
      ),
    create: (data: Record<string, unknown>) =>
      request<unknown>(
        "/inventory-allocations",
        { method: "POST", body: JSON.stringify(data) }
      ),
    get: (id: number) =>
      request<unknown>(`/inventory-allocations/${id}`),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(
        `/inventory-allocations/${id}`,
        { method: "PATCH", body: JSON.stringify(data) }
      ),
    delete: (id: number) =>
      request<void>(`/inventory-allocations/${id}`, { method: "DELETE" }),
    assignToManualBuild: (manualBuildId: number, inventoryItemIds: number[]) =>
      request<{ created: number; units_assigned: number; build_name: string }>(
        `/inventory-allocations/manual-builds/${manualBuildId}/bulk`,
        { method: "POST", body: JSON.stringify({ inventory_item_ids: inventoryItemIds }) },
      ),
    releaseFromManualBuild: (manualBuildId: number, inventoryItemId: number) =>
      request<void>(`/inventory-allocations/manual-builds/${manualBuildId}/items/${inventoryItemId}`, { method: "DELETE" }),
  },

  inventory: {
    freeItems: (componentType?: string) => request<Array<{
      id: number; component_name: string; component_type: string; quantity_free: number;
      actual_cost: number; source: string | null; listing_url: string | null; purchase_date: string;
    }>>(`/inventory/free-items${componentType ? `?component_type=${encodeURIComponent(componentType)}` : ""}`),
    health: () => request<{
      free_units: number; reserved_units: number; consumed_units: number;
      free_value: number; reserved_value: number; consumed_value: number; expected_profit: number;
      stale_items: Array<{ id: number; name: string; days: number; value: number }>;
      excess_stock: Array<{ component_type: string; free_units: number }>;
      build_blockers: Array<{ build_id: number; build_name: string; missing: string[] }>;
    }>("/inventory/summary/health"),
    events: (inventoryItemId: number) => request<Array<{
      id: number; event_type: string; quantity: number; manual_build_id: number | null;
      build_name: string | null; detail: Record<string, unknown>; created_at: string;
    }>>(`/inventory-allocations/inventory/${inventoryItemId}/events`),
    units: (inventoryItemId: number) => request<Array<{
      id: number; inventory_item_id: number; unit_number: number; serial_number: string | null;
      condition_grade: string; status: string; storage_location: string | null;
      warranty_expires_at: string | null; test_results: Record<string, unknown>; photos: string[];
      exception_reason: string | null; writeoff_amount: number | null; received_at: string | null;
      inspected_at: string | null; created_at: string; updated_at: string;
    }>>(`/inventory-intelligence/items/${inventoryItemId}/units`),
    updateUnit: (unitId: number, data: Record<string, unknown>) => request<Record<string, unknown>>(
      `/inventory-intelligence/units/${unitId}`, { method: "PATCH", body: JSON.stringify(data) },
    ),
    unitLabel: (unitId: number) => request<{
      unit_id: number; sku: string; component_name: string; serial_number: string | null;
      location: string | null; qr_payload: string;
    }>(`/inventory-intelligence/units/${unitId}/label`),
    buildCandidates: (manualBuildId: number) => request<Array<{
      id: number; component_name: string; component_type: string; slot: string; quantity_free: number;
      actual_cost: number; source: string | null; compatible: boolean; confidence: string;
      reasons: string[]; warnings: string[];
    }>>(`/inventory-intelligence/builds/${manualBuildId}/candidates`),
    forecast: (days = 30) => request<{
      horizon_days: number; capital_required: number; rows: Array<{
        component_type: string; free_now: number; monthly_usage: number; projected_free: number;
        recommendation: "buy" | "hold" | "liquidate"; units: number; estimated_capital: number;
      }>;
    }>(`/inventory-intelligence/forecast?days=${days}`),
    sourcingAdjustments: () => request<Array<{
      component_type: string; free_now: number; recommendation: string; units: number;
      deal_score_adjustment: number; reason: string;
    }>>("/inventory-intelligence/sourcing-adjustments"),
    buildOpportunities: () => request<Array<{
      name: string; completion_pct: number; ready: boolean; missing: string[]; owned_cost: number;
      additional_spend_estimate: number; components: Array<{ inventory_item_id: number; component_type: string; name: string; cost: number }>;
      warnings: string[];
    }>>("/inventory-intelligence/build-opportunities"),
    reorderRules: () => request<Array<{
      id: number; component_type: string; minimum_free: number; maximum_free: number; target_free: number; notes: string | null;
    }>>("/inventory-intelligence/reorder-rules"),
    saveReorderRule: (componentType: string, data: { minimum_free: number; maximum_free: number; target_free: number; notes?: string }) =>
      request<Record<string, unknown>>(`/inventory-intelligence/reorder-rules/${encodeURIComponent(componentType)}`, {
        method: "PUT", body: JSON.stringify({ component_type: componentType, ...data }),
      }),
    accountingExportUrl: () => `${API_BASE_URL}/inventory-intelligence/accounting-export.csv`,
  },

  flipProfitBreakdown: {
    get: (flipId: number) =>
      request<unknown>(`/flips/${flipId}/profit-breakdown`),
  },

  ebayOAuth: {
    authorizeUrl: () => request<{ url: string }>("/ebay/oauth/authorize-url"),
    status: () =>
      request<{
        connected: boolean;
        connected_at: string | null;
        scopes: string[];
        refresh_token_expires_at: string | null;
      }>("/ebay/oauth/status"),
    disconnect: () => request<{ connected: boolean }>("/ebay/oauth/disconnect", { method: "POST" }),
  },

  adminPerformance: {
    summary: (days = 90) =>
      request<{
        window_days: number;
        sold_count: number;
        active_count: number;
        total_revenue: number;
        total_profit: number;
        avg_margin_pct: number;
        avg_days_to_sell: number;
        sell_through_rate: number | null;
      }>(`/admin/performance/summary?days=${days}`),
    sellerStandards: () =>
      request<{ available: boolean; note: string | null; metrics: unknown }>(
        "/admin/performance/seller-standards"
      ),
    keywordResearch: (query: string) =>
      request<{
        query: string;
        sample_titles: string[];
        frequent_tokens: [string, number][];
        note: string;
      }>(`/admin/performance/keyword-research?query=${encodeURIComponent(query)}`),
  },
};

// ── Hermes Companion ──────────────────────────────────────────────────────────

export interface CompanionMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CompanionSSEEvent {
  type: "token" | "search_results" | "done";
  content?: string;
  results?: import("@/components/hermes-context").SearchResult[];
  model_used?: string;
}

export async function streamCompanion(
  message: string,
  history: CompanionMessage[],
  pageContext: string,
  onEvent: (event: CompanionSSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(apiUrl("/companion/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, page_context: pageContext }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Companion stream failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event: CompanionSSEEvent = JSON.parse(line.slice(6));
          onEvent(event);
        } catch {
          // malformed SSE line, skip
        }
      }
    }
  }
}
