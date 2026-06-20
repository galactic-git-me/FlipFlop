from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Float, Integer, String, Text, JSON,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PlaybookSlot(Base):
    __tablename__ = "playbook_slots"
    __table_args__ = (
        UniqueConstraint("playbook_id", "slot_type", name="uq_playbook_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    playbook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # cpu | gpu | ram | storage | cooling | os
    is_customer_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    tier_names: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"budget": "Budget", "mid": "Mid-Range", "high": "High End"}
    )
    score_band_budget: Mapped[list] = mapped_column(JSON, default=lambda: [40, 65])
    score_band_mid: Mapped[list] = mapped_column(JSON, default=lambda: [65, 80])
    score_band_high: Mapped[list] = mapped_column(JSON, default=lambda: [80, 100])
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )


class CatalogueVariant(Base):
    __tablename__ = "catalogue_variants"
    __table_args__ = (
        Index("ix_catalogue_variants_slot_status", "slot_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("playbook_slots.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True)
    # pending_review | active | hidden | rejected
    display_price: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    # budget | mid | high
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    auto_published_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    reviewed_at: Mapped[Optional[str]] = mapped_column(String(50))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))
    reject_reason: Mapped[Optional[str]] = mapped_column(String(200))
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )


class CaseCatalogue(Base):
    __tablename__ = "case_catalogue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    form_factor: Mapped[str] = mapped_column(String(10), nullable=False)
    # atx | matx | itx
    images: Mapped[list] = mapped_column(JSON, default=list)
    rrp_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    is_transparent_panel: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)
    # active | hidden
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat()
    )
