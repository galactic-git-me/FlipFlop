export type Classification =
  | "amazing_gem"
  | "gem"
  | "already_flipped"
  | "no_profit"
  | "overpriced"
  | "unclassified";

export type ListingStatus = "active" | "missing" | "removed" | "sold";
export type FlipStage = "selected" | "building" | "ready_for_sale" | "sold";
export type PartCategory = "ram" | "gpu" | "ssd" | "psu" | "case" | "cpu" | "motherboard";
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
  config?: Record<string, unknown>;
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
