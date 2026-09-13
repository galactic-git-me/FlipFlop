"""Reviewable identity reconciliation proposals for sold observations.

Proposals are intentionally separate from ``gem_radar_sold_observations``:
generating a proposal is read-only with respect to market cohorts, and a
reviewer can reject an ambiguous match without losing the source evidence.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GemRadarIdentityProposal(Base):
    __tablename__ = "gem_radar_identity_proposals"
    __table_args__ = (
        Index("ix_gem_radar_identity_proposals_status", "status"),
        Index("ix_gem_radar_identity_proposals_candidate", "suggested_cpk"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sold_observation_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    suggested_cpk: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_cpks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
