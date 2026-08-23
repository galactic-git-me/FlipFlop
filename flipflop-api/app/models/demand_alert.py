"""Demand Alert model for Phase 3 F3.1.

Threshold-based alerts for demand signals.
Tracks high demand, low demand, and risk flags.
"""

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DemandAlert(Base):
    __tablename__ = "demand_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int] = mapped_column(Integer, ForeignKey("manual_builds.id"), nullable=False)

    alert_type: Mapped[str] = mapped_column(String(30))  # high_demand, low_demand, risk_flag
    severity: Mapped[str] = mapped_column(String(20))    # info, warning, critical
    message: Mapped[str] = mapped_column(String(500))

    metric_name: Mapped[str] = mapped_column(String(50))
    threshold_value: Mapped[float] = mapped_column(Float)
    actual_value: Mapped[float] = mapped_column(Float)

    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
