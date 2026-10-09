"""Current market availability for a Gem Radar listing ID."""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GemRadarListingLifecycle(Base):
    __tablename__ = "gem_radar_listing_lifecycle"

    listing_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    archive_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
