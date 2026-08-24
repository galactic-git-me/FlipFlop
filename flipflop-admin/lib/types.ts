export type Classification =
  | "amazing_gem"
  | "gem"
  | "already_flipped"
  | "no_profit"
  | "overpriced"
  | "unclassified";

export type ListingStatus = "active" | "missing" | "removed" | "sold";
export type FlipStage = "selected" | "building" | "ready_for_sale" | "sold";
export type PartCategory = "ram" | "gpu" | "ssd" | "psu" | "case" | "cpu" | "motherboard" | "cooling" | "accessory";
export type PartCondition = "new" | "used" | "refurb";

export interface Listing {
  id: number;
  external_id: string;
  source_name: string;
  title: string;
  price: number;
  url: string;
  image_urls: string[];
  location: string | null;
  condition: string | null;
  cpu: string | null;
  ram_gb: number | null;
  ram_type: string | null;
  storage_gb: number | null;
  storage_type: string | null;
  gpu: string | null;
  has_psu: boolean;
  gem_score: number;
  classification: Classification;
  gem_signals: string[];
  estimated_resale: number | null;
  estimated_upgrade_cost: number | null;
  resale_low: number | null;
  resale_high: number | null;
  resale_comp_count: number | null;
  estimated_profit: number | null;
  // Auction / listing metadata
  listing_type: "auction" | "buy_it_now" | "classified" | null;
  listing_ends_at: string | null;   // ISO datetime, null for BIN/classified
  expected_buy_price: number | null; // auctions: estimated final hammer price
  // Seller intelligence
  seller_name: string | null;
  seller_feedback_count: number | null;
  seller_feedback_pct: number | null;   // 0–100 positive %
  seller_type: "shop" | "refurb_shop" | "flipper" | "private" | null;
  seller_has_shop: boolean;
  listed_at: string | null;             // when seller originally posted it
  status: ListingStatus;
  first_seen_at: string;
  last_seen_at: string;
  // Demand signals (eBay: watch count, bid count)
  watch_count: number | null;
  bid_count: number | null;
  // Claude LLM evaluation (populated asynchronously after initial save)
  claude_verdict:            string | null;
  claude_flipability_score:  number | null;
  claude_expected_profit:    number | null;
  claude_roi:                number | null;
  claude_confidence:         number | null;
  claude_capital_efficiency: number | null;
  claude_resale_demand:      number | null;
  claude_upgrade_complexity: number | null;
  claude_reasoning:          string | null;
  claude_main_risk:          string | null;
  claude_judged_at:          string | null;
  // Cross-vendor alternatives with the same hardware specs (cheaper listing is shown; these are the others)
  alternatives?: { id: number; source_name: string; price: number; url: string }[];
}

export interface Part {
  id: number;
  name: string;
  brand: string | null;
  model: string | null;
  category: PartCategory;
  condition: PartCondition;
  specs: string | null;
  source_site: string | null;
  source_url: string | null;
  price: number | null;
  price_new: number | null;
  price_used: number | null;
  price_refurb: number | null;
  image_url: string | null;
  theme: string | null;
  resale_value_add: number;
  is_active: boolean;
  last_price_update: string | null;
  created_at: string;
}

export interface GroupedPart {
  name: string;
  category: PartCategory;
  image_url: string | null;
  cheapest_price: number | null;
  cheapest_source: string | null;
  cheapest_url: string | null;
  cheapest_good_price: number | null;
  cheapest_good_source: string | null;
  cheapest_good_url: string | null;
  price_used: number | null;
  price_refurb: number | null;
  price_new: number | null;
  last_price_update: string | null;
  all_sources: {
    source: string | null;
    price: number | null;
    url: string | null;
    condition: string | null;
  }[];
  gem_classification: "super_gem" | "gem" | null;
  gem_score: number | null;
  // AI verification (populated asynchronously after rule-based scoring)
  claude_verdict: "GEM" | "GOOD" | "REJECT" | null;
  claude_reasoning: string | null;
}

