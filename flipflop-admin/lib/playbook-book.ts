import type { PlaybookOffer } from "./playbook-proposals";

export const BOOK_PAGES = [
  ["build", "Recommended build"],
  ["pricing", "Market & target pricing"],
  ["economics", "Costs, profit & delivery"],
  ["supply", "Linked listings & availability"],
  ["upsells", "Upsell components"],
  ["upsell-economics", "Upsell commercials"],
  ["media", "Listing media"],
  ["assets", "3D assets"],
  ["performance", "Performance"],
  ["live", "Live status"],
  ["approvals", "Approvals"],
  ["history", "History & decisions"],
  ["distribution", "Distribution"],
  ["compatibility", "Compatibility"],
  ["software", "Software"],
  ["automation", "Automation health"],
] as const;
export type BookPage = (typeof BOOK_PAGES)[number][0];
export type BookEvent = {
  id: string;
  at: string | null;
  event: string;
  reason: string | null;
  actor: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
};
export type PricingGuidance = {
  authority: "admin_estimate_only"; purchasable: false; status: "partial" | "estimated";
  estimated_price_gbp: string | null; estimated_profit_gbp: string | null;
  known_parts_subtotal_gbp: string | null; gaps: string[]; assumptions: string[];
  profit_check?: {status:string;passes_on_recorded_costs:boolean;actual_costs_verified?:boolean;minimum_margin_fraction:string;margin_fraction?:string;profit_gbp?:string;total_cost_gbp?:string;basis?:string};
  cost_allowances_gbp?: Record<string,string>;
  market_advice: {status: "evidence_needed" | "pending" | "ready" | "unavailable"; summary: string;
    position?: string; price_option_gbp?: string; model?: string;
    comparisons?: {id:string;title:string;url:string;kind:string;total_gbp:string}[]};
};
export type BookCell = {
  pricing_guidance?: PricingGuidance;
  mvp_autonomy?: boolean;
  automation_reason?: string | null;
  playbook_id?: number | null;
  market_review_status?: string;
  cell_id: string;
  segment_id: number | null;
  customer_type: string;
  budget_tier: string;
  name: string;
  definition: { components: Record<string, string>; use?: string };
  offer: PlaybookOffer | null;
  approved_offer: PlaybookOffer | null;
  offer_basis: "pending_proposal" | "approved_offer" | "no_offer";
  proposal_status: string | null;
  proposal_observed_at: string | null;
  approved_price_gbp: number | null;
  market: {
    sold_median_gbp?: string | null;
    sold_sample_size?: number;
    observed_at?: string;
    evidence_source?: string;
    evidence_ref?: string;
  } | null;
  active_build_market_gbp: string | null;
  walk_away_price_gbp: string | null;
  proposed_walk_away_price_gbp?: string | null;
  walk_away_observed_at?: string | null;
  pricing_gaps: string[];
  is_live: boolean;
  checkout_enabled: boolean;
  availability_status: string;
  software_profile: {
    recommended_package_ids?: string[];
    rationale?: string;
  } | null;
  policy_version: number | null;
  history: BookEvent[];
  history_coverage: string;
  distribution: {
    channel: string;
    status: string;
    source: string;
    external_id: string | null;
    updated_at?: string;
    offer_kind?: string;
    title?: string;
    manual_build_id?: number | null;
    product_id?: number | null;
    assignment_reason?: string | null;
  }[];
  distribution_coverage: string;
};
export type PlaybookBook = {
  observed_at: string;
  cells: BookCell[];
  unassigned_channel_records: number;
  unassigned_distribution?: BookCell["distribution"];
  build_market_references?: {
    build_id: number;
    name: string;
    observations: number;
    last_observed_at: string | null;
    reason: string;
  }[];
};
export const deliveryModes = [
  ["fast_track", "Fast Track"],
  ["standard", "Standard"],
  ["flexible", "Flexible"],
] as const;
export function bookMoney(value: string | number | null | undefined) {
  return value == null || !Number.isFinite(Number(value))
    ? "Not recorded"
    : new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: "GBP",
        maximumFractionDigits: 2,
      }).format(Number(value));
}
export function bookPage(value: string | null): BookPage {
  return BOOK_PAGES.find(([id]) => id === value)?.[0] ?? "build";
}
