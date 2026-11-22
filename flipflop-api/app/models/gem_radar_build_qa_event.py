"""Durable event and snapshot for post-scrape component compatibility QA."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarBuildQAEvent(Base):
    __tablename__ = "gem_radar_build_qa_events"
    __table_args__ = (UniqueConstraint("environment", "sweep_run_id", name="uq_gem_build_qa_environment_run"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    environment: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    sweep_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sheet_sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_configured")
    sheet_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
