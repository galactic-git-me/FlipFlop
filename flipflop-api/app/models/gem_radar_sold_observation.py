"""Scraped eBay sold/completed-listing comparables (see
app.gem_radar.adapters.sold_comps.LiveSoldCompsAdapter for the scrape itself).

Persisted so a sold-price lookup for a given model+condition is scraped once
and reused by every other listing that resolves to the same model within the
lookback window, instead of every listing independently re-scraping eBay's
sold-search page for data that's already sitting in this table — the same
"researched once, referenced twice" principle gem_radar_listing_observations
already applies to active-listing data.
"""
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarSoldObservation(Base):
    __tablename__ = "gem_radar_sold_observations"
    __table_args__ = (
        Index("ix_gem_radar_sold_obs_key_condition_time", "match_key", "condition", "observed_at"),
        Index("ix_gem_radar_sold_obs_cpk", "cpk"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Normalised match key (see benchmarks.normalize_match_key) — same
    # bucketing key used for BIN price matching, so a sold observation and a
    # BIN observation for the same real product always land under one key
    # regardless of the two listings' differently-worded titles.
    match_key: Mapped[str] = mapped_column(String(255), index=True)
    # Canonical Product Key mapped from a recent listing with the same match_key.
    # Allows sold observations to be included in CPK market price aggregation.
    cpk: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition: Mapped[str] = mapped_column(String(10))  # "new" | "used"
    price: Mapped[float] = mapped_column(Float)
    postage: Mapped[float] = mapped_column(Float, default=0.0)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # Peer-sync conflict clock. cpk_pipeline.py's CPK-backfill path updates
    # this table with raw SQL, which bypasses SQLAlchemy's onupdate -- that
    # call site sets updated_at explicitly.
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarSoldObservation {self.match_key} {self.condition} £{self.price} @{self.observed_at}>"
