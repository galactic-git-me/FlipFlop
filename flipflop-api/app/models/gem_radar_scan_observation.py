"""Scan price observations from physical barcode scans.

One row per (cpk, scan) of a new-condition product scan via barcode. Scan prices
are solid new/retail prices (not used), providing a cross-vendor consensus
benchmark for new items — complementing marketplace listings (which may be
outliers/scalped) with verified new-stock retail pricing.

Used in gem_radar/cpk_market.py to enrich market-price aggregation, pooled
alongside marketplace listings, sold comps, and Amazon prices in the rolling
MARKET_PRICE_WINDOW_DAYS window.
"""
from datetime import datetime
from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarScanObservation(Base):
    __tablename__ = "gem_radar_scan_observation"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpk: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    match_key: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<GemRadarScanObservation cpk={self.cpk} price=£{self.price} @{self.observed_at}>"
