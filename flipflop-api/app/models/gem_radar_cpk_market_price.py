"""Per-CPK market price aggregate, recomputed from every row in
gem_radar_cpk_listing_price sharing that cpk (see app/gem_radar/cpk_market.py).
listing_count is the trust gate: a market price backed by fewer than 2
contributing listings has not "settled" yet (per the two-phase CPK design —
phase 1 accumulates, phase 2 only classifies against a settled price) and
must not be used for classification even though a row already exists here."""
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarCpkMarketPrice(Base):
    __tablename__ = "gem_radar_cpk_market_price"

    cpk: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    listing_count: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarCpkMarketPrice {self.cpk} median=£{self.median_price} n={self.listing_count}>"
