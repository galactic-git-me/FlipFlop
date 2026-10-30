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
  sourcing_candidate?: boolean;
  gem_classification?: "SUPER_GEM" | "GEM";
  gem_radar_listing_id?: number;
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
  kind:
    | "photo"
    | "video"
    | "spec_card"
    | "registration_plate"
    | "performance_card";
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
  manual_build_id: number | null;
  build_name: string;
  build_status: string | null;
  current_price_gbp: number | null;
  user_email: string;
  target_price_gbp: number | null;
  is_active: boolean;
  triggered_at: string | null;
  triggered_price_gbp: number | null;
  listing_url: string | null;
  created_at: string;
  updated_at: string;
  alert_type: "build" | "component";
  component_key: string | null;
  component_slot: string | null;
  market_reference_price_gbp: number | null;
  reference_basis:
    | "build_valuation"
    | "market_median"
    | "fixed_retailer"
    | null;
  cpk: string | null;
  condition_cohort: "new" | "used" | null;
  monitoring_status:
    | "pending_identity"
    | "pending_evidence"
    | "armed"
    | "triggered"
    | "dismissed";
  reference_evidence: Record<string, unknown> | null;
  triggered_evidence: Record<string, unknown> | null;
  last_evaluated_at: string | null;
  discount_threshold_pct: number | null;
}

export interface PriceAlertList {
  items: PriceAlert[];
  active_count: number;
  triggered_count: number;
  pending_count: number;
  rules_enabled: boolean;
  email_enabled: boolean;
  smtp_configured: boolean;
}

export interface ManualBuild {
  id: number;
  name: string;
  creation_method?: "manual" | "ai" | "gem_spotlight";
  components: BuildComponent[];
  total_cost: number | null;
  last_evaluation: ManualBuildEvaluation | null;
  status: ManualBuildStatus;
  generated_title: string | null;
  generated_description: string | null;
  generated_aspects: Record<string, string[]> | null;
  ebay_listing_id: string | null;
  ebay_listing_url: string | null;
  ebay_offer_id?: string | null;
  ebay_draft_id?: string | null;
  ebay_draft_url?: string | null;
  ebay_listing_status?:
    | "never_listed"
    | "draft"
    | "active"
    | "sold"
    | "ended"
    | "missing"
    | "unknown";
  ebay_listing_status_checked_at?: string | null;
  ebay_listing_end_reason?: string | null;
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
  // Existing manual-build relist/recreate clock. Per-channel schedules take
  // precedence in the cross-listing view when one is configured.
  next_recreate_at?: string | null;
  listed_at?: string | null;
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
  signature_tracking: boolean;
  protection_scope: "loss_only" | "loss_and_damage" | "unknown";
  full_value_damage_cover: boolean;
  protection_warning: string;
}

export interface Build3DAsset {
  provider: "meshy";
  status: "queued" | "processing" | "succeeded" | "failed";
  progress?: number;
  meshy_status?: string;
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
  creation_method?: "manual" | "ai" | "gem_spotlight";
  total_cost: number | null;
  ebay_price?: number | null;
  component_count: number;
  status: ManualBuildStatus;
  updated_at: string;
}

export interface AiReadyToShipProposal {
  build_name: string;
  rationale: string;
  components: Array<{
    id: number;
    slot: string;
    name: string;
    classification: "SUPER_GEM" | "GEM";
    deal_score: number;
    price: number;
    listing_url: string;
    image_url: string | null;
  }>;
  estimated_parts_cost: number;
  playbook_recommendation: {
    id: string;
    name: string;
    segment: string;
    tier: string;
    use: string;
    playbook_id: number;
    rationale: string;
  };
  compatibility_notes: string[];
  model: string;
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
  listing_mode: "active" | "sold" | "both";
  created_at: string;
}

// REST calls stay same-origin. The dedicated Next route forwards them to the
// backend after middleware has attached the httpOnly admin_session token.
// NEXT_PUBLIC_API_URL remains reserved for browser-only SSE/websocket callers.
export const API_BASE_URL = "/proxy-api";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function operationLabel(path: string): string {
  if (path.includes("/post-to-ebay")) return "publish this eBay listing";
  if (path.includes("/list-on-storefront"))
    return "add this build to FlipFlop.shop";
  return "complete this request";
}

function apiErrorMessage(
  path: string,
  status: number,
  body: unknown,
  rawText: string
): string {
  const detail =
    body && typeof body === "object"
      ? (body as Record<string, unknown>).detail ??
        (body as Record<string, unknown>).error ??
        (body as Record<string, unknown>).message
      : undefined;
  if (detail) {
    const text = typeof detail === "string" ? detail : JSON.stringify(detail);
    if (text && text !== "Internal Server Error") return text;
  }
  const rawSummary = rawText.trim().replace(/\s+/g, " ").slice(0, 240);
  if (rawSummary && !/^Internal Server Error$/i.test(rawSummary))
    return rawSummary;
  if (status >= 500) {
    return `Could not ${operationLabel(
      path
    )} because the server failed internally (HTTP ${status}). No successful listing response was received; check the backend log and retry.`;
  }
  return `Could not ${operationLabel(
    path
  )} (HTTP ${status}). Check the connection and try again.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Add trailing slash to path only (not end of query string) — backend handles both
  // NOTE: the old regex /([^/])(\?|$)/ was corrupting query params like status=active → status=active/
  const url = apiUrl(path).replace(/([^/])(\?)/, "$1/$2");
  const token = getAdminToken();
  const isMultipart = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const res = await fetch(url, {
    credentials: "include",
    headers: {
      ...(!isMultipart ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    signal: AbortSignal.timeout(120_000),
    redirect: "follow",
    ...init,
  });
  if (!res.ok) {
    const rawText = await res.text();
    let body: unknown;
    try {
      body = JSON.parse(rawText);
    } catch {
      body = undefined;
    }
    throw new Error(apiErrorMessage(path, res.status, body, rawText));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface SoldScrapingItem {
  id: number;
  observed_at: string | null;
  title: string;
  match_key: string;
  condition: string;
  price: number;
  postage: number;
  source_url: string | null;
  cpk: string | null;
  identity_confidence: number | null;
}

export interface PriceEvidenceProduct {
  cpk: string;
  label: string;
  brand: string | null;
  model: string | null;
  category: string | null;
  min_price: number | null;
  median_price: number | null;
  max_price: number | null;
  listing_count: number;
}

async function requestGemRadar<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`/api/gem-radar${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
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
    throw new Error(
      detail ? String(detail) : `Gem Radar ${path} → ${res.status}`
    );
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function qs(params?: Record<string, string | undefined>): string {
  if (!params) return "";
  const p = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined)
  ) as Record<string, string>;
  return Object.keys(p).length ? "?" + new URLSearchParams(p).toString() : "";
}

