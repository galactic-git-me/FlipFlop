from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Enum, ForeignKey, JSON
from datetime import datetime
from app.database import Base
import enum


class USBTemplate(Base):
    """CXP PRD Ch.7.12."""
    __tablename__ = "usb_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    linked_playbook_id = Column(Integer, ForeignKey("playbooks.id"), nullable=True)
    content_categories = Column(JSON, nullable=True)
    static_file_refs = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class USBManifestStatus(enum.Enum):
    PENDING = "pending"
    BUILT = "built"
    VALIDATED = "validated"
    WRITTEN_TO_MEDIA = "written_to_media"
    FAILED = "failed"
    DIGITAL_FALLBACK = "digital_fallback"


class USBManifest(Base):
    """CXP PRD Ch.7.11, Ch.19."""
    __tablename__ = "usb_manifests"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    template_id = Column(Integer, ForeignKey("usb_templates.id"), nullable=True)
    status = Column(Enum(USBManifestStatus), default=USBManifestStatus.PENDING, nullable=False)

    total_size_bytes = Column(BigInteger, default=0)
    capacity_bytes = Column(BigInteger, nullable=True)
    file_manifest_json = Column(JSON, nullable=True)

    built_at = Column(DateTime, nullable=True)
    written_at = Column(DateTime, nullable=True)
    written_by = Column(Integer, ForeignKey("customers.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
