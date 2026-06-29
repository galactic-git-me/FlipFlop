from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class OrderChecklist(Base):
    """
    Tracks checklist items for each order (build steps and QA tests).
    Section can be 'build' or 'qa'.
    """
    __tablename__ = "order_checklists"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    section = Column(String(20), nullable=False, index=True)  # 'build' or 'qa'
    item = Column(String(255), nullable=False)  # e.g., "CPU installed", "Boot test"
    completed = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite index for efficient queries by order + section
    __table_args__ = (
        {"sqlite_autoincrement": False},  # Not needed for PostgreSQL but doesn't hurt
    )
