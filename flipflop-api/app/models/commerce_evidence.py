"""Append-only supplier evidence and commercial quote assessments."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SupplierOfferEvidence(Base):
    __tablename__ = "supplier_offer_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    supplier: Mapped[str] = mapped_column(String(160), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    item_gbp: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    delivery_gbp: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fees_gbp: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    risk_gbp: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stock_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_working_days: Mapped[int | None] = mapped_column(Integer)
    supplier_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    captured_by_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class PriceQuoteSnapshot(Base):
    __tablename__ = "price_quote_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    decision_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class WorkshopCapacityEvidence(Base):
    __tablename__ = "workshop_capacity_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    build_week: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    available_builds: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    captured_by_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
