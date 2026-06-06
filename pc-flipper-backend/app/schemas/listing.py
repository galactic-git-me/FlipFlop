from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.models.listing import Classification, ListingStatus


class ListingAlternative(BaseModel):
    """A cheaper/more-expensive duplicate of the same hardware on a different vendor."""
    id: int
    source_name: str
    price: float
    url: str

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: int
    external_id: str
    dedupe_fingerprint: Optional[str] = None
    source_name: str
    source_confidence: str
    title: str
    price: float
    url: str
    image_urls: list[str]
    location: Optional[str]
    condition: Optional[str]
    cpu: Optional[str]
    ram_gb: Optional[int]
    ram_type: Optional[str]
    storage_gb: Optional[int]
    storage_type: Optional[str]
    gpu: Optional[str]
    has_psu: bool
    gem_score: float
    classification: Classification
    gem_signals: list[str]
    gem_explainer: Optional[str] = None
    # Resale range (market price low / median / high)
    estimated_resale: Optional[float]    # median — the anchor
    resale_low: Optional[float]          # 25th-pct or −12 %
    resale_high: Optional[float]         # 75th-pct or +12 %
    resale_comp_count: Optional[int]     # 0 = fallback estimate
    # Cost and profit
    estimated_upgrade_cost: Optional[float]   # total upgrade spend
    estimated_profit: Optional[float]    # profit at median resale
    # Auction / listing metadata
    listing_type: Optional[str]          # "auction" | "buy_it_now" | "classified"
    listing_ends_at: Optional[datetime]  # when the auction/listing expires
    expected_buy_price: Optional[float]  # for auctions: estimated final hammer price
    # Seller intelligence
    seller_name: Optional[str]
    seller_feedback_count: Optional[int]
    seller_feedback_pct: Optional[float]
    seller_type: Optional[str]           # shop | refurb_shop | flipper | private
    seller_has_shop: bool
    listed_at: Optional[datetime]        # when the seller originally posted this
    # Demand intelligence — from the search term that found this listing
    demand_score: Optional[float]        # 0-10 demand score of the search term
    found_via_term: Optional[str]        # the search term text
    status: ListingStatus
    first_seen_at: datetime
    last_seen_at: datetime
    # Claude authoritative evaluation
    claude_verdict:            Optional[str]      = None
    claude_flipability_score:  Optional[float]    = None
    claude_expected_profit:    Optional[float]    = None
    claude_roi:                Optional[float]    = None
    claude_confidence:         Optional[float]    = None
    claude_capital_efficiency: Optional[int]      = None
    claude_resale_demand:      Optional[int]      = None
    claude_upgrade_complexity: Optional[int]      = None
    claude_reasoning:          Optional[str]      = None
    claude_main_risk:          Optional[str]      = None
    claude_judged_at:          Optional[datetime] = None

    # Cross-vendor alternatives: same spec fingerprint, higher price, different source.
    # Populated by the listings API; empty for listings without a spec fingerprint.
    alternatives: list[ListingAlternative] = []

    model_config = {"from_attributes": True}


class ListingFilter(BaseModel):
    classification: Optional[Classification] = None
    status: Optional[ListingStatus] = None
    source_name: Optional[str] = None
    min_profit: Optional[float] = None
    max_price: Optional[float] = None
    search: Optional[str] = None
    limit: int = 50
    offset: int = 0
    sort_by: str = "estimated_profit"
    sort_desc: bool = True
