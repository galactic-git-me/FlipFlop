from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class DraftBuild(Base):
    """A saved, unfinished playbook build a customer can resume later.

    config_json shape: {"slot_selections": {slot_id: variant_id, ...},
    "case_id": int|None, "chosen_week": str|None} — mirrors
    PlaybookBuildConfig (app/schemas/payment.py) and is re-priced live from
    the catalogue on every read rather than storing a stale total.
    """

    __tablename__ = "draft_builds"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id"), nullable=False)
    name = Column(String, nullable=True)
    config_json = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer")
    playbook = relationship("Playbook")
