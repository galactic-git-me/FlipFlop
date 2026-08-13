import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, Enum, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FlipStage(str, enum.Enum):
    selected = "selected"
    building = "building"
    ready_for_sale = "ready_for_sale"
    sold = "sold"


class Flip(Base):
    __tablename__ = "flips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"), index=True)

    stage: Mapped[FlipStage] = mapped_column(Enum(FlipStage), default=FlipStage.selected)

    # Selected upgrades stored as JSON: {category: part_id}
    selected_upgrade_ids: Mapped[dict] = mapped_column(JSON, default=dict)

    # Costs
    base_cost: Mapped[float] = mapped_column(Float, default=0.0)
    upgrade_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    platform_fee_pct: Mapped[float] = mapped_column(Float, default=0.127)

    # Estimates — versioned
    initial_estimated_resale: Mapped[float | None] = mapped_column(Float)
    current_estimated_resale: Mapped[float | None] = mapped_column(Float)
    initial_estimated_profit: Mapped[float | None] = mapped_column(Float)
    current_estimated_profit: Mapped[float | None] = mapped_column(Float)

    # Actuals
    actual_sale_price: Mapped[float | None] = mapped_column(Float)
    actual_profit: Mapped[float | None] = mapped_column(Float)
    sale_platform: Mapped[str | None] = mapped_column(String(100))

    # eBay Listing tracking
    ebay_listing_id: Mapped[str | None] = mapped_column(String(50))
    ebay_listing_url: Mapped[str | None] = mapped_column(String(500))

    # Fee snapshots (captured when listing created)
    listing_fee_pct: Mapped[float | None] = mapped_column(Float)
    final_value_fee_pct: Mapped[float | None] = mapped_column(Float)
    actual_selling_fee: Mapped[float | None] = mapped_column(Float)

    # Listing content
    generated_title: Mapped[str | None] = mapped_column(String(500))
    generated_description: Mapped[str | None] = mapped_column(Text)

    # Generated images for listing (processed with FlipFlop branding)
    generated_images_urls: Mapped[list | None] = mapped_column(JSON)
    image_generation_status: Mapped[str | None] = mapped_column(String(50))  # pending, processing, complete, error

    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ── Pricing & Offers engine (playbook rows 8, 19, 20, 21, 45, 49) ──
    min_offer_price: Mapped[float | None] = mapped_column(Float)
    offers_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    listing_price: Mapped[float | None] = mapped_column(Float)  # current BIN anchor
    sold_comp_target: Mapped[float | None] = mapped_column(Float)
    active_range_ceiling: Mapped[float | None] = mapped_column(Float)
    price_floor: Mapped[float | None] = mapped_column(Float)  # cost basis + min margin
    price_last_recalculated_at: Mapped[datetime | None] = mapped_column(DateTime)
    price_floor_hit_review_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_counter_offer_price: Mapped[float | None] = mapped_column(Float)
    counter_offer_round: Mapped[int] = mapped_column(Integer, default=0)
    last_watcher_offer_sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ── Demand check (row 10, 33) ──
    demand_sold_count_90d: Mapped[int | None] = mapped_column(Integer)
    demand_active_count: Mapped[int | None] = mapped_column(Integer)
    demand_checked_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ── Freshness / recreate cycle (rows 1, 2, 3, 5, 6, 9, 36) ──
    recreate_cycle_count: Mapped[int] = mapped_column(Integer, default=0)
    next_recreate_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_recreate_at: Mapped[datetime | None] = mapped_column(DateTime)
    recreate_price_step_pct: Mapped[float] = mapped_column(Float, default=0.03)

    # ── Deferred-listing scheduler (row 3) ──
    deferred_publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    traffic_band: Mapped[str | None] = mapped_column(String(50))
    listed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # ── Paid visibility (rows 40, 46) ──
    promoted_ad_rate_pct: Mapped[float | None] = mapped_column(Float)
    promoted_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    markdown_event_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

    listing = relationship("Listing", foreign_keys=[listing_id])

    def __repr__(self):
        return f"<Flip {self.id} stage={self.stage} profit={self.current_estimated_profit}>"
