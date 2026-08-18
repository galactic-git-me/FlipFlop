"""Canonical Product Key assigned to a listing, persisted independently of
gem_radar_scored_listings so it survives a full rescore/delete of that table
(see app/gem_radar/cpk_extractor.py for how the key is derived)."""
from datetime import datetime
from sqlalchemy import String, Float, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarListingCpk(Base):
    __tablename__ = "gem_radar_listing_cpk"

    # Vendor-qualified IDs can include a source prefix plus a product slug.
    # Keep this aligned with gem_radar_listing_observations.listing_id.
    listing_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    cpk: Mapped[str] = mapped_column(String(64), index=True)
    cpk_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cpk_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarListingCpk {self.listing_id} cpk={self.cpk}>"
