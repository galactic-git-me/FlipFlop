from sqlalchemy import Column, Integer, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class BuildType(enum.Enum):
    FLIP = "flip"
    MADE_TO_ORDER = "made_to_order"


class BuildStatus(enum.Enum):
    PLANNING = "planning"
    SOURCING = "sourcing"
    MANUFACTURING = "manufacturing"
    FINALISED = "finalised"
    CANCELLED = "cancelled"


class Build(Base):
    """
    Thin orchestration/routing record shared by flip-origin and Made-to-Order-origin
    physical units. Does not duplicate cost/component data already owned by Flip/Order —
    exists so the Finalise Build pipeline has one consistent trigger object regardless
    of origin. See docs/prd/flipflop-commerce-and-cxp-platform-prd.md Ch.6.1.
    """
    __tablename__ = "builds"

    id = Column(Integer, primary_key=True)
    build_type = Column(Enum(BuildType), nullable=False)
    flip_id = Column(Integer, ForeignKey("flips.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id"), nullable=True)

    spec_json = Column(JSON, nullable=True)
    status = Column(Enum(BuildStatus), default=BuildStatus.PLANNING, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="build", uselist=False)
