"""Seller intelligence profile (PRD §25) — one row per seller, aggregated
from every listing Gem Radar has ever scored. cancellation_count and
issue_count have no automatic data source yet (that requires the email
reconciliation monitor this PRD explicitly places out of scope, per
docs/ARCHITECTURE_GAP_ANALYSIS.md) — they exist as fields so a future
reconciliation feature has somewhere to write, and stay at 0 until then
rather than being omitted and silently reintroduced later as a schema
migration surprise.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarSellerProfile(Base):
    __tablename__ = "gem_radar_seller_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    feedback_percent: Mapped[float | None] = mapped_column(Float)
    feedback_count: Mapped[int | None] = mapped_column(Integer)
    seller_type: Mapped[str | None] = mapped_column(String(20))  # shop | refurb_shop | flipper | private (best-effort, unset until a signal exists)

    observed_listings_count: Mapped[int] = mapped_column(Integer, default=0)
    historical_gem_count: Mapped[int] = mapped_column(Integer, default=0)
    historical_super_gem_count: Mapped[int] = mapped_column(Integer, default=0)
    historical_purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    cancellation_count: Mapped[int] = mapped_column(Integer, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarSellerProfile {self.seller_name} listings={self.observed_listings_count} gems={self.historical_gem_count}>"
