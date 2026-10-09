"""Customer-owned PC assessment and explicit scope approval."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.database import Base


class UpgradeAssessment(Base):
    __tablename__ = "upgrade_assessments"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    submitted_spec = Column(JSON, nullable=False)
    desired_outcome = Column(Text, nullable=False)
    budget_gbp = Column(Integer, nullable=False)
    photo_urls = Column(JSON, nullable=False, default=list)
    system_report_url = Column(String(1000), nullable=True)
    status = Column(String(32), nullable=False, default="submitted")
    advice = Column(JSON, nullable=True)
    scope_revision = Column(Integer, nullable=False, default=0)
    approval_required = Column(Boolean, nullable=False, default=False)
    approved_revision = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
