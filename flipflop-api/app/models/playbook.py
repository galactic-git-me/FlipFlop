from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class PlaybookStatus(enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class Playbook(Base):
    __tablename__ = "playbooks"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    emoji = Column(String, nullable=True)
    target_budget = Column(Float, nullable=True)
    target_use_case = Column(String, nullable=True)
    target_customer = Column(String, nullable=True)

    specs = Column(JSON, nullable=True)

    historical_demand_pct = Column(Float, default=0.0)
    historical_margin_avg = Column(Float, default=0.0)
    avg_days_to_sell = Column(Float, default=0.0)

    market_selling_price = Column(Float, nullable=True)
    used_market_price = Column(Float, nullable=True)

    status = Column(Enum(PlaybookStatus), default=PlaybookStatus.ACTIVE)

    activated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="playbook")


class PlaybookProposal(Base):
    __tablename__ = "playbook_proposals"

    id = Column(Integer, primary_key=True)
    playbook_id = Column(Integer, index=True, nullable=False)
    action = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    payload = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
