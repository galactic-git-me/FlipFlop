"""Durable Chrome publishing work; an expired lease requires reconciliation."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BrowserListingJob(Base):
    __tablename__ = "browser_listing_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_listing_id: Mapped[int] = mapped_column(ForeignKey("channel_listings.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    lease_token: Mapped[str | None] = mapped_column(String(64))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (Index("uq_browser_listing_job_pending", "channel_listing_id", unique=True,
        postgresql_where=text("status IN ('queued', 'running', 'blocked', 'needs_review')"),
        sqlite_where=text("status IN ('queued', 'running', 'blocked', 'needs_review')")),)
