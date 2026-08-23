"""Demand Metrics Snapshot model for Phase 3 F3.1.

Denormalized metrics for fast dashboard querying.
Captures view counts, conversion rates, trends, and volatility.
"""

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DemandMetricsSnapshot(Base):
    __tablename__ = "demand_metrics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"), nullable=False)

    view_count: Mapped[int] = mapped_column(Integer, default=0)
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)

    view_to_conversion_rate: Mapped[float | None] = mapped_column(Float)
    sell_through_rate: Mapped[float | None] = mapped_column(Float)

    views_per_day: Mapped[float | None] = mapped_column(Float)
    conversions_per_day: Mapped[float | None] = mapped_column(Float)

    demand_trend: Mapped[str] = mapped_column(String(20), default="unknown")
    trend_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    volatility_score: Mapped[float] = mapped_column(Float, default=0.0)

    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
