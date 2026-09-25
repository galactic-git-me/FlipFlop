from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CuratedBuildSegment(Base):
    """One editable curated build for a customer type and budget level."""

    __tablename__ = "curated_build_segments"
    __table_args__ = (
        UniqueConstraint("customer_type", "budget_level", name="uq_curated_segment_type_budget"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_type: Mapped[str] = mapped_column(String(120), nullable=False)
    budget_level: Mapped[str] = mapped_column(String(80), nullable=False)
    budget_min: Mapped[float | None] = mapped_column(Float)
    budget_max: Mapped[float | None] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    selling_price: Mapped[float | None] = mapped_column(Float)
    proposed_selling_price: Mapped[float | None] = mapped_column(Float)
    component_cost_snapshot: Mapped[float | None] = mapped_column(Float)
    availability_status: Mapped[str] = mapped_column(String(30), default="in_stock", nullable=False)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regeneration_status: Mapped[str] = mapped_column(String(30), default="idle", nullable=False)
    regeneration_request_id: Mapped[str | None] = mapped_column(String(100))
    regeneration_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
