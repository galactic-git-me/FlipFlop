"""Track demand signal history (watch/bid counts) for time-to-sell velocity."""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarListingDemandHistory(Base):
    __tablename__ = "gem_radar_listing_demand_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(255), index=True)
    search_run_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)

    # Demand signals at observation time
    watch_count: Mapped[int] = mapped_column(Integer, default=0)
    bid_count: Mapped[int] = mapped_column(Integer, default=0)

    # Calculated velocity metrics (populated once we have 2+ observations)
    watch_velocity_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_velocity_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Observed price at this snapshot (to detect price drops)
    delivered_price: Mapped[float] = mapped_column(Float)

    # Listing status (active/sold/ended) — inferred from disappearance
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, sold, ended, relisted

    # When this observation was recorded
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
