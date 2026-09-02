from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class PhotoTypeEnum(enum.Enum):
    ASSEMBLY = "assembly"
    COMPLETION = "completion"
    PACKAGING = "packaging"
    FINAL_BOXED = "final_boxed"


class OrderPhoto(Base):
    """
    Stores photo URLs for each build stage (optional documentation photos).
    Stage examples: 'parts_received', 'cpu', 'gpu', 'ram', 'ssd', 'cooling', 'cables', 'test'

    Extended per CXP PRD Ch.7.13: requirement_id/photo_type/is_hero_shot support the
    mandatory Photography Workflow gate (Ch.20); `stage` is retained for backward-compat
    display.
    """
    __tablename__ = "order_photos"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    stage = Column(String(50), nullable=False)  # Build stage this photo documents
    photo_url = Column(String(500), nullable=False)  # URL to stored image
    notes = Column(String(255), nullable=True)

    requirement_id = Column(Integer, ForeignKey("photo_requirements.id"), nullable=True)
    photo_type = Column(Enum(PhotoTypeEnum), nullable=True)
    captured_by = Column(Integer, ForeignKey("customers.id"), nullable=True)
    is_hero_shot = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
