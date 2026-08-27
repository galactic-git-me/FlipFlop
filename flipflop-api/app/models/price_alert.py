"""Price alert models for Phase 2 Price Alerts feature."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PriceAlert(Base):
    """User-defined price alert on a specific build.

    Enables: "Notify me when this build drops below £X"
    """
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("manual_builds.id"), index=True, nullable=True)
    owner_admin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("admin_users.id"), index=True, nullable=True)
    alert_type: Mapped[str] = mapped_column(String(20), default="build", index=True)
    component_key: Mapped[str | None] = mapped_column(String(255), index=True)
    component_slot: Mapped[str | None] = mapped_column(String(50), index=True)
    cpk: Mapped[str | None] = mapped_column(String(64), index=True)
    condition_cohort: Mapped[str | None] = mapped_column(String(20))
    monitoring_status: Mapped[str] = mapped_column(String(30), default="armed", index=True)
    market_reference_price_gbp: Mapped[int | None] = mapped_column(Integer)
    reference_basis: Mapped[str | None] = mapped_column(String(40))
    discount_threshold_pct: Mapped[float | None] = mapped_column(Float)
    user_email: Mapped[str] = mapped_column(String(255), index=True)
    # Stored in pennies (£79.99 → 7999 pennies) to avoid float rounding
    target_price_gbp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Alert is active until user dismisses or price reaches target
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # When alert triggered (price dropped below target)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Price at time of trigger (pennies)
    triggered_price_gbp: Mapped[int | None] = mapped_column(Integer)
    # Exact marketplace listing that caused a component alert to fire.
    triggered_listing_url: Mapped[str | None] = mapped_column(String(1000))
    reference_evidence_json: Mapped[dict | None] = mapped_column(JSON)
    triggered_evidence_json: Mapped[dict | None] = mapped_column(JSON)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PriceAlert {self.id} build={self.manual_build_id} target=£{self.target_price_gbp/100:.2f}>"


class PriceAlertEvent(Base):
    """Audit trail of price alert lifecycle events.

    Tracks: triggered, acknowledged, dismissed, re-armed.
    """
    __tablename__ = "price_alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_alerts.id"), index=True)
    # Event type: triggered, acknowledged, dismissed, re_armed
    event_type: Mapped[str] = mapped_column(String(50))
    # Price at time of event (pennies), if relevant
    price_gbp: Mapped[int | None] = mapped_column(Integer)
    # Human-readable notes (e.g., "User dismissed alert after reviewing current price")
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PriceAlertEvent {self.id} alert={self.alert_id} type={self.event_type}>"
