from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum
from app.database import Base
import enum


class PhotoType(enum.Enum):
    ASSEMBLY = "assembly"
    COMPLETION = "completion"
    PACKAGING = "packaging"
    FINAL_BOXED = "final_boxed"


class PhotoRequirement(Base):
    """Mandatory/optional photo checklist definitions. CXP PRD Ch.7.14, Ch.20."""
    __tablename__ = "photo_requirements"

    id = Column(Integer, primary_key=True)
    packaging_playbook_id = Column(Integer, ForeignKey("packaging_playbooks.id"), nullable=True)
    photo_type = Column(Enum(PhotoType), nullable=False)
    label = Column(String, nullable=False)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True, nullable=False)
