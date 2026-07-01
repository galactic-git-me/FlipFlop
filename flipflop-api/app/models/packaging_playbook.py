from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, Enum, ForeignKey
from datetime import datetime
from app.database import Base
import enum


class PackagingPlaybookStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class PackagingPlaybook(Base):
    """CXP PRD Ch.7.1. Every active Build Playbook references exactly one of these (BR-1)."""
    __tablename__ = "packaging_playbooks"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    status = Column(Enum(PackagingPlaybookStatus), default=PackagingPlaybookStatus.DRAFT, nullable=False)
    description = Column(Text, nullable=True)

    carton_spec = Column(JSON, nullable=True)
    protection_spec = Column(JSON, nullable=True)
    void_fill_spec = Column(JSON, nullable=True)
    security_spec = Column(JSON, nullable=True)
    label_spec = Column(JSON, nullable=True)
    documentation_pack = Column(JSON, nullable=True)
    captains_log_spec = Column(JSON, nullable=True)
    usb_content_spec = Column(JSON, nullable=True)
    welcome_gifts = Column(JSON, nullable=True)
    accessories = Column(JSON, nullable=True)
    premium_extras = Column(JSON, nullable=True)
    presentation_order = Column(JSON, nullable=True)
    unboxing_sequence = Column(JSON, nullable=True)

    estimated_cost = Column(Float, default=0.0)
    estimated_labour_minutes = Column(Float, default=15.0)

    created_by = Column(Integer, ForeignKey("customers.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PackagingPlaybookVersion(Base):
    """Append-only version snapshot. CXP PRD Ch.7.2."""
    __tablename__ = "packaging_playbook_versions"

    id = Column(Integer, primary_key=True)
    packaging_playbook_id = Column(Integer, ForeignKey("packaging_playbooks.id"), nullable=False, index=True)
    snapshot_json = Column(JSON, nullable=False)
    changed_by = Column(Integer, ForeignKey("customers.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    change_note = Column(Text, nullable=True)


class PackagingComponentCategory(enum.Enum):
    CARTON = "carton"
    PROTECTION = "protection"
    VOID_FILL = "void_fill"
    SECURITY = "security"
    LABEL = "label"
    GIFT = "gift"
    ACCESSORY = "accessory"
    PREMIUM_EXTRA = "premium_extra"


class PackagingPlaybookComponent(Base):
    """Normalized BOM rows derived from the JSON spec, for reporting joins. CXP PRD Ch.7.3."""
    __tablename__ = "packaging_playbook_components"

    id = Column(Integer, primary_key=True)
    packaging_playbook_id = Column(Integer, ForeignKey("packaging_playbooks.id"), nullable=False, index=True)
    category = Column(Enum(PackagingComponentCategory), nullable=False)
    procurement_product_id = Column(Integer, ForeignKey("procurement_products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_cost_snapshot = Column(Float, nullable=False)
