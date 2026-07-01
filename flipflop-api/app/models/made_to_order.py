from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum
from datetime import datetime
from app.database import Base
import enum


class QueuePriority(enum.Enum):
    STANDARD = "standard"
    FAST_TRACK = "fast_track"


class MadeToOrderQueue(Base):
    """Made-to-Order build queue entry. PRD Ch.6.8, Ch.10.4."""
    __tablename__ = "made_to_order_queue"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    build_id = Column(Integer, ForeignKey("builds.id"), nullable=True)
    priority = Column(Enum(QueuePriority), default=QueuePriority.STANDARD, nullable=False)

    queued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    planning_started_at = Column(DateTime, nullable=True)
