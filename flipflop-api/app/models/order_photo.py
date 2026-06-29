from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class OrderPhoto(Base):
    """
    Stores photo URLs for each build stage (optional documentation photos).
    Stage examples: 'parts_received', 'cpu', 'gpu', 'ram', 'ssd', 'cooling', 'cables', 'test'
    """
    __tablename__ = "order_photos"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    stage = Column(String(50), nullable=False)  # Build stage this photo documents
    photo_url = Column(String(500), nullable=False)  # URL to stored image
    notes = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Composite index for efficient queries by order + stage
    __table_args__ = (
        {"sqlite_autoincrement": False},
    )
