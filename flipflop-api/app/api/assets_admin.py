"""
Admin endpoints for the component 3D asset registry (Meshy pipeline).

Lifecycle: MISSING → MESHY_DRAFT → CLEANED → VALIDATED → FINAL (or REJECTED).
Only VALIDATED/FINAL rows with is_active=True are ever served publicly
(see public_configurator.py).
"""
from datetime import datetime
import json
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.case import Case
from app.models.component_3d_asset import (
    AssetSubjectType,
    Component3DAsset,
    Component3DAssetStatus,
)
from app.routes.admin_auth import get_current_admin
from pydantic import ValidationError as PydanticValidationError
from app.schemas.case_mount import validate_case_mount_manifest
from app.services.component_family_classifier import KNOWN_FAMILY_BUCKETS
from app.services.media_sync import sync_to_public_media
from app.services.meshy_generation import build_prompt, generate_multi_image_asset

router = APIRouter(prefix="/assets-3d", tags=["assets-3d"], dependencies=[Depends(get_current_admin)])
public_router = APIRouter(prefix="/assets-3d", tags=["assets-3d"])

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
_REFERENCE_ROOT = _WORKSPACE_ROOT / "assets" / "3d-reference-images" / "catalogue"
_PUBLIC_MEDIA_ROOT = _WORKSPACE_ROOT.parent / "FlipFlop.shop" / "public" / "media"
_PUBLIC_MEDIA_URL = "https://theflipflop.shop/media"
_REFERENCE_ALIASES = {
    "cpu_amd": "cpu_amd_am4_am5",
    "cpu_intel": "cpu_intel_lga1700",
    # GPU generation is intentionally split by brand. The current photo
    # library is shape-based, so use the closest available geometry set until
    # dedicated AMD and Intel reference photography is curated.
    "gpu_nvidia": "gpu_mid_dual_fan",
    "gpu_amd": "gpu_large_triple_fan",
    "gpu_intel": "gpu_compact_dual_fan",
}


def _reference_family(category: str, family_key: str) -> dict | None:
    manifest_path = _REFERENCE_ROOT / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reference_key = _REFERENCE_ALIASES.get(family_key, family_key)
    return next(
        (family for family in manifest["families"] if family["category"] == category and family["key"] == reference_key),
        None,
    )


async def _publish_reference_images(category: str, family_key: str) -> tuple[list[str], dict]:
    family = _reference_family(category, family_key)
    if not family:
        raise HTTPException(status_code=409, detail=f"No approved photo set for {category}/{family_key}")
    source_dir = _REFERENCE_ROOT / family["directory"]
    images = sorted(path for path in source_dir.iterdir() if path.is_file())[:4]
    if not images:
        raise HTTPException(status_code=409, detail=f"Photo set is empty for {category}/{family_key}")

    _PUBLIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    urls: list[str] = []
    for index, source in enumerate(images, start=1):
        filename = f"catalogue-3d-ref-{family_key}-{index}{source.suffix.lower()}"
        public_path = _PUBLIC_MEDIA_ROOT / filename
        shutil.copy2(source, public_path)
        if not await sync_to_public_media(public_path):
            raise HTTPException(status_code=502, detail=f"Could not publish reference image {source.name}")
        urls.append(f"{_PUBLIC_MEDIA_URL}/{filename}")
    return urls, family


