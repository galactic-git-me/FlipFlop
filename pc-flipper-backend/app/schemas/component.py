"""Component catalogue schemas."""
from pydantic import BaseModel
from typing import Optional


class ComponentSourceListing(BaseModel):
    """A component listing from a single source."""
    source: str  # "vinted", "gumtree", "amazon", "temu", "aliexpress", "ebay"
    price: float
    title: str
    url: str
    image_url: Optional[str] = None
    condition: Optional[str] = None


class ComponentPriceData(BaseModel):
    """Live price data for a component model."""
    model: str
    tier: str  # "budget", "mid", "high", "ultra"

    # eBay benchmarks (used for gem scoring)
    new_price: Optional[float] = None
    new_count: int
    used_median: Optional[float] = None
    used_count: int
    used_cheapest_price: Optional[float] = None
    used_cheapest_url: Optional[str] = None
    used_cheapest_title: Optional[str] = None
    used_cheapest_image: Optional[str] = None

    # Gem classification
    discount_pct: Optional[float] = None
    gem_classification: Optional[str] = None  # "super_gem", "gem", or None

    # All-source listings
    all_sources: list[ComponentSourceListing] = []