export interface Flip {
  id: number;
  listing_id: number;
  listing?: Listing;
  stage: FlipStage;
  selected_upgrade_ids: Record<string, number>;
  base_cost: number;
  upgrade_cost: number;
  total_cost: number;
  platform_fee_pct: number;
  initial_estimated_resale: number | null;
  current_estimated_resale: number | null;
  initial_estimated_profit: number | null;
  current_estimated_profit: number | null;
  actual_sale_price: number | null;
  actual_profit: number | null;
  sale_platform: string | null;
  generated_title: string | null;
  notes: string | null;
  created_at: string;
  sold_at: string | null;
}

export interface DataSource {
  id: number;
  name: string;
  url: string;
  source_type: "api" | "scrape";
  enabled: boolean;
  config?: {
    consecutive_failures?: number;
    [key: string]: unknown;
  };
  listings_found?: number;
  listings_found_total?: number;
  listings_found_last_run?: number;
  last_scraped_at: string | null;
  last_error?: string | null;
  created_at: string;
}

export interface SearchConfig {
  id: number;
  name: string;
  is_active: boolean;
  min_price: number;
  max_price: number;
  conditions: string[];
  cpu_types: string[];
  ram_min_gb: number;
  ram_types: string[];
  require_storage: boolean;
  require_gpu: boolean;
  keywords: string[];
  exclude_keywords: string[];
  gem_keywords: string[];
  intent: string;
  updated_at: string;
}

// ── Playbook types ─────────────────────────────────────────────────────────────

export type PlaybookStatus = "candidate" | "active" | "deprecated";
export type PlaybookUseCase = "gaming" | "office" | "workstation" | "budget" | "ai_workstation" | "htpc";
export type ProposalAction = "CREATE" | "UPDATE" | "RETIRE";
export type ProposalStatus = "pending" | "approved" | "rejected";

export interface PlaybookRequirements {
  gpu_required?: boolean;
  cpu_min_tier?: string;
  ram_min_gb?: number;
  psu_required?: boolean;
  form_factor?: string;
  storage_min_gb?: number;
  cooling?: string;
}

export interface PlaybookSearchStrategy {
  keywords?: string[];
  listing_types?: string[];
  price_min?: number;
  price_max?: number;
  boost_terms?: string[];
}

export interface PlaybookUpgradeItem {
  component: string;
  target: string;
  max_cost: number;
}

export interface PlaybookUpgradeStrategy {
  required?: PlaybookUpgradeItem[];
  optional?: PlaybookUpgradeItem[];
}

export interface PlaybookProfitStrategy {
  target_margin_pct?: number;
  target_profit_gbp?: number;
  sell_platform?: string;
  flip_structure?: "buy_upgrade_sell" | "buy_clean_sell" | "bulk_lot";
  notes?: string;
}

export interface PlaybookIdealBuildComponent {
  candidate_models: string[];
  target_price: number;
  walk_away_price: number;
  search_terms: string[];
  negative_search_terms: string[];
}

export interface PlaybookPricingModel {
  minimum_build_cost?: number;
  expected_build_cost?: number;
  maximum_build_cost?: number;
  sell_target_min?: number;
  sell_target_exp?: number;
  sell_target_max?: number;
  [key: string]: number | undefined;
}

export interface PlaybookProfitModel {
  minimum_profit?: number;
  expected_profit?: number;
  maximum_profit?: number;
  expected_roi_pct?: number;
}

export interface PlaybookSeasonality {
  jan?: number; feb?: number; mar?: number; apr?: number;
  may?: number; jun?: number; jul?: number; aug?: number;
  sep?: number; oct?: number; nov?: number; dec?: number;
  peak_months?: string[];
  slow_months?: string[];
  current_position?: string;
  days_until_peak?: number;
}