export const api = {
  marketingCopy: {
    status: () => request<{ total: number; ready: number; remaining: number; enriched: number; source_guides: number }>("/catalogue/marketing-copy/status"),
    generateBatch: (limit = 4) => request<{ total: number; ready: number; remaining: number; enriched: number; source_guides: number; attempted: number; generated: number; failed: { task_key: string; error: string }[] }>(
      "/catalogue/marketing-copy/generate-batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ limit }) },
    ),
  },
  emailEvents: {
    list: () =>
      request<
        Array<{
          id: number;
          subject: string;
          sender: string;
          summary: string;
          event_type: string;
          marketplace?: string | null;
          received_at?: string | null;
          link_url: string;
        }>
      >("/email-events"),
    get: (id: number) =>
      request<{
        id: number;
        subject: string;
        sender: string;
        body: string;
        summary: string;
        event_type: string;
        marketplace?: string | null;
        received_at?: string | null;
      }>(`/email-events/${id}`),
  },
  dispatch: {
    list: () =>
      request<
        Array<{
          id: number;
          name: string;
          status: "built" | "listed" | "sold";
          dispatch_status: string;
          has_physical_handover: boolean;
          portal_order_id?: number | null;
          portal_grant_id?: number | null;
          portal_claim_email_status?: "pending" | "sent" | "failed" | null;
          playbook_assignment?: {playbook_id: number; curated_build_id: string; customer_type: string; budget_tier: string; cell_name: string; software_profile: {recommended_package_ids: string[]; rationale: string}} | null;
          sale_price?: number | null;
          buyer_name?: string | null;
          customer_email?: string | null;
          buyer_address?: Record<string, string> | null;
          collection_date?: string | null;
          tracking_number?: string | null;
          shipping_label_url?: string | null;
          parcel2go_order_id?: string | null;
          parcel2go_order_line_id?: string | null;
          shipment_booked_at?: string | null;
          shipment_booking_state?: string;
          insurance_status?: string;
          insurance_policy_id?: string | null;
          insurance_cost_gbp?: number | null;
          insurance_provider_response?: {
            policy_id?: string | null;
            invoice_id?: string | null;
            insured_value_gbp?: number | null;
            price_gbp?: number | null;
            currency?: string | null;
            mode?: string | null;
            received_at?: string | null;
            mismatches: string[];
          } | null;
          getting_started?: {
            status: string;
            order_id?: number | null;
            software_selections: string[];
            purchased_ai_services: Record<string, unknown>[];
            checklist: Record<string, unknown>;
            shipment_evidence?: Array<{id: string; category: "working_pc" | "package_contents" | "sealed_package"; filename: string; content_type: string; size_bytes: number; sha256: string; uploaded_at: string; uploaded_by_admin_name?: string; review_status?: "needs_review" | "approved" | "rejected"; reviewed_by_admin_name?: string; reviewed_at?: string; review_note?: string}>;
            manifest?: Record<string, unknown> | null;
            cached_component_manuals?: Array<{manual_id: number; component_key: string; component_name: string; source_url: string; filename: string; sha256: string; size_bytes: number}>;
            approved_research_bundle?: Record<string, unknown>[];
            latest_package?: {version: number; filename: string; size_bytes: number; sha256: string; workshop_filename?: string; workshop_size_bytes?: number; workshop_sha256?: string; windows_license_helper_required?: boolean} | null;
            generated_at?: string | null;
          } | null;
        }>
      >("/manual-builds/dispatch-zone"),
    reconcileShipmentBooking: (id: number, payload: {
      resolution: "no_active_booking" | "paid_booking" | "attach_tracking_reference";
      provider_order_id?: string;
      provider_order_line_id?: string;
      tracking_number?: string;
      shipping_label_url?: string;
      note: string;
    }) =>
      request<{success: boolean; shipment_booking_state: string}>(`/manual-builds/${id}/shipment-booking/reconcile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider_checked: true, ...payload }),
      }),
    setCollectionDate: (id: number, collection_date: string) =>
      request<{
        ok: boolean;
        collection_date: string;
        dispatch_status: string;
      }>(`/manual-builds/${id}/collection-date`, {
        method: "PATCH",
        body: JSON.stringify({ collection_date }),
      }),
    generateGettingReady: (id: number, payload: {
      playbook_id?: number;
      curated_build_id?: string;
      playbook_segment?: string;
      customer_software_selections?: string[];
      approved_research_bundle?: Record<string, unknown>[];
      approved_component_manuals?: Record<string, unknown>[];
    }) => request<Record<string, unknown>>(`/manual-builds/${id}/getting-ready/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
    suggestGettingReadySources: (id: number, component_name: string, topic: "driver_firmware" | "manual" | "rgb" | "software" | "compatibility") =>
      request<{
        build_id: number;
        component_name: string;
        topic: typeof topic;
        suggestions: Array<{title: string; source_url: string; publisher: string}>;
        cached_manual_matches: Array<{manual_id: number; component_key: string; component_name: string; source_url: string; filename: string; sha256: string; size_bytes: number}>;
        cache_checked: boolean;
        review_required: true;
        saved: false;
        downloaded: false;
      }>(`/manual-builds/${id}/getting-ready/source-suggestions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ component_name, topic }),
      }),
    approveGettingReadyPackage: (id: number, reviewer_notes?: string, confirm_playbook_defaults_for_indirect_customer = false) =>
      request<{filename: string; version: number; size_bytes: number; sha256: string; workshop_filename: string; workshop_size_bytes: number; workshop_sha256: string; windows_license_helper_required: boolean; download_url: string}>(`/manual-builds/${id}/getting-ready/approve-and-package`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirm_manifest_reviewed: true,
          confirm_customer_details_checked: true,
          confirm_windows_license_handling: true,
          confirm_playbook_defaults_for_indirect_customer,
          reviewer_notes: reviewer_notes || null,
        }),
      }),
    packageDownloadUrl: (id: number, version: number) => apiUrl(`/manual-builds/${id}/getting-ready/package/${version}`),
    downloadSoftwareInstallScript: async (id: number) => {
      const token = getAdminToken();
      const response = await fetch(apiUrl(`/manual-builds/${id}/getting-ready/software-script`), {
        credentials: "include",
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Could not download the reviewed software script.");
      }
      const blobUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `FlipFlop-Build-${id}-software-install.ps1`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    },
    dispatchChecklistDownloadUrl: (id: number) => apiUrl(`/manual-builds/${id}/getting-ready/dispatch-checklist`),
    downloadWindowsLicenseHelper: async (id: number) => {
      const token = getAdminToken();
      const response = await fetch(apiUrl(`/manual-builds/${id}/getting-ready/windows-license-helper`), {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ confirm_private_key_release: true }),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Could not download the Windows licence helper.");
      }
      const blobUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `FlipFlop-Build-${id}-install-windows-license.ps1`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    },
    updateChecklist: (id: number, action: string, status: string, note?: string, windows_deployment_evidence?: Record<string, unknown>, confirm_paid_ai_scope = false, windows_target?: Record<string, unknown>, driver_firmware_outcomes?: Array<{component_id: string; component_name: string; outcome: "updated" | "no_update_applicable"; source_url?: string | null; details: string}>) =>
      request<{action: string; status: string; checklist: Record<string, unknown>}>(`/manual-builds/${id}/getting-ready/checklist/${encodeURIComponent(action)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, note: note || null, evidence_ref: null, windows_deployment_evidence: windows_deployment_evidence || null, windows_target: windows_target || null, confirm_paid_ai_scope, driver_firmware_outcomes: driver_firmware_outcomes || null }),
      }),
    markDispatched: (id: number) =>
      request<{success: boolean; dispatch_status: string; tracking_number?: string; email_sent?: boolean; portal_claim_email_sent?: boolean | null; portal_grant_id?: number | null; portal_claim_email_status?: "pending" | "sent" | "failed" | null; ebay_marked_shipped?: boolean; warning?: string | null}>(`/manual-builds/${id}/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_physical_handover: true }),
      }),
    createGuestPortalClaim: (id: number, orderId: number | null, contact_email: string | null, channel: "direct_guest" | "ebay" | "vinted" | "marketplace" | "printed_insert") =>
      request<{id: number; claim_url: string | null; expires_at: string; delivery_guidance: string; leaflet_download_url: string; email_sent: boolean; email_status: "pending" | "sent" | "failed" | null}>("/admin/portal-access-grants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...(channel === "direct_guest" ? { order_id: orderId } : { manual_build_id: id }), contact_email, channel, expires_in_days: 400 }),
      }),
    portalLeafletDownloadUrl: (grantId: number) => apiUrl(`/admin/portal-access-grants/${grantId}/leaflet`),
    softwareCatalogue: () => request<{items: Array<{package_id: string; name: string; category: string; estimated_minutes_saved: number; license_note: string}>; estimate_basis: string}>("/playbooks/software-catalogue"),
    uploadEvidence: (id: number, category: "working_pc" | "package_contents" | "sealed_package", file: File) => {
      const form = new FormData(); form.set("category", category); form.set("file", file);
      return request<{id: string; category: string; content_type: string; size_bytes: number}>(`/manual-builds/${id}/getting-ready/evidence`, { method: "POST", body: form });
    },
    reviewEvidence: (id: number, artifactId: string, approved: boolean, note: string) =>
      request<{id: string; category: string; review_status: string; reviewed_at: string; reviewed_by_admin_id: number}>(`/manual-builds/${id}/getting-ready/evidence/${encodeURIComponent(artifactId)}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, note }),
      }),
    getEvidenceFile: async (id: number, artifactId: string) => {
      const token = getAdminToken();
      const response = await fetch(apiUrl(`/manual-builds/${id}/getting-ready/evidence/${encodeURIComponent(artifactId)}`), {
        credentials: "include",
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(`Could not retrieve evidence (${response.status})`);
      return response.blob();
    },
    reconcileInsurancePolicy: (id: number, payload: {resolution: "policy_exists" | "no_policy"; provider_checked: true; note: string; policy_id?: string; invoice_id?: string; provider_tracking_number?: string; insured_value_gbp?: number; cost_gbp?: number}) =>
      request<{status: string; policy_id?: string | null; cost_gbp?: number | null; idempotent: boolean}>(
        `/manual-builds/${id}/insurance-policy/reconcile`,
        {method: "POST", body: JSON.stringify(payload)}
      ),
  },
  crossListing: {
    amazonStatus: () =>
      request<{
        connected: boolean;
        configured?: boolean;
        marketplace_found?: boolean;
        message?: string;
        environment?: string;
        marketplace_id?: string;
      }>("/cross-listing/amazon/status"),
    publishAmazon: (
      buildId: number,
      data: {
        title: string;
        description: string;
        bullet_points: string[];
        price: number;
        quantity: number;
        condition: string;
        images: string[];
        sku?: string;
      }
    ) =>
      request<{
        success: boolean;
        status: string;
        sku: string;
        listing_url?: string | null;
        response?: unknown;
        message: string;
      }>(`/cross-listing/amazon/publish/${buildId}`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    settings: () =>
      request<{ indirect_channel_recreate_interval_days: number }>(
        "/cross-listing/settings"
      ),
    saveSettings: (data: { interval_days: number }) =>
      request<{ indirect_channel_recreate_interval_days: number }>(
        "/cross-listing/settings",
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      ),
    schedules: (buildId?: number) =>
      request<
        Array<{
          id: number;
          build_id: number;
          channel: string;
          status: string;
          external_listing_id?: string | null;
          published_at?: string | null;
          withdrawn_at?: string | null;
          updated_at?: string | null;
          recreate_enabled: boolean;
          interval_days?: number | null;
          next_recreate_at?: string | null;
          last_recreate_at?: string | null;
          recreate_count: number;
          last_recreate_status?: string | null;
          last_recreate_message?: string | null;
        }>
      >(`/cross-listing/schedules${buildId ? `?build_id=${buildId}` : ""}`),
    saveSchedule: (data: {
      build_id: number;
      channel: string;
      interval_days: number;
      enabled: boolean;
    }) =>
      request<unknown>("/cross-listing/schedules", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    recordCodexResult: (
      eventId: number,
      data: {
        success: boolean;
        message: string;
        external_listing_id?: string;
        listing_url?: string;
      }
    ) =>
      request<unknown>(`/cross-listing/actions/${eventId}/codex-result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    actions: (buildId?: number) =>
      request<
        Array<{
          id: number;
          build_id: number;
          channel: string;
          event_type: string;
          message?: string | null;
          metadata?: Record<string, unknown> | null;
          created_at?: string | null;
        }>
      >(`/cross-listing/actions${buildId ? `?build_id=${buildId}` : ""}`),
  },
  priceAlerts: {
    list: () => request<PriceAlertList>("/price-alerts"),
    create: (data: {
      manual_build_id: number;
      user_email: string;
      target_price_gbp: number;
    }) =>
      request<PriceAlert>("/price-alerts", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    dismiss: (id: number) =>
      request<{ ok: boolean }>(`/price-alerts/${id}/dismiss`, {
        method: "POST",
      }),
    rearm: (id: number) =>
      request<{ ok: boolean }>(`/price-alerts/${id}/re-arm`, {
        method: "POST",
      }),
    history: (id: number) =>
      request<{
        items: Array<{
          id: number;
          event_type: string;
          price_gbp: number | null;
          notes: string | null;
          created_at: string;
        }>;
      }>(`/price-alerts/${id}/history`),
  },
  listings: {
    // DEPRECATED: Use gemRadar.scoredListings instead
    list: (params?: Record<string, string>) =>
      request<unknown[]>(`/listings/${qs(params)}`),
    stats: () =>
      request<{
        total_listings: number;
        gems_count: number;
        avg_profit: number;
      }>("/listings/stats"),
    get: (id: number) => request<unknown>(`/listings/${id}`),
  },

  gemRadar: {
    scoredListings: () => requestGemRadar<unknown[]>("/scored-listings"),
    scoredListingsLatestRun: (environment?: "DEV" | "LIVE", limit = 500) =>
      requestGemRadar<unknown[]>(
        `/scored-listings-latest-run${
          `?${new URLSearchParams({
            ...(environment ? { environment } : {}),
            limit: String(limit),
          }).toString()}`
        }`
      ),
    listings: () => requestGemRadar<unknown[]>("/listings"),
    currentGem: () => requestGemRadar<unknown>("/current-gem"),
    // This read model belongs to the main API database. Use the main API
    // proxy rather than the separately deployed Gem Radar worker, whose
    // route set can lag behind during a rolling deployment.
    opportunityPolicyData: () =>
      request<{
        active_scored_count: number;
        total_scored_count: number;
        historical_scored_count: number;
        items: Array<{
          listing_id: string;
          title: string;
          category: string | null;
          condition: string | null;
          classification: string;
          deal_score: number | null;
          expected_profit: number | null;
          roi_pct: number | null;
          market_confidence: number | null;
          market_sample_size: number | null;
          market_source_diversity: number | null;
          liquidity_score: number | null;
          desirability_score: number | null;
          risk_score: number | null;
          eligible: boolean;
          listing_price: number | null;
          resale_price: number | null;
          market_new_price: number | null;
          market_used_price: number | null;
          sold_count: number | null;
          active_count: number | null;
          scoring_explanation: {
            risk_flags?: string[];
            reasons?: string[];
          } | null;
          evidence_status: string | null;
          evidence_reason: string | null;
        }>;
      }>("/gem-radar/opportunity-policy-data", { cache: "no-store" }),
    // Whole-DB market snapshot (all currently-active listings, not just the
    // latest scan run) — same shape as the Current Scan Run panel's stats.
    marketSnapshot: () =>
      requestGemRadar<MarketSnapshot>("/market-snapshot", {
        cache: "no-store",
        // The whole-market aggregation can be slower than the interactive
        // dashboard reads. Bound it independently so it can fail and refresh
        // later without leaving page loading dependent on this endpoint.
        signal: AbortSignal.timeout(30_000),
      }),
    // Real scan cadence derived from actual observation activity, since
    // there's no backend-scheduled "next scan" job (scanning happens
    // client-side in the browser extension) — see the endpoint's docstring.
    scanScheduleStatus: () =>
      requestGemRadar<ScanScheduleStatus>("/scan-schedule-status"),
  },

  flips: {
    list: () => request<unknown[]>("/flips"),
    get: (id: number) => request<unknown>(`/flips/${id}`),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/flips", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    patch: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/flips/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/flips/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    markSold: (
      id: number,
      data: { actual_sale_price: number; sale_platform: string }
    ) =>
      request<unknown>(`/flips/${id}/sold`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
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
      request<{ titles: string[]; description: string }>(
        `/flips/${id}/generate-listing`,
        { method: "POST" }
      ),
    generateImages: (id: number) =>
      request<{ images: string[] }>(`/flips/${id}/generate-images`, {
        method: "POST",
      }),
    uploadVideo: async (id: number, file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE_URL}/flips/${id}/upload-video`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Video upload failed: ${res.status}`);
      return res.json() as Promise<{
        video_url: string;
        video_ebay_status: string;
      }>;
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
      request<{
        published: boolean;
        reason?: string;
        ebay_listing_url?: string;
      }>(`/flips/${id}/publish-now`, { method: "POST" }),
    pricingSuggestions: (id: number) =>
      request<{
        shipping: {
          estimated_weight_kg: number;
          estimated_shipping_cost: number;
          shipping_inclusive_price: number;
        };
        promoted_listings: {
          suggested_ad_rate_pct: number;
          too_thin_to_promote: boolean;
          max_ad_spend: number;
          reason: string;
        };
      }>(`/flips/${id}/pricing-suggestions`),
    watcherOfferPlan: (id: number) =>
      request<{
        should_send: boolean;
        discount_pct: number;
        offer_price: number | null;
        reason: string;
      }>(`/flips/${id}/watcher-offer-plan`),
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
    list: (category?: string) =>
      request<unknown[]>(`/parts${category ? `?category=${category}` : ""}`),
    grouped: (category?: string) =>
      request<unknown[]>(
        `/parts/grouped${category ? `?category=${category}` : ""}`
      ),
    cases: (params?: Record<string, string>) =>
      request<unknown[]>(`/parts/cases${qs(params)}`),
    themes: () => request<string[]>("/parts/themes"),
  },

  manualBuilds: {
    list: () => request<ManualBuildSummary[]>("/manual-builds/"),
    get: (id: number) => request<ManualBuild>(`/manual-builds/${id}`),
    generateAi: () => request<AiReadyToShipProposal>("/manual-builds/ai-generate", { method: "POST" }),
    createAi: (data: { component_ids: number[]; playbook_id: number; curated_build_id: string; build_name: string; rationale: string; playbook_rationale: string }) =>
      request<ManualBuild>("/manual-builds/ai-create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    createGemSpotlightDraft: (data: { listing_ids: number[]; build_name: string; concept?: "best" | "cheapest" | "highest_end" | "most_profitable" | "most_popular" }) =>
      request<ManualBuild>("/manual-builds/gem-spotlight-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    getFaqs: (id: number) =>
      request<BuildFaqSelection>(`/manual-builds/${id}/faqs`),
    updateFaqs: (
      id: number,
      selectedIds: string[],
      answerOverrides: Record<string, string>
    ) =>
      request<{ selected_ids: string[]; selected_faqs: ProductFaq[] }>(
        `/manual-builds/${id}/faqs`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            selected_ids: selectedIds,
            answer_overrides: answerOverrides,
          }),
        }
      ),
    create: (name: string, playbookCell?: { playbook_id: number; curated_build_id: string }) =>
      request<ManualBuild>("/manual-builds/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, ...playbookCell }),
      }),
    patch: (
      id: number,
      data: { name?: string; components?: BuildComponent[] }
    ) =>
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
      request<ManualBuild>(`/manual-builds/${id}/mark-built`, {
        method: "POST",
      }),
    purchaseComponent: (
      id: number,
      slot: string,
      data: { price_paid?: number; source?: string }
    ) =>
      request<ManualBuild>(
        `/manual-builds/${id}/components/${encodeURIComponent(slot)}/purchase`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      ),
    getComponentRatings: (id: number) =>
      request<ComponentRating[]>(`/manual-builds/${id}/component-ratings`),
    saveComponentRatings: (id: number, ratings: ComponentRating[]) =>
      request<{
        saved: number;
        preferred_added: number;
        alerts_created: number;
        alerts_updated: number;
      }>(`/manual-builds/${id}/component-ratings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ratings }),
      }),
    generateListing: (id: number) =>
      request<{
        titles: string[];
        description: string;
        aspects: Record<string, string[]>;
      }>(`/manual-builds/${id}/generate-listing`, { method: "POST" }),
    generateSpecifics: (id: number) =>
      request<{
        titles: string[];
        description: string;
        aspects: Record<string, string[]>;
      }>(`/manual-builds/${id}/generate-specifics`, { method: "POST" }),
    updateListingTitle: (id: number, title: string) =>
      request<ManualBuild>(`/manual-builds/${id}/listing-title`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      }),
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
    updateEbayConfig: (
      id: number,
      config: Partial<
        Pick<
          ManualBuild,
          | "ebay_condition"
          | "ebay_price"
          | "allow_offers"
          | "auto_reject_below_price"
          | "auction_start_price"
          | "return_days"
          | "shipping_method"
          | "shipping_cost"
          | "marketplace_fees_actual"
          | "promotion_cost_actual"
          | "refund_amount"
          | "warranty_claim_cost"
          | "handling_time_days"
          | "ships_to_countries"
          | "domestic_only"
          | "shipping_damage_cover_confirmed"
          | "fulfillment_policy_id"
          | "package_weight_kg"
          | "package_length_cm"
          | "package_width_cm"
          | "package_height_cm"
          | "deferred_publish_at"
        >
      >
    ) =>
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
        `/manual-builds/${id}/courier-quote${
          deliveryCountry ? `?delivery_country=${deliveryCountry}` : ""
        }`,
        { method: "POST" }
      ),
    // Fetches the build's real eBay order — buyer name, actual delivery
    // address, actual sale price — only possible once it's actually sold.
    syncEbayOrder: (id: number) =>
      request<SyncEbayOrderResult>(`/manual-builds/${id}/sync-ebay-order`, {
        method: "POST",
      }),
    // Books and pays for a real Parcel2Go shipment, then pushes tracking to
    // eBay. Spends real money — only call from an explicit user confirmation.
    bookShipment: (
      id: number,
      data: { service_slug: string; price_gbp: number; signed_for_delivery_confirmed?: boolean; confirm_live_purchase: boolean }
    ) =>
      request<BookShipmentResult>(`/manual-builds/${id}/book-shipment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    postToEbay: (
      id: number,
      data: { price: number; condition: string; publish?: boolean; images?: string[]; title?: string; description?: string }
    ) =>
      request<{
        success: boolean;
        listing_id?: string;
        url?: string;
        error?: string;
        action?: "posted" | "updated";
        draft_id?: string;
        draft_url?: string;
      }>(`/manual-builds/${id}/post-to-ebay`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    publishEbayDraft: (id: number) =>
      request<{
        success: boolean;
        listing_id?: string;
        url?: string;
        error?: string;
      }>(`/manual-builds/${id}/publish-ebay-draft`, { method: "POST" }),
    getInsuranceQuote: (id: number, listingValueGbp: number) =>
      request<InsuranceQuote>(
        `/manual-builds/${id}/insurance-quote?listing_value_gbp=${encodeURIComponent(
          listingValueGbp
        )}`,
        { method: "POST" }
      ),
    createInsurancePolicy: (id: number, quotedPriceGbp: number, confirmations: { signedForDelivery: boolean; doublePackaging: boolean; discreetPackaging: boolean; rigidOuterContainer: boolean; contentsNotDeducible: boolean; directSignature: boolean; officialCarrierHandover: boolean }) =>
      request<{status: string; policy_id?: string; invoice_id?: string | null; cost_gbp?: number; idempotent?: boolean}>(
        `/manual-builds/${id}/insurance-policy`,
        { method: "POST", body: JSON.stringify({ confirm_terms: true, confirm_live_purchase: true, confirm_customer_data_share: true, confirm_signed_for_delivery: confirmations.signedForDelivery, confirm_double_packaging: confirmations.doublePackaging, confirm_discreet_packaging: confirmations.discreetPackaging, confirm_rigid_outer_container: confirmations.rigidOuterContainer, confirm_contents_not_deducible: confirmations.contentsNotDeducible, confirm_direct_signature: confirmations.directSignature, confirm_official_carrier_handover: confirmations.officialCarrierHandover, quoted_price_gbp: quotedPriceGbp }) }
      ),
    reconcileInsurancePolicy: (id: number, payload: {resolution: "policy_exists" | "no_policy"; provider_checked: true; note: string; policy_id?: string; invoice_id?: string; provider_tracking_number?: string; insured_value_gbp?: number; cost_gbp?: number}) =>
      request<{status: string; policy_id?: string | null; cost_gbp?: number | null; idempotent: boolean}>(
        `/manual-builds/${id}/insurance-policy/reconcile`,
        {method: "POST", body: JSON.stringify(payload)}
      ),
    endEbayListing: (id: number) =>
      request<ManualBuild>(`/manual-builds/${id}/ebay-listing`, {
        method: "DELETE",
      }),
    uploadPhotos: async (
      id: number,
      files: File[],
      kind: "photo" | "performance_card" = "photo"
    ): Promise<ManualBuild> => {
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
    updateEvidenceData: (
      id: number,
      kind: "spec_card" | "registration_plate" | "performance_card",
      data: Record<string, unknown>
    ) =>
      request<ManualBuild>(`/manual-builds/${id}/evidence-data`, {
        method: "PUT",
        body: JSON.stringify({ kind, data }),
      }),
    uploadBrandedAsset: async (
      id: number,
      kind: "spec_card" | "registration_plate",
      blob: Blob
    ): Promise<ManualBuild> => {
      const formData = new FormData();
      formData.append("file", blob, `${kind}.png`);
      const token = getAdminToken();
      const res = await fetch(
        `${API_BASE_URL}/manual-builds/${id}/photos/branded?kind=${kind}`,
        {
          method: "POST",
          body: formData,
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        }
      );
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
        const detail = await res
          .json()
          .then((body) => body?.detail)
          .catch(() => undefined);
        throw new Error(
          detail ? String(detail) : `3D model upload failed (${res.status})`
        );
      }
      return res.json();
    },
    generate3dAssets: (id: number, assets: Record<string, string[]>) =>
      request<{ queued: string[]; assets: Record<string, Build3DAsset> }>(
        `/manual-builds/${id}/model-3d/generate`,
        {
          method: "POST",
          body: JSON.stringify({ assets }),
        }
      ),
    generate3dAssetsWithUploads: async (
      id: number,
      selectedUrls: string[],
      files: File[]
    ) => {
      const formData = new FormData();
      formData.append("selected_urls", JSON.stringify(selectedUrls));
      for (const file of files) formData.append("files", file);
      const token = getAdminToken();
      const res = await fetch(
        `${API_BASE_URL}/manual-builds/${id}/model-3d/generate-upload`,
        {
          method: "POST",
          body: formData,
          credentials: "include",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        }
      );
      if (!res.ok) {
        const detail = await res
          .json()
          .then((body) => body?.detail)
          .catch(() => undefined);
        throw new Error(
          detail
            ? String(detail)
            : `3D generation upload failed (${res.status})`
        );
      }
      return res.json() as Promise<{
        queued: string[];
        assets: Record<string, Build3DAsset>;
      }>;
    },
    removePhoto: (id: number, url: string) =>
      request<ManualBuild>(`/manual-builds/${id}/photos`, {
        method: "DELETE",
        body: JSON.stringify({ url }),
      }),
    reorderPhotos: (id: number, urls: string[]) =>
      request<ManualBuild>(`/manual-builds/${id}/photos/order`, {
        method: "PUT",
        body: JSON.stringify({ urls }),
      }),
    setHeroPhoto: (id: number, url: string) =>
      request<ManualBuild>(`/manual-builds/${id}/photos/hero`, {
        method: "POST",
        body: JSON.stringify({ url }),
      }),
    listOnStorefront: (id: number, price: number) =>
      request<{
        product_id: number;
        build_id: number;
        storefront_url?: string;
      }>(`/manual-builds/${id}/list-on-storefront`, {
        method: "POST",
        body: JSON.stringify({ price }),
      }),
  },

  sources: {
    list: () => request<unknown[]>("/sources"),
    health: () =>
      request<{ avg_health_score: number; items: unknown[] }>(
        "/sources/health"
      ),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/sources", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/sources/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/sources/${id}`, { method: "DELETE" }),
    trigger: (id: number) =>
      request<unknown>(`/sources/${id}/scrape`, { method: "POST" }),
  },

  searchTelemetry: {
    recent: (limit?: number) =>
      request<{ items: SearchTelemetryItem[] }>(
        `/search-telemetry/recent${limit ? `?limit=${limit}` : ""}`
      ),
    bySource: (limit?: number) =>
      request<{
        summary: Record<string, SearchTelemetrySourceSummary>;
        items: Record<string, SearchTelemetryItem[]>;
      }>(`/search-telemetry/by-source${limit ? `?limit=${limit}` : ""}`),
  },

  config: {
    get: () => request<unknown>("/config/search"),
    update: (data: Record<string, unknown>) =>
      request<unknown>("/config/search", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
  },

  settings: {
    get: () => request<unknown>("/settings"),
    aiSetupOffers: () => request<{offers: Array<{id: string; name: string; description: string; requires_vram_gb: number | null; enabled: boolean; price_gbp: number | null; commercial_scope_reviewed: boolean}>}>("/settings/ai-setup-offers"),
    updateAISetupOffers: (offers: Array<{id: string; enabled: boolean; price_gbp: number | null}>, confirm_commercial_scope_review: boolean) => request<{offers: Array<{id: string; name: string; description: string; requires_vram_gb: number | null; enabled: boolean; price_gbp: number | null; commercial_scope_reviewed: boolean}>}>("/settings/ai-setup-offers", {method: "PUT", body: JSON.stringify({offers, confirm_commercial_scope_review})}),
    gettingStartedGuide: () => request<{ uploaded: boolean; filename: string | null; sha256: string | null; size_bytes?: number }>("/settings/getting-started-guide"),
    uploadGettingStartedGuide: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<{ uploaded: boolean; filename: string; sha256: string; size_bytes: number }>("/settings/getting-started-guide", { method: "PUT", body: form });
    },
    componentManuals: () => request<{items: Array<{id: number; component_key: string; component_name: string; source_url: string; filename: string; sha256: string; size_bytes: number; is_active: boolean}>}>("/settings/component-manuals"),
    uploadComponentManual: (data: {component_key: string; component_name: string; source_url: string; file: File; confirm_official_source: boolean}) => {
      const form = new FormData();
      form.set("component_key", data.component_key);
      form.set("component_name", data.component_name);
      form.set("source_url", data.source_url);
      form.set("confirm_official_source", String(data.confirm_official_source));
      form.set("file", data.file);
      return request<{id: number; component_key: string; component_name: string; source_url: string; filename: string; sha256: string; size_bytes: number; is_active: boolean}>("/settings/component-manuals", {method: "POST", body: form});
    },
    setComponentManualActive: (id: number, active: boolean) => request<{id: number; is_active: boolean}>(`/settings/component-manuals/${id}/active?active=${active}`, {method: "PATCH"}),
    update: (data: Record<string, unknown>) =>
      request<unknown>("/settings", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
  },

  sourceSearchTerms: {
    list: (scope?: string) =>
      request<{
        items: SourceSearchTerm[];
        groups: string[];
        scopes: string[];
      }>(
        `/source-search-terms${
          scope ? `?scope=${encodeURIComponent(scope)}` : ""
        }`
      ),
    create: (data: Record<string, unknown>) =>
      request<SourceSearchTerm>("/source-search-terms", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Record<string, unknown>) =>
      request<SourceSearchTerm>(`/source-search-terms/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/source-search-terms/${id}`, { method: "DELETE" }),
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
    bySource: () =>
      request<
        {
          source: string;
          count: number;
          avg_profit: number;
          total_profit: number;
        }[]
      >("/intel/by-source"),
    byCpuTier: () =>
      request<{ cpu_tier: string; count: number; avg_profit: number }[]>(
        "/intel/by-cpu"
      ),
    byPlatform: () =>
      request<{ platform: string; count: number; avg_profit: number }[]>(
        "/intel/by-platform"
      ),
    history: (params?: Record<string, string>) =>
      request<unknown[]>(`/intel/history${qs(params)}`),
    recommendations: () =>
      request<{ insight: string; action: string; confidence: number }[]>(
        "/intel/recommendations"
      ),
    retrainStatus: () =>
      request<{
        checkpoint: string;
        sold_flips_since: number;
        retrain_ready: boolean;
        last_flip_id: number;
        updated_at: string | null;
      }>("/intel/retrain-status"),
    modelVersions: (limit = 20) =>
      request<{ items: unknown[] }>(`/intel/models/versions?limit=${limit}`),
    modelRuns: (limit = 30) =>
      request<{ items: unknown[] }>(`/intel/models/runs?limit=${limit}`),
  },

  chat: {
    send: (
      message: string,
      history: { role: string; content: string }[],
      listing_id?: number
    ) =>
      request<{ response: string; model_used: string }>("/chat", {
        method: "POST",
        body: JSON.stringify({ message, history, listing_id }),
      }),
  },

  swarms: {
    list: () => request<unknown[]>("/swarms"),
    trigger: (id: string) =>
      request<unknown>(`/swarms/${id}/trigger`, { method: "POST" }),
    scanStatus: () => request<ScanStatus>("/swarms/scan/status"),
  },

  schedule: {
    list: () => request<ScheduleJob[]>("/schedule"),
    toggle: (id: string) =>
      request<{ ok: boolean; enabled: boolean }>(`/schedule/${id}/toggle`, {
        method: "POST",
      }),
    run: (id: string) =>
      request<{
        ok: boolean;
        status: "success" | "failed";
        duration_ms: number;
      }>(`/schedule/${id}/run`, { method: "POST" }),
    runs: (id: string) => request<ScheduleRun[]>(`/schedule/${id}/runs`),
  },

  alerts: {
    list: (limit = 100, includeAcked = false) =>
      request<unknown[]>(
        `/alerts?limit=${limit}&include_acked=${
          includeAcked ? "true" : "false"
        }`
      ),
    ack: (id: number) =>
      request<{ ok: boolean }>(`/alerts/${id}/ack`, { method: "POST" }),
  },

  favourites: {
    list: () =>
      request<{ items: import("./types").Favourite[]; groups: string[] }>(
        "/favourites"
      ),
    search: (q: string) =>
      request<import("./types").FavouriteMatrixRow>(
        `/favourites/search?q=${encodeURIComponent(q)}`
      ),
    matrix: () =>
      request<Record<number, import("./types").FavouriteMatrixRow>>(
        "/favourites/matrix"
      ),
    create: (
      term?: string | null,
      category?: string | null,
      cpk?: string | null
    ) =>
      request<import("./types").Favourite>("/favourites", {
        method: "POST",
        body: JSON.stringify({
          term: term ?? null,
          category: category ?? null,
          cpk: cpk ?? null,
        }),
      }),
    update: (id: number, category: string) =>
      request<import("./types").Favourite>(`/favourites/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ category }),
      }),
    remove: (id: number) =>
      request<void>(`/favourites/${id}`, { method: "DELETE" }),
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
      return fetch(url, {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(45_000),
      }).then((r) => {
        if (!r.ok)
          return r.json().then((d) => {
            throw new Error(d.detail || `HTTP ${r.status}`);
          });
        return r.json();
      }) as Promise<import("./types").Listing>;
    },
  },

  demand: {
    categories: () =>
      request<import("./types").DemandCategory[]>("/demand/categories"),
    auctionIntel: (limit?: number) =>
      request<import("./types").AuctionIntelItem[]>(
        `/demand/auction-intel${limit ? `?limit=${limit}` : ""}`
      ),
    summary: () => request<import("./types").DemandSummary>("/demand/summary"),
    soldMarket: (days = 90) =>
      request<import("./types").SoldMarketDemand>(
        `/demand/sold-market?days=${days}`
      ),
    soldMarketListings: (
      category: import("./types").SoldComponentCategory,
      days = 90,
      limit = 250
    ) =>
      request<import("./types").SoldMarketListing[]>(
        `/demand/sold-market/listings?category=${category}&days=${days}&limit=${limit}`
      ),
    soldMarketInsights: (days = 90, refresh = false) =>
      request<import("./types").SoldMarketInsight>(
        `/demand/sold-market/insights?days=${days}&refresh=${refresh}`
      ),
    externalSignals: (limit_per_source?: number) =>
      request<{
        summary: Record<
          string,
          { count: number; avg_score: number; avg_confidence: number }
        >;
        items: Record<string, unknown[]>;
      }>(
        `/demand/external-signals${
          limit_per_source ? `?limit_per_source=${limit_per_source}` : ""
        }`
      ),
    refreshExternalSignals: () =>
      request<{
        ok: boolean;
        inserted: number;
        topics: number;
        signals: number;
      }>("/demand/external-signals/refresh", { method: "POST" }),
    richSignals: () =>
      request<{
        google_trends: {
          queries: string[];
          timeseries: Record<string, { date: string; value: number }[]>;
          geo: Record<
            string,
            { region: string; code: string | null; value: number }[]
          >;
        };
        reddit: {
          posts: {
            reddit_id: string;
            query: string;
            topic: string;
            title: string;
            subreddit: string;
            score: number;
            comments: number;
            url: string | null;
            created_utc: string | null;
          }[];
        };
        steam: {
          stats: {
            category: string;
            name: string;
            percentage: number;
            change: number | null;
            collected_at: string | null;
          }[];
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
    status: () =>
      request<{
        exists: boolean;
        valid: boolean;
        expired: boolean;
        expiry_warning: boolean;
        message: string;
        days_remaining?: number;
      }>("/facebook/status"),
    updateCookies: (cookies_json: string) =>
      request<{ ok: boolean; message: string }>("/facebook/cookies", {
        method: "PUT",
        body: JSON.stringify({ cookies_json }),
      }),
  },
  preflight: {
    antibotStatus: () => request<AntiBotPreflightStatus>("/preflight/antibot"),
    triggerAntibot: () =>
      request<{ ok: boolean; started: boolean; reason?: string }>(
        "/preflight/antibot/trigger",
        {
          method: "POST",
        }
      ),
  },

  buildWizard: {
    componentCandidates: () =>
      request<{
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
    generateGemMatrix: (
      body: Omit<GenerateRequest, "playbook_id"> & {
        gem_limit?: number;
        playbook_limit?: number;
        listing_id?: number;
      }
    ) =>
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

  commercialReadiness: {
    mvpRules: () => request<import('@/components/playbooks/PlaybookOperatingRules').MvpRules>('/commerce-intelligence/playbook-service/mvp-rules'),
    saveMvpRules: (body: {enabled:boolean;budget_ceilings:Record<string,number>;max_price_change_fraction:number}) => request<{enabled:boolean;job:unknown}>('/commerce-intelligence/playbook-service/mvp-rules', {method:'PUT',body:JSON.stringify(body)}),
    market: (parent: number, cell: string) => request<import('@/components/playbooks/PlaybookMarketReview').MarketReview>(`/commerce-intelligence/playbook-service/market/${parent}/${encodeURIComponent(cell)}`),
    collectMarket: (parent: number, cell: string) => request<import('@/components/playbooks/PlaybookMarketReview').MarketReview>(`/commerce-intelligence/playbook-service/market/${parent}/${encodeURIComponent(cell)}/collect`, {method:'POST'}),
    reviewMarket: (parent: number, cell: string, body: {batch_id:number;decision:'approve'|'reject';candidate_ids:string[];exact_build_confirmed:boolean}) => request<import('@/components/playbooks/PlaybookMarketReview').MarketReview>(`/commerce-intelligence/playbook-service/market/${parent}/${encodeURIComponent(cell)}/review`, {method:'POST',body:JSON.stringify(body)}),
    book: () => request<import('./playbook-book').PlaybookBook>('/commerce-intelligence/playbook-service/book'),
    refreshPricingGuidance: () => request<{queued:boolean;checkout_changed:false;published:false}>('/commerce-intelligence/playbook-service/pricing-guidance/refresh', {method:'POST'}),
    proposals: () => request<{items:import('./playbook-proposals').PlaybookOffer[]}>('/commerce-intelligence/playbook-service/proposals', {cache:'no-store'}),
    supplierLicences: () => request<{items:import('./playbook-proposals').SupplierLicenceCandidate[]}>('/commerce-intelligence/playbook-service/supplier-licences'),
    approveSupplierLicence: (candidate:import('./playbook-proposals').SupplierLicenceCandidate) =>
      request<{listing_id:number;reviewed:true;reused:boolean;category:'os'|'office'|'ai_subscription';activated_catalogue_links:number;prices_published:false;checkout_changed:false;customer_offering_enabled:false}>(`/commerce-intelligence/playbook-service/supplier-licences/${candidate.listing_id}/approve`,{method:'POST',body:JSON.stringify({licence_review_fingerprint:candidate.licence_review_fingerprint})}),
    engineeringSuggestions: () => request<{items:import('./playbook-proposals').MotherboardEngineeringSuggestion[]}>('/commerce-intelligence/playbook-service/engineering-suggestions'),
    productEngineeringSuggestions: () => request<{items:import('./playbook-proposals').ProductEngineeringSuggestion[]}>('/commerce-intelligence/playbook-service/product-engineering-suggestions'),
    approveProductEngineeringSuggestion: (item:import('./playbook-proposals').ProductEngineeringSuggestion,replaceReviewedValues=false) =>
      request<{listing_id:number;role:string;approved_specs:Record<string,unknown>;reviewed:true;published:false}>(`/commerce-intelligence/playbook-service/product-engineering-suggestions/${item.listing_id}/approve`,{method:'POST',body:JSON.stringify({fingerprint:item.fingerprint,...(replaceReviewedValues?{replace_reviewed_values:true}:{})})}),
    researchEngineeringSuggestions: () => request<{created_count:number;created:{canonical_model:string;source_title:string}[];skipped:number;unresolved:string[];reviewed:false;published:false}>('/commerce-intelligence/playbook-service/engineering-suggestions/research',{method:'POST'}),
    approveEngineeringSuggestion: (id:number) => request<{id:number;canonical_model:string;reviewed:true;published:false}>(`/commerce-intelligence/playbook-service/engineering-suggestions/${id}/approve`,{method:'POST'}),
    refreshProposals: () => request<{job_id:string;status:'queued'|'running'|'succeeded'|'failed';phase:string;started:boolean}>('/commerce-intelligence/playbook-service/refresh',{method:'POST'}),
    rebuildProposals: () => request<{job_id:string;mode:'rebuild';status:'queued'|'running'|'succeeded'|'failed';phase:string;started:boolean}>('/commerce-intelligence/playbook-service/rebuild',{method:'POST'}),
    automation: () => request<{setting_enabled:boolean;registered:boolean;enabled:boolean;next_run_at:string|null;scheduled_latest:import('./playbook-proposals').PlaybookRefreshRun|null;scheduled_rebuild_latest:import('./playbook-proposals').PlaybookRefreshRun|null;manual_latest:import('./playbook-proposals').PlaybookRefreshRun|null}>('/commerce-intelligence/playbook-service/automation'),
    refreshStatus: (jobId:string) => request<{job_id:string;mode?:'refresh'|'rebuild';status:'queued'|'running'|'succeeded'|'failed';phase:string;error:string|null;result?:{cells:number;complete_hardware:number;ready_for_approval:number;published?:false;catalogue_sync?:{source_products:number;created_listings:number;created_variants:number;new_products_published:0};bestseller_refresh?:{scraped:number;matched:number;categories:number;errors:number};gamers_outlet_refresh?:{attempted:number;captured:number;retained:number;unresolved:number;published:false;reason?:string};product_capture?:{attempted:number;captured:number;retained:number;unresolved:number;amazon_catalogue_attributes?:{attempted:number;captured:number;unresolved:number;unavailable:number;cached_unavailable:number;status:string};published:false}}}>(`/commerce-intelligence/playbook-service/refresh/${encodeURIComponent(jobId)}`),
    reviewProposal: (offer:import('./playbook-proposals').PlaybookOffer,decision:'approve'|'reject') =>
      request<{status:string}>(`/commerce-intelligence/playbook-service/proposals/${offer.proposal_id}/${decision}`,{method:'POST',body:JSON.stringify({revision_sha256:offer.revision_sha256})}),
    compatibilitySecondOpinion: (offer:import('./playbook-proposals').PlaybookOffer) =>
      request<import('./playbook-proposals').CompatibilitySecondOpinion>(`/commerce-intelligence/playbook-service/proposals/${offer.proposal_id}/compatibility-second-opinion`,{method:'POST',body:JSON.stringify({revision_sha256:offer.revision_sha256})}),
    approveSupplierSources: (offer:import('./playbook-proposals').PlaybookOffer,source_evidence:Array<{role:string;listing_id:number;fingerprint:string}>) =>
      request<{imported:number;reused:number;pending_roles:string[];checkout_changed:false;prices_published:false}>(`/commerce-intelligence/playbook-service/proposals/${offer.proposal_id}/approve-supplier-sources`,{method:'POST',body:JSON.stringify({revision_sha256:offer.revision_sha256,source_evidence})}),
    approveAllSupplierSources: (offers:Array<import('./playbook-proposals').PlaybookOffer & {source_evidence:Array<{role:string;listing_id:number;fingerprint:string}>}>) =>
      request<{proposals:number;skipped_proposals:number;imported:number;reused:number;pending_roles:{cell_id:string;role:string}[];prices_published:false}>('/commerce-intelligence/playbook-service/supplier-sources/approve-all',{method:'POST',body:JSON.stringify({proposals:offers.map(offer=>({proposal_id:offer.proposal_id,revision_sha256:offer.revision_sha256,source_evidence:offer.source_evidence}))})}),
    configurations: () => request<{items:import('./commercial-readiness').ConfigurationReview[]}>('/commerce-intelligence/configurations'),
    configuration: (id:number) => request<import('./commercial-readiness').ConfigurationDetail>(`/commerce-intelligence/configurations/${id}`),
    approveConfiguration: (id:number,reviewSha?:string|null) =>
      request<{checkout_enabled:boolean;policy_version:number;assessment:unknown}>(`/commerce-intelligence/configurations/${id}/policy`,{method:'PUT',body:JSON.stringify({review_sha256:reviewSha})}),
    importConfiguration: (detail:import('./commercial-readiness').ConfigurationDetail,entries:import('./commercial-readiness').ConfigurationEvidenceSelection[]) =>
      request<{imported:number;reused:number;blocked:string[];checkout_changed:false}>(`/commerce-intelligence/configurations/${detail.request_id}/import-evidence`,{method:'POST',body:JSON.stringify({definition_sha256:detail.definition_sha256,case_id:detail.parts.find(part=>part.role==='case')?.case_id??null,entries})}),
    saveCapacity: (body:{build_week:string;available_builds:number;observed_at:string;evidence_source:string;evidence_ref:string}) =>
      request<{id:number;build_week:string;available_builds:number}>('/commerce-intelligence/workshop-capacity-evidence',{method:'POST',body:JSON.stringify(body)}),
    health: () => request<import('./commercial-readiness').ReconciliationHealth>('/commerce-intelligence/reconciliation/health'),
    reconcile: () => request<{audit_id:number;status:string;imported?:number;reused?:number}>('/commerce-intelligence/reconciliation/run',{method:'POST'}),
    list: () => request<import('./commercial-readiness').ReadinessIndex>('/commerce-intelligence/readiness'),
    detail: (playbookId:number,cellId:string,caseId?:number,resetDraft=false) => {
      const query=new URLSearchParams();
      if(caseId) query.set('case_id',String(caseId));
      if(resetDraft) query.set('reset_draft','true');
      return request<import('./commercial-readiness').ReadinessDetail>(`/commerce-intelligence/playbooks/${playbookId}/cells/${encodeURIComponent(cellId)}/readiness${query.size?'?'+query:''}`);
    },
  },

  playbooks: {
    curatedCells: () => request<{items: Array<{id: string; name: string; segment: string; tier: string; playbook_id: number | null}>}>("/curated-builds/definitions"),
    list: (status?: string) =>
      request<import("./types").Playbook[]>(
        `/playbooks${status ? `?status=${status}` : ""}`
      ),
    ranked: () => request<import("./types").Playbook[]>("/playbooks/ranked"),
    seed: () =>
      request<{ ok: boolean; created: number }>("/playbooks/seed", {
        method: "POST",
      }),
    get: (id: number) =>
      request<import("./types").Playbook>(`/playbooks/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Playbook>("/playbooks", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Playbook>(`/playbooks/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/playbooks/${id}`, { method: "DELETE" }),
    activeKeywords: () => request<string[]>("/playbooks/active-keywords"),
    proposals: {
      list: (status?: string) =>
        request<import("./types").PlaybookProposal[]>(
          `/playbooks/proposals${status ? `?status=${status}` : ""}`
        ),
      create: (data: Record<string, unknown>) =>
        request<import("./types").PlaybookProposal>("/playbooks/proposals", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      approve: (id: number, resolved_by?: string) =>
        request<import("./types").Playbook>(
          `/playbooks/proposals/${id}/approve`,
          {
            method: "POST",
            body: JSON.stringify({
              approved: true,
              resolved_by: resolved_by ?? "user",
            }),
          }
        ),
      reject: (id: number, reason?: string) =>
        request<import("./types").PlaybookProposal>(
          `/playbooks/proposals/${id}/reject`,
          {
            method: "POST",
            body: JSON.stringify({ approved: false, rejection_reason: reason }),
          }
        ),
    },
    rollbackLastUpdate: (id: number) =>
      request<import("./types").PlaybookProposal>(
        `/playbooks/${id}/rollback-last-update`,
        { method: "POST" }
      ),
    experimentSummary: () =>
      request<{
        variants: Record<
          string,
          {
            total: number;
            pending: number;
            approved: number;
            rejected: number;
            approval_rate: number;
          }
        >;
      }>("/playbooks/experiments/summary"),
    experimentAttribution: (window_days?: number) =>
      request<{
        window_days: number;
        variants: Record<
          string,
          {
            proposal_windows: number;
            attributed_flips: number;
            avg_profit: number;
            avg_roi_pct: number;
            sample_quality: "low" | "medium" | "high";
          }
        >;
      }>(
        `/playbooks/experiments/attribution${
          window_days ? `?window_days=${window_days}` : ""
        }`
      ),
  },

  benchmarks: {
    status: () =>
      request<{
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
      request<
        Array<{
          model: string;
          normalized_model: string;
          overall_score: number;
          gaming_score: number | null;
          last_refreshed_at: string | null;
          confidence_score: number;
        }>
      >(`/benchmarks/top?component_type=${component_type}&limit=${limit}`),
    refreshRuns: (limit = 10) =>
      request<
        Array<{
          id: number;
          run_type: string;
          status: string;
          started_at: string;
          completed_at: string | null;
          components_checked: number;
          components_updated: number;
          components_failed: number;
          error_log: string | null;
        }>
      >(`/benchmarks/refresh-runs?limit=${limit}`),
    triggerRefresh: async (run_type = "manual") => {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const token = getAdminToken();
      const resp = await fetch(
        `${base}/api/benchmarks/refresh?run_type=${run_type}`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        }
      );
      return resp.json();
    },
  },

  reselling: {
    getSellerFees: () =>
      request<{
        insertion_fee: number;
        final_value_fee_pct: number;
        category: string;
        seller_tier: string;
        last_updated: string;
        expires_at: number;
      }>("/reselling/seller-fees"),

    analyzePricing: (flipId: number) =>
      request<{
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

    getPricingSummary: (flipId: number) =>
      request<{
        flip_id: number;
        total_cost: number;
        estimated_resale: number;
        walk_away_price: number;
        optimal_listing_price: number;
        estimated_profit: number;
        margin_pct: number;
      }>(`/reselling/flips/${flipId}/pricing-summary`),

    generateListing: (flipId: number) =>
      request<{
        flip_id: number;
        title_options: string[];
        description: string;
        recommended_title: string;
        specs: string;
      }>(`/reselling/flips/${flipId}/generate-listing`, { method: "POST" }),

    processImages: (
      flipId: number,
      imageUrls: string[],
      addWatermark: boolean = true
    ) =>
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
        body: JSON.stringify({
          image_urls: imageUrls,
          add_watermark: addWatermark,
        }),
      }),

    getListingPreview: (flipId: number) =>
      request<{
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
      request<unknown[]>(
        `/catalogue/variants${params ? "?" + new URLSearchParams(params) : ""}`
      ),
    toggleVariantStatus: (id: number) =>
      request<unknown>(`/catalogue/variants/${id}/toggle-status`, {
        method: "PATCH",
      }),
    cases: () => request<unknown[]>("/catalogue/cases"),
    createCase: (data: Record<string, unknown>) =>
      request<unknown>("/catalogue/cases", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    updateCase: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/catalogue/cases/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    slots: (playbookId?: number) =>
      request<unknown[]>(
        `/catalogue/slots${playbookId ? `?playbook_id=${playbookId}` : ""}`
      ),
    updateSlot: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/catalogue/slots/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },

  inventoryAllocations: {
    list: (flipId?: number) =>
      request<unknown[]>(
        `/inventory-allocations${flipId ? `?flip_id=${flipId}` : ""}`
      ),
    create: (data: Record<string, unknown>) =>
      request<unknown>("/inventory-allocations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    get: (id: number) => request<unknown>(`/inventory-allocations/${id}`),
    update: (id: number, data: Record<string, unknown>) =>
      request<unknown>(`/inventory-allocations/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/inventory-allocations/${id}`, { method: "DELETE" }),
    assignToManualBuild: (manualBuildId: number, inventoryItemIds: number[]) =>
      request<{ created: number; units_assigned: number; build_name: string }>(
        `/inventory-allocations/manual-builds/${manualBuildId}/bulk`,
        {
          method: "POST",
          body: JSON.stringify({ inventory_item_ids: inventoryItemIds }),
        }
      ),
    releaseFromManualBuild: (manualBuildId: number, inventoryItemId: number) =>
      request<void>(
        `/inventory-allocations/manual-builds/${manualBuildId}/items/${inventoryItemId}`,
        { method: "DELETE" }
      ),
  },

  logs: {
    history: (tail = 300) => request<unknown[]>(`/logs/history?tail=${tail}`),
    targets: () =>
      request<Array<{ id: string; label: string; available: boolean }>>(
        "/logs/targets"
      ),
    soldScraping: (limit = 100) =>
      request<{
        items: SoldScrapingItem[];
        stored_count: number;
        note: string;
      }>(`/logs/sold-scraping?limit=${limit}`),
  },

  priceEvidence: {
    products: (q = "", limit = 100) =>
      request<{ items: PriceEvidenceProduct[] }>(
        `/price-evidence/products?q=${encodeURIComponent(q)}&limit=${limit}`
      ),
    product: (cpk: string) =>
      request<{
        product: PriceEvidenceProduct;
        observations: Array<{
          kind: string;
          price: number;
          observed_at: string | null;
          source: string | null;
          source_url: string | null;
          title: string;
        }>;
      }>(`/price-evidence/products/${encodeURIComponent(cpk)}`),
  },

  inventory: {
    freeItems: (componentType?: string) =>
      request<
        Array<{
          id: number;
          component_name: string;
          component_type: string;
          quantity_free: number;
          actual_cost: number;
          source: string | null;
          listing_url: string | null;
          purchase_date: string;
        }>
      >(
        `/inventory/free-items${
          componentType
            ? `?component_type=${encodeURIComponent(componentType)}`
            : ""
        }`
      ),
    health: () =>
      request<{
        free_units: number;
        reserved_units: number;
        consumed_units: number;
        free_value: number;
        reserved_value: number;
        consumed_value: number;
        expected_profit: number;
        stale_items: Array<{
          id: number;
          name: string;
          days: number;
          value: number;
        }>;
        excess_stock: Array<{ component_type: string; free_units: number }>;
        build_blockers: Array<{
          build_id: number;
          build_name: string;
          missing: string[];
        }>;
      }>("/inventory/summary/health"),
    events: (inventoryItemId: number) =>
      request<
        Array<{
          id: number;
          event_type: string;
          quantity: number;
          manual_build_id: number | null;
          build_name: string | null;
          detail: Record<string, unknown>;
          created_at: string;
        }>
      >(`/inventory-allocations/inventory/${inventoryItemId}/events`),
    units: (inventoryItemId: number) =>
      request<
        Array<{
          id: number;
          inventory_item_id: number;
          unit_number: number;
          serial_number: string | null;
          condition_grade: string;
          status: string;
          storage_location: string | null;
          warranty_expires_at: string | null;
          test_results: Record<string, unknown>;
          photos: string[];
          exception_reason: string | null;
          writeoff_amount: number | null;
          received_at: string | null;
          inspected_at: string | null;
          created_at: string;
          updated_at: string;
        }>
      >(`/inventory-intelligence/items/${inventoryItemId}/units`),
    updateUnit: (unitId: number, data: Record<string, unknown>) =>
      request<Record<string, unknown>>(
        `/inventory-intelligence/units/${unitId}`,
        { method: "PATCH", body: JSON.stringify(data) }
      ),
    unitLabel: (unitId: number) =>
      request<{
        unit_id: number;
        sku: string;
        component_name: string;
        serial_number: string | null;
        location: string | null;
        qr_payload: string;
      }>(`/inventory-intelligence/units/${unitId}/label`),
    buildCandidates: (manualBuildId: number) =>
      request<
        Array<{
          id: number;
          component_name: string;
          component_type: string;
          slot: string;
          quantity_free: number;
          actual_cost: number;
          source: string | null;
          compatible: boolean;
          confidence: string;
          reasons: string[];
          warnings: string[];
        }>
      >(`/inventory-intelligence/builds/${manualBuildId}/candidates`),
    forecast: (days = 30) =>
      request<{
        horizon_days: number;
        capital_required: number;
        rows: Array<{
          component_type: string;
          free_now: number;
          monthly_usage: number;
          projected_free: number;
          recommendation: "buy" | "hold" | "liquidate";
          units: number;
          estimated_capital: number;
        }>;
      }>(`/inventory-intelligence/forecast?days=${days}`),
    sourcingAdjustments: () =>
      request<
        Array<{
          component_type: string;
          free_now: number;
          recommendation: string;
          units: number;
          deal_score_adjustment: number;
          reason: string;
        }>
      >("/inventory-intelligence/sourcing-adjustments"),
    buildOpportunities: () =>
      request<
        Array<{
          name: string;
          completion_pct: number;
          ready: boolean;
          missing: string[];
          owned_cost: number;
          additional_spend_estimate: number;
          components: Array<{
            inventory_item_id: number;
            component_type: string;
            name: string;
            cost: number;
          }>;
          warnings: string[];
        }>
      >("/inventory-intelligence/build-opportunities"),
    reorderRules: () =>
      request<
        Array<{
          id: number;
          component_type: string;
          minimum_free: number;
          maximum_free: number;
          target_free: number;
          notes: string | null;
        }>
      >("/inventory-intelligence/reorder-rules"),
    saveReorderRule: (
      componentType: string,
      data: {
        minimum_free: number;
        maximum_free: number;
        target_free: number;
        notes?: string;
      }
    ) =>
      request<Record<string, unknown>>(
        `/inventory-intelligence/reorder-rules/${encodeURIComponent(
          componentType
        )}`,
        {
          method: "PUT",
          body: JSON.stringify({ component_type: componentType, ...data }),
        }
      ),
    accountingExportUrl: () =>
      `${API_BASE_URL}/inventory-intelligence/accounting-export.csv`,
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
        environment: string;
        connected_at: string | null;
        username: string | null;
        email: string | null;
        seller_eligible: boolean | null;
        scopes: string[];
        refresh_token_expires_at: string | null;
      }>("/ebay/oauth/status"),
    disconnect: () =>
      request<{ connected: boolean }>("/ebay/oauth/disconnect", {
        method: "POST",
      }),
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
      }>(
        `/admin/performance/keyword-research?query=${encodeURIComponent(query)}`
      ),
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
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(apiUrl("/companion/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, page_context: pageContext }),
    signal,
  });
  if (!res.ok || !res.body)
    throw new Error(`Companion stream failed: ${res.status}`);

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