async def _store_generated_glb(family_key: str, version: int, source_url: str) -> tuple[str, int]:
    filename = f"catalogue-3d-{family_key}-v{version}.glb"
    public_path = _PUBLIC_MEDIA_ROOT / filename
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not download generated GLB: {exc}") from exc
    public_path.write_bytes(response.content)
    if not await sync_to_public_media(public_path):
        raise HTTPException(status_code=502, detail="Generated GLB could not be published")
    return f"{_PUBLIC_MEDIA_URL}/{filename}", max(1, len(response.content) // 1024)


def _serialize(a: Component3DAsset) -> dict:
    return {
        "id": a.id,
        "subject_type": a.subject_type.value,
        "subject_id": a.subject_id,
        "category": a.category,
        "family_key": a.family_key,
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
    family_key: str | None = None
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
                Component3DAsset.family_key == body.family_key,
            )
            .order_by(Component3DAsset.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    asset = Component3DAsset(
        subject_type=stype,
        subject_id=body.subject_id,
        category=body.category,
        family_key=body.family_key,
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


# Public read-only endpoint (no auth required)
@public_router.get("/public")
async def list_assets_public(
    subject_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all 3D assets (public read-only, no auth required).

    Returns both component assets and PC case 3D models in a unified format.
    PC cases are transformed to match the Component3DAsset schema for compatibility.
    """
    results = []

    # Fetch component assets
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
    results.extend([_serialize(a) for a in rows])

    # Fetch PC cases with 3D models
    case_query = select(Case).where(Case.has_3d_model == True).order_by(Case.id)
    cases = (await db.execute(case_query)).scalars().all()

    # Transform cases to match Component3DAsset format
    for case in cases:
        results.append({
            "id": f"case_{case.id}",  # Prefix to avoid ID collisions
            "subject_type": "case",
            "subject_id": case.id,
            "category": "case",
            "family_key": None,
            "status": "validated",  # Cases with models are considered validated
            "version": 1,
            "is_active": True,
            "glb_ref": case.model_3d_url,
            "preview_image_ref": case.image_url,
            "source_image_refs": [case.image_url] if case.image_url else [],
            "poly_count": case.model_3d_polygons,
            "file_size_kb": case.model_3d_file_size // 1024 if case.model_3d_file_size else None,
            "dimensions_mm": None,
            "scale_validated": False,
            "anchor_manifest_json": None,
            "notes": f"PC Case: {case.name}",
            "created_by": "system",
            "provenance_status": case.model_3d_source or "unknown",
            "source_name": case.brand or case.name,
            "source_url": case.source_url,
            "licence": case.model_3d_license,
            "licence_url": None,
            "commercial_use_approved": True,
            "redistribution_approved": True,
            "attribution": case.model_3d_creator,
            "provenance_reviewed_at": None,
            "provenance_reviewed_by": None,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "rank": None,
        })

    return results


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


@router.get("/family-buckets")
async def list_family_buckets(db: AsyncSession = Depends(get_db)):
    """Every bucket in the family taxonomy (component_family_classifier.py),
    joined against whatever Component3DAsset row currently exists for it —
    the admin generation queue reads this to see what's missing vs done."""
    rows = (
        await db.execute(
            select(Component3DAsset).where(
                Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
                Component3DAsset.family_key.isnot(None),
            )
        )
    ).scalars().all()
    # Latest version per (category, family_key)
    latest_by_bucket: dict[tuple[str, str], Component3DAsset] = {}
    for row in rows:
        key = (row.category, row.family_key)
        if key not in latest_by_bucket or row.version > latest_by_bucket[key].version:
            latest_by_bucket[key] = row

    return [
        {
            "category": category,
            "family_key": family_key,
            "prompt": build_prompt(category, family_key),
            "asset": _serialize(latest_by_bucket[(category, family_key)])
            if (category, family_key) in latest_by_bucket
            else None,
        }
        for category, family_key in KNOWN_FAMILY_BUCKETS
    ]


@router.post("/family-buckets/{category}/{family_key}/generate")
async def generate_family_bucket_asset(
    category: str,
    family_key: str,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Kicks off a Meshy generation for one bucket and saves the result as a
    new MESHY_DRAFT version. Synchronous end-to-end (the request blocks until
    Meshy finishes, typically a few minutes) — acceptable for an admin-
    triggered, occasional, one-bucket-at-a-time action; not something a
    customer-facing endpoint would ever do."""
    if (category, family_key) not in KNOWN_FAMILY_BUCKETS:
        raise HTTPException(status_code=404, detail=f"Unknown bucket {category}/{family_key}")

    prompt = build_prompt(category, family_key)
    image_urls, reference_family = await _publish_reference_images(category, family_key)
    result = await generate_multi_image_asset(image_urls)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Meshy generation failed — check MESHY_API_KEY is set and try again",
        )
    if result.status != "SUCCEEDED" or not result.glb_url:
        raise HTTPException(status_code=502, detail=f"Meshy generation did not succeed (status: {result.status})")

    prior_version = (
        await db.execute(
            select(Component3DAsset.version)
            .where(
                Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
                Component3DAsset.category == category,
                Component3DAsset.family_key == family_key,
            )
            .order_by(Component3DAsset.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    version = (prior_version or 0) + 1
    stable_glb_url, file_size_kb = await _store_generated_glb(family_key, version, result.glb_url)

    asset = Component3DAsset(
        subject_type=AssetSubjectType.CATEGORY_GENERIC,
        subject_id=None,
        category=category,
        family_key=family_key,
        status=Component3DAssetStatus.MESHY_DRAFT,
        version=version,
        glb_ref=stable_glb_url,
        preview_image_ref=result.thumbnail_url,
        source_image_refs=image_urls,
        file_size_kb=file_size_kb,
        notes=f"Meshy multi-image task {result.task_id}; reference family: {reference_family['key']}",
        created_by=getattr(admin, "email", None),
        # Original AI-generated recreation from a generic text prompt — never
        # a copy of a specific product. Still starts unapproved: a human
        # reviews the actual output before it can be promoted (patch_asset's
        # provenance gate below still requires explicit approval either way).
        provenance_status="original-recreation",
        source_name=f"Meshy AI multi-image recreation (task {result.task_id})",
        source_url=reference_family.get("source_page"),
        commercial_use_approved=False,
        redistribution_approved=False,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)
