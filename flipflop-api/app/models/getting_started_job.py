from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GettingStartedJob(Base):
    """Durable preparation workflow for one sold build/order portal."""

    __tablename__ = "getting_started_jobs"
    __table_args__ = (
        CheckConstraint(
            "manual_build_id IS NOT NULL OR order_id IS NOT NULL",
            name="ck_getting_started_job_has_build_or_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int | None] = mapped_column(
        ForeignKey("manual_builds.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    playbook_id: Mapped[int | None] = mapped_column(ForeignKey("playbooks.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="ready_to_ship", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="awaiting_review", nullable=False)
    checklist: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    customer_software_selections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    purchased_ai_services: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_index: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    private_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
