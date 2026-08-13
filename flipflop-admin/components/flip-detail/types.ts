export type FlipStage = "selected" | "building" | "ready_for_sale" | "sold";

export interface Listing {
  id: number;
  title: string;
  price: number;
  url: string;
  source_name: string;
  cpu?: string;
  gpu?: string;
  ram_gb?: number;
  ram_type?: string;
  storage_gb?: number;
  storage_type?: string;
  image_urls: string[];
  gem_score: number;
  estimated_resale?: number;
  estimated_profit?: number;
}

export interface Flip {
  id: number;
  listing_id: number;
  listing?: Listing;
  stage: FlipStage;
  base_cost: number;
  upgrade_cost: number;
  total_cost: number;
  platform_fee_pct: number;
  initial_estimated_resale?: number;
  current_estimated_resale?: number;
  initial_estimated_profit?: number;
  current_estimated_profit?: number;
  actual_sale_price?: number;
  actual_profit?: number;
  sale_platform?: string;
  ebay_listing_id?: string | null;
  ebay_listing_url?: string | null;
  generated_title?: string;
  generated_description?: string | null;
  generated_images_urls?: string[] | null;
  image_generation_status?: string | null;
  notes?: string;
  created_at: string;
  sold_at?: string;
  selected_upgrade_ids?: Record<string, number>;

  // Pricing & offers engine
  min_offer_price?: number | null;
  offers_enabled: boolean;
  listing_price?: number | null;
  sold_comp_target?: number | null;
  active_range_ceiling?: number | null;
  price_floor?: number | null;
  price_last_recalculated_at?: string | null;
  price_floor_hit_review_needed: boolean;
  last_counter_offer_price?: number | null;
  counter_offer_round: number;
  last_watcher_offer_sent_at?: string | null;

  // Demand check
  demand_sold_count_90d?: number | null;
  demand_active_count?: number | null;
  demand_checked_at?: string | null;

  // Freshness / recreate cycle
  recreate_cycle_count: number;
  next_recreate_at?: string | null;
  last_recreate_at?: string | null;
  recreate_price_step_pct: number;

  // Deferred-listing scheduler
  deferred_publish_at?: string | null;
  traffic_band?: string | null;
  listed_at?: string | null;

  // Paid visibility
  promoted_ad_rate_pct?: number | null;
  promoted_enabled: boolean;
  markdown_event_opt_in: boolean;
}

export interface TabProps {
  flip: Flip;
  onFlipUpdated: (f: Flip) => void;
}
