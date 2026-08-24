"""Pydantic contracts for the Gem Radar extension integration.

These mirror gem-radar-extension/src/lib/types.ts field-for-field (camelCase
on the wire via alias generation) so the extension's Zod schemas and this
API agree on shape without a translation layer drifting out of sync.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


def _to_camel(snake: str) -> str:
    first, *rest = snake.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


NormalisedCondition = Literal["new", "new_other", "refurbished", "used", "parts_only", "untested", "unknown"]
ListingType = Literal["buy_it_now", "auction", "classified"]
Classification = Literal["SUPER_GEM", "GEM", "OK_DEAL", "AVERAGE_DEAL", "POOR_DEAL"]
Decision = Literal["BUY_NOW", "MAKE_OFFER", "WATCH", "INVESTIGATE", "IGNORE"]
BenchmarkStatus = Literal["ok", "insufficient_sample", "unavailable"]
ConfidenceBand = Literal["high", "medium", "low"]


class ExtractedListing(CamelModel):
    listing_id: str
    url: str
    title: str
    seller: Optional[str]
    seller_feedback_percent: Optional[float]
    seller_feedback_count: Optional[int]
    condition_raw: Optional[str]
    condition_normalised: NormalisedCondition
    item_price: float
    postage_price: float
    current_delivered_price: float
    currency: Literal["GBP"] = "GBP"
    listing_type: ListingType
    best_offer_enabled: bool
    bid_count: Optional[int]
    watch_count: Optional[int] = None
    auction_end_at: Optional[datetime]
    image_url: Optional[str]
    sponsored: bool
    extracted_at: datetime
    # Barcode scan price (new retail price from physical scan, not used condition)
    scan_price: Optional[float] = None
    # eBay catalog product ID (Browse API itemSummaries[].epid) — a real
    # cross-listing identity key, unlike our own title-regex-derived model
    # string, which fragments the same product across title wording
    # variants. Only populated for listings sourced via the eBay Browse API
    # path (see services/ebay_browse.py); other marketplaces/DOM-scraped
    # eBay listings leave this None, and matching falls back to identity.py.
    epid: Optional[str] = None
    # Global Trade Item Number (UPC/barcode) — canonical product identifier
    # across retailers and title variants. More stable than epid for consolidating
    # the same product listed under different titles (e.g. "9800X3D" vs
    # "Ryzen 9 9800X3D" vs "AMD Ryzen 9 9800X3D" all have the same GTIN).
    # Only populated for listings sourced via eBay Browse API with productSummary.
    gtin: Optional[str] = None
    # Manufacturer Part Number — another stable, canonical identifier for the
    # same product across title variants. Used alongside GTIN for consolidating
    # listings into a single price bucket. Only populated via eBay Browse API.
    mpn: Optional[str] = None
    # Product model number from vendor API (eBay productSummary.modelNumber).
    # Stable across title variants and a primary consolidation key after GTIN/MPN.
    # Example: "100-10000108​4WOF" for AMD Ryzen 9 9800X3D.
    model_number: Optional[str] = None
    # Product review rating (0-5) and review count. eBay: only populated for
    # GEM/SUPER_GEM-classified listings via the Catalog API (see
    # services/ebay_catalog.py), gated + 7-day cached since it's a per-epid
    # external call, not part of the free Browse API search response.
    # Amazon/AliExpress: scraped directly off the search-result card, same
    # extraction pass as price/title (see FlipFlopXtension's ebay-extractor.ts).
    review_average_rating: Optional[float] = None
    review_count: Optional[int] = None
    review_url: Optional[str] = None
    prime_eligible: Optional[bool] = None
    delivery_text: Optional[str] = None
    delivery_postcode: Optional[str] = None


class ScanSubmitRequest(CamelModel):
    search_run_id: str
    search_id: str
    query: str
    source_url: str
    max_candidates_for_deep_research: int
    listings: list[ExtractedListing]


class ScanRunHistorySubmitRequest(CamelModel):
    """One row of FlipFlopXtension's local scan-history CSV, mirrored to the
    backend so the admin Sourcing Dashboard can show it without reading a
    file from the user's Downloads folder."""
    search_term: str
    total_listings_found: int
    vendors: list[str]
    run_by: Literal["Manual", "Automatic"]
    duration_seconds: float
    occurred_at: datetime


class ScanRunHistoryOut(CamelModel):
    id: int
    search_term: str
    total_listings_found: int
    vendors: list[str]
    run_by: str
    duration_seconds: float
    occurred_at: datetime
    is_legacy: bool = False
    completion_known: bool = True


class SoldCompSubmitRequest(CamelModel):
    """FlipFlopXtension's sold/completed-listings scrape (LH_Sold=1&
    LH_Complete=1), extracted via the same real-browser-tab mechanism as
    ordinary listings — never through headless automation, see
    flipflop-api/experiments/ebay_manual_login_scrape.py for why. Reuses
    ExtractedListing's shape since the content-script extractor produces
    identical fields for a sold-search page as for a live-search page."""
    search_id: str
    query: str
    # Set for a backend-nominated exact-model enrichment. The ingestion
    # endpoint validates every returned comp against this CPK's canonical
    # identity before linking it; broad per-search collection leaves it null.
    target_cpk: Optional[str] = None
    comps: list[ExtractedListing]


class SoldCompSubmitResponse(CamelModel):
    inserted: int
    skipped: int


class SoldCompTarget(CamelModel):
    cpk: str
    query: str
    condition: Literal["new", "used"]
    candidate_count: int
    discount_pct: float


