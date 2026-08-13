"""
Admin endpoints for the component 3D asset registry (Meshy pipeline).

Lifecycle: MISSING → MESHY_DRAFT → CLEANED → VALIDATED → FINAL (or REJECTED).
Only VALIDATED/FINAL rows with is_active=True are ever served publicly
(see public_configurator.py).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.component_3d_asset import (
    AssetSubjectType,
    Component3DAsset,
    Component3DAssetStatus,
)
from app.routes.admin_auth import get_current_admin
from pydantic import ValidationError as PydanticValidationError
from app.schemas.case_mount import validate_case_mount_manifest

router = APIRouter(prefix="/assets-3d", tags=["assets-3d"], dependencies=[Depends(get_current_admin)])


def _serialize(a: Component3DAsset) -> dict:
    return {
        "id": a.id,
        "subject_type": a.subject_type.value,
        "subject_id": a.subject_id,
        "category": a.category,
        "status": a.status.value,
        "version": a.version,
        "is_active": a.is_active,
        "glb_ref": a.glb_ref,
        "preview_image_ref": a.preview_image_ref,
        "source_image_refs": a.source_image_refs,
        "poly_count": a.poly_count,
        "file_size_kb": a.file_size_kb,
        "dimensions_mm": a.dimensions_mm,
        "scale_validated": a.scale_validated,
        "anchor_manifest_json": a.anchor_manifest_json,
        "notes": a.notes,
        "created_by": a.created_by,
        "provenance_status": a.provenance_status,
        "source_name": a.source_name,
        "source_url": a.source_url,
        "licence": a.licence,
        "licence_url": a.licence_url,
        "commercial_use_approved": a.commercial_use_approved,
        "redistribution_approved": a.redistribution_approved,
        "attribution": a.attribution,
        "provenance_reviewed_at": a.provenance_reviewed_at.isoformat() if a.provenance_reviewed_at else None,
        "provenance_reviewed_by": a.provenance_reviewed_by,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.get("")
async def list_assets(
    subject_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Component3DAsset).order_by(
        Component3DAsset.subject_type,
        Component3DAsset.subject_id,
        Component3DAsset.version.desc(),
    )
    if subject_type:
        try:
            q = q.where(Component3DAsset.subject_type == AssetSubjectType(subject_type))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown subject_type '{subject_type}'")
    if status:
        try:
            q = q.where(Component3DAsset.status == Component3DAssetStatus(status))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown status '{status}'")
    rows = (await db.execute(q)).scalars().all()
    return [_serialize(a) for a in rows]


class AssetCreate(BaseModel):
    subject_type: str = Field(pattern="^(case|variant|category_generic)$")
    subject_id: int | None = None
    category: str | None = None
    status: str = "meshy_draft"
    glb_ref: str | None = None
    preview_image_ref: str | None = None
    source_image_refs: list[str] = Field(default_factory=list)
    poly_count: int | None = None
    file_size_kb: int | None = None
    dimensions_mm: dict | None = None
    anchor_manifest_json: dict | None = None
    notes: str | None = None
    created_by: str | None = None


@router.post("")
async def create_asset(body: AssetCreate, db: AsyncSession = Depends(get_db)):
    stype = AssetSubjectType(body.subject_type)
    if stype == AssetSubjectType.CATEGORY_GENERIC and not body.category:
        raise HTTPException(status_code=422, detail="category_generic assets require category")
    if stype != AssetSubjectType.CATEGORY_GENERIC and body.subject_id is None:
        raise HTTPException(status_code=422, detail="case/variant assets require subject_id")

    if stype == AssetSubjectType.CASE and body.anchor_manifest_json is not None:
        try:
            validate_case_mount_manifest(body.anchor_manifest_json)
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid case mount manifest: {exc}")

    try:
        status = Component3DAssetStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown status '{body.status}'")

    # Next version for this subject
    prior = (
        await db.execute(
            select(Component3DAsset.version)
            .where(
                Component3DAsset.subject_type == stype,
                Component3DAsset.subject_id == body.subject_id,
                Component3DAsset.category == body.category,
            )
            .order_by(Component3DAsset.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    asset = Component3DAsset(
        subject_type=stype,
        subject_id=body.subject_id,
        category=body.category,
        status=status,
        version=(prior or 0) + 1,
        glb_ref=body.glb_ref,
        preview_image_ref=body.preview_image_ref,
        source_image_refs=body.source_image_refs,
        poly_count=body.poly_count,
        file_size_kb=body.file_size_kb,
        dimensions_mm=body.dimensions_mm,
        anchor_manifest_json=body.anchor_manifest_json,
        notes=body.notes,
        created_by=body.created_by,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)


class AssetPatch(BaseModel):
    status: str | None = None
    glb_ref: str | None = None
    preview_image_ref: str | None = None
    poly_count: int | None = None
    file_size_kb: int | None = None
    dimensions_mm: dict | None = None
    scale_validated: bool | None = None
    anchor_manifest_json: dict | None = None
    notes: str | None = None
    provenance_status: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    licence: str | None = None
    licence_url: str | None = None
    commercial_use_approved: bool | None = None
    redistribution_approved: bool | None = None
    attribution: str | None = None


_PROVENANCE_GATED_STATUSES = (Component3DAssetStatus.VALIDATED, Component3DAssetStatus.FINAL)


@router.patch("/{asset_id}")
async def patch_asset(asset_id: int, body: AssetPatch, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    asset = (
        await db.execute(select(Component3DAsset).where(Component3DAsset.id == asset_id))
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if (
        asset.subject_type == AssetSubjectType.CASE
        and body.anchor_manifest_json is not None
    ):
        try:
            validate_case_mount_manifest(body.anchor_manifest_json)
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid case mount manifest: {exc}")

    for field in (
        "glb_ref", "preview_image_ref", "poly_count", "file_size_kb",
        "dimensions_mm", "scale_validated", "anchor_manifest_json", "notes",
        "provenance_status", "source_name", "source_url", "licence", "licence_url",
        "commercial_use_approved", "redistribution_approved", "attribution",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(asset, field, value)

    if body.status is not None:
        try:
            new_status = Component3DAssetStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown status '{body.status}'")

        # Provenance gate (flipflop-3d-builder-claude-prd.md §11): a publicly
        # downloadable CAD/model file is NOT automatically permission to
        # redistribute a converted web asset — VALIDATED/FINAL requires both
        # flags explicitly approved, not just a source_url being present.
        if new_status in _PROVENANCE_GATED_STATUSES:
            if not (asset.commercial_use_approved and asset.redistribution_approved):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Cannot promote to {new_status.value}: commercial_use_approved and "
                        "redistribution_approved must both be true first. If this is an original "
                        "recreation (no external source), set both flags true with source_name "
                        "explaining it's an in-house/original asset, not an external one."
                    ),
                )
        asset.status = new_status
        if new_status in _PROVENANCE_GATED_STATUSES and asset.provenance_reviewed_at is None:
            asset.provenance_reviewed_at = datetime.utcnow()
            asset.provenance_reviewed_by = getattr(admin, "email", None)

    asset.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)


@router.post("/{asset_id}/activate")
async def activate_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Make this version the served one for its subject. Requires
    VALIDATED or FINAL status; deactivates sibling versions atomically."""
    asset = (
        await db.execute(select(Component3DAsset).where(Component3DAsset.id == asset_id))
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.status not in (Component3DAssetStatus.VALIDATED, Component3DAssetStatus.FINAL):
        raise HTTPException(
            status_code=409,
            detail=f"Only validated/final assets can be activated (current: {asset.status.value})",
        )
    if not asset.glb_ref:
        raise HTTPException(status_code=409, detail="Asset has no glb_ref to serve")

    await db.execute(
        update(Component3DAsset)
        .where(
            Component3DAsset.subject_type == asset.subject_type,
            Component3DAsset.subject_id == asset.subject_id,
            Component3DAsset.category == asset.category,
        )
        .values(is_active=False)
    )
    asset.is_active = True
    asset.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)
