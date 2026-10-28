"""
Admin endpoints for the component 3D asset registry (Meshy pipeline).

Lifecycle: MISSING → MESHY_DRAFT → CLEANED → VALIDATED → FINAL (or REJECTED).
Only VALIDATED/FINAL rows with is_active=True are ever served publicly
(see public_configurator.py).
"""
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.config import get_settings
from app.models.case import Case
from app.models.component_3d_asset import (
    AssetSubjectType,
    Component3DAsset,
    Component3DAssetStatus,
)
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.catalogue_marketing_copy import CatalogueMarketingCopy
from app.models.listing import Listing
from app.routes.admin_auth import get_current_admin
from pydantic import ValidationError as PydanticValidationError
from app.schemas.case_mount import validate_case_mount_manifest
from app.schemas.fan_layout import FanLayout
from app.services.component_family_classifier import KNOWN_FAMILY_BUCKETS
from app.services.media_sync import sync_to_public_media
from app.services.glb_optimizer import GlbOptimizationError, persist_optimized_glb
from app.services.meshy_generation import build_prompt, generate_multi_image_asset, poll_multi_image_asset
from app.services.curated_media_pipeline import MediaPipelineError, select_component_photo
from app.services.catalogue_photo_inventory import catalogue_generation_queue, catalogue_photo_inventory
from app.services.shared_variant_assets import component_slot_type, component_slot_types
from app.services.component_media_identity import media_members, media_key, media_family, media_asset_filter, group_media_inventory, family_label

router = APIRouter(prefix="/assets-3d", tags=["assets-3d"], dependencies=[Depends(get_current_admin)])
public_router = APIRouter(prefix="/assets-3d", tags=["assets-3d"])
logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
_REFERENCE_ROOT = _WORKSPACE_ROOT / "assets" / "3d-reference-images" / "catalogue"
_APP_ENV = get_settings().app_env.strip().lower()
_DEV_MEDIA_ROOT = _WORKSPACE_ROOT / "flipflop-api" / "data" / "3d-media"
_ORIGINAL_MEDIA_ROOT = (
    _DEV_MEDIA_ROOT.parent / "3d-media-originals"
    if _APP_ENV == "dev"
    else _WORKSPACE_ROOT / "data" / "3d-media-originals"
)
_PUBLIC_MEDIA_ROOT = (
    _DEV_MEDIA_ROOT
    if _APP_ENV == "dev"
    else _WORKSPACE_ROOT.parent / "FlipFlop.shop" / "public" / "media"
)
_PUBLIC_MEDIA_URL = (
    "http://127.0.0.1:4311/api/3d-media"
    if _APP_ENV == "dev"
    else "https://theflipflop.shop/media"
)
_MAX_GLB_UPLOAD_BYTES = 100 * 1024 * 1024
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


async def _sync_asset_media(path: Path) -> bool:
    """Keep DEV media local; production assets are mirrored to the shop host."""
    if _APP_ENV == "dev":
        return True
    return await sync_to_public_media(path)


def _validate_uploaded_glb(content: bytes) -> None:
    """Reject malformed binary glTF v2 containers before making them public."""
    if len(content) < 20 or content[:4] != b"glTF":
        raise ValueError("The selected file is not a valid binary GLB")
    version = int.from_bytes(content[4:8], byteorder="little")
    declared_length = int.from_bytes(content[8:12], byteorder="little")
    if version != 2:
        raise ValueError("Only GLB version 2 files are supported")
    if declared_length != len(content):
        raise ValueError("The GLB header size does not match the uploaded file")

    offset = 12
    chunk_index = 0
    while offset < declared_length:
        if offset + 8 > declared_length:
            raise ValueError("The GLB contains a truncated chunk header")
        chunk_length = int.from_bytes(content[offset:offset + 4], byteorder="little")
        chunk_type = int.from_bytes(content[offset + 4:offset + 8], byteorder="little")
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        if chunk_length % 4 or chunk_end > declared_length:
            raise ValueError("The GLB contains an invalid chunk length")
        if chunk_index == 0:
            if chunk_type != 0x4E4F534A:
                raise ValueError("The first GLB chunk must contain JSON")
            try:
                document = json.loads(content[chunk_start:chunk_end].decode("utf-8").rstrip(" "))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("The GLB JSON chunk is invalid") from exc
            if not isinstance(document, dict) or not isinstance(document.get("asset"), dict) or document["asset"].get("version") != "2.0":
                raise ValueError("The GLB JSON chunk is missing valid glTF 2.0 asset metadata")
        offset = chunk_end
        chunk_index += 1
    if offset != declared_length or chunk_index == 0:
        raise ValueError("The GLB chunks do not match the declared container size")


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
        if not await _sync_asset_media(public_path):
            raise HTTPException(status_code=502, detail=f"Could not publish reference image {source.name}")
        urls.append(f"{_PUBLIC_MEDIA_URL}/{filename}")
    return urls, family


async def _store_generated_glb(family_key: str, version: int, source_url: str) -> tuple[str, int]:
    filename = f"catalogue-3d-{family_key}-v{version}.glb"
    public_path = _PUBLIC_MEDIA_ROOT / filename
    public_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not download generated GLB: {exc}") from exc
    from app.services.glb_textures import require_embedded_colour_texture
    try:
        require_embedded_colour_texture(response.content)
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    try:
        optimized = await persist_optimized_glb(response.content, public_path, _ORIGINAL_MEDIA_ROOT)
        require_embedded_colour_texture(optimized.content)
    except (GlbOptimizationError, ValueError) as error:
        raise HTTPException(status_code=502, detail=f"Generated GLB could not be safely optimized: {error}") from error
    if not await _sync_asset_media(public_path):
        raise HTTPException(status_code=502, detail="Generated GLB could not be published")
    return f"{_PUBLIC_MEDIA_URL}/{filename}", max(1, optimized.output_bytes // 1024)


async def _store_generated_preview(family_key: str, version: int, source_url: str | None) -> str | None:
    """Persist Meshy's expiring thumbnail beside the durable generated GLB."""
    if not source_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(source_url)
            response.raise_for_status()
        if not response.headers.get("content-type", "").split(";", 1)[0].lower().startswith("image/"):
            logger.warning("catalogue_3d.preview_not_an_image", family_key=family_key, version=version)
            return None
        if not response.content or len(response.content) > 8 * 1024 * 1024:
            logger.warning("catalogue_3d.preview_invalid_size", family_key=family_key, version=version)
            return None
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type)
        if not extension:
            logger.warning("catalogue_3d.preview_unsupported_type", family_key=family_key, version=version, content_type=content_type)
            return None
        safe_key = re.sub(r"[^a-zA-Z0-9_-]+", "-", family_key).strip("-") or "component"
        filename = f"catalogue-3d-{safe_key}-v{version}-preview{extension}"
        public_path = _PUBLIC_MEDIA_ROOT / filename
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_bytes(response.content)
        if not await _sync_asset_media(public_path):
            public_path.unlink(missing_ok=True)
            logger.warning("catalogue_3d.preview_publish_failed", family_key=family_key, version=version)
            return None
        return f"{_PUBLIC_MEDIA_URL}/{filename}"
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("catalogue_3d.preview_download_failed", family_key=family_key, version=version, error=str(exc))
        return None


def _case_status_to_asset_status(case_status: str) -> str:
    """Map Case workflow status to Component3DAsset status."""
    status_map = {
        "pending": "meshy_draft",
        "sourcing": "meshy_draft",
        "ready_for_approval": "meshy_draft",
        "approved": "validated",
        "modeling": "validated",
        "completed": "final",
    }
    return status_map.get(case_status, "meshy_draft")


def _serialize(a: Component3DAsset, source_video_refs: list[dict] | None = None) -> dict:
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
        "source_video_refs": source_video_refs or [],
        "poly_count": a.poly_count,
        "file_size_kb": a.file_size_kb,
        "dimensions_mm": a.dimensions_mm,
        "scale_validated": a.scale_validated,
        "anchor_manifest_json": a.anchor_manifest_json,
        "fan_layout_json": a.fan_layout_json,
        "notes": a.notes,
        "created_by": a.created_by,
        "review_batch_id": a.review_batch_id,
        "review_decision": a.review_decision,
        "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        "reviewed_by": a.reviewed_by,
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


def _youtube_refs(evidence: dict | None) -> list[dict]:
    """Extract genuine YouTube results from the case sourcing evidence."""
    stage = ((evidence or {}).get("stages") or {}).get("youtube_video") or {}
    refs: list[dict] = []
    for attempt in stage.get("attempts") or []:
        url = attempt.get("source_url")
        if not isinstance(url, str) or not ("youtube.com/" in url or "youtu.be/" in url):
            continue
        refs.append({
            "url": url,
            "title": attempt.get("result") or attempt.get("query") or "YouTube reference",
            "timestamp": attempt.get("timestamp"),
        })
    return refs


async def _serialize_many(db: AsyncSession, assets: list[Component3DAsset]) -> list[dict]:
    case_ids = {
        asset.subject_id
        for asset in assets
        if asset.subject_type == AssetSubjectType.CASE and asset.subject_id is not None
    }
    videos_by_case: dict[int, list[dict]] = {}
    if case_ids:
        cases = (await db.execute(select(Case).where(Case.id.in_(case_ids)))).scalars().all()
        videos_by_case = {
            case.id: _youtube_refs(case.sourcing_3d_evidence)
            for case in cases
        }
    return [
        _serialize(asset, videos_by_case.get(asset.subject_id, []))
        for asset in assets
    ]


