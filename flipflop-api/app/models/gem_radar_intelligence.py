"""Audit and feedback records used to validate sourcing decisions."""
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarDecisionEvent(Base):
    __tablename__ = "gem_radar_decision_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(255), index=True)
    classification: Mapped[str] = mapped_column(String(50), index=True)
    decision: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float)
    explanation: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ComponentRatingEvent(Base):
    __tablename__ = "component_rating_events"
    __table_args__ = (UniqueConstraint("build_id", "component_slot", "component_key", name="uq_component_rating_build_slot_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    build_id: Mapped[int] = mapped_column(ForeignKey("manual_builds.id", ondelete="CASCADE"), index=True)
    component_slot: Mapped[str] = mapped_column(String(50))
    component_key: Mapped[str] = mapped_column(String(255), index=True)
    overall_rating: Mapped[int] = mapped_column(Integer)
    reliability_rating: Mapped[int | None] = mapped_column(Integer)
    installation_rating: Mapped[int | None] = mapped_column(Integer)
    aesthetics_rating: Mapped[int | None] = mapped_column(Integer)
    value_rating: Mapped[int | None] = mapped_column(Integer)
    customer_appeal_rating: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PreferredComponent(Base):
    __tablename__ = "preferred_components"
    component_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    component_slot: Mapped[str] = mapped_column(String(50), index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    average_rating: Mapped[float] = mapped_column(Float, default=5.0)
    status: Mapped[str] = mapped_column(String(20), default="preferred")
    last_build_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    outcome_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
