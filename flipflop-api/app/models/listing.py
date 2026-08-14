import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.database import Base


class ListingStatus(str, enum.Enum):
    active = "active"
    missing = "missing"
    removed = "removed"
    sold = "sold"


class Classification(str, enum.Enum):
    amazing_gem = "amazing_gem"
    gem = "gem"
    already_flipped = "already_flipped"
    no_profit = "no_profit"
    overpriced = "overpriced"
    unclassified = "unclassified"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    dedupe_fingerprint: Mapped[str | None] = mapped_column(String(255), index=True)
    # Spec-based fingerprint: cpu|gpu|ram_gb|storage_gb — groups same-hardware listings
    # across sources and re-lists so only the cheapest is surfaced in results.
    spec_fingerprint: Mapped[str | None] = mapped_column(String(255), index=True)
    source_id: Mapped[int] = mapped_column(Integer, index=True)
    source_name: Mapped[str] = mapped_column(String(100))
    source_confidence: Mapped[str] = mapped_column(String(32), default="browser_verified", index=True)

    # Raw listing data
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    url: Mapped[str] = mapped_column(String(1000))
    image_urls: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[str | None] = mapped_column(String(200))
    condition: Mapped[str | None] = mapped_column(String(50))

    # Parsed specs
    cpu: Mapped[str | None] = mapped_column(String(200))

    # RAM fields — comprehensive tracking
    ram_gb: Mapped[int | None] = mapped_column(Integer)  # Capacity in GB
    ram_type: Mapped[str | None] = mapped_column(String(20))  # DDR3/DDR4/DDR5
    ram_brand: Mapped[str | None] = mapped_column(String(100))  # Corsair, Kingston, G.Skill, etc.
    ram_model: Mapped[str | None] = mapped_column(String(200))  # Vengeance Pro RGB, Fury Beast, etc.
    ram_speed: Mapped[int | None] = mapped_column(Integer)  # MHz (6000, 5600, 3600, etc.)
    ram_cl: Mapped[int | None] = mapped_column(Integer)  # CAS Latency (16, 18, 20, etc.)
    ram_sticks: Mapped[int | None] = mapped_column(Integer)  # Number of modules (1, 2, 4, etc.)

    # Storage fields — comprehensive tracking
    storage_gb: Mapped[int | None] = mapped_column(Integer)  # Capacity in GB
    storage_type: Mapped[str | None] = mapped_column(String(20))  # M.2, SATA, NVMe, PCIE3, PCIE4, etc.
    storage_brand: Mapped[str | None] = mapped_column(String(100))  # Samsung, Western Digital, SK Hynix, etc.
    storage_model: Mapped[str | None] = mapped_column(String(200))  # 970 EVO, Red, 860 Evo, etc.
    storage_form_factor: Mapped[str | None] = mapped_column(String(20))  # 2.5", 3.5", M.2, etc.

    gpu: Mapped[str | None] = mapped_column(String(200))

    # PSU fields — comprehensive tracking (replaces has_psu boolean)
    psu_included: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether PSU is in build
    psu_brand: Mapped[str | None] = mapped_column(String(100))  # Corsair, EVGA, Seasonic, etc.
    psu_wattage: Mapped[int | None] = mapped_column(Integer)  # Watts (750, 1000, 1200, etc.)
    psu_rating: Mapped[str | None] = mapped_column(String(20))  # 80+ Gold/Silver/Bronze/None

    # Case fields — comprehensive tracking
    case_brand: Mapped[str | None] = mapped_column(String(100))  # Lian Li, NZXT, Corsair, etc.
    case_model: Mapped[str | None] = mapped_column(String(200))  # O11 Vision Compact, H510, etc.
    case_form_factor: Mapped[str | None] = mapped_column(String(20))  # ATX, MATX, ITX, SFF, etc.
    case_color: Mapped[str | None] = mapped_column(String(50))  # Black, White, Transparent, etc.
    # Reference to case_catalogue if we know the exact case (links to full specs/dimensions)
    case_catalogue_id: Mapped[int | None] = mapped_column(Integer)

    raw_specs: Mapped[dict] = mapped_column(JSON, default=dict)

    # Gem scoring
    gem_score: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification), default=Classification.unclassified
    )
    gem_signals: Mapped[list] = mapped_column(JSON, default=list)

    # Profit estimates
    estimated_resale: Mapped[float | None] = mapped_column(Float)
    resale_low: Mapped[float | None] = mapped_column(Float)       # 25th-pct comp price
    resale_high: Mapped[float | None] = mapped_column(Float)      # 75th-pct comp price
    resale_comp_count: Mapped[int | None] = mapped_column(Integer) # 0 = static fallback
    estimated_profit: Mapped[float | None] = mapped_column(Float)
    estimated_upgrade_cost: Mapped[float | None] = mapped_column(Float)
    initial_estimated_profit: Mapped[float | None] = mapped_column(Float)

    # Auction / listing metadata
    # listing_type: "auction" | "buy_it_now" | "classified"
    listing_type: Mapped[Optional[str]] = mapped_column(String(20))
    # When the auction/listing expires (None for fixed-price / classified)
    listing_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # For auction listings: estimated final hammer price from completed eBay auction comps.
    # Raw price = current bid (too low); BIN price = too high; this is the Goldilocks value.
    expected_buy_price: Mapped[Optional[float]] = mapped_column(Float)

    # Seller intelligence
    seller_name: Mapped[Optional[str]] = mapped_column(String(200))
    seller_feedback_count: Mapped[Optional[int]] = mapped_column(Integer)
    seller_feedback_pct: Mapped[Optional[float]] = mapped_column(Float)
    # shop | refurb_shop | flipper | private
    seller_type: Mapped[Optional[str]] = mapped_column(String(20))
    seller_has_shop: Mapped[bool] = mapped_column(Boolean, default=False)
    # When the listing was originally posted by the seller (as opposed to first_seen_at which is when WE saw it)
    listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Demand intelligence — annotated at ingest time from the search term that found this listing
    demand_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    found_via_term: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

    # Lifecycle
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus), default=ListingStatus.active
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Claude authoritative evaluation
    claude_verdict:            Mapped[Optional[str]]      = mapped_column(String(10))    # GEM | GOOD | MAYBE | REJECT
    claude_flipability_score:  Mapped[Optional[float]]    = mapped_column(Float)
    claude_expected_profit:    Mapped[Optional[float]]    = mapped_column(Float)
    claude_roi:                Mapped[Optional[float]]    = mapped_column(Float)
    claude_confidence:         Mapped[Optional[float]]    = mapped_column(Float)
    claude_capital_efficiency: Mapped[Optional[int]]      = mapped_column(Integer)
    claude_resale_demand:      Mapped[Optional[int]]      = mapped_column(Integer)
    claude_upgrade_complexity: Mapped[Optional[int]]      = mapped_column(Integer)
    claude_reasoning:          Mapped[Optional[str]]      = mapped_column(Text)
    claude_main_risk:          Mapped[Optional[str]]      = mapped_column(Text)
    claude_judged_at:          Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self):
        return f"<Listing {self.id} {self.title[:40]!r} £{self.price}>"