@router.get("")
async def list_assets(
    subject_type: str | None = None,
    status: str | None = None,
    curated_only: bool = False,
    custom_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if curated_only and custom_only:
        raise HTTPException(status_code=422, detail="Choose either curated_only or custom_only")
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
    if curated_only:
        q = q.join(
            CatalogueVariant,
            (Component3DAsset.subject_type == AssetSubjectType.VARIANT)
            & (Component3DAsset.subject_id == CatalogueVariant.id),
        ).where(CatalogueVariant.curated_for_builds.is_(True))
    if custom_only:
        q = q.join(
            CatalogueVariant,
            (Component3DAsset.subject_type == AssetSubjectType.VARIANT)
            & (Component3DAsset.subject_id == CatalogueVariant.id),
        ).where(CatalogueVariant.curated_for_builds.is_(True))
    rows = (await db.execute(q)).scalars().all()
    return await _serialize_many(db, rows)


def catalogue_asset_queue_query(catalogue: str, selected_ids: list[int] | None):
    """An exact build's media workspace is independent of sale visibility."""
    membership = CatalogueVariant.curated_for_builds
    return (
        select(CatalogueVariant, PlaybookSlot, Listing)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(
            CatalogueVariant.status.in_(("active", "pending_review")) if selected_ids is None else True,
            CatalogueVariant.curated_for_builds.is_(True)
                if selected_ids is not None else membership.is_(True),
            CatalogueVariant.id.in_(selected_ids) if selected_ids is not None else True,
        )
        .order_by(PlaybookSlot.slot_type, Listing.title, CatalogueVariant.id)
    )


@router.get("/catalogue-queue")
async def list_catalogue_asset_queue(
    catalogue: str,
    variant_ids: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return selected catalogue variants, including variants with no asset yet."""
    if catalogue not in {"curated", "custom"}:
        raise HTTPException(status_code=422, detail="catalogue must be curated or custom")
    selected_ids = None
    if variant_ids is not None:
        try:
            selected_ids = list(dict.fromkeys(int(value) for value in variant_ids.split(",")))
        except ValueError:
            raise HTTPException(status_code=422, detail="variant_ids must be comma-separated positive integers")
        if not selected_ids or len(selected_ids) > 100 or any(value <= 0 for value in selected_ids):
            raise HTTPException(status_code=422, detail="Choose between 1 and 100 component variants")
    raw_rows = (await db.execute(catalogue_asset_queue_query(catalogue, selected_ids))).all()
    # Each exact listing is materialized once per Playbook slot. 3D assets and
    # captured media belong to the product, so collapse those slot copies into
    # one queue item and keep their variant IDs as aliases for publication.
    groups: dict[tuple[int, str], dict] = {}
    for variant, slot, listing in raw_rows:
        key = (listing.id, component_slot_type(slot.slot_type))
        group = groups.setdefault(key, {"slot": slot, "listing": listing, "variants": []})
        group["variants"].append(variant)
    if selected_ids is not None and groups:
        # Expand a selected Playbook cell's component to every segment alias
        # before loading asset and approval state. The GLB stays a single row
        # keyed to its original variant, but every alias resolves to that row.
        listing_ids = list({listing_id for listing_id, _slot_type in groups})
        slot_types = list({role for _listing_id, slot_type in groups for role in component_slot_types(slot_type)})
        alias_rows = (await db.execute(
            select(CatalogueVariant, PlaybookSlot)
            .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
            .where(
                CatalogueVariant.listing_id.in_(listing_ids),
                PlaybookSlot.slot_type.in_(slot_types),
            )
        )).all()
        for alias, alias_slot in alias_rows:
            group = groups.get((alias.listing_id, component_slot_type(alias_slot.slot_type)))
            if group is not None and all(item.id != alias.id for item in group["variants"]):
                group["variants"].append(alias)
    rows = [(group["variants"][0], group["slot"], group["listing"], group["variants"])
        for group in groups.values()]
    variant_ids = list(dict.fromkeys(variant.id for _, _, _, variants in rows for variant in variants))
    assets = (await db.execute(
        select(Component3DAsset).where(
            Component3DAsset.subject_type == AssetSubjectType.VARIANT,
            Component3DAsset.subject_id.in_(variant_ids) if variant_ids else False,
        ).order_by(Component3DAsset.version.desc(), Component3DAsset.id.desc())
    )).scalars().all()
    latest_by_variant = {}
    assets_by_variant: dict[int, list[Component3DAsset]] = {}
    for asset in assets:
        latest_by_variant.setdefault(asset.subject_id, asset)
        assets_by_variant.setdefault(asset.subject_id, []).append(asset)
    def scorer_listing_id(listing: Listing) -> str:
        external_id = listing.external_id or ""
        return external_id.split("|", 1)[1] if external_id.startswith("ebay_v1|") and "|" in external_id else external_id

    scorer_ids = {listing.id: scorer_listing_id(listing) for _, _, listing, _ in rows}
    external_ids = list(dict.fromkeys(value for value in scorer_ids.values() if value))
    observations = (await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id.in_(external_ids) if external_ids else False)
        .order_by(GemRadarListingObservation.observed_at.desc(), GemRadarListingObservation.id.desc())
    )).scalars().all()
    latest_observation_by_listing = {}
    for observation in observations:
        latest_observation_by_listing.setdefault(observation.listing_id, observation)
    scored_rows = (await db.execute(
        select(GemRadarScoredListing)
        .where(GemRadarScoredListing.listing_id.in_(external_ids) if external_ids else False)
        .order_by(GemRadarScoredListing.scored_at.desc(), GemRadarScoredListing.id.desc())
    )).scalars().all()
    latest_scored_by_listing = {}
    for scored in scored_rows:
        latest_scored_by_listing.setdefault(scored.listing_id, scored)
    listing_ids = list(dict.fromkeys(listing.id for _, _, listing, _ in rows))
    marketing_rows = (await db.execute(
        select(CatalogueMarketingCopy)
        .where(CatalogueMarketingCopy.subject_type == "listing", CatalogueMarketingCopy.subject_id.in_(listing_ids) if listing_ids else False)
        .order_by(CatalogueMarketingCopy.updated_at.desc(), CatalogueMarketingCopy.id.desc())
    )).scalars().all()
    product_copy_by_listing = {}
    upsell_copy_by_listing = {}
    for copy in marketing_rows:
        if copy.context_key == "product":
            product_copy_by_listing.setdefault(copy.subject_id, copy)
        elif copy.context_key.startswith("upgrade:"):
            upsell_copy_by_listing.setdefault(copy.subject_id, []).append(copy)

    def valid_urls(values):
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))

    def unique_urls(*values):
        return list(dict.fromkeys(url for group in values for url in valid_urls(group)))

    def unique_photo_urls(*values):
        """Collapse resized copies of the same source photo, not just exact URLs."""
        from app.services.curated_media import media_urls
        result = []
        seen = set()
        candidates = media_urls([url for group in values for url in valid_urls(group)])
        for url in candidates:
            identity = url
            try:
                path = urlparse(url).path
                amazon = re.search(r"/images/I/([^/.]+)", path, re.IGNORECASE)
                ebay = re.search(r"/images/g/([^/]+)", path, re.IGNORECASE)
                if amazon:
                    identity = f"amazon:{amazon.group(1)}"
                elif ebay:
                    identity = f"ebay:{ebay.group(1)}"
            except (TypeError, ValueError):
                pass
            if identity not in seen:
                seen.add(identity)
                result.append(url)
        return result

    output = []
    from app.services.curated_media import captured_media
    for variant, slot, listing, variants in rows:
        media_review = next((item.asset_media_review for item in variants
            if item.asset_media_review and item.asset_media_review.get("model_image_urls")),
            variant.asset_media_review or {})
        from app.services.curated_media import media_urls
        media_review = dict(media_review)
        for key in ("image_urls", "model_image_urls"):
            if isinstance(media_review.get(key), list):
                media_review[key] = media_urls(media_review[key])
        listing_specs = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
        product_captures = [listing_specs.get(key) or {} for key in ("playbook_product_capture", "playbook_amazon_catalog_capture")]
        captured_product_images = [
            image_url
            for capture in product_captures
            if capture.get("url") == listing.url
            for image_url in (capture.get("product_image_urls") or [])
            if isinstance(image_url, str)
        ]
        asset = latest_by_variant.get(variant.id)
        listing_status = getattr(listing.status, "value", listing.status)
        reasons = []
        if listing_status != "active":
            reasons.append("Underlying supplier listing is not active")
        bestseller = listing_specs.get("bestseller") or {}
        scorer = latest_scored_by_listing.get(scorer_ids[listing.id])
        cpk = bestseller.get("cpk") or (scorer.cpk if scorer else None)
        gallery = await captured_media(db, str(bestseller.get("category") or slot.slot_type), str(cpk), str(bestseller.get("asin") or "") or None) if cpk else {"images": [], "videos": []}
        image_sources: dict[str, str] = {}
        def add_image_sources(urls, source):
            for image_url in urls if isinstance(urls, list) else []:
                if not isinstance(image_url, str):
                    continue
                host = (urlparse(image_url).hostname or "").lower()
                if host == "amazon.co.uk" or host.endswith(".amazon.co.uk") or host.endswith("amazon.com"):
                    label = "Amazon"
                elif host == "overclockers.co.uk" or host.endswith(".overclockers.co.uk"):
                    label = "Overclockers"
                else:
                    label = source or "Captured listing"
                image_sources.setdefault(image_url, label)

        listing_image_urls = unique_photo_urls(
            listing.image_urls,
            captured_product_images,
            [item.get("url") for item in gallery["images"]],
            latest_scored_by_listing.get(scorer_ids[listing.id]).image_urls if scorer_ids[listing.id] in latest_scored_by_listing else [],
            [latest_scored_by_listing[scorer_ids[listing.id]].image_url] if scorer_ids[listing.id] in latest_scored_by_listing else [],
            latest_observation_by_listing.get(scorer_ids[listing.id]).image_urls if scorer_ids[listing.id] in latest_observation_by_listing else [],
            [latest_observation_by_listing[scorer_ids[listing.id]].image_url] if scorer_ids[listing.id] in latest_observation_by_listing else [],
        )
        add_image_sources(listing.image_urls, listing.source_name)
        add_image_sources(captured_product_images, "Retailer product page")
        for gallery_image in gallery["images"]:
            image_url = gallery_image.get("url")
            if isinstance(image_url, str):
                image_sources.setdefault(image_url, gallery_image.get("source") or "Matched product gallery")
        if scorer:
            add_image_sources(scorer.image_urls, scorer.source)
            add_image_sources([scorer.image_url], scorer.source)
        observation = latest_observation_by_listing.get(scorer_ids[listing.id])
        if observation:
            add_image_sources(observation.image_urls, observation.source)
            add_image_sources([observation.image_url], observation.source)
        # Keep the host-derived retailer labels even when the same photo first
        # appeared in another captured gallery.
        for image_url in listing_image_urls:
            host = (urlparse(image_url).hostname or "").lower()
            if host == "amazon.co.uk" or host.endswith(".amazon.co.uk") or host.endswith("amazon.com"):
                image_sources[image_url] = "Amazon"
            elif host == "overclockers.co.uk" or host.endswith(".overclockers.co.uk"):
                image_sources[image_url] = "Overclockers"
        listing_video_urls = unique_urls(
            [item.get("url") for item in gallery["videos"]],
            latest_scored_by_listing[scorer_ids[listing.id]].video_urls if scorer_ids[listing.id] in latest_scored_by_listing else [],
            latest_observation_by_listing[scorer_ids[listing.id]].video_urls if scorer_ids[listing.id] in latest_observation_by_listing else [],
        )
        if not listing_image_urls:
            reasons.append("No captured product photos are available")
        model_image_urls = media_review.get("model_image_urls") or (
            media_review.get("image_urls") if len(media_review.get("image_urls") or []) <= 4 else []
        )
        if not model_image_urls:
            reasons.append("Choose one to four model-reference photos and generate a 3D draft")
        asset = next((candidate for item in variants for candidate in assets_by_variant.get(item.id, [])
            if candidate.is_active and candidate.status == Component3DAssetStatus.FINAL
            and candidate.source_image_refs == model_image_urls), None)
        display_asset = asset or next((latest_by_variant.get(item.id) for item in variants
            if latest_by_variant.get(item.id) and latest_by_variant[item.id].status != Component3DAssetStatus.REJECTED), None)
        if not asset:
            reasons.append("Exact 3D model is not published")
        elif asset.source_image_refs != model_image_urls:
            reasons.append("Published model uses a different photo set")
        output.append({
            "variant_id": variant.id,
            "catalogue_status": variant.status,
            "variant_ids": [item.id for item in variants],
            "listing_id": listing.id,
            "source_reference": (listing.external_id or str(listing.id)).split(":", 1)[-1],
            "title": listing.title,
            "category": component_slot_type(slot.slot_type),
            "listing_url": listing.url,
            "listing_description_preview": (listing.description or "").strip()[:500],
            "listing_description_length": len((listing.description or "").strip()),
            "product_copy_preview": (product_copy_by_listing[listing.id].copy or {}).get("summary", "") if listing.id in product_copy_by_listing else "",
            "product_copy_provider": product_copy_by_listing[listing.id].provider if listing.id in product_copy_by_listing else None,
            "upsell_copy_count": len(upsell_copy_by_listing.get(listing.id, [])),
            "upsell_copy_preview": ((upsell_copy_by_listing[listing.id][0].copy or {}).get("summary", "") if upsell_copy_by_listing.get(listing.id) else ""),
            # Keep the operator gallery focused while retaining source order:
            # listing hero first, followed by the captured product gallery.
            "listing_image_urls": listing_image_urls[:300],
            "main_photo_url": listing_image_urls[0] if listing_image_urls else None,
            "main_photo_approved": bool(listing_image_urls and media_review.get("main_photo_approved_url") == listing_image_urls[0]),
            "listing_image_sources": {url: image_sources[url] for url in listing_image_urls[:300] if url in image_sources},
            "suggested_model_image_urls": listing_image_urls[:300],
            "listing_video_urls": listing_video_urls,
            "asset_media_review": media_review,
            "automatic_media_preparation_enabled": _APP_ENV == "dev",
            "display_price": variant.custom_display_price if catalogue == "custom" and variant.custom_display_price is not None else variant.display_price,
            "curated_for_builds": bool(variant.curated_for_builds),
            "custom_for_builds": bool(variant.custom_for_builds),
            "asset": _serialize(display_asset) if display_asset else None,
            "storefront_ready": not reasons,
            "storefront_blockers": reasons,
        })
    generic_assets = (await db.execute(select(Component3DAsset).where(
        Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
        Component3DAsset.status != Component3DAssetStatus.REJECTED,
    ).order_by(Component3DAsset.version.desc(), Component3DAsset.id.desc()))).scalars().all()
    return group_media_inventory(output, [_serialize(a) for a in generic_assets])


class VariantMediaApproval(BaseModel):
    image_urls: list[str] = Field(default_factory=list, max_length=500)
    video_urls: list[str] = Field(default_factory=list, max_length=100)
    model_image_urls: list[str] | None = Field(default=None, max_length=4)


class VariantMeshyGenerate(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)
    review_batch_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F-]{36}$")
    comparison_draft: bool = False


@router.put("/variants/{variant_id}/media-approval")
async def approve_variant_media(variant_id: int, body: VariantMediaApproval, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db), background_tasks: BackgroundTasks = None):
    """Auto-include captured listing media and persist only the chosen model photos."""
    row = (await db.execute(select(CatalogueVariant, PlaybookSlot, Listing)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(CatalogueVariant.id == variant_id))).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Catalogue component not found")
    variant, slot, listing = row
    available_images = list(dict.fromkeys(url for url in (listing.image_urls or []) if isinstance(url, str)))
    listing_specs = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
    for capture_key in ("playbook_product_capture", "playbook_amazon_catalog_capture"):
        product_capture = listing_specs.get(capture_key) or {}
        if product_capture.get("url") == listing.url and isinstance(product_capture.get("product_image_urls"), list):
            available_images.extend(url for url in product_capture["product_image_urls"] if isinstance(url, str))
    available_videos: list[str] = []
    scored = []
    if listing.external_id:
        source_id = listing.external_id.split("|", 1)[-1] if listing.external_id.startswith("ebay_v1|") else listing.external_id
        observations = (await db.execute(select(GemRadarListingObservation).where(GemRadarListingObservation.listing_id == source_id))).scalars().all()
        scored = (await db.execute(select(GemRadarScoredListing).where(GemRadarScoredListing.listing_id == source_id))).scalars().all()
        for media in [*observations, *scored]:
            available_images.extend(url for url in (media.image_urls or []) if isinstance(url, str))
            if media.image_url:
                available_images.append(media.image_url)
            available_videos.extend(url for url in (media.video_urls or []) if isinstance(url, str))
    bestseller = listing_specs.get("bestseller") or {}
    cpk = bestseller.get("cpk") or next((media.cpk for media in scored if getattr(media, "cpk", None)), None)
    if cpk:
        from app.services.curated_media import captured_media
        gallery = await captured_media(db, str(bestseller.get("category") or slot.slot_type), str(cpk), str(bestseller.get("asin") or "") or None)
        available_images.extend(item["url"] for item in gallery["images"] if item.get("url"))
        available_videos.extend(item["url"] for item in gallery["videos"] if item.get("url"))
    from app.services.curated_media import media_urls
    available_images.extend(item.get("url") for item in (listing.raw_specs or {}).get("catalogue_imported_photos", []))
    available_images.extend((variant.asset_media_review or {}).get("image_urls") or [])
    available_images = media_urls(available_images)
    available_videos = list(dict.fromkeys(available_videos))
    model_image_urls = body.model_image_urls
    if model_image_urls is None:
        model_image_urls = body.image_urls if len(body.image_urls) <= 4 else []
    if not 1 <= len(model_image_urls) <= 4:
        raise HTTPException(status_code=422, detail="Choose one to four captured photos for the 3D model")
    if len(set(model_image_urls)) != len(model_image_urls) or not set(model_image_urls) <= set(available_images):
        raise HTTPException(status_code=422, detail="3D reference photos must come from this component's captured listing gallery")
    previous = variant.asset_media_review or {}
    previous_refs = previous.get("model_image_urls") or []
    generation = previous.get("generation") or {}
    if previous_refs != model_image_urls and generation.get("status") in {"STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING"}:
        raise HTTPException(409, "Wait for the current model job before changing its approved reference photos")
    shared_review = {"status": "approved", "image_urls": available_images,
        "model_image_urls": model_image_urls, "video_urls": available_videos,
        "included_at": datetime.utcnow().isoformat(), "model_references_selected_by": getattr(admin, "email", None),
        "model_references_approved_at": datetime.utcnow().isoformat(),
        **({"generation": generation} if previous_refs == model_image_urls and generation else {})}
    media_category, family_key, siblings = await media_members(db, variant, lock=True)
    shared_review.update({"media_scope": "product" if media_category == "case" else "family", "media_family_key": None if media_category == "case" else family_key})
    for sibling in siblings:
        sibling.asset_media_review = shared_review
    await db.commit()
    from app.services.playbook_service import enqueue_scheduled_playbook_rebuild
    await enqueue_scheduled_playbook_rebuild("Owner approved exact product photos")
    if background_tasks is not None:
        from app.services.playbook_service import run_pending_scheduled_playbook_rebuild
        background_tasks.add_task(run_pending_scheduled_playbook_rebuild)
    return shared_review


async def _run_variant_generation(
    variant_id: int,
    image_urls: list[str],
    version: int,
    review_batch_id: str,
    notes: str | None,
    created_by: str | None,
    resume_task_id: str | None = None,
) -> None:
    """Run Meshy outside the request so browser/proxy timeouts cannot mask progress."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(CatalogueVariant, PlaybookSlot)
            .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
            .where(CatalogueVariant.id == variant_id)
        )).one_or_none()
        if row is None:
            return
        variant, slot = row
        media_category, family_key, sibling_variants = await media_members(db, variant, lock=True)
        approval = variant.asset_media_review or {}

        async def record_progress(progress: int, status: str, task_id: str | None, error: str | None = None) -> None:
            updated_review = {
                **approval,
                "generation": {
                    "status": status,
                    "progress": max(0, min(100, int(progress))),
                    "task_id": task_id,
                    "review_batch_id": review_batch_id,
                    "error": error,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            }
            for sibling in sibling_variants:
                sibling.asset_media_review = updated_review
            await db.commit()

        try:
            if resume_task_id:
                result = await poll_multi_image_asset(resume_task_id, len(image_urls) == 1, record_progress)
            else:
                result = await generate_multi_image_asset(image_urls, progress_callback=record_progress)
            if result is not None and getattr(result, "reference_image_urls", None):
                approval = {**approval, "generation_input_image_urls": image_urls,
                    "generation_input_basis": (
                        "Single original captured photo selected and verified by local Qwen"
                        if approval.get("model_references_selected_by") == "local_qwen_auto_review"
                        else "Original-size renditions of the owner-approved photos"
                    )}
            if result is None:
                await record_progress(0, "FAILED", None, "Meshy did not return a generation result")
                return
            if result.status != "SUCCEEDED":
                await record_progress(result.progress, result.status, result.task_id or None, result.error)
                return
            if not result.glb_url:
                await record_progress(100, "FAILED", result.task_id, "Meshy succeeded but returned no GLB file")
                return

            await record_progress(100, "PUBLISHING", result.task_id)
            try:
                stable_url, file_size_kb = await _store_generated_glb(f"variant-{variant_id}" if media_category == "case" else family_key, version, result.glb_url)
            except Exception as exc:
                logger.exception("catalogue_3d.variant_glb_publish_failed", extra={"variant_id": variant_id, "task_id": result.task_id})
                await record_progress(100, "FAILED", result.task_id, f"Model generated but could not be saved: {exc}")
                return

            preview_url = await _store_generated_preview(
                f"variant-{variant_id}" if media_category == "case" else family_key,
                version,
                result.thumbnail_url,
            )
            asset = Component3DAsset(
                subject_type=AssetSubjectType.VARIANT if media_category == "case" else AssetSubjectType.CATEGORY_GENERIC,
                subject_id=variant_id if media_category == "case" else None,
                category=media_category,
                family_key=None if media_category == "case" else family_key,
                status=Component3DAssetStatus.MESHY_DRAFT,
                version=version,
                glb_ref=stable_url,
                preview_image_ref=preview_url,
                source_image_refs=image_urls,
                file_size_kb=file_size_kb,
                notes=notes or f"Generated from operator-approved catalogue photos (Meshy task {result.task_id})",
                created_by=created_by,
                provenance_status="original-recreation",
                source_name=f"Meshy AI recreation (task {result.task_id})",
                commercial_use_approved=False,
                redistribution_approved=False,
                review_batch_id=review_batch_id,
            )
            db.add(asset)
            await db.commit()
            await record_progress(100, "DRAFT_CREATED", result.task_id)
        except Exception as exc:
            await db.rollback()
            logger.exception("catalogue_3d.variant_generation_failed", extra={"variant_id": variant_id})
            async with AsyncSessionLocal() as status_db:
                status_variant = await status_db.get(CatalogueVariant, variant_id)
                if status_variant is not None:
                    status_slot_type = (await status_db.execute(
                        select(PlaybookSlot.slot_type)
                        .join(CatalogueVariant, CatalogueVariant.slot_id == PlaybookSlot.id)
                        .where(CatalogueVariant.id == variant_id)
                    )).scalar_one_or_none()
                    failed_review = {
                        **(status_variant.asset_media_review or approval),
                        "generation": {
                            "status": "FAILED",
                            "progress": 0,
                            "task_id": None,
                            "error": f"Generation service error: {type(exc).__name__}",
                            "updated_at": datetime.utcnow().isoformat(),
                        },
                    }
                    _, _, status_siblings = await media_members(status_db, status_variant, lock=True)
                    for status_sibling in status_siblings:
                        status_sibling.asset_media_review = failed_review
                    await status_db.commit()


@router.post("/variants/{variant_id}/generate", status_code=202)
async def generate_variant_asset(
    variant_id: int,
    body: VariantMeshyGenerate,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Accept an exact-variant draft job and return before Meshy generation starts."""
    row = (await db.execute(
        select(CatalogueVariant, PlaybookSlot)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .where(CatalogueVariant.id == variant_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Catalogue component not found")
    variant, slot = row
    media_category, family_key, sibling_variants = await media_members(db, variant, lock=True)
    if media_category.startswith("os") or family_key.endswith("_unclassified"):
        raise HTTPException(409, "Choose a supported hardware family before generating a model")
    approval = variant.asset_media_review or {}
    image_urls = approval.get("model_image_urls", approval.get("image_urls")) or []
    if approval.get("status") not in {"approved", "auto_included"} or not image_urls:
        raise HTTPException(status_code=409, detail="Choose one to four model reference photos before generating the draft")
    if not 1 <= len(image_urls) <= 4:
        raise HTTPException(status_code=409, detail="Choose between one and four model reference photos")
    prior_generation = approval.get("generation") or {}
    active_statuses = {"QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING", "TIMED_OUT"}
    resume_task_id = None
    if prior_generation.get("status") in active_statuses:
        updated_at = prior_generation.get("updated_at")
        try:
            last_update = datetime.fromisoformat(updated_at) if updated_at else datetime.min
        except (TypeError, ValueError):
            last_update = datetime.min
        if prior_generation.get("status") != "TIMED_OUT" and datetime.utcnow() - last_update <= timedelta(minutes=2):
            raise HTTPException(status_code=409, detail="A 3D draft is already generating for this product")
        resume_task_id = prior_generation.get("task_id") or None
        safe_capacity_retry = (prior_generation.get("status") == "QUEUED"
            and str(prior_generation.get("error") or "").startswith("Meshy pending-task capacity is full"))
        if not resume_task_id and not safe_capacity_retry:
            raise HTTPException(409, "Existing generation has no saved provider task ID; recover it before submitting another paid job")
    elif (
        prior_generation.get("status") == "FAILED"
        and str(prior_generation.get("error") or "").startswith("Model generated but could not be saved:")
    ):
        # Meshy succeeded, but the local media save failed. Re-poll the saved
        # Meshy task and retry the download/save instead of creating a paid task.
        resume_task_id = prior_generation.get("task_id") or None

    siblings = [sibling.id for sibling in sibling_variants]
    latest = (await db.execute(select(Component3DAsset).where(
        media_asset_filter(media_category, family_key, siblings),
        Component3DAsset.status != Component3DAssetStatus.REJECTED,
    ).order_by(Component3DAsset.version.desc()).limit(1))).scalar_one_or_none()
    if latest and latest.status != Component3DAssetStatus.REJECTED:
        if not body.comparison_draft:
            raise HTTPException(status_code=409, detail="A model already exists for this component; review or publish it before generating another")
        if latest.is_active or latest.status == Component3DAssetStatus.FINAL:
            raise HTTPException(status_code=409, detail="A published model cannot be replaced with a comparison draft")
    elif body.comparison_draft:
        raise HTTPException(status_code=409, detail="A comparison draft requires an existing unpublished model")
    prior_version = (await db.execute(select(Component3DAsset.version).where(
        media_asset_filter(media_category, family_key, siblings),
    ).order_by(Component3DAsset.version.desc()).limit(1))).scalar_one_or_none()
    version = (prior_version or 0) + 1
    review_batch_id = body.review_batch_id or str(uuid4())
    starting_review = {
        **approval,
        "generation": {
            "status": "RESUMING" if resume_task_id else "STARTING",
            "progress": int(prior_generation.get("progress") or 0) if resume_task_id else 0,
            "task_id": resume_task_id,
            "error": None,
            "updated_at": datetime.utcnow().isoformat(),
        },
    }
    for sibling in sibling_variants:
        sibling.asset_media_review = starting_review
    await db.commit()
    background_tasks.add_task(
        _run_variant_generation,
        variant_id,
        image_urls,
        version,
        review_batch_id,
        body.notes,
        getattr(admin, "email", None),
        resume_task_id,
    )
    return {"status": "accepted", "variant_id": variant_id, "review_batch_id": review_batch_id}


class ReviewBatchCreate(BaseModel):
    size: int = Field(default=10, ge=1, le=10)
    asset_ids: list[int] | None = Field(default=None, min_length=1, max_length=10)
    curated_only: bool = False
    custom_only: bool = False


async def _batch_payload(batch_id: str, assets: list[Component3DAsset], db: AsyncSession) -> dict:
    decided = sum(asset.review_decision is not None for asset in assets)
    return {
        "batch_id": batch_id,
        "size": len(assets),
        "decided": decided,
        "complete": bool(assets) and decided == len(assets),
        "published": bool(assets) and all(
            asset.review_decision == "rejected" or asset.is_active for asset in assets
        ),
        "assets": await _serialize_many(db, assets),
    }


@router.post("/review-batches")
async def create_review_batch(
    body: ReviewBatchCreate,
    db: AsyncSession = Depends(get_db),
):
    if body.curated_only and body.custom_only:
        raise HTTPException(status_code=422, detail="Choose either curated_only or custom_only")
    """Claim the next unreviewed candidates, with a hard maximum of ten."""
    query = select(Component3DAsset).where(
        Component3DAsset.review_batch_id.is_(None),
        Component3DAsset.status.in_((
            Component3DAssetStatus.MESHY_DRAFT,
            Component3DAssetStatus.CLEANED,
        )),
        Component3DAsset.glb_ref.isnot(None),
    )
    if body.asset_ids is not None:
        requested_ids = list(dict.fromkeys(body.asset_ids))
        if len(requested_ids) != len(body.asset_ids):
            raise HTTPException(status_code=422, detail="asset_ids must be unique")
        query = query.where(Component3DAsset.id.in_(requested_ids)).limit(len(requested_ids))
    else:
        query = query.limit(body.size)
    if body.curated_only:
        query = query.join(
            CatalogueVariant,
            (Component3DAsset.subject_type == AssetSubjectType.VARIANT)
            & (Component3DAsset.subject_id == CatalogueVariant.id),
        ).where(CatalogueVariant.curated_for_builds.is_(True))
    if body.custom_only:
        query = query.join(
            CatalogueVariant,
            (Component3DAsset.subject_type == AssetSubjectType.VARIANT)
            & (Component3DAsset.subject_id == CatalogueVariant.id),
        ).where(CatalogueVariant.curated_for_builds.is_(True))
    candidates = (
        await db.execute(
            query.order_by(Component3DAsset.created_at, Component3DAsset.id)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if body.asset_ids is not None and len(candidates) != len(body.asset_ids):
        raise HTTPException(status_code=409, detail="One or more requested assets are unavailable for review")
    if not candidates:
        raise HTTPException(status_code=409, detail="No unbatched 3D candidates are ready for review")

    batch_id = str(uuid4())
    for asset in candidates:
        asset.review_batch_id = batch_id
    await db.commit()
    return await _batch_payload(batch_id, candidates, db)


@router.get("/review-batches/{batch_id}")
async def get_review_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    assets = (
        await db.execute(
            select(Component3DAsset)
            .where(Component3DAsset.review_batch_id == batch_id)
            .order_by(Component3DAsset.created_at, Component3DAsset.id)
        )
    ).scalars().all()
    if not assets:
        raise HTTPException(status_code=404, detail="Review batch not found")
    return await _batch_payload(batch_id, assets, db)


class ReviewDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|pending)$")
    notes: str | None = None


def _regeneration_file_key(asset: Component3DAsset) -> str:
    if asset.subject_type == AssetSubjectType.CASE:
        return f"case-{asset.subject_id}"
    if asset.family_key:
        return asset.family_key
    if asset.subject_type == AssetSubjectType.VARIANT:
        return f"variant-{asset.subject_id}"
    return f"{asset.category or 'component'}-generic"


def _approved_case_image_urls(evidence: dict | None) -> set[str]:
    """URLs that passed the empty illuminated chassis acquisition gate."""
    approved: set[str] = set()
    stages = (evidence or {}).get("stages") or {}
    selection = (stages.get("product_images") or {}).get("approved_selection") or {}
    if selection.get("status") == "approved":
        for item in selection.get("images") or []:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                approved.add(item["url"])
    for stage_name in ("product_images", "meshy_generation"):
        for attempt in (stages.get(stage_name) or {}).get("attempts") or []:
            for item in attempt.get("image_assessments") or []:
                if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                    continue
                if all(item.get(field) is True for field in _CASE_MESHY_IMAGE_REQUIREMENTS):
                    approved.add(item["url"])
    return approved


def _owner_approved_case_image_order(evidence: dict | None) -> list[str]:
    """Return one to four current owner-approved photos in their chosen order."""
    stages = (evidence or {}).get("stages") or {}
    selection = (stages.get("product_images") or {}).get("approved_selection") or {}
    images = selection.get("images") or []
    urls = [
        item["url"]
        for item in images
        if isinstance(item, dict) and isinstance(item.get("url"), str)
    ]
    return urls if selection.get("status") == "approved" and 1 <= len(urls) <= 4 else []


async def _run_rejected_asset_regeneration(
    replacement_id: int,
    source_image_refs: list[str],
    file_key: str,
) -> None:
    """Finish a queued replacement using a fresh DB session.

    The placeholder row remains ``missing`` if Meshy or media publication
    fails, leaving a visible, retryable audit record instead of losing the
    owner's rejection feedback.
    """
    result = await generate_multi_image_asset(source_image_refs)
    async with AsyncSessionLocal() as task_db:
        replacement = (
            await task_db.execute(
                select(Component3DAsset).where(Component3DAsset.id == replacement_id)
            )
        ).scalar_one_or_none()
        if replacement is None:
            return
        if result is None or result.status != "SUCCEEDED" or not result.glb_url:
            outcome = "service unavailable" if result is None else f"Meshy status {result.status}"
            replacement.notes = f"{replacement.notes}\nRegeneration failed: {outcome}. Retry required."
            replacement.updated_at = datetime.utcnow()
            await task_db.commit()
            return

        try:
            stable_url, file_size_kb = await _store_generated_glb(
                file_key, replacement.version, result.glb_url
            )
        except Exception as exc:
            replacement.notes = f"{replacement.notes}\nRegeneration failed while publishing: {exc}"
            replacement.updated_at = datetime.utcnow()
            await task_db.commit()
            return

        replacement.glb_ref = stable_url
        replacement.preview_image_ref = await _store_generated_preview(file_key, replacement.version, result.thumbnail_url)
        replacement.file_size_kb = file_size_kb
        replacement.status = Component3DAssetStatus.MESHY_DRAFT
        replacement.source_name = f"Meshy AI feedback regeneration (task {result.task_id})"
        replacement.notes = f"{replacement.notes}\nCompleted Meshy task {result.task_id}; ready for review."
        replacement.updated_at = datetime.utcnow()
        await task_db.commit()


async def _variant_source_urls(db: AsyncSession, listing: Listing, slot_type: str) -> list[str]:
    """Collect this listing's images plus its canonical captured product gallery."""
    values = list(listing.image_urls or [])
    values.extend(item.get("url") for item in (listing.raw_specs or {}).get("catalogue_imported_photos", []))
    specs = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
    for key in ("playbook_product_capture", "playbook_amazon_catalog_capture"):
        capture = specs.get(key) or {}
        if capture.get("url") == listing.url:
            values.extend(capture.get("product_image_urls") or [])
    bestseller = specs.get("bestseller") or {}
    cpk = bestseller.get("cpk")
    category = str(bestseller.get("category") or slot_type)
    asin = str(bestseller.get("asin") or "") or None
    external_id = listing.external_id or ""
    scorer_listing_id = external_id.split("|", 1)[1] if external_id.startswith("ebay_v1|") and "|" in external_id else external_id
    if not cpk and scorer_listing_id:
        scorer = (await db.execute(
            select(GemRadarScoredListing)
            .where(GemRadarScoredListing.listing_id == scorer_listing_id)
            .order_by(GemRadarScoredListing.scored_at.desc(), GemRadarScoredListing.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        if scorer:
            cpk = scorer.cpk
    if cpk:
        from app.services.curated_media import captured_media
        gallery = await captured_media(db, category, str(cpk), asin)
        values.extend(item.get("url") for item in gallery["images"] if isinstance(item, dict))

    from app.services.curated_media import media_urls
    unique = []
    seen = set()
    for value in media_urls(values):
        path = urlparse(value).path
        amazon = re.search(r"/images/I/([^/.]+)", path, re.IGNORECASE)
        ebay = re.search(r"/images/g/([^/]+)", path, re.IGNORECASE)
        identity = f"amazon:{amazon.group(1)}" if amazon else f"ebay:{ebay.group(1)}" if ebay else value
        if identity not in seen:
            seen.add(identity)
            unique.append(value)
    return unique[:300]


async def _run_variant_auto_media(variant_id: int, source_urls: list[str], created_by: str | None) -> None:
    """Run local-Qwen photo selection and one textured, single-image Meshy draft."""
    if _APP_ENV != "dev":
        return
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(CatalogueVariant, PlaybookSlot, Listing)
            .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
            .join(Listing, CatalogueVariant.listing_id == Listing.id)
            .where(CatalogueVariant.id == variant_id)
        )).one_or_none()
        if row is None:
            return
        variant, slot, listing = row
        media_category, family_key, sibling_variants = await media_members(db, variant, lock=True)
        sibling_ids = [item.id for item in sibling_variants]

        async def update_preparation(status: str, progress: int, error: str | None = None) -> None:
            for sibling in sibling_variants:
                review = dict(sibling.asset_media_review or {})
                review["media_preparation"] = {
                    "status": status,
                    "progress": max(0, min(100, int(progress))),
                    "error": error,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                review["generation"] = {
                    "status": "PREPARING" if status not in {"READY", "FAILED"} else ("STARTING" if status == "READY" else "FAILED"),
                    "progress": max(0, min(100, int(progress))),
                    "task_id": None,
                    "error": error,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                sibling.asset_media_review = review
            await db.commit()

        try:
            approved_main = (variant.asset_media_review or {}).get("main_photo_approved_url")
            use_approved_main = bool(approved_main and approved_main in source_urls)
            if use_approved_main:
                selected_photo_url = approved_main
                manifest = {"selected_source_url": approved_main, "source_decision": {"basis": "owner-approved main catalogue photo"}, "candidate_count_reviewed": 1}
            else:
                if media_category != "case":
                    raise ValueError("Approve the shared family photo before model generation")
                await update_preparation("loading_source_photos", 0)
                selected_photo_url, manifest = await select_component_photo(
                    title=listing.title,
                    candidate_urls=source_urls,
                    progress=update_preparation,
                )

            # Recheck the shared component cache before paying for Meshy. The
            # DB state is keyed by listing_id + slot type and shared to aliases.
            latest = (await db.execute(select(Component3DAsset).where(
                media_asset_filter(media_category, family_key, sibling_ids),
                Component3DAsset.status != Component3DAssetStatus.REJECTED,
            ).order_by(Component3DAsset.version.desc()).limit(1))).scalar_one_or_none()
            if latest:
                await update_preparation("READY", 100)
                return

            prior_version = (await db.execute(select(Component3DAsset.version).where(
                media_asset_filter(media_category, family_key, sibling_ids),
            ).order_by(Component3DAsset.version.desc()).limit(1))).scalar_one_or_none()
            version = (prior_version or 0) + 1
            review_batch_id = str(uuid4())
            shared_review = {
                **(variant.asset_media_review or {}),
                "status": "approved",
                "image_urls": source_urls,
                "model_image_urls": [selected_photo_url],
                "model_references_selected_by": (variant.asset_media_review or {}).get("main_photo_approved_by") if use_approved_main else "local_qwen_auto_review",
                "media_preparation": {
                    "status": "READY",
                    "progress": 100,
                    "pipeline_version": "curated-single-photo-v1",
                    "selected_source_url": manifest.get("selected_source_url"),
                    "source_decision": manifest.get("source_decision"),
                    "candidate_count_reviewed": manifest.get("candidate_count_reviewed"),
                    "updated_at": datetime.utcnow().isoformat(),
                },
                "generation": {
                    "status": "STARTING",
                    "progress": 0,
                    "task_id": None,
                    "review_batch_id": review_batch_id,
                    "error": None,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            }
            for sibling in sibling_variants:
                sibling.asset_media_review = shared_review
            await db.commit()

            # Meshy's image-to-3D endpoint receives exactly the selected
            # captured image. Its request explicitly enables PBR texturing and GLB.
            await _run_variant_generation(
                variant_id,
                [selected_photo_url],
                version,
                review_batch_id,
                "Single owner-approved main catalogue photo; Meshy textured GLB generation." if use_approved_main else "Single captured component photo selected and verified by local Qwen; Meshy textured GLB generation.",
                created_by,
            )
        except Exception as exc:
            logger.exception("catalogue_3d.auto_media_pipeline_failed", extra={"variant_id": variant_id})
            await db.rollback()
            await update_preparation("FAILED", 0, str(exc)[:500])


@router.post("/variants/{variant_id}/auto-prepare", status_code=202)
async def auto_prepare_variant_asset(
    variant_id: int,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Auto-select one exact-product photo, then submit one Meshy draft (DEV only)."""
    if _APP_ENV != "dev":
        raise HTTPException(status_code=409, detail="Automatic image preparation is enabled only in DEV")
    row = (await db.execute(
        select(CatalogueVariant, PlaybookSlot, Listing)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .where(CatalogueVariant.id == variant_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Catalogue component not found")
    variant, slot, listing = row
    if slot.slot_type.lower() in {"os", "os_secondary", "software"}:
        raise HTTPException(status_code=409, detail="Software does not need a physical 3D model")
    media_category, family_key, siblings = await media_members(db, variant, lock=True)
    sibling_ids = [item.id for item in siblings]
    latest = (await db.execute(select(Component3DAsset).where(
        media_asset_filter(media_category, family_key, sibling_ids),
        Component3DAsset.status != Component3DAssetStatus.REJECTED,
    ).order_by(Component3DAsset.version.desc()).limit(1))).scalar_one_or_none()
    if latest:
        raise HTTPException(status_code=409, detail="A shared model already exists for this component; review it before generating another")

    review = dict(variant.asset_media_review or {})
    generation = review.get("generation") or {}
    generation_status = generation.get("status")
    active_statuses = {"QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING", "TIMED_OUT"}
    safe_capacity_retry = (generation_status == "QUEUED"
        and str(generation.get("error") or "").startswith("Meshy pending-task capacity is full"))
    if generation_status == "QUEUED" and not safe_capacity_retry:
        raise HTTPException(status_code=409, detail="This component is already queued for automatic preparation")
    if generation_status in active_statuses:
        updated_at = generation.get("updated_at")
        try:
            last_update = datetime.fromisoformat(updated_at) if updated_at else datetime.min
        except (TypeError, ValueError):
            last_update = datetime.min
        if generation_status != "TIMED_OUT" and datetime.utcnow() - last_update <= timedelta(minutes=2):
            raise HTTPException(status_code=409, detail="Media or model generation is already running for this component")
        if generation_status != "PREPARING" and generation.get("task_id"):
            refs = review.get("model_image_urls") or []
            if not refs:
                raise HTTPException(status_code=409, detail="A previous model task needs operator recovery before new media can be prepared")
            siblings_latest = (await db.execute(select(Component3DAsset.version).where(
                media_asset_filter(media_category, family_key, sibling_ids),
            ).order_by(Component3DAsset.version.desc()).limit(1))).scalar_one_or_none()
            background_tasks.add_task(
                _run_variant_generation,
                variant_id,
                refs,
                (siblings_latest or 0) + 1,
                generation.get("review_batch_id") or str(uuid4()),
                "Resuming the existing Meshy task; no second paid generation submitted.",
                getattr(admin, "email", None),
                generation.get("task_id"),
            )
            return {"status": "accepted", "variant_id": variant_id, "message": "Resuming the existing model task; no duplicate model will be created."}
        if generation_status != "PREPARING" and not safe_capacity_retry:
            raise HTTPException(status_code=409, detail="A previous Meshy submission has no saved task ID. Check the asset queue before retrying so a second paid model is not created.")
    source_urls = await _variant_source_urls(db, listing, slot.slot_type)
    if media_category != "case":
        approved = review.get("main_photo_approved_url")
        if family_key.endswith("_unclassified") or review.get("media_family_key") != family_key or not review.get("main_photo_approved_by") or not approved:
            raise HTTPException(409, "Approve the shared hardware family photo first")
        source_urls = [approved]
    if not source_urls:
        raise HTTPException(status_code=409, detail="No captured product photos are available for this component")
    now = datetime.utcnow().isoformat()
    starting = {
        **review,
        "media_preparation": {"status": "STARTING", "progress": 0, "error": None, "updated_at": now},
        "generation": {"status": "PREPARING", "progress": 0, "task_id": None, "error": None, "updated_at": now},
    }
    for sibling in siblings:
        sibling.asset_media_review = starting
    await db.commit()
    background_tasks.add_task(_run_variant_auto_media, variant_id, source_urls, getattr(admin, "email", None))
    return {"status": "accepted", "variant_id": variant_id, "message": "The app is selecting one product photo with local Qwen before submitting one textured Meshy model job."}


@router.get("/catalogue/photo-queue")
async def get_catalogue_photo_inventory(db: AsyncSession = Depends(get_db)):
    return await catalogue_photo_inventory(db)


@router.get("/catalogue/generation-queue")
async def get_catalogue_generation_queue(db: AsyncSession = Depends(get_db)):
    return await catalogue_generation_queue(db)


@router.delete("/catalogue/components/{variant_id}")
async def delete_catalogue_component(variant_id: int, background_tasks: BackgroundTasks, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant:
        raise HTTPException(404, "Component not found")
    listing = (await db.execute(select(Listing).where(Listing.id == variant.listing_id).with_for_update())).scalar_one()
    now = datetime.utcnow().isoformat()
    listing.raw_specs = {**(listing.raw_specs or {}), "catalogue_deleted": {"at": now, "by": str(getattr(admin, "id", "admin"))}}
    siblings = (await db.execute(select(CatalogueVariant).where(CatalogueVariant.listing_id == listing.id).with_for_update())).scalars().all()
    for sibling in siblings:
        sibling.status = "rejected"
        sibling.curated_for_builds = False
        sibling.custom_for_builds = False
        sibling.reject_reason = "Permanently deleted from catalogue by operator"
        sibling.updated_at = now
    await db.commit()
    from app.services.playbook_service import enqueue_scheduled_playbook_rebuild, run_pending_scheduled_playbook_rebuild
    await enqueue_scheduled_playbook_rebuild("Operator permanently deleted catalogue component")
    background_tasks.add_task(run_pending_scheduled_playbook_rebuild)
    return {"deleted_listing_id": listing.id, "deleted_variant_ids": [item.id for item in siblings]}


@router.post("/catalogue/components/{variant_id}/hardware-photo")
async def find_catalogue_hardware_photo(variant_id: int):
    raise HTTPException(410, "Automatic Qwen photo selection has been retired. Choose a captured photo in the catalogue grid.")


class MainPhotoSelection(BaseModel):
    variant_id: int = Field(gt=0)
    photo_url: str = Field(min_length=1, max_length=2000)


@router.get("/catalogue/components/{variant_id}/image-search")
async def search_component_images(variant_id: int, query: str | None = None, db: AsyncSession = Depends(get_db)):
    from app.services.catalogue_image_search import google_image_results, short_product_title
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant or not variant.curated_for_builds:
        raise HTTPException(404, "Catalogue component not found")
    listing = await db.get(Listing, variant.listing_id)
    if (listing.raw_specs or {}).get("catalogue_deleted"):
        raise HTTPException(410, "Component was deleted")
    slot = await db.get(PlaybookSlot, variant.slot_id)
    family = media_family(slot.slot_type, listing.title)
    query = (query or (family_label(family) if family else short_product_title(listing.title))).strip()
    if not 2 <= len(query) <= 180:
        raise HTTPException(422, "Use a search phrase between 2 and 180 characters")
    cached = (listing.raw_specs or {}).get("catalogue_image_search") or {}
    if cached.get("query") == query and cached.get("searched_at", "") > (datetime.utcnow() - timedelta(hours=12)).isoformat():
        return cached
    results = await google_image_results(query)
    # Lock only after the remote read; preserve concurrent deletion/approval state.
    listing = (await db.execute(select(Listing).where(Listing.id == listing.id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one()
    if (listing.raw_specs or {}).get("catalogue_deleted"):
        raise HTTPException(410, "Component was deleted")
    cached = {"query": query, "results": results, "searched_at": datetime.utcnow().isoformat()}
    listing.raw_specs = {**(listing.raw_specs or {}), "catalogue_image_search": cached}
    await db.commit()
    return cached


class SearchPhotoSelection(BaseModel):
    result_id: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/catalogue/components/{variant_id}/search-photo")
async def select_component_search_photo(variant_id: int, body: SearchPhotoSelection,
    admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.services.catalogue_image_search import download_catalogue_photo
    variant = await db.get(CatalogueVariant, variant_id)
    if not variant or not variant.curated_for_builds:
        raise HTTPException(404, "Catalogue component not found")
    listing = await db.get(Listing, variant.listing_id)
    specs = listing.raw_specs or {}
    result = next((item for item in (specs.get("catalogue_image_search") or {}).get("results", []) if item.get("id") == body.result_id), None)
    if not result or specs.get("catalogue_deleted"):
        raise HTTPException(409, "These search results changed. Search again before choosing a photo.")
    saved = next((item for item in specs.get("catalogue_imported_photos", []) if item.get("source_url") == result["url"]), None)
    url = saved["url"] if saved else await download_catalogue_photo(result["url"], thumbnail_url=result.get("thumbnail_url"))
    listing = (await db.execute(select(Listing).where(Listing.id == listing.id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one()
    specs = listing.raw_specs or {}
    if specs.get("catalogue_deleted"):
        raise HTTPException(410, "Component was deleted")
    record = {"url": url, "source_url": result["url"], "source_page": result.get("source_page"),
        "source": "google", "selected_at": datetime.utcnow().isoformat(), "selected_by": str(getattr(admin, "id", "admin"))}
    imports = [item for item in specs.get("catalogue_imported_photos", []) if item.get("url") != url]
    listing.raw_specs = {**specs, "catalogue_selected_photo": record, "catalogue_imported_photos": [record, *imports][:20]}
    category, family, members = await media_members(db, variant, lock=True)
    if category != "case":
        review = {**(variant.asset_media_review or {}), "media_scope": "family", "media_family_key": family,
            "family_selected_photo_url": url, "image_urls": [url]}
        for member in members:
            member.asset_media_review = dict(review)
    await db.commit()
    return {"photo_url": url}


class MainPhotoApprovals(BaseModel):
    selections: list[MainPhotoSelection] = Field(min_length=1, max_length=100)


@router.post("/catalogue/approve-main-photos")
async def approve_catalogue_main_photos(
    body: MainPhotoApprovals,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve the main photos the operator saw, once per shared component.

    Preserve existing model references/tasks: approving a listing photo must
    not invalidate or regenerate a model created from another reference.
    """
    ids = list(dict.fromkeys(item.variant_id for item in body.selections))
    queue = await catalogue_photo_inventory(db, ids)
    by_id = {alias_id: item for item in queue for alias_id in item["variant_ids"]}
    approved, skipped, handled = [], [], set()
    now = datetime.utcnow().isoformat()
    actor = getattr(admin, "email", None) or str(getattr(admin, "id", "admin"))
    for selection in body.selections:
        item = by_id.get(selection.variant_id)
        if not item or selection.photo_url not in item.get("listing_image_urls", []):
            skipped.append({"variant_id": selection.variant_id, "reason": "This photo is no longer in the captured product gallery. Refresh and review it again."})
            continue
        key = (item["listing_id"], item["category"])
        if key in handled:
            continue
        handled.add(key)
        selected_variant = await db.get(CatalogueVariant, selection.variant_id)
        media_category, family_key, siblings = await media_members(db, selected_variant, lock=True)
        shared = next(
            (s.asset_media_review for s in siblings if (s.asset_media_review or {}).get("model_image_urls")),
            next((s.asset_media_review for s in siblings if s.asset_media_review), {}),
        ) or {}
        review = {
            **shared, "status": "approved", "media_scope": "product" if media_category == "case" else "family", "media_family_key": None if media_category == "case" else family_key, "main_photo_approved_url": selection.photo_url,
            "main_photo_approved_at": now, "main_photo_approved_by": actor,
            "image_urls": list(dict.fromkeys([*(shared.get("image_urls") or []), selection.photo_url])),
        }
        generation = review.get("generation") or {}
        if not review.get("model_image_urls") and not generation.get("task_id") and generation.get("status") not in {"QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING"} and not item.get("asset"):
            review.update({"model_image_urls": [selection.photo_url], "model_references_selected_by": actor, "model_references_approved_at": now})
        review.pop("family_selected_photo_url", None)
        for sibling in siblings:
            sibling.asset_media_review = review
        approved.append(selection.variant_id)
    await db.commit()
    if approved:
        from app.services.playbook_service import enqueue_scheduled_playbook_rebuild, run_pending_scheduled_playbook_rebuild
        await enqueue_scheduled_playbook_rebuild("Owner approved shared catalogue photos")
        background_tasks.add_task(run_pending_scheduled_playbook_rebuild)
    return {"approved_count": len(approved), "approved_variant_ids": approved, "skipped": skipped}


async def _refresh_playbooks_after_model_review():
    from app.services.playbook_service import enqueue_scheduled_playbook_rebuild, run_pending_scheduled_playbook_rebuild
    try:
        await enqueue_scheduled_playbook_rebuild("Owner changed model approval and publication")
        await run_pending_scheduled_playbook_rebuild()
    except Exception:
        # The asset decision is committed before this best-effort follow-up.
        # A rebuild failure must not make the review UI report that the
        # already-saved approval failed; the durable queue can be retried.
        logger.exception("catalogue_3d.playbook_rebuild_after_review_failed")


@router.post("/review-batches/{batch_id}/assets/{asset_id}/decision")
async def decide_review_asset(
    batch_id: str,
    asset_id: int,
    body: ReviewDecision,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    asset = (
        await db.execute(
            select(Component3DAsset).where(
                Component3DAsset.id == asset_id,
                Component3DAsset.review_batch_id == batch_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset is not part of this review batch")
    if body.decision == "pending":
        if asset.review_decision != "approved":
            raise HTTPException(status_code=409, detail="Only an approved model can be unapproved")
        asset.is_active = False
        asset.status = Component3DAssetStatus.MESHY_DRAFT
        asset.review_decision = None
        asset.reviewed_at = None
        asset.reviewed_by = None
        asset.commercial_use_approved = False
        asset.redistribution_approved = False
        asset.scale_validated = False
        asset.provenance_reviewed_at = None
        asset.provenance_reviewed_by = None
        await db.commit()
        await db.refresh(asset)
        background_tasks.add_task(_refresh_playbooks_after_model_review)
        return _serialize(asset)

    if body.decision == "approved":
        if not asset.glb_ref:
            raise HTTPException(status_code=409, detail="A generated GLB is required before approval")
        if asset.review_decision == "rejected":
            raise HTTPException(status_code=409, detail="A rejected model must be regenerated before approval")
        # Owner approval is the single visual, rights, scale and publication action.
        await db.execute(
            update(Component3DAsset).where(
                Component3DAsset.id != asset.id,
                Component3DAsset.subject_type == asset.subject_type,
                Component3DAsset.subject_id == asset.subject_id,
                Component3DAsset.category == asset.category,
                Component3DAsset.family_key == asset.family_key,
            ).values(is_active=False)
        )
        asset.review_decision = "approved"
        asset.reviewed_at = datetime.utcnow()
        asset.reviewed_by = getattr(admin, "email", None)
        asset.commercial_use_approved = True
        asset.redistribution_approved = True
        asset.scale_validated = True
        asset.provenance_reviewed_at = asset.reviewed_at
        asset.provenance_reviewed_by = asset.reviewed_by
        asset.status = Component3DAssetStatus.FINAL
        asset.is_active = True
        if body.notes is not None:
            asset.notes = body.notes
        await db.commit()
        await db.refresh(asset)
        background_tasks.add_task(_refresh_playbooks_after_model_review)
        return _serialize(asset)

    if asset.review_decision is not None:
        raise HTTPException(status_code=409, detail="This asset already has a review decision")

    asset.review_decision = body.decision
    asset.reviewed_at = datetime.utcnow()
    asset.reviewed_by = getattr(admin, "email", None)
    if body.notes is not None:
        asset.notes = body.notes
    regeneration: dict | None = None
    if body.decision == "rejected":
        asset.status = Component3DAssetStatus.REJECTED
        asset.is_active = False
        source_images = [url for url in (asset.source_image_refs or []) if isinstance(url, str)][:4]
        if asset.subject_type == AssetSubjectType.CASE and asset.subject_id is not None:
            case = (await db.execute(select(Case).where(Case.id == asset.subject_id))).scalar_one_or_none()
            evidence = case.sourcing_3d_evidence if case else None
            current_owner_selection = _owner_approved_case_image_order(evidence)
            if current_owner_selection:
                # The case's latest approved selection is authoritative, even
                # when the rejected legacy asset has no (or stale) references.
                source_images = current_owner_selection
            else:
                approved_case_urls = _approved_case_image_urls(evidence)
                source_images = [url for url in source_images if url in approved_case_urls]
        if source_images:
            feedback = (body.notes or "").strip() or (
                "Recreate the object more faithfully from the source photographs. "
                "Correct the rejected model's shape, materials, colours, lighting details and proportions."
            )
            prior_version = (
                await db.execute(
                    select(Component3DAsset.version)
                    .where(
                        Component3DAsset.subject_type == asset.subject_type,
                        Component3DAsset.subject_id == asset.subject_id,
                        Component3DAsset.category == asset.category,
                        Component3DAsset.family_key == asset.family_key,
                    )
                    .order_by(Component3DAsset.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            replacement = Component3DAsset(
                subject_type=asset.subject_type,
                subject_id=asset.subject_id,
                category=asset.category,
                family_key=asset.family_key,
                status=Component3DAssetStatus.MISSING,
                version=(prior_version or asset.version) + 1,
                is_active=False,
                source_image_refs=source_images,
                dimensions_mm=asset.dimensions_mm,
                anchor_manifest_json=asset.anchor_manifest_json,
                notes=(
                    f"Queued automatically from rejected asset {asset.id}. "
                    f"Owner feedback: {feedback}"
                ),
                created_by=getattr(admin, "email", None),
                provenance_status="original-recreation",
                source_name="Meshy AI feedback regeneration (queued)",
                commercial_use_approved=False,
                redistribution_approved=False,
            )
            db.add(replacement)
            await db.flush()
            regeneration = {
                "status": "queued",
                "asset_id": replacement.id,
                "version": replacement.version,
                "message": f"Replacement v{replacement.version} queued from the approved case photos.",
            }
            background_tasks.add_task(
                _run_rejected_asset_regeneration,
                replacement.id,
                source_images,
                _regeneration_file_key(asset),
            )
        else:
            regeneration = {
                "status": "not_queued",
                "message": (
                    "Rejected, but regeneration needs at least one acquisition-approved source picture "
                    "showing the empty chassis with its RGB fans installed and illuminated."
                ),
            }
    elif asset.status == Component3DAssetStatus.MESHY_DRAFT:
        asset.status = Component3DAssetStatus.CLEANED
    await db.commit()
    payload = _serialize(asset)
    payload["regeneration"] = regeneration
    return payload


@router.post("/review-batches/{batch_id}/publish")
async def publish_review_batch(
    batch_id: str,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    assets = (
        await db.execute(
            select(Component3DAsset)
            .where(Component3DAsset.review_batch_id == batch_id)
            .order_by(Component3DAsset.id)
            .with_for_update()
        )
    ).scalars().all()
    if not assets:
        raise HTTPException(status_code=404, detail="Review batch not found")
    if any(asset.review_decision is None for asset in assets):
        raise HTTPException(status_code=409, detail="Every model in the batch must be approved or rejected before publishing")

    approved = [asset for asset in assets if asset.review_decision == "approved"]
    for asset in approved:
        if not (asset.commercial_use_approved and asset.redistribution_approved):
            raise HTTPException(
                status_code=409,
                detail=f"Asset {asset.id} is approved visually but its commercial-use and redistribution rights are not approved",
            )
        if not asset.scale_validated:
            raise HTTPException(status_code=409, detail=f"Asset {asset.id} has not passed scale validation")
        await db.execute(
            update(Component3DAsset)
            .where(
                Component3DAsset.id != asset.id,
                Component3DAsset.subject_type == asset.subject_type,
                Component3DAsset.subject_id == asset.subject_id,
                Component3DAsset.category == asset.category,
                Component3DAsset.family_key == asset.family_key,
            )
            .values(is_active=False)
        )
        asset.status = Component3DAssetStatus.FINAL
        asset.is_active = True
        asset.provenance_reviewed_at = asset.provenance_reviewed_at or datetime.utcnow()
        asset.provenance_reviewed_by = asset.provenance_reviewed_by or getattr(admin, "email", None)
    await db.commit()
    from app.services.playbook_service import enqueue_scheduled_playbook_rebuild
    await enqueue_scheduled_playbook_rebuild("Owner published reviewed 3D models")
    if background_tasks is not None:
        from app.services.playbook_service import run_pending_scheduled_playbook_rebuild
        background_tasks.add_task(run_pending_scheduled_playbook_rebuild)
    return await _batch_payload(batch_id, assets, db)


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


class CaseMeshyGenerate(BaseModel):
    image_urls: list[str] = Field(min_length=1, max_length=4)
    notes: str | None = None
    request_id: str = Field(min_length=1, max_length=100)


_CASE_MESHY_IMAGE_REQUIREMENTS = (
    "chassis_empty",
    "included_rgb_fans_installed",
    "rgb_illuminated",
    "no_text_overlay",
    "no_dimension_overlay",
    "no_exploded_view",
    "same_chassis_configuration",
)


def _owner_approved_case_images(case: Case, requested_urls: list[str]) -> list[str]:
    selection = (
        ((case.sourcing_3d_evidence or {}).get("stages") or {})
        .get("product_images", {})
        .get("approved_selection", {})
    )
    model_images = selection.get("model_images")
    if model_images is None:  # Legacy selections used one set for both listing and model photos.
        model_images = selection.get("images") or []
    approved = [item.get("url") for item in model_images if isinstance(item, dict)]
    if selection.get("status") != "approved" or not 1 <= len(approved) <= 4:
        raise HTTPException(status_code=409, detail="Select between one and four separate 3D reference pictures before generating the model")
    if requested_urls != approved:
        raise HTTPException(status_code=409, detail="Generation must use the owner-approved pictures in their approved order")
    return approved


@router.get("/cases/{case_id}/generate-status")
async def get_case_generation_status(
    case_id: int,
    request_id: str,
    db: AsyncSession = Depends(get_db),
):
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    generation = (((case.sourcing_3d_evidence or {}).get("stages") or {}).get("meshy_generation") or {})
    if generation.get("request_id") != request_id:
        return {"request_id": request_id, "progress": 0, "task_status": "STARTING"}
    return {
        "request_id": request_id,
        "progress": max(0, min(100, int(generation.get("progress") or 0))),
        "task_status": generation.get("task_status", "STARTING"),
    }


@router.post("/cases/{case_id}/generate")
async def generate_case_asset(
    case_id: int,
    body: CaseMeshyGenerate,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate an exact-case draft only after its sourcing funnel is exhausted.

    The result deliberately remains a non-active MESHY_DRAFT. It must pass the
    ten-at-a-time owner review, provenance review and dimensional validation
    before the storefront can serve it.
    """
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    stages = (case.sourcing_3d_evidence or {}).get("stages", {})
    if stages.get("manufacturer_3d", {}).get("status") not in ("not_found", "complete"):
        raise HTTPException(status_code=409, detail="Complete the manufacturer 3D search first")
    if stages.get("third_party_3d", {}).get("status") != "not_found":
        raise HTTPException(status_code=409, detail="Meshy is only allowed when no usable third-party model was found")
    if stages.get("product_images", {}).get("status") not in ("found", "complete"):
        raise HTTPException(status_code=409, detail="An approved product image set is required")

    approved_image_urls = _owner_approved_case_images(case, body.image_urls)
    prior_version = (
        await db.execute(
            select(Component3DAsset.version)
            .where(
                Component3DAsset.subject_type == AssetSubjectType.CASE,
                Component3DAsset.subject_id == case.id,
            )
            .order_by(Component3DAsset.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    version = (prior_version or 0) + 1
    local_glb = _PUBLIC_MEDIA_ROOT / f"catalogue-3d-case-{case.id}-v{version}.glb"
    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    evidence_stages = dict(evidence.get("stages") or {})
    generation = dict(evidence_stages.get("meshy_generation") or {"attempts": []})
    prior_task_id = generation.get("task_id")
    retry_source = local_glb if local_glb.is_file() else next(
        iter(sorted(_ORIGINAL_MEDIA_ROOT.glob(f"{local_glb.stem}-*.original.glb"), reverse=True)),
        None,
    )
    retrying_publish = (
        generation.get("task_status") in ("SUCCEEDED", "PUBLISH_FAILED")
        and bool(prior_task_id)
        and retry_source is not None
    )
    if retrying_publish:
        try:
            _validate_uploaded_glb(retry_source.read_bytes())
        except (OSError, ValueError):
            retrying_publish = False
    generation.update(
        status="searching", request_id=body.request_id,
        progress=100 if retrying_publish else 0,
        task_status="PUBLISHING" if retrying_publish else "STARTING",
        updated_at=datetime.utcnow().isoformat(),
    )
    evidence_stages["meshy_generation"] = generation
    evidence["stages"] = evidence_stages
    case.sourcing_3d_evidence = evidence
    await db.commit()

    async def record_meshy_progress(progress: int, task_status: str, task_id: str | None) -> None:
        current_evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
        current_stages = dict(current_evidence.get("stages") or {})
        current_generation = dict(current_stages.get("meshy_generation") or {"attempts": []})
        current_generation.update(
            status="searching", request_id=body.request_id,
            progress=max(0, min(100, int(progress))), task_status=task_status,
            updated_at=datetime.utcnow().isoformat(),
        )
        if task_id:
            current_generation["task_id"] = task_id
        current_stages["meshy_generation"] = current_generation
        current_evidence["stages"] = current_stages
        case.sourcing_3d_evidence = current_evidence
        await db.commit()

    if retrying_publish:
        # Meshy already succeeded. Reuse its preserved source or local output,
        # run the optimizer, and retry publication without another paid task.
        result_task_id = str(prior_task_id)
        thumbnail_url = None
        try:
            source_bytes = retry_source.read_bytes()
            optimized = await persist_optimized_glb(source_bytes, local_glb, _ORIGINAL_MEDIA_ROOT)
            if not await _sync_asset_media(local_glb):
                raise HTTPException(status_code=502, detail="media sync failed")
        except Exception as exc:
            await record_meshy_progress(100, "PUBLISH_FAILED", result_task_id)
            if isinstance(exc, HTTPException):
                raise HTTPException(
                    status_code=502,
                    detail="Meshy already generated this model and its GLB is saved locally. Publishing still failed; retry Generate draft model to resume the saved GLB without running Meshy again.",
                ) from exc
            raise
        stable_glb_url = f"{_PUBLIC_MEDIA_URL}/{local_glb.name}"
        file_size_kb = max(1, optimized.output_bytes // 1024)
    else:
        result = await generate_multi_image_asset(approved_image_urls, progress_callback=record_meshy_progress)
        if result is None:
            await record_meshy_progress(0, "FAILED", None)
            raise HTTPException(status_code=502, detail="Meshy generation failed — check service configuration")
        if result.status != "SUCCEEDED" or not result.glb_url:
            await record_meshy_progress(result.progress or 0, result.status, result.task_id)
            raise HTTPException(status_code=502, detail=f"Meshy task ended as {result.status}")

        result_task_id = result.task_id
        await record_meshy_progress(100, "PUBLISHING", result_task_id)
        try:
            stable_glb_url, file_size_kb = await _store_generated_glb(f"case-{case.id}", version, result.glb_url)
        except HTTPException as exc:
            await record_meshy_progress(100, "PUBLISH_FAILED", result_task_id)
            raise HTTPException(
                status_code=502,
                detail="Meshy generated the model, but publishing its GLB failed. The local GLB was kept; retry Generate draft model to resume publication without running Meshy again.",
            ) from exc
        thumbnail_url = await _store_generated_preview(f"case-{case.id}", version, result.thumbnail_url)

    asset = Component3DAsset(
        subject_type=AssetSubjectType.CASE,
        subject_id=case.id,
        category="case",
        status=Component3DAssetStatus.MESHY_DRAFT,
        version=version,
        glb_ref=stable_glb_url,
        preview_image_ref=thumbnail_url,
        source_image_refs=approved_image_urls,
        file_size_kb=file_size_kb,
        notes=body.notes or (
            f"Amazon bestseller rank #{case.bestseller_rank}; Meshy task {result_task_id}"
            if case.source_site == "Amazon" and case.bestseller_rank
            else f"Priority rank #{case.priority_3d_rank}; Meshy task {result_task_id}"
            if case.priority_3d_rank
            else f"Meshy task {result_task_id}"
        ),
        created_by=getattr(admin, "email", None),
        provenance_status="original-recreation",
        source_name=f"Meshy AI {'single-image' if len(approved_image_urls) == 1 else 'multi-image'} recreation (task {result_task_id})",
        commercial_use_approved=False,
        redistribution_approved=False,
        # Create the one-model review batch atomically with the asset. The
        # browser may disconnect during a long Meshy request, but a completed
        # draft must never be left undiscoverable and unreviewable.
        review_batch_id=str(uuid4()),
    )
    db.add(asset)

    evidence = dict(case.sourcing_3d_evidence or {"schema_version": 1, "stages": {}})
    evidence_stages = dict(evidence.get("stages") or {})
    generation = dict(evidence_stages.get("meshy_generation") or {"attempts": []})
    attempts = list(generation.get("attempts") or [])
    attempts.append({
        "provider": "Meshy",
        "task_id": result_task_id,
        "asset_version": version,
        "source_image_urls": approved_image_urls,
        "generation_mode": "image-to-3d" if len(approved_image_urls) == 1 else "multi-image-to-3d",
        "endpoint": "/openapi/v1/image-to-3d" if len(approved_image_urls) == 1 else "/openapi/v1/multi-image-to-3d",
        "reference_selection_approved": True,
        "texture_reference_urls": approved_image_urls if len(approved_image_urls) > 1 else [],
        # Retain the original primary-view field for existing readers.
        "texture_reference_url": approved_image_urls[0],
        "requires_separate_model_approval": True,
        "recorded_at": datetime.utcnow().isoformat(),
    })
    generation.update(
        status="found", attempts=attempts, request_id=body.request_id,
        progress=100, task_status="SUCCEEDED", updated_at=datetime.utcnow().isoformat(),
    )
    evidence_stages["meshy_generation"] = generation
    evidence["stages"] = evidence_stages
    case.sourcing_3d_evidence = evidence
    case.status = "ready_for_approval"
    await db.commit()
    await db.refresh(asset)
    return _serialize(asset)


@router.post("")
async def create_asset(body: AssetCreate, db: AsyncSession = Depends(get_db)):
    stype = AssetSubjectType(body.subject_type)
    if stype == AssetSubjectType.CATEGORY_GENERIC and not body.category:
        raise HTTPException(status_code=422, detail="category_generic assets require category")
    if stype != AssetSubjectType.CATEGORY_GENERIC and body.subject_id is None:
        raise HTTPException(status_code=422, detail="case/variant assets require subject_id")

    if stype == AssetSubjectType.VARIANT:
        owner = await db.get(CatalogueVariant, body.subject_id)
        if not owner:
            raise HTTPException(404, "Catalogue component not found")
        category, family, _ = await media_members(db, owner, lock=True)
        if category != "case":
            if family.endswith("_unclassified") or category.startswith("os"):
                raise HTTPException(409, "Choose a supported hardware family")
            stype = AssetSubjectType.CATEGORY_GENERIC
            body = body.model_copy(update={"subject_id": None, "category": category, "family_key": family})

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


@router.post("/variants/{variant_id}/upload-glb")
async def upload_variant_glb(
    variant_id: int,
    file: UploadFile = File(...),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload one shared catalogue-variant GLB for Curated and Custom use.

    Catalogue membership is deliberately absent from the asset identity: when
    the same variant belongs to both catalogues, both screens resolve this one
    versioned asset row.
    """
    if not (file.filename or "").lower().endswith(".glb"):
        raise HTTPException(status_code=415, detail="Upload a self-contained .glb model")

    row = (await db.execute(
        select(CatalogueVariant, PlaybookSlot)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .where(CatalogueVariant.id == variant_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Catalogue component not found")
    _variant, slot = row
    media_category, family_key, members = await media_members(db, _variant, lock=True)
    if media_category.startswith("os") or family_key.endswith("_unclassified"):
        raise HTTPException(409, "Choose a supported hardware family before uploading a model")
    media_review = _variant.asset_media_review or {}
    model_image_urls = media_review.get("model_image_urls", media_review.get("image_urls")) or []
    if media_review.get("status") not in {"approved", "auto_included"} or not model_image_urls:
        raise HTTPException(status_code=409, detail="Choose one to four model reference photos before uploading its model")

    content = await file.read(_MAX_GLB_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > _MAX_GLB_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="GLB files must be 100 MB or smaller")
    try:
        _validate_uploaded_glb(content)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    prior_version = (await db.execute(
        select(Component3DAsset.version)
        .where(
            media_asset_filter(media_category, family_key, [v.id for v in members]),
        )
        .order_by(Component3DAsset.version.desc())
        .limit(1)
    )).scalar_one_or_none()
    version = (prior_version or 0) + 1
    filename = f"catalogue-variant-{variant_id}-v{version}-{uuid4().hex[:8]}.glb"
    _PUBLIC_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    public_path = _PUBLIC_MEDIA_ROOT / filename
    try:
        optimized = await persist_optimized_glb(content, public_path, _ORIGINAL_MEDIA_ROOT)
    except GlbOptimizationError as exc:
        raise HTTPException(status_code=422, detail=f"The GLB passed upload validation but could not be safely optimized: {exc}") from exc
    if not await _sync_asset_media(public_path):
        public_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail="The GLB was valid but could not be published to shared media")

    asset = Component3DAsset(
        subject_type=AssetSubjectType.VARIANT if media_category == "case" else AssetSubjectType.CATEGORY_GENERIC,
        subject_id=variant_id if media_category == "case" else None,
        category=media_category,
        family_key=None if media_category == "case" else family_key,
        status=Component3DAssetStatus.CLEANED,
        version=version,
        glb_ref=f"{_PUBLIC_MEDIA_URL}/{filename}",
        source_image_refs=model_image_urls,
        file_size_kb=max(1, optimized.output_bytes // 1024),
        notes="Operator-uploaded GLB; validate scale, orientation, geometry and provenance before activation.",
        created_by=getattr(admin, "email", None) or "admin-upload",
        provenance_status="metadata-only",
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
    # Filter: only include component assets that have both category and glb_ref
    results.extend([_serialize(a) for a in rows if a.category and a.glb_ref])

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
            "status": _case_status_to_asset_status(case.status),
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
    fan_layout_json: dict | None = None
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

    if body.fan_layout_json is not None:
        if asset.subject_type != AssetSubjectType.CASE:
            raise HTTPException(status_code=422, detail="Procedural fan layouts can only be saved on case assets")
        try:
            body.fan_layout_json = FanLayout.model_validate(body.fan_layout_json).model_dump(mode="json")
        except PydanticValidationError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid fan layout: {exc}") from exc

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
        "dimensions_mm", "scale_validated", "anchor_manifest_json", "fan_layout_json", "notes",
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
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Use the shared durable job/cache rather than submitting a second paid task."""
    rows = (await db.execute(select(CatalogueVariant, Listing).join(
        Listing, Listing.id == CatalogueVariant.listing_id).join(
        PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id).where(
        CatalogueVariant.curated_for_builds.is_(True),
        CatalogueVariant.status.in_(("active", "pending_review")),
        PlaybookSlot.slot_type.in_(component_slot_types(category)),
    ).order_by(CatalogueVariant.id))).all()
    owner = next((v for v, listing in rows if media_family(category, listing.title) == family_key
        and not (listing.raw_specs or {}).get("catalogue_deleted")), None)
    if owner is None:
        raise HTTPException(404, "No curated component belongs to this hardware family")
    return await generate_variant_asset(owner.id, VariantMeshyGenerate(), background_tasks, admin, db)
