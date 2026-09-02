"""Scored listings with gem classification and market prices."""
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarScoredListing(Base):
    __tablename__ = "gem_radar_scored_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(255), index=True)
    search_run_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # Marketplace the listing was scraped from (ebay, vinted, ...). The
    # extension is eBay-only today, so this is hardcoded at ingestion time
    # rather than derived from ExtractedListing — see submit_scan in
    # app/api/gem_radar.py. Column exists now so multi-marketplace scraping
    # doesn't require a schema change later.
    source: Mapped[str] = mapped_column(String(20), default="ebay", server_default="ebay", index=True)
    # Real scraped listing URL (from ExtractedListing.url) — was never
    # stored here at all before; every "view listing" link in the app
    # (dashboard table, gem-of-day/week, AI build generator) was a hardcoded
    # f"https://www.ebay.co.uk/itm/{listing_id}/" template that silently
    # produced a wrong/dead link for every non-eBay marketplace. NULL for
    # rows scored before this column existed — those still fall back to the
    # old eBay-shaped guess at read time, see the fallback callers.
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    seller_name: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(30), nullable=True)  # new, used, refurbished, etc.
    # Resolved product category (cpu, gpu, ram, motherboard, ssd, psu, cooler)
    # from identity.resolve_identity() — None when identity resolution found
    # no real component match (including accessories like protector cases or
    # mounting brackets, see identity.is_likely_accessory). This is the
    # authoritative category; never re-derive it from naive title keyword
    # matching, which is what let accessories masquerade as components.
    category: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # Claude-assigned stable "BRAND MODEL" matching key (see
    # gem_radar/claude_screening.py canonical_model_id) — only populated for
    # SUPER_GEM/GEM listings, which are the only tier that gets the deep-
    # research pass. Used as the batch/historical price-match grouping key
    # in pipeline.build_batch_price_index instead of the raw regex-derived
    # model string, which fragments the same product across title wording
    # variants (e.g. "Intel Core i7-11700T" vs "Intel i7-11700T").
    canonical_model_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # eBay catalog product ID (Browse API itemSummaries[].epid) — a real
    # cross-listing identity key, unlike canonical_model_id (LLM-derived from
    # title text) or the raw regex model string. Only populated for listings
    # sourced via the eBay Browse API path. See pipeline.build_batch_price_index.
    epid: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    # Canonical Product Key (see gem_radar/cpk_market.py) — the market-price
    # grouping key used by phase2_runner's classification pass. Column has
    # existed since the CPK market-price system shipped (see scripts/
    # batch_extract_cpk.py, rescore_with_cpk.py) but was never declared here;
    # reads went through raw SQL only until favourites needed ORM access to
    # match listings to a saved product (see app/api/favourites.py).
    cpk: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    # eBay Browse API seller.feedbackPercentage/feedbackScore — free, carried
    # through from gem_radar_listing_observations (see observations.record_observation).
    seller_feedback_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    seller_feedback_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Product review rating/count. Only populated for SUPER_GEM/GEM listings
    # with an epid, via eBay's Catalog API (see services/ebay_catalog.py and
    # phase2_runner.py's classification-gated fetch) — a 7-day-cached, gated
    # external call, unlike seller feedback above which comes free with every
    # Browse API search response.
    review_average_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Listing prices
    actual_listing_price: Mapped[float] = mapped_column(Float)
    postage_price: Mapped[float] = mapped_column(Float)
    delivered_price: Mapped[float] = mapped_column(Float)

    # Market prices (from eBay Browse API)
    market_new_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # Today's new BIN
    market_used_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # Today's used BIN

    # Demand signals (for GEM/SUPER_GEM quality scoring)
    bid_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Scoring
    classification: Mapped[str] = mapped_column(String(50), index=True)  # SUPER_GEM, GEM, OK_DEAL, etc.
    deal_score: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    confidence_band: Mapped[str] = mapped_column(String(20))  # high, medium, low

    # Decision
    decision: Mapped[str] = mapped_column(String(50))  # BUY_NOW, MAKE_OFFER, WATCH, INVESTIGATE, IGNORE

    # Explainable opportunity model.  These are current decision facts, not
    # another event ledger; listing_id is unique after the migration.
    expected_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    walk_away_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    conservative_resale_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_source_diversity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_spread_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Matched CPK + condition demand evidence.  These are deliberately
    # nullable: a missing value means evidence was not available, whereas 0
    # is a measured zero.  The current source is a bounded 90-day cohort, so
    # this must not be presented as marketplace-wide sell-through.
    active_listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sold_listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sell_through_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_through_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sell_through_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    liquidity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    desirability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    scoring_explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Reasoning
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Year the identified product was originally released, from Claude's own
    # knowledge during deep-research screening (see claude_screening.py) —
    # only populated for listings that got the deep-research pass, so this
    # is frequently null even on real components.
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    listing_observed_at: Mapped[datetime] = mapped_column(DateTime)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # Peer-sync conflict clock. phase2_runner's rescore path updates this
    # table with raw SQL, which bypasses SQLAlchemy's onupdate -- that call
    # site sets updated_at explicitly (see app/gem_radar/phase2_runner.py).
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<GemRadarScoredListing {self.listing_id} {self.classification} £{self.delivered_price} @{self.scored_at}>"
