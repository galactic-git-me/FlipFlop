from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WarrantyReserve(Base):
    """Ring-fenced warranty provision for one delivered sale.

    The ledger records eligibility separately from release so an elapsed
    warranty never moves money without an operator decision.
    """

    __tablename__ = "warranty_reserves"
    __table_args__ = (
        CheckConstraint(
            "(order_id IS NOT NULL AND manual_build_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL)",
            name="ck_warranty_reserve_one_sale_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    manual_build_id: Mapped[int | None] = mapped_column(ForeignKey("manual_builds.id"), unique=True, index=True)
    sale_value_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    reserve_pct: Mapped[float] = mapped_column(Float, nullable=False)
    reserved_amount_gbp: Mapped[float] = mapped_column(Float, nullable=False)
    allocated_claim_amount_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    released_amount_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="held", index=True)
    warranty_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    warranty_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    eligible_at: Mapped[datetime | None] = mapped_column(DateTime)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    released_by: Mapped[str | None] = mapped_column(String(320))
    release_note: Mapped[str | None] = mapped_column(Text)
    expiry_alerted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class WarrantyClaim(Base):
    """One warranty case and its approved draw against a reserve."""

    __tablename__ = "warranty_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserve_id: Mapped[int] = mapped_column(ForeignKey("warranty_reserves.id"), nullable=False, index=True)
    customer_problem_id: Mapped[int | None] = mapped_column(ForeignKey("customer_problems.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    issue_summary: Mapped[str] = mapped_column(Text, nullable=False)
    approved_cost_gbp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    outcome: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
