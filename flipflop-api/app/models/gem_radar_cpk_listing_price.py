"""One row per listing that has contributed a price to a CPK's market-price
aggregate (app/gem_radar/cpk_market.py). listing_id is the primary key so a
listing re-seen across scan runs updates its existing contribution rather
than being double-counted — the CPK's min/median/max/listing_count are always
recomputed from every row currently in this table for that cpk, never from an
incrementally-maintained running total."""
from datetime import datetime
from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarCpkListingPrice(Base):
    __tablename__ = "gem_radar_cpk_listing_price"

    # Vendor-qualified IDs can include a source prefix plus a product slug.
    listing_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    cpk: Mapped[str] = mapped_column(String(64), index=True)
    price: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarCpkListingPrice {self.listing_id} cpk={self.cpk} £{self.price}>"
