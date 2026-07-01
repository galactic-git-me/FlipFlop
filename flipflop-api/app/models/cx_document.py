from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, Enum, ForeignKey, JSON
from datetime import datetime
from app.database import Base
import enum


class CXDocumentType(enum.Enum):
    BUILD_CERTIFICATE = "build_certificate"
    CAPTAINS_LOG = "captains_log"
    BENCHMARK_REPORT = "benchmark_report"
    GETTING_STARTED_GUIDE = "getting_started_guide"
    UPGRADE_GUIDE = "upgrade_guide"
    WARRANTY_PACK = "warranty_pack"
    QR_CODE_CARD = "qr_code_card"
    WELCOME_LETTER = "welcome_letter"
    ACCESSORY_CHECKLIST = "accessory_checklist"
    USB_MANIFEST = "usb_manifest"


class CXDocumentTemplateStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class CXDocumentTemplate(Base):
    """CXP PRD Ch.7.10."""
    __tablename__ = "cx_document_templates"

    id = Column(Integer, primary_key=True)
    document_type = Column(Enum(CXDocumentType), nullable=False)
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    status = Column(Enum(CXDocumentTemplateStatus), default=CXDocumentTemplateStatus.DRAFT, nullable=False)
    layout_spec = Column(JSON, nullable=True)
    is_shipment_blocking = Column(Integer, default=0)  # bool-as-int for simple default seeding; BR-4

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CXDocumentStatus(enum.Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class CXDocumentGeneratedBy(enum.Enum):
    SYSTEM = "system"
    OPERATOR = "operator"


class CXDocument(Base):
    """One row per generated document instance. CXP PRD Ch.7.9."""
    __tablename__ = "cx_documents"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    document_type = Column(Enum(CXDocumentType), nullable=False)
    version = Column(Integer, default=1)
    status = Column(Enum(CXDocumentStatus), default=CXDocumentStatus.GENERATING, nullable=False)
    template_id = Column(Integer, ForeignKey("cx_document_templates.id"), nullable=True)

    pdf_blob = Column(LargeBinary, nullable=True)
    pdf_url = Column(String, nullable=True)
    content_json = Column(JSON, nullable=True)

    generated_at = Column(DateTime, nullable=True)
    generated_by = Column(Enum(CXDocumentGeneratedBy), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
