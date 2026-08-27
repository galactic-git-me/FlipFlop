from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum, JSON, Index,
)
from datetime import datetime
from app.database import Base
import enum


class AssetSubjectType(enum.Enum):
    """What a 3D asset represents.

    CASE              — a CaseCatalogue row (subject_id = case_catalogue.id)
    VARIANT           — a CatalogueVariant row (subject_id = catalogue_variants.id)
    CATEGORY_GENERIC  — honest placeholder for a whole slot category
                        (subject_id NULL, category set, e.g. "gpu")
    """
    CASE = "case"
    VARIANT = "variant"
    CATEGORY_GENERIC = "category_generic"


class Component3DAssetStatus(enum.Enum):
    """Meshy asset lifecycle. Distinct from Capture3DStatus (per-order build
    twins); this registry is for the modular configurator library."""
    MISSING = "missing"            # subject known, no asset work started
    MESHY_DRAFT = "meshy_draft"    # raw Meshy generation from source photos
    CLEANED = "cleaned"            # retopo/texture fixes, compressed
    VALIDATED = "validated"        # scale/orientation/pivot/poly budget checked
    FINAL = "final"                # published, immutable — new work = new version
    REJECTED = "rejected"          # unusable generation, kept for audit


class Component3DAsset(Base):
    """Versioned registry of configurator 3D assets (GLB), one row per
    (subject, version). The row with is_active=True is the one served to the
    storefront; prior versions are retained. Cases additionally carry an
    anchor manifest used to place component assets at runtime."""
    __tablename__ = "component_3d_assets"
    __table_args__ = (
        Index("ix_c3da_subject", "subject_type", "subject_id"),
        Index("ix_c3da_active", "subject_type", "subject_id", "is_active"),
    )

    id = Column(Integer, primary_key=True)
    subject_type = Column(Enum(AssetSubjectType), nullable=False)
    subject_id = Column(Integer, nullable=True)  # NULL for CATEGORY_GENERIC
    category = Column(String(30), nullable=True)  # slot category for generics (gpu, cooling, ram…)
    # Bucket within a category, e.g. "gpu_large_triple_fan", "mobo_asus_atx" —
    # NULL means "plain whole-category generic" (the original, coarser
    # fallback level). See app/services/component_family_classifier.py for the
    # taxonomy and how a variant's listing title maps to a bucket.
    family_key = Column(String(60), nullable=True)

    status = Column(
        Enum(Component3DAssetStatus),
        default=Component3DAssetStatus.MISSING,
        nullable=False,
    )
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)

    glb_ref = Column(String(1000), nullable=True)            # served GLB path/URL
    preview_image_ref = Column(String(1000), nullable=True)  # poster/thumbnail
    source_image_refs = Column(JSON, default=list)           # stock photos fed to Meshy

    poly_count = Column(Integer, nullable=True)
    file_size_kb = Column(Integer, nullable=True)
    dimensions_mm = Column(JSON, nullable=True)     # {"w":..,"h":..,"d":..} from spec sheet
    scale_validated = Column(Boolean, default=False, nullable=False)
    anchor_manifest_json = Column(JSON, nullable=True)  # cases/motherboards only

    notes = Column(String(2000), nullable=True)
    created_by = Column(String(100), nullable=True)

    # Owner review is deliberately batched. Candidates are assigned to a
    # ten-item review batch and cannot become active storefront assets until
    # every item in that batch has an explicit decision.
    review_batch_id = Column(String(36), nullable=True, index=True)
    review_decision = Column(String(20), nullable=True)  # approved | rejected
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)

    # Provenance — see flipflop-3d-builder-claude-prd.md §5/§11. A row must
    # never be promoted to VALIDATED/FINAL without commercial_use_approved
    # AND redistribution_approved both true; a publicly downloadable CAD/model
    # file is NOT automatically permission to redistribute a converted web
    # asset, so these two flags are recorded independently of source_url
    # existing at all. Enforced in code (services/component_3d_asset_service
    # promotion path), not just documented here — see PROVENANCE_STATUSES.
    provenance_status = Column(
        String(30), nullable=False, default="metadata-only",
    )  # exact-approved | original-recreation | dimensionally-accurate-proxy | metadata-only
    source_name = Column(String(200), nullable=True)
    source_url = Column(String(1000), nullable=True)
    licence = Column(String(200), nullable=True)
    licence_url = Column(String(1000), nullable=True)
    commercial_use_approved = Column(Boolean, default=False, nullable=False)
    redistribution_approved = Column(Boolean, default=False, nullable=False)
    attribution = Column(String(500), nullable=True)
    provenance_reviewed_at = Column(DateTime, nullable=True)
    provenance_reviewed_by = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


PROVENANCE_STATUSES = (
    "exact-approved",
    "original-recreation",
    "dimensionally-accurate-proxy",
    "metadata-only",
)
