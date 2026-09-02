"""Scraped Amazon UK retail-price comparables (see
app.gem_radar.adapters.amazon_price.LiveAmazonPriceAdapter for the scrape
itself — reuses app.scrapers.amazon_scraper, the same Playwright-based
scraper already used by component_search.py, rather than the Product
Advertising API, which gates access behind an Amazon Associates account
with 3 qualifying referral sales in the trailing 180 days.

Persisted so an Amazon price lookup for a given model is scraped once and
reused by every other listing that resolves to the same model within the
lookback window — a real browser launch per listing would be far too slow
for a scan of hundreds of listings, the same reasoning
gem_radar_sold_observations already applies to eBay sold comps.
"""
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarAmazonObservation(Base):
    __tablename__ = "gem_radar_amazon_observations"
    __table_args__ = (
        Index("ix_gem_radar_amazon_obs_key_time", "match_key", "observed_at"),
        Index("ix_gem_radar_amazon_obs_cpk", "cpk"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Same normalised match key as gem_radar_sold_observations/BIN matching
    # (see benchmarks.normalize_match_key) — one bucketing key shared across
    # every price source for a given real product.
    match_key: Mapped[str] = mapped_column(String(255), index=True)
    # Canonical Product Key mapped from a recent listing with the same match_key.
    cpk: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarAmazonObservation {self.match_key} £{self.price} @{self.observed_at}>"