export interface Playbook {
  id: number;
  name: string;
  description?: string | null;
  emoji?: string;
  status: PlaybookStatus;
  target_use_case: PlaybookUseCase;
  requirements: PlaybookRequirements;
  component_catalogue: Record<string, unknown>;
  search_strategy: PlaybookSearchStrategy;
  upgrade_strategy: PlaybookUpgradeStrategy;
  profit_strategy: PlaybookProfitStrategy;
  flip_count: number;
  avg_profit_gbp: number | null;
  avg_days_to_sell: number | null;
  conversion_rate: number | null;
  created_at: string;
  updated_at: string;
  activated_at: string | null;
  deprecated_at: string | null;
  // Customer profile
  target_customer?: string | null;
  what_they_use_it_for?: string | null;
  what_they_want_from_build?: string | null;
  critical_success_factors?: string[];
  // Scores
  profit_opportunity_score?: number;
  market_size_score?: number;
  resellability_score?: number;
  liquidity_score?: number;
  risk_score?: number;
  composite_rank_score?: number;
  market_growth_direction?: string | null;
  // Intelligence
  seasonality?: PlaybookSeasonality;
  ideal_build?: Record<string, PlaybookIdealBuildComponent>;
  pricing_model?: PlaybookPricingModel;
  profit_model?: PlaybookProfitModel;
  // Evolution metadata
  last_reviewed?: string | null;
}

export interface PlaybookProposal {
  id: number;
  action: ProposalAction;
  playbook_id: number | null;
  playbook_name?: string | null;
  proposed_data: Partial<Playbook> & Record<string, unknown>;
  reason: string;
  demand_signals: Record<string, unknown>;
  status: ProposalStatus;
  rejection_reason: string | null;
  proposed_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
}

// ── Favourites ─────────────────────────────────────────────────────────────────

export interface Favourite {
  id: number;
  term: string | null;
  cpk: string | null;
  category: string | null;
  created_at: string;
  last_matched_at: string | null;
}

export interface FavouriteVendorCell {
  lowest_price: number;
  listing_id: string;
  url: string;
  classification: string;
}

export interface FavouriteProductOption {
  cpk: string;
  lowest_price: number;
  title: string;
}

export interface FavouriteMatrixRow {
  query: string;
  category: string | null;
  vendors: Record<string, FavouriteVendorCell>;
  products: FavouriteProductOption[];
}

// ── Demand types ──────────────────────────────────────────────────────────────

export type DemandStrength = "High" | "Medium" | "Low";
export type TrendDir = "rising" | "stable" | "falling";
export type MarketHealth = "hot" | "warm" | "cold";

export interface DemandCategory {
  name: string;
  emoji: string;
  use_case: string;
  count: number;
  gem_count: number;
  sparkline: number[];   // 7-day counts, oldest → newest
  trend: TrendDir;
  strength: DemandStrength;
  avg_profit: number | null;
  avg_price: number | null;
  insight: string;
}

export interface AuctionIntelItem {
  id: number;
  title: string;
  url: string;
  price: number;
  expected_buy_price: number | null;
  estimated_profit: number | null;
  gem_score: number;
  classification: string;
  source_name: string;
  listing_ends_at: string | null;
  time_left_secs: number | null;
  urgency: "ending_soon" | "today" | "upcoming";
  image_url: string | null;
  cpu: string | null;
  gpu: string | null;
}

export interface DemandSummary {
  total_listings: number;
  total_gems: number;
  gem_rate_pct: number;
  market_health: MarketHealth;
  hottest_category: DemandCategory | null;
  rising_count: number;
  falling_count: number;
  categories: DemandCategory[];
  ending_soon_auctions: number;
}

export interface SoldMarketCategory {
  category: string;
  label: string;
  sold_observations: number;
  active_listings: number;
  products_with_sold_evidence: number;
  median_sold_price: number | null;
  median_active_price: number | null;
  evidence_ratio_pct: number;
  sample_confidence_pct: number;
  demand_score: number;
  strength: "High" | "Medium" | "Low";
  recent_30d: number;
  previous_30d: number;
  trend_pct: number | null;
}

export interface SoldMarketDemand {
  generated_at: string;
  window_days: number;
  methodology: string;
  totals: {
    sold_observations: number;
    matched_sold_observations: number;
    unmatched_sold_observations: number;
    active_listings: number;
    products_with_sold_evidence: number;
  };
  categories: SoldMarketCategory[];
  top_products: Array<{
    cpk: string; name: string; category: string; sold_observations: number;
    active_listings: number; median_sold_price: number | null;
    median_active_price: number | null; evidence_ratio_pct: number;
  }>;
  weekly: Array<{ week: string; sold_observations: number }>;
}

