from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerProblem(Base):
    """Customer-originated aftercare case, scoped to one order or build."""

    __tablename__ = "customer_problems"
    __table_args__ = (
        CheckConstraint(
            "(order_id IS NOT NULL AND manual_build_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL)",
            name="ck_customer_problem_one_source",
        ),
        UniqueConstraint("repair_tracking_provider_reference", name="uq_customer_problem_repair_provider_reference"),
        CheckConstraint(
            "(repair_tracking_provider IS NULL AND repair_tracking_provider_reference IS NULL) OR "
            "(repair_tracking_provider = 'parcel2go' AND repair_tracking_provider_reference IS NOT NULL)",
            name="ck_customer_problem_repair_tracking_provider_reference",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    manual_build_id: Mapped[int | None] = mapped_column(ForeignKey("manual_builds.id"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    portal_grant_id: Mapped[int | None] = mapped_column(ForeignKey("portal_access_grants.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="received")
    evidence_files: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True, default=list)
    repair_tracking: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    repair_tracking_audit: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True, default=list)
    repair_tracking_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    repair_tracking_provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def evidence(self) -> list[dict]:
        """Customer/admin-safe evidence metadata; never expose storage paths."""
        return [
            {
                key: item.get(key)
                for key in ("id", "filename", "content_type", "size_bytes", "sha256", "uploaded_at")
                if item.get(key) is not None
            }
            for item in (self.evidence_files or [])
            if isinstance(item, dict)
        ]
