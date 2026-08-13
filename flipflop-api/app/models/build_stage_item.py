"""Build fulfillment checklists — per-build task tracking during BUILD stage.

Separate from OrderChecklist (order-scoped, fulfillment-specific) to avoid
contaminating the existing CXP order pipeline. BuildStageItem tracks admin
tasks: software installation, 3D model capture, photography, performance tests,
registration plate creation.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from app.database import Base
import enum


class BuildStageItemSection(enum.Enum):
    SOFTWARE = "software"
    MODEL_3D = "model_3d"
    PICTURES = "pictures"
    PERFORMANCE_TESTS = "performance_tests"
    REGISTRATION_PLATE = "registration_plate"


class BuildStageItem(Base):
    """Individual task in the BUILD stage checklist for a PreBuilt PC."""
    __tablename__ = "build_stage_items"

    id = Column(Integer, primary_key=True)
    build_id = Column(Integer, ForeignKey("builds.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(Enum(BuildStageItemSection), nullable=False, index=True)

    item = Column(String(255), nullable=False)  # e.g., "Install Windows 11 Pro"
    is_required = Column(Boolean, default=True)
    completed = Column(Boolean, default=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    file_url = Column(String(512), nullable=True)  # photos, 3D files, test results

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        status = "✓" if self.completed else "○"
        return f"<BuildStageItem {self.build_id}:{self.section.value} {status} {self.item}>"