export interface SoldMarketInsight {
  insight: string;
  model: string;
  generated_at: string;
}

export const PLAYBOOK_STATUS_CONFIG: Record<PlaybookStatus, { label: string; color: string; bg: string; dot: string }> = {
  active:     { label: "Active",     color: "text-emerald-400", bg: "bg-emerald-400/10 border-emerald-400/30", dot: "bg-emerald-400" },
  candidate:  { label: "Candidate",  color: "text-yellow-400",  bg: "bg-yellow-400/10 border-yellow-400/30",   dot: "bg-yellow-400"  },
  deprecated: { label: "Retired",    color: "text-slate-400",   bg: "bg-slate-400/10 border-slate-400/30",     dot: "bg-slate-500"   },
};

export const PROPOSAL_ACTION_CONFIG: Record<ProposalAction, { label: string; color: string }> = {
  CREATE: { label: "New Playbook",  color: "text-cyan-400"    },
  UPDATE: { label: "Update",        color: "text-yellow-400"  },
  RETIRE: { label: "Retire",        color: "text-red-400"     },
};

export const USE_CASE_CONFIG: Record<PlaybookUseCase, { label: string; emoji: string }> = {
  gaming:        { label: "Gaming",         emoji: "🎮" },
  office:        { label: "Office",         emoji: "💼" },
  workstation:   { label: "Workstation",    emoji: "🖥️" },
  budget:        { label: "Budget",         emoji: "💸" },
  ai_workstation:{ label: "AI/ML",          emoji: "🤖" },
  htpc:          { label: "HTPC",           emoji: "📺" },
};

export const CLASSIFICATION_CONFIG: Record<Classification, { label: string; emoji: string; color: string; bg: string }> = {
  amazing_gem: { label: "Amazing Gem", emoji: "💎", color: "text-cyan-400", bg: "bg-cyan-400/10 border-cyan-400/30" },
  gem: { label: "Gem", emoji: "✅", color: "text-emerald-400", bg: "bg-emerald-400/10 border-emerald-400/30" },
  already_flipped: { label: "Already Flipped", emoji: "🔄", color: "text-yellow-400", bg: "bg-yellow-400/10 border-yellow-400/30" },
  no_profit: { label: "No Profit", emoji: "❌", color: "text-red-400", bg: "bg-red-400/10 border-red-400/30" },
  overpriced: { label: "Overpriced", emoji: "⚠️", color: "text-orange-400", bg: "bg-orange-400/10 border-orange-400/30" },
  unclassified: { label: "Unscored", emoji: "?", color: "text-slate-400", bg: "bg-slate-400/10 border-slate-400/30" },
};

export const SCORE_TIER = (score: number) => {
  if (score >= 80) return { label: "S", color: "text-cyan-400", bg: "bg-cyan-400/15 border-cyan-400/40", ring: "ring-cyan-400/30" };
  if (score >= 60) return { label: "A", color: "text-emerald-400", bg: "bg-emerald-400/15 border-emerald-400/40", ring: "ring-emerald-400/30" };
  if (score >= 40) return { label: "B", color: "text-yellow-400", bg: "bg-yellow-400/15 border-yellow-400/40", ring: "ring-yellow-400/30" };
  if (score >= 20) return { label: "C", color: "text-orange-400", bg: "bg-orange-400/15 border-orange-400/40", ring: "ring-orange-400/30" };
  return { label: "D", color: "text-red-400", bg: "bg-red-400/15 border-red-400/40", ring: "ring-red-400/30" };
};

export const SOURCE_FAVICON: Record<string, string> = {
  "eBay": "https://www.ebay.co.uk/favicon.ico",
  "eBay UK": "https://www.ebay.co.uk/favicon.ico",
  "Gumtree": "https://www.gumtree.com/favicon.ico",
  "Facebook Marketplace": "https://www.facebook.com/favicon.ico",
  "Amazon": "https://www.amazon.co.uk/favicon.ico",
  "AliExpress": "https://www.aliexpress.com/favicon.ico",
  "Temu": "https://www.temu.com/favicon.ico",
};
