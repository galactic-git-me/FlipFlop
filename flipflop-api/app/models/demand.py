from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from datetime import datetime
from app.database import Base


class DemandEvent(Base):
    __tablename__ = "demand_events"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, index=True, nullable=False)

    budget_chosen = Column(String, nullable=False)
    use_case = Column(String, nullable=True)
    specs = Column(JSON, nullable=False)

    quote_generated = Column(Boolean, default=False)
    converted_to_order = Column(Boolean, default=False)

    time_spent_minutes = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
