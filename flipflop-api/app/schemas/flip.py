from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.models.flip import FlipStage
from app.schemas.listing import ListingOut


class FlipCreate(BaseModel):
    listing_id: int
    notes: Optional[str] = None


class FlipUpdate(BaseModel):
    stage: Optional[FlipStage] = None
    selected_upgrade_ids: Optional[dict[str, int]] = None
    notes: Optional[str] = None
    actual_sale_price: Optional[float] = None
    sale_platform: Optional[str] = None

    # Pricing & offers (Pricing tab)
    min_offer_price: Optional[float] = None
    offers_enabled: Optional[bool] = None
    listing_price: Optional[float] = None

    # Live Listing Management tab
    deferred_publish_at: Optional[datetime] = None
    traffic_band: Optional[str] = None
    promoted_enabled: Optional[bool] = None
    promoted_ad_rate_pct: Optional[float] = None
    markdown_event_opt_in: Optional[bool] = None
    recreate_price_step_pct: Optional[float] = None


class FlipOut(BaseModel):
    id: int
    listing_id: int
    listing: Optional[ListingOut] = None
    stage: FlipStage
    selected_upgrade_ids: dict
    base_cost: float
    upgrade_cost: float
    total_cost: float
    platform_fee_pct: float
    initial_estimated_resale: Optional[float]
    current_estimated_resale: Optional[float]
    initial_estimated_profit: Optional[float]
    current_estimated_profit: Optional[float]
    actual_sale_price: Optional[float]
    actual_profit: Optional[float]
    sale_platform: Optional[str]
    ebay_listing_id: Optional[str] = None
    ebay_listing_url: Optional[str] = None
    listing_fee_pct: Optional[float] = None
    final_value_fee_pct: Optional[float] = None
    actual_selling_fee: Optional[float] = None
    generated_title: Optional[str]
    generated_description: Optional[str] = None
    generated_images_urls: Optional[list] = None
    image_generation_status: Optional[str] = None
    notes: Optional[str]
    created_at: datetime
    sold_at: Optional[datetime]

    # Pricing & offers engine
    min_offer_price: Optional[float] = None
    offers_enabled: bool = True
    listing_price: Optional[float] = None
    sold_comp_target: Optional[float] = None
    active_range_ceiling: Optional[float] = None
    price_floor: Optional[float] = None
    price_last_recalculated_at: Optional[datetime] = None
    price_floor_hit_review_needed: bool = False
    last_counter_offer_price: Optional[float] = None
    counter_offer_round: int = 0
    last_watcher_offer_sent_at: Optional[datetime] = None

    # Demand check
    demand_sold_count_90d: Optional[int] = None
    demand_active_count: Optional[int] = None
    demand_checked_at: Optional[datetime] = None

    # Freshness / recreate cycle
    recreate_cycle_count: int = 0
    next_recreate_at: Optional[datetime] = None
    last_recreate_at: Optional[datetime] = None
    recreate_price_step_pct: float = 0.03

    # Deferred-listing scheduler
    deferred_publish_at: Optional[datetime] = None
    traffic_band: Optional[str] = None
    listed_at: Optional[datetime] = None

    # Paid visibility
    promoted_ad_rate_pct: Optional[float] = None
    promoted_enabled: bool = False
    markdown_event_opt_in: bool = False

    model_config = {"from_attributes": True}
