from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerProblemShipment(Base):
    """One independently tracked parcel leg for a support or warranty case."""

    __tablename__ = "customer_problem_shipments"
    __table_args__ = (
        CheckConstraint("purpose IN ('customer_return', 'replacement')", name="ck_customer_problem_shipment_purpose"),
        CheckConstraint(
            "(provider IS NULL AND provider_reference IS NULL) OR "
            "(provider = 'parcel2go' AND provider_reference IS NOT NULL)",
            name="ck_customer_problem_shipment_provider_reference",
        ),
        UniqueConstraint("customer_problem_id", "purpose", name="uq_customer_problem_shipment_purpose"),
        UniqueConstraint("provider", "provider_reference", name="uq_customer_problem_shipment_provider_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_problem_id: Mapped[int] = mapped_column(
        ForeignKey("customer_problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    carrier: Mapped[str] = mapped_column(String(100), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(160), nullable=False)
    tracking_url: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
