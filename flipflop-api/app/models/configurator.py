from sqlalchemy import Column, Integer, Boolean, ForeignKey, DateTime, Enum, JSON
from datetime import datetime
from app.database import Base
import enum


class ConfiguratorCatalogueVisibility(Base):
    """Admin curation of which CatalogueVariants are publicly selectable. PRD Ch.6.5."""
    __tablename__ = "configurator_catalogue_visibility"

    id = Column(Integer, primary_key=True)
    playbook_slot_id = Column(Integer, ForeignKey("playbook_slots.id"), nullable=False, index=True)
    catalogue_variant_id = Column(Integer, ForeignKey("catalogue_variants.id"), nullable=False, index=True)
    is_publicly_visible = Column(Boolean, default=False, nullable=False)
    display_order = Column(Integer, default=0)
    updated_by = Column(Integer, ForeignKey("customers.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompatibilityRuleType(enum.Enum):
    SOCKET_MATCH = "socket_match"
    FORM_FACTOR_FIT = "form_factor_fit"
    PSU_WATTAGE_MIN = "psu_wattage_min"
    CLEARANCE_MAX = "clearance_max"
    RAM_TYPE_MATCH = "ram_type_match"
    CUSTOM = "custom"


class CompatibilityRule(Base):
    """Data-driven configurator live-filtering rule. PRD Ch.6.6, Ch.12.4."""
    __tablename__ = "compatibility_rules"

    id = Column(Integer, primary_key=True)
    rule_type = Column(Enum(CompatibilityRuleType), nullable=False)
    subject_slot_id = Column(Integer, ForeignKey("playbook_slots.id"), nullable=False)
    constraint_json = Column(JSON, nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
