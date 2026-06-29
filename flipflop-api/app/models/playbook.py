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
    target_budget = Column(Float, nullable=False)
    target_use_case = Column(String, nullable=True)

    specs = Column(JSON, nullable=False)

    historical_demand_pct = Column(Float, default=0.0)
    historical_margin_avg = Column(Float, default=0.0)
    avg_days_to_sell = Column(Float, default=0.0)

    market_selling_price = Column(Float, nullable=True)
    used_market_price = Column(Float, nullable=True)

    status = Column(Enum(PlaybookStatus), default=PlaybookStatus.ACTIVE)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="playbook")
