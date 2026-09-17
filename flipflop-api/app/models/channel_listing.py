"""Channel Listing model for Phase 2 F2.2 (Listing Proliferator).

Represents a listing on a specific channel (eBay, Storefront, etc.).
One build can have multiple listings across different channels.
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ChannelListing(Base):
    __tablename__ = "channel_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)  # 'ebay', 'storefront', etc.
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")  # draft, scheduled, published, withdrawn
    external_listing_id: Mapped[str | None] = mapped_column(String(100))  # eBay item ID or Storefront SKU
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Persisted per-channel recreate clock. APScheduler only triggers work;
    # these fields make the schedule survive an API/process restart.
    recreate_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    recreate_interval_days: Mapped[int | None] = mapped_column(Integer)
    next_recreate_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    last_recreate_at: Mapped[datetime | None] = mapped_column(DateTime)
    recreate_count: Mapped[int] = mapped_column(Integer, default=0)
    last_recreate_status: Mapped[str | None] = mapped_column(String(30))
    last_recreate_message: Mapped[str | None] = mapped_column(String(500))
