# pc-flipper-backend/app/schemas/manual_build.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class BuildComponent(BaseModel):
    slot: str                        # "GPU", "CPU", "Base PC", etc.
    name: str
    price_paid: float
    source: str = "manual"           # "catalogue" | "manual"
    part_id: Optional[int] = None   # set when source == "catalogue"
    listing_url: Optional[str] = None
    image_url: Optional[str] = None
    purchased: bool = False
    inventory_item_id: int | None = None


class ManualBuildCreate(BaseModel):
    name: str = "Untitled Build"


class ManualBuildPatch(BaseModel):
    name: Optional[str] = None
    components: Optional[list[BuildComponent]] = None


class EvaluationSuggestion(BaseModel):
    text: str
    uplift: float


class EvaluationResult(BaseModel):
    low: float
    mid: float
    high: float
    narrative: str
    suggestions: list[EvaluationSuggestion]


class BuildPhoto(BaseModel):
    url: str
    kind: str = "photo"  # "photo" | "spec_card" | "registration_plate"


class ManualBuildOut(BaseModel):
    id: int
    name: str
    components: list[BuildComponent]
    total_cost: Optional[float]
    last_evaluation: Optional[dict]
    status: str
    generated_title: Optional[str]
    generated_description: Optional[str]
    generated_aspects: Optional[dict[str, list[str]]] = None
    ebay_listing_id: Optional[str]
    ebay_listing_url: Optional[str]
    ebay_sku: Optional[str] = None
    photos: list[BuildPhoto]
    evidence_data: dict = {}
    hero_photo_url: Optional[str]
    model_3d_url: Optional[str] = None
    model_3d_assets: dict = Field(default_factory=dict)
    selected_faq_ids: Optional[list[str]] = None
    selected_faq_answer_overrides: dict[str, str] = Field(default_factory=dict)
    storefront_product_id: Optional[int]
    # eBay Listing Configuration
    ebay_condition: Optional[str] = None
    ebay_price: Optional[float] = None
    allow_offers: bool = True
    auto_reject_below_price: Optional[float] = None
    auction_start_price: Optional[float] = None
    return_days: int = 30
    shipping_method: str = "tracked"
    shipping_cost: float = 0.0
    shipping_insurance_cost: float = 0.0
    packaging_cost: float = 0.0
    warranty_reserve_pct: float = 3.0
    handling_time_days: int = 1
    delivery_min_days: int = 1
    delivery_max_days: int = 2
    shipping_damage_cover_confirmed: bool = False
    ships_to_countries: list[str] = ["GB"]
    domestic_only: bool = True
    fulfillment_policy_id: Optional[str] = None
    package_weight_kg: Optional[float] = None
    package_length_cm: Optional[float] = None
    package_width_cm: Optional[float] = None
    package_height_cm: Optional[float] = None
    # Real post-sale order/shipment data — see app/services/ebay_order_sync.py
    # and app/services/parcel2go_booking.py. NULL until the build actually sells.
    ebay_order_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_address_json: Optional[dict] = None
    sale_price_actual: Optional[float] = None
    parcel2go_order_id: Optional[str] = None
    parcel2go_service_slug: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_label_url: Optional[str] = None
    shipment_booked_at: Optional[datetime] = None
    # Computed per-channel "is this actually purchasable right now" status —
    # only populated by GET /{build_id} (the single-build detail view where
    # the channel badges render); None elsewhere rather than a stale guess.
    ebay_live: Optional[bool] = None
    storefront_live: Optional[bool] = None
    deferred_publish_at: Optional[datetime] = None
    # Pricing/offer/recreate-cycle/promoted-visibility engine, ported from
    # the retired Flip system — see app/models/manual_build.py.
    sold_comp_target: Optional[float] = None
    active_range_ceiling: Optional[float] = None
    price_floor: Optional[float] = None
    price_last_recalculated_at: Optional[datetime] = None
    price_floor_hit_review_needed: bool = False
    demand_sold_count_90d: Optional[int] = None
    demand_active_count: Optional[int] = None
    demand_checked_at: Optional[datetime] = None
    last_counter_offer_price: Optional[float] = None
    counter_offer_round: int = 0
    last_watcher_offer_sent_at: Optional[datetime] = None
    recreate_cycle_count: int = 0
    next_recreate_at: Optional[datetime] = None
    last_recreate_at: Optional[datetime] = None
    recreate_price_step_pct: float = 0.03
    traffic_band: Optional[str] = None
    listed_at: Optional[datetime] = None
    promoted_ad_rate_pct: Optional[float] = None
    promoted_enabled: bool = False
    markdown_event_opt_in: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ManualBuildSummary(BaseModel):
    id: int
    name: str
    total_cost: Optional[float]
    component_count: int
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateListingResult(BaseModel):
    titles: list[str]
    description: str
    aspects: dict[str, list[str]] = {}


