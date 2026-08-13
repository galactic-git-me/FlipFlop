from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Float, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MotherboardSpec(Base):
    """Structured reference row for one motherboard model — the compatibility
    engine's honest alternative to guessing socket/RAM limits from listing
    title text. Rows start unreviewed when AI-generated; only a human-reviewed
    row (reviewed=True) should ever produce a HARD_INCOMPATIBLE verdict —
    unreviewed AI data can still enrich soft NOT_RECOMMENDED signals, per the
    same "unknown/unconfirmed = never a silent hard block" principle used
    throughout configurator_compatibility.py."""

    __tablename__ = "motherboard_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_model: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    socket: Mapped[Optional[str]] = mapped_column(String(30))
    chipset: Mapped[Optional[str]] = mapped_column(String(50))
    ram_type: Mapped[Optional[str]] = mapped_column(String(10))
    # ddr4 | ddr5
    ram_slots: Mapped[Optional[int]] = mapped_column(Integer)
    max_ram_gb: Mapped[Optional[int]] = mapped_column(Integer)
    pcie_x16_slots: Mapped[Optional[int]] = mapped_column(Integer)
    m2_slots: Mapped[Optional[int]] = mapped_column(Integer)
    sata_ports: Mapped[Optional[int]] = mapped_column(Integer)
    form_factor: Mapped[Optional[str]] = mapped_column(String(10))
    # atx | matx | itx
    wifi: Mapped[Optional[bool]] = mapped_column(Boolean)

    source: Mapped[str] = mapped_column(String(20), default="manual")
    # manual | ai_generated
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float)
    ai_reasoning: Mapped[Optional[str]] = mapped_column(String(500))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100))

    # Raw model fields as a JSON blob too, so an admin can see exactly what the
    # AI returned even if a later manual edit changes individual columns above.
    raw_ai_response: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.utcnow().isoformat(), onupdate=lambda: datetime.utcnow().isoformat()
    )
