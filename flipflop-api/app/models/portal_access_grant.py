from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortalAccessGrant(Base):
    """Single-use claim secret for one guest or indirect-channel build portal."""

    __tablename__ = "portal_access_grants"
    __table_args__ = (
        CheckConstraint(
            "(order_id IS NOT NULL AND manual_build_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL)",
            name="ck_portal_access_grant_one_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    manual_build_id: Mapped[int | None] = mapped_column(ForeignKey("manual_builds.id"), index=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    channel: Mapped[str] = mapped_column(String(60), nullable=False, default="direct_guest")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(320))
    leaflet_storage_key: Mapped[str | None] = mapped_column(String(500))
    email_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