class UpdateAspectsRequest(BaseModel):
    aspects: dict[str, list[str]]


class UpdateEvidenceDataRequest(BaseModel):
    kind: str  # "spec_card" | "registration_plate" | "performance_card"
    data: dict


class PostToEbayRequest(BaseModel):
    price: float
    condition: str = "USED_EXCELLENT"


class PostToEbayResult(BaseModel):
    success: bool
    listing_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    action: Optional[str] = None  # "posted" or "updated"


class SetHeroPhotoRequest(BaseModel):
    url: str


class RemovePhotoRequest(BaseModel):
    url: str


class ListOnStorefrontRequest(BaseModel):
    price: float


class ListOnStorefrontResult(BaseModel):
    product_id: int
    build_id: int
    storefront_url: Optional[str] = None


class ReorderPhotosRequest(BaseModel):
    urls: list[str]  # "photo"-kind urls in the desired display order


class FulfillmentPolicyOut(BaseModel):
    policy_id: str
    name: str
    marketplace_id: str
    ship_to_regions: list[str]
    handling_time_days: Optional[int] = None


class UpdateEbayListingConfigRequest(BaseModel):
    ebay_condition: Optional[str] = None
    ebay_price: Optional[float] = None
    allow_offers: Optional[bool] = None
    auto_reject_below_price: Optional[float] = None
    auction_start_price: Optional[float] = None
    return_days: Optional[int] = None
    shipping_method: Optional[str] = None
    shipping_cost: Optional[float] = None
    shipping_insurance_cost: Optional[float] = None
    packaging_cost: Optional[float] = None
    warranty_reserve_pct: Optional[float] = None
    handling_time_days: Optional[int] = None
    ships_to_countries: Optional[list[str]] = None
    domestic_only: Optional[bool] = None
    fulfillment_policy_id: Optional[str] = None
    package_weight_kg: Optional[float] = None
    package_length_cm: Optional[float] = None
    package_width_cm: Optional[float] = None
    package_height_cm: Optional[float] = None
    deferred_publish_at: Optional[datetime] = None
    shipping_damage_cover_confirmed: Optional[bool] = None
    # Recreate-cycle/markdown/promoted-visibility engine settings (see
    # app/models/manual_build.py) — configured once per build, then run
    # unattended by the scheduled jobs in app/workers/manual_build_lifecycle.py.
    traffic_band: Optional[str] = None
    recreate_price_step_pct: Optional[float] = None
    markdown_event_opt_in: Optional[bool] = None
    promoted_enabled: Optional[bool] = None
    promoted_ad_rate_pct: Optional[float] = None


class CourierQuoteOut(BaseModel):
    courier_name: str
    service_name: str
    price_gbp: float
    tracked: bool
    service_slug: Optional[str] = None
    estimated_days: Optional[int] = None
    protection_scope: str
    full_value_damage_cover: bool
    protection_warning: str


class InsuranceQuoteOut(BaseModel):
    provider: str
    insured_value_gbp: float
    price_gbp: float
    currency: str
    quote_only: bool = True


class BuyerAddressOut(BaseModel):
    contact_name: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_or_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str
    phone: Optional[str] = None


class SyncEbayOrderResult(BaseModel):
    ebay_order_id: str
    buyer_name: str
    buyer_address: BuyerAddressOut
    sale_price_actual: float


class BookShipmentRequest(BaseModel):
    service_slug: str  # from a CourierQuoteOut fetched against the real buyer address
    price_gbp: float   # the quoted price the seller confirmed — logged for audit, not re-validated server-side


class BookShipmentResult(BaseModel):
    success: bool
    tracking_number: Optional[str] = None
    shipping_label_url: Optional[str] = None
    parcel2go_order_id: Optional[str] = None
    ebay_marked_shipped: bool = False
    warning: Optional[str] = None
    error: Optional[str] = None
    estimated_days: Optional[int] = None
