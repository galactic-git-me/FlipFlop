from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ManualBuild(Base):
    __tablename__ = "manual_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), default="Untitled Build")
    components: Mapped[list] = mapped_column(JSON, default=list)
    total_cost: Mapped[float | None] = mapped_column(Float)
    last_evaluation: Mapped[dict | None] = mapped_column(JSON)
    # in_progress -> built -> listed -> sold
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    generated_title: Mapped[str | None] = mapped_column(String(80))
    generated_description: Mapped[str | None] = mapped_column(String)
    # eBay Item Specifics for this category, e.g. {"Processor": ["AMD Ryzen 7 7800X3D"], ...}
    generated_aspects: Mapped[dict | None] = mapped_column(JSON)
    ebay_listing_id: Mapped[str | None] = mapped_column(String(60))
    ebay_listing_url: Mapped[str | None] = mapped_column(String(300))
    # eBay Inventory API SKU used to create this listing's offer — needed
    # later to look up the offerId and withdraw the listing (see
    # app/services/ebay_listing_withdraw.py), since eBay's publish response
    # only returns listingId, not offerId.
    ebay_sku: Mapped[str | None] = mapped_column(String(60))
    # [{"url": "...", "kind": "photo" | "spec_card" | "registration_plate" | "performance_card"}, ...]
    photos: Mapped[list] = mapped_column(JSON, default=list)
    # Structured factual data backing the rendered spec card / registration
    # plate / performance card images, keyed by kind — e.g.
    # {"spec_card": {...}, "registration_plate": {...}, "performance_card": {...}}.
    # This is what actually gets sent to the LLM for listing generation (as
    # plain text/JSON), not the images — the images are a rendering of it.
    evidence_data: Mapped[dict] = mapped_column(JSON, default=dict)
    hero_photo_url: Mapped[str | None] = mapped_column(String(500))
    # Customer-facing GLB for the completed machine's storefront 3D viewer.
    model_3d_url: Mapped[str | None] = mapped_column(String(500))
    # Per-build image-to-3D generation jobs and resulting assets. Keys are
    # complete_build/chassis/motherboard/cpu/gpu/ram/psu/liquid_cooler/rgb_fan;
    # values retain the selected
    # source photos, Meshy task id, status and locally mirrored GLB URL.
    model_3d_assets: Mapped[dict] = mapped_column(JSON, default=dict)
    # None means use the stable set of ten defaults; [] is an intentional
    # user choice to publish no FAQs.
    selected_faq_ids: Mapped[list | None] = mapped_column(JSON)
    # Per-build answer text keyed by FAQ id. Questions/categories remain in
    # the shared bank so copy can be tailored without duplicating the bank.
    selected_faq_answer_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    storefront_product_id: Mapped[int | None] = mapped_column(Integer)
    # eBay Listing Configuration
    ebay_condition: Mapped[str | None] = mapped_column(String(30))  # NEW, USED_EXCELLENT, FOR_PARTS_OR_NOT_WORKING, etc.
    ebay_price: Mapped[float | None] = mapped_column(Float)
    allow_offers: Mapped[bool] = mapped_column(default=True)
    auto_reject_below_price: Mapped[float | None] = mapped_column(Float)  # Auto-reject offers below this
    auction_start_price: Mapped[float | None] = mapped_column(Float)  # If using auction format
    return_days: Mapped[int] = mapped_column(Integer, default=30)  # 14, 30, 60, or 0 for no returns
    # Shipping Configuration
    shipping_method: Mapped[str] = mapped_column(String(30), default="tracked")  # tracked, untracked, local_pickup
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)
    handling_time_days: Mapped[int] = mapped_column(Integer, default=1)  # 1-3 typical
    delivery_min_days: Mapped[int] = mapped_column(Integer, default=1)
    delivery_max_days: Mapped[int] = mapped_column(Integer, default=2)
    shipping_damage_cover_confirmed: Mapped[bool] = mapped_column(default=False)
    ships_to_countries: Mapped[list] = mapped_column(JSON, default=lambda: ["GB"])  # ["GB", "EU", "WORLD"]
    domestic_only: Mapped[bool] = mapped_column(default=True)
    # Per-build override of which real eBay fulfillment policy (shipping
    # services + regions, configured in the seller's own eBay Seller Hub) to
    # use when posting this listing. NULL falls back to the single global
    # EBAY_*_FULFILLMENT_POLICY_ID env setting every listing used before —
    # see app/services/ebay_fulfillment_policies.py for how the choices are
    # fetched and app/api/manual_builds.py's post_to_ebay for the fallback.
    fulfillment_policy_id: Mapped[str | None] = mapped_column(String(60))
    # Deferred-listing scheduler — mirrors Flip.deferred_publish_at (see
    # app/models/flip.py and app/workers/manual_build_scheduler.py). NULL
    # means "no scheduled time set"; publishing via the "List on eBay"
    # button clears it (see manual_builds.py's post_to_ebay).
    deferred_publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Real physical package dimensions for this build, entered once per
    # build (never guessed/inferred from components — see
    # app/services/parcel2go_courier.py's docstring for why) so courier
    # quotes and the "Get Courier Quote" button on the sell page can price
    # real tracked-delivery cost instead of a hand-guessed flat rate.
    package_weight_kg: Mapped[float | None] = mapped_column(Float)
    package_length_cm: Mapped[float | None] = mapped_column(Float)
    package_width_cm: Mapped[float | None] = mapped_column(Float)
    package_height_cm: Mapped[float | None] = mapped_column(Float)
    # Populated once the real eBay order is synced post-sale (see
    # app/services/ebay_order_sync.py) — the buyer's actual delivery
    # address is only known after purchase, never at listing time, so
    # these stay NULL until then.
    ebay_order_id: Mapped[str | None] = mapped_column(String(100))
    buyer_name: Mapped[str | None] = mapped_column(String(200))
    buyer_address_json: Mapped[dict | None] = mapped_column(JSON)
    sale_price_actual: Mapped[float | None] = mapped_column(Float)
    # ── Pricing engine (playbook rows 10, 19, 20, 21, 22, 23, 33, 49) —
    # ported from the retired Flip system, adapted to ManualBuild's fields
    # (ebay_price is this system's listing-price anchor, auto_reject_below_price
    # is its min-offer floor — reused rather than duplicated).
    sold_comp_target: Mapped[float | None] = mapped_column(Float)
    active_range_ceiling: Mapped[float | None] = mapped_column(Float)
    price_floor: Mapped[float | None] = mapped_column(Float)
    price_last_recalculated_at: Mapped[datetime | None] = mapped_column(DateTime)
    price_floor_hit_review_needed: Mapped[bool] = mapped_column(default=False)
    demand_sold_count_90d: Mapped[int | None] = mapped_column(Integer)
    demand_active_count: Mapped[int | None] = mapped_column(Integer)
    demand_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    # ── Offer engine (rows 8, 21, 45) ──
    last_counter_offer_price: Mapped[float | None] = mapped_column(Float)
    counter_offer_round: Mapped[int] = mapped_column(Integer, default=0)
    last_watcher_offer_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    # ── Recreate/relist cycle (rows 1, 2, 5, 6, 7, 9, 36) — ongoing
    # end-and-republish, distinct from deferred_publish_at's one-time
    # initial listing above. ──
    recreate_cycle_count: Mapped[int] = mapped_column(Integer, default=0)
    next_recreate_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_recreate_at: Mapped[datetime | None] = mapped_column(DateTime)
    recreate_price_step_pct: Mapped[float] = mapped_column(Float, default=0.03)
    traffic_band: Mapped[str | None] = mapped_column(String(50))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # ── Paid visibility / markdown (rows 40, 46) ──
    promoted_ad_rate_pct: Mapped[float | None] = mapped_column(Float)
    promoted_enabled: Mapped[bool] = mapped_column(default=False)
    markdown_event_opt_in: Mapped[bool] = mapped_column(default=False)
    # Populated once the seller confirms and pays for a real courier
    # booking (see app/services/parcel2go_booking.py) — booking is a real
    # financial transaction, so this only happens on explicit user
    # confirmation, never automatically.
    parcel2go_order_id: Mapped[str | None] = mapped_column(String(100))
    parcel2go_service_slug: Mapped[str | None] = mapped_column(String(100))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    shipping_label_url: Mapped[str | None] = mapped_column(String(500))
    shipment_booked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ManualBuild {self.id} {self.name!r}>"
