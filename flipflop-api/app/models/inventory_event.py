from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryEvent(Base):
    """Append-only physical stock audit trail."""

    __tablename__ = "inventory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inventory.id", ondelete="CASCADE"), index=True
    )
    manual_build_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("manual_builds.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
