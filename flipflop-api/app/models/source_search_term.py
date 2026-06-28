from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SourceSearchTerm(Base):
    __tablename__ = "source_search_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(80), index=True, default="cases")
    group_name: Mapped[str] = mapped_column(String(200), index=True)
    term: Mapped[str] = mapped_column(String(400), index=True)
    source_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Demand intelligence
    demand_score: Mapped[float] = mapped_column(Float, default=5.0)
    # Baseline terms are anchors — never auto-disabled regardless of zero results
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    # How many consecutive scrape runs returned zero results
    zero_results_streak: Mapped[int] = mapped_column(Integer, default=0)
    # Last time this term found at least one result
    last_result_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
