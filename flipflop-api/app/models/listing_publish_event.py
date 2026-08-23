"""Listing Publish Event model for Phase 2 F2.2.

Immutable audit trail of all listing publication activities.
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ListingPublishEvent(Base):
    __tablename__ = "listing_publish_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("channel_listings.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # published, withdrawn, dry_run, validation_failed
    message: Mapped[str | None] = mapped_column(String(500))
    event_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
