from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Favourite(Base):
    """A saved component search or product the user wants tracked across every data run.

    Can track either a fuzzy search term (term + category) OR a specific CPK
    (Canonical Product Key), or both. matched_listing_ids is a dedup ledger:
    phase2_runner appends a listing_id here the first time it fires a
    favourite_gem_match alert for it, so the same GEM/SUPER_GEM listing never
    re-alerts on a later scan.
    """

    __tablename__ = "gem_radar_favourites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str | None] = mapped_column(String(400), index=True, nullable=True)
    cpk: Mapped[str | None] = mapped_column(String(400), index=True, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    matched_listing_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_matched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