class ExclusionReason(CamelModel):
    reason: str
    count: int


class BenchmarkStat(CamelModel):
    status: BenchmarkStatus
    average: Optional[float]
    median: Optional[float]
    trimmed_mean: Optional[float]
    min: Optional[float]
    max: Optional[float]
    sample_size: int
    valid_sample_size: int
    currency: Literal["GBP"] = "GBP"
    match_level_counts: dict[str, int]
    exclusions: list[ExclusionReason]
    source: str
    source_url: Optional[str]
    observed_at: Optional[datetime]
    age_minutes: Optional[float]
    unavailable_reason: Optional[str] = None


class Identity(CamelModel):
    brand: Optional[str]
    model: Optional[str]
    mpn: Optional[str]
    category: Optional[str]
    exact_sku_confidence: Optional[float]
    # Stable "BRAND MODEL"-only grouping key from Claude's natural-language
    # reading of the title (see claude_screening.py) — unlike `model` above
    # (a regex-captured raw substring that varies with word order/SKU-code
    # placement in the source title), this is normalised so the same real
    # product always produces the same string across differently-worded
    # listings. Only ever populated for GEM/SUPER_GEM-tier listings, since
    # that's the only tier that gets the deep-research Claude pass — see
    # pipeline.py's always_screen_ids. None for everything else.
    model_canonical: Optional[str] = None


class RiskFlag(CamelModel):
    code: str
    severity: Literal["low", "medium", "high"]
    evidence: str


class InventoryAwareness(CamelModel):
    exact_matches_owned: int
    same_model_owned: int
    category_count: int
    reserved_count: int
    available_count: int


class OfferStrategy(CamelModel):
    opening_offer: Optional[float]
    target_buy_price: Optional[float]
    walk_away_price: Optional[float]


class PriceObservation(CamelModel):
    observed_at: datetime
    price: float
    postage: float
    delivered_price: float
    bid_count: Optional[int]
    best_offer_enabled: bool


class WatchSignals(CamelModel):
    """PRD §23-24 — change/relisting detection. All fields are computed from
    real prior observations in gem_radar_listing_observations; a listing
    seen for the first time gets observation_count=1 and every boolean flag
    false, never an inferred "no change" guess.
    """
    observation_count: int
    price_drop_detected: bool
    price_drop_amount: Optional[float]
    price_drop_percent: Optional[float]
    postage_changed: bool
    bid_count_changed: bool
    best_offer_newly_enabled: bool
    condition_changed: bool
    relisting_detected: bool
    likely_previous_listing_id: Optional[str]
    history: list[PriceObservation]


class SellerIntelligence(CamelModel):
    seller_name: str
    feedback_percent: Optional[float]
    feedback_count: Optional[int]
    seller_type: Optional[str]
    observed_listings: int
    historical_gem_count: int
    historical_super_gem_count: int
    historical_purchase_count: int
    cancellation_count: int
    issue_count: int


class PriceBundle(CamelModel):
    actual_listing: float
    ebay_new_bin: BenchmarkStat
    ebay_used_bin: BenchmarkStat
    ebay_new_sold: BenchmarkStat
    ebay_used_sold: BenchmarkStat
    amazon_uk_new: BenchmarkStat


class ScoredListing(CamelModel):
    rank: int
    listing: ExtractedListing
    identity: Identity
    prices: PriceBundle
    deal_score: float
    classification: Classification
    confidence_score: float
    confidence_band: ConfidenceBand
    decision: Decision
    flip_score: Optional[float]
    build_value_score: Optional[float]
    inventory_awareness: Optional[InventoryAwareness]
    risk_flags: list[RiskFlag]
    offer_strategy: Optional[OfferStrategy]
    reasoning_summary: Optional[str]
    release_year: Optional[int] = None
    watch_signals: Optional[WatchSignals] = None
    seller_intelligence: Optional[SellerIntelligence] = None


class ScanSubmitResponse(CamelModel):
    search_run_id: str
    results: list[ScoredListing]
    deep_researched_count: int
    excluded_auction_count: int = 0


class ScanIngestResponse(CamelModel):
    """Response for ingestion-only submission handling (see
    app/api/gem_radar.py's _submit_scan_body) — Phase 1 of the CPK
    market-price system. No scoring/classification happens at ingestion
    anymore; a listing only gets an observation row, a CPK, and a folded-in
    market-price contribution. See app/gem_radar/deal_classification.py for
    Phase 2, which classifies once a scan sweep signals completion."""
    search_run_id: str
    ingested_count: int
    cpk_assigned_count: int
    excluded_auction_count: int = 0


class ScanQueuedResponse(CamelModel):
    search_run_id: str
    submission_id: int
    status: Literal["queued"]
    message: str = "Submission queued for processing"


class BoughtItPayload(CamelModel):
    source: Literal["gem_radar_extension"]
    marketplace: Literal["ebay_uk"]
    listing_id: str
    listing_url: str
    title: str
    seller: Optional[str]
    actual_item_price_paid: float
    postage_paid: float
    discount_amount: float = 0
    total_paid: float
    quantity: int = 1
    purchase_date: datetime
    notes: str = ""


class BoughtItResponse(CamelModel):
    inventory_item_id: int
    status: Literal["PURCHASED_MANUAL"] = "PURCHASED_MANUAL"
    reconciliation_status: Literal["PENDING_EMAIL_CONFIRMATION"] = "PENDING_EMAIL_CONFIRMATION"
    duplicate_of: Optional[int]
