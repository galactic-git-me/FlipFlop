"""Replayable customer requirements and envelope decisions."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.database import Base


class RecommendationSession(Base):
    __tablename__ = "recommendation_sessions"

    id = Column(Integer, primary_key=True)
    rules_version = Column(String(20), nullable=False)
    requirements_json = Column(JSON, nullable=False)
    envelope_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
