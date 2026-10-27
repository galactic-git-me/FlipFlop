"""Resolve exact case models and shared representative hardware family models."""
from sqlalchemy import select

from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.component_3d_asset import AssetSubjectType, Component3DAsset, Component3DAssetStatus
from app.services.curated_media import media_urls
from app.models.listing import Listing
from app.services.component_media_identity import media_key


def component_slot_type(slot_type):
    return "storage" if slot_type == "storage_secondary" else slot_type


def component_slot_types(slot_type):
    return ("storage", "storage_secondary") if component_slot_type(slot_type) == "storage" else (slot_type,)


def _model_images(variant: CatalogueVariant) -> list[str]:
    media = variant.asset_media_review or {}
    selected = media.get("model_image_urls") or (
        media.get("image_urls") if len(media.get("image_urls") or []) <= 4 else []
    )
    return media_urls(selected)


def approved_model_photos(variant) -> list[str]:
    """Use a shared main-photo approval without changing existing model refs."""
    media = variant.asset_media_review or {}
    main_photo = media.get("main_photo_approved_url")
    from app.config import get_settings
    local_owned = (get_settings().app_env == "dev" and isinstance(main_photo, str)
        and main_photo.startswith("http://127.0.0.1:4311/api/uploads/catalogue-photos/"))
    if (media.get("status") in {"approved", "auto_included"}
            and media.get("main_photo_approved_by")
            and isinstance(main_photo, str) and (main_photo.startswith("https://") or local_owned)):
        return media_urls([main_photo])
    images = media.get("model_image_urls")
    if (media.get("status") not in {"approved", "auto_included"}
            or not media.get("model_references_selected_by")
            or not isinstance(images, list) or not 1 <= len(images) <= 4
            or not all(isinstance(url, str) and url.startswith("https://") for url in images)
            or len(set(images)) != len(images)):
        return []
    return media_urls(images)


async def final_assets_by_variant(db, variants: list[CatalogueVariant]) -> dict[int, Component3DAsset]:
    """Return approved family models; cases retain exact listing/photo matching."""
    if not variants:
        return {}
    # Family lookup needs identity only. Loading complete listings once per
    # variant duplicates large source captures across the whole catalogue.
    aliases = (await db.execute(select(CatalogueVariant.id, Listing.id, Listing.title,
        PlaybookSlot.slot_type, Listing.raw_specs['catalogue_deleted'])
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .join(Listing, Listing.id == CatalogueVariant.listing_id))).all()
    keys = {variant_id: media_key(category, title, listing_id)
        for variant_id, listing_id, title, category, deleted in aliases if not deleted}
    assets = (await db.execute(select(Component3DAsset).where(
        Component3DAsset.status == Component3DAssetStatus.FINAL,
        Component3DAsset.is_active.is_(True),
        Component3DAsset.glb_ref.is_not(None),
    ).order_by(Component3DAsset.version.desc(), Component3DAsset.id.desc()))).scalars().all()
    by_key = {}
    # Explicit family assets take precedence over retained legacy product assets.
    assets.sort(key=lambda a: a.subject_type != AssetSubjectType.CATEGORY_GENERIC)
    for asset in assets:
        key = ((asset.category, asset.family_key) if asset.subject_type == AssetSubjectType.CATEGORY_GENERIC
            else keys.get(asset.subject_id) if asset.subject_type == AssetSubjectType.VARIANT else None)
        if key and not key[1].endswith("_unclassified"):
            by_key.setdefault(key, []).append(asset)
    result = {}
    for variant in variants:
        key = keys.get(variant.id)
        if variant.status != "active" or not key:
            continue
        candidates = by_key.get(key, [])
        if key[0] == "case":
            media = variant.asset_media_review or {}
            candidates = [a for a in candidates if media.get("status") in {"approved", "auto_included"}
                and _model_images(variant) and a.source_image_refs == _model_images(variant)]
        if candidates:
            result[variant.id] = candidates[0]
    return result
