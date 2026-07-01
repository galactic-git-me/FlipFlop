from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from datetime import datetime
from app.database import Base
import enum


class Capture3DStatus(enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    OPTIMIZING = "optimizing"
    OPTIMIZED = "optimized"
    PUBLISHED = "published"
    FAILED = "failed"


class Capture3DAsset(Base):
    """CXP PRD Ch.7.15, Ch.21. Wraps/orchestrates the existing 3D capture pipeline
    (MotherboardViewer3D et al.) — does not reimplement it."""
    __tablename__ = "capture_3d_assets"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    status = Column(Enum(Capture3DStatus), default=Capture3DStatus.PENDING, nullable=False)

    raw_asset_ref = Column(String, nullable=True)
    optimized_asset_ref = Column(String, nullable=True)
    preview_image_ref = Column(String, nullable=True)
    ar_ready = Column(Boolean, default=False)

    captured_at = Column(DateTime, nullable=True)
    optimized_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
