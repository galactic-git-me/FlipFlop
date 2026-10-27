from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShipmentTrackingEvent(Base):
    """Provider-neutral courier event retained for portal and email history."""

    __tablename__ = "shipment_tracking_events"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_shipment_event_provider_event_id"),
        CheckConstraint(
            "(order_id IS NOT NULL AND manual_build_id IS NULL AND customer_problem_id IS NULL AND customer_problem_shipment_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL AND customer_problem_id IS NULL AND customer_problem_shipment_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NULL AND customer_problem_id IS NOT NULL AND customer_problem_shipment_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NULL AND customer_problem_id IS NULL AND customer_problem_shipment_id IS NOT NULL)",
            name="ck_shipment_event_one_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    manual_build_id: Mapped[int | None] = mapped_column(ForeignKey("manual_builds.id"), index=True)
    customer_problem_id: Mapped[int | None] = mapped_column(ForeignKey("customer_problems.id"), index=True)
    customer_problem_shipment_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_problem_shipments.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(200), index=True)
    status_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    tracking_url: Mapped[str | None] = mapped_column(String(1000))
    live_map_url: Mapped[str | None] = mapped_column(String(1000))
    material: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    customer_notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    customer_notification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customer_notification_attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
