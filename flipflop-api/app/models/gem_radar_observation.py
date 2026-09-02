"""Gem Radar listing-sighting ledger (PRD §23 watchlist, §24 relisting
detection, §31 caching). One row per (listing_id, scan) — recorded for
every scored listing, not just watched ones, since relisting detection and
cross-search dedup both need a broad "have we seen this before" signal, and
DB storage is cheap enough that gating it to watched-only would trade real
correctness for a marginal storage saving.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarListingObservation(Base):
    __tablename__ = "gem_radar_listing_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(255), index=True)
    seller_name: Mapped[str | None] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50))
    condition_normalised: Mapped[str] = mapped_column(String(20))
    listing_type: Mapped[str] = mapped_column(String(20))
    item_price: Mapped[float] = mapped_column(Float)
    postage_price: Mapped[float] = mapped_column(Float)
    delivered_price: Mapped[float] = mapped_column(Float)
    bid_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_offer_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # Which extension scan run most recently re-confirmed this listing is
    # still around — updated on EVERY sighting, including ones the 7-day
    # dedup window skips from full re-scoring (see observations.touch_observation).
    # This is what makes "active" (last N runs) mean something real: without
    # it, a still-live listing that keeps getting deduped would never touch
    # this row again after its first sighting, and would silently age out of
    # "last N runs" within hours even though it never stopped appearing in
    # scrapes.
    search_run_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # The extension search term that found this sighting (e.g. "cpu cooler",
    # "AMD CPU", "case chassis") — the primary "active" grouping key (see
    # observations.get_active_listing_ids), falling back to resolved
    # category only if this is somehow missing. Several search lines
    # commonly resolve to the same category (e.g. "AMD CPU" and "Intel CPU"
    # both resolve to category "cpu"), so grouping by category instead would
    # let one search line's runs evict a completely different search line's
    # still-fresh listings from "active" the moment a third distinct search
    # under the same category landed.
    search_query: Mapped[str | None] = mapped_column(String(500), index=True, nullable=True)
    # Marketplace this sighting came from (ebay/vinted/overclockers/temu),
    # inferred from the listing URL at write time (see
    # app.gem_radar.marketplace.infer_marketplace) — ExtractedListing itself
    # has no explicit source field. Used by build_batch_price_index to keep
    # untrusted-for-pricing marketplaces (Temu: counterfeit/drop-ship risk)
    # from silently corrupting "new" price benchmarks pooled from everywhere
    # else.
    source: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    # eBay catalog product ID (Browse API itemSummaries[].epid) — see
    # gem_radar_scored_listings.epid and pipeline.build_batch_price_index.
    epid: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    # Global Trade Item Number (UPC/barcode) — canonical product identifier
    # extracted from Browse API productSummary.gtin. More stable than epid for
    # consolidating the same product across title variants. Indexed for batch
    # price lookups in build_batch_price_index.
    gtin: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    # Manufacturer Part Number — another stable canonical identifier extracted
    # from Browse API productSummary.mpn. Used as a backup when GTIN is unavailable.
    # Indexed for batch price lookups.
    mpn: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    # Product model number from vendor API (e.g. eBay productSummary.modelNumber).
    # Stable across title variants, used as 3rd-priority matching key after GTIN/MPN.
    # Example: "100-10000108​4WOF" for AMD Ryzen 9 9800X3D.
    model_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    # eBay Browse API item.seller.feedbackPercentage/feedbackScore — free on
    # every search response, carried through to gem_radar_scored_listings so
    # the dashboard can render it (see services/ebay_browse.py's EbayListing).
    seller_feedback_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    seller_feedback_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Barcode scan price — new retail price from physical scan, used for market
    # price aggregation alongside marketplace listings. Only populated for new
    # condition items where scan provides a solid retail reference.
    scan_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cross-search dedup / cost-control cache (PRD §24 "researched once,
    # referenced twice", §31 caching). Stores the full ScoredListing JSON so
    # a listing seen again under a different search within the freshness
    # window doesn't re-hit the eBay Browse API or Claude — see
    # app.gem_radar.observations.get_cached_score.
    scored_result_json: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Peer-sync conflict clock. Bumped by touch_observation() and any other
    # ORM-level mutation via SQLAlchemy's onupdate; a raw-SQL UPDATE against
    # this table must set it explicitly or the change won't be recognised
    # as newer by app.services.peer_sync.
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<GemRadarListingObservation {self.listing_id} £{self.delivered_price} @{self.observed_at}>"
