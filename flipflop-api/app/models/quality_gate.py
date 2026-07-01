from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Enum, ForeignKey, UniqueConstraint
from datetime import datetime
from app.database import Base
import enum


class EvidenceRequirement(enum.Enum):
    NONE = "none"
    PHOTO = "photo"
    SIGNATURE = "signature"
    PHOTO_AND_SIGNATURE = "photo_and_signature"


class QualityGateCheck(Base):
    """Final QC check definitions. CXP PRD Ch.7.16, Ch.22."""
    __tablename__ = "quality_gate_checks"

    id = Column(Integer, primary_key=True)
    packaging_playbook_id = Column(Integer, ForeignKey("packaging_playbooks.id"), nullable=True)
    code = Column(String, unique=True, nullable=False)
    label = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    requires_evidence = Column(Enum(EvidenceRequirement), default=EvidenceRequirement.NONE, nullable=False)
    sort_order = Column(Integer, default=0)
    active = Column(Boolean, default=True, nullable=False)


class QualityGateResult(Base):
    """Per-order QC evidence/outcome. CXP PRD Ch.7.17."""
    __tablename__ = "quality_gate_results"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    check_id = Column(Integer, ForeignKey("quality_gate_checks.id"), nullable=False)
    passed = Column(Boolean, nullable=True)
    evidence_photo_url = Column(String, nullable=True)
    evidence_signature_ref = Column(String, nullable=True)
    performed_by = Column(Integer, ForeignKey("customers.id"), nullable=True)
    performed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("order_id", "check_id", name="uq_qc_result_order_check"),)
