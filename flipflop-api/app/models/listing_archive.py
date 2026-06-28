"""
ListingArchive — a permanent record of listings that went unseen for 3+ days
and were never chosen for a flip.

The main `listings` table stays lean (active + recently missing listings only).
This table is append-only: rows are never updated or deleted after insertion.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.listing import Classification, ListingStatus


class ListingArchive(Base):
    __tablename__ = "listing_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Original listing PK (not a FK — the source row is deleted after archiving)
    original_id: Mapped[int] = mapped_column(Integer, index=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # ── All columns mirrored from Listing ────────────────────────────────────
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    dedupe_fingerprint: Mapped[Optional[str]] = mapped_column(String(255))
    source_id: Mapped[int] = mapped_column(Integer)
    source_name: Mapped[str] = mapped_column(String(100))
    source_confidence: Mapped[str] = mapped_column(String(32), default="browser_verified")

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    url: Mapped[str] = mapped_column(String(1000))
    image_urls: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    condition: Mapped[Optional[str]] = mapped_column(String(50))

    cpu: Mapped[Optional[str]] = mapped_column(String(200))
    ram_gb: Mapped[Optional[int]] = mapped_column(Integer)
    ram_type: Mapped[Optional[str]] = mapped_column(String(20))
    storage_gb: Mapped[Optional[int]] = mapped_column(Integer)
    storage_type: Mapped[Optional[str]] = mapped_column(String(20))
    gpu: Mapped[Optional[str]] = mapped_column(String(200))
    has_psu: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_specs: Mapped[dict] = mapped_column(JSON, default=dict)

    gem_score: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification), default=Classification.unclassified
    )
    gem_signals: Mapped[list] = mapped_column(JSON, default=list)

    estimated_resale: Mapped[Optional[float]] = mapped_column(Float)
    resale_low: Mapped[Optional[float]] = mapped_column(Float)
    resale_high: Mapped[Optional[float]] = mapped_column(Float)
    resale_comp_count: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_profit: Mapped[Optional[float]] = mapped_column(Float)
    estimated_upgrade_cost: Mapped[Optional[float]] = mapped_column(Float)
    initial_estimated_profit: Mapped[Optional[float]] = mapped_column(Float)

    listing_type: Mapped[Optional[str]] = mapped_column(String(20))
    listing_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expected_buy_price: Mapped[Optional[float]] = mapped_column(Float)

    seller_name: Mapped[Optional[str]] = mapped_column(String(200))
    seller_feedback_count: Mapped[Optional[int]] = mapped_column(Integer)
    seller_feedback_pct: Mapped[Optional[float]] = mapped_column(Float)
    seller_type: Mapped[Optional[str]] = mapped_column(String(20))
    seller_has_shop: Mapped[bool] = mapped_column(Boolean, default=False)
    listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    demand_score: Mapped[Optional[float]] = mapped_column(Float)
    found_via_term: Mapped[Optional[str]] = mapped_column(String(400))

    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus), default=ListingStatus.missing
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    claude_verdict: Mapped[Optional[str]] = mapped_column(String(10))
    claude_flipability_score: Mapped[Optional[float]] = mapped_column(Float)
    claude_expected_profit: Mapped[Optional[float]] = mapped_column(Float)
    claude_roi: Mapped[Optional[float]] = mapped_column(Float)
    claude_confidence: Mapped[Optional[float]] = mapped_column(Float)
    claude_capital_efficiency: Mapped[Optional[int]] = mapped_column(Integer)
    claude_resale_demand: Mapped[Optional[int]] = mapped_column(Integer)
    claude_upgrade_complexity: Mapped[Optional[int]] = mapped_column(Integer)
    claude_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    claude_main_risk: Mapped[Optional[str]] = mapped_column(Text)
    claude_judged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    playbook_match: Mapped[Optional[str]] = mapped_column(String(200))
    demand_fit: Mapped[Optional[str]] = mapped_column(String(50))
    upsell_strategy: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<ListingArchive original_id={self.original_id} {self.title[:40]!r}>"
