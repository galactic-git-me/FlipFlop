"""Cases own exact media; other hardware owns one representative family asset."""
import zlib
from sqlalchemy import and_, or_, select, text
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.models.component_3d_asset import Component3DAsset, AssetSubjectType
from app.services.component_family_classifier import classify_family, RAM_MANUFACTURERS, MOTHERBOARD_MANUFACTURERS

FAMILY_LABELS = {
    "cpu_amd": "AMD Ryzen CPUs", "cpu_amd_threadripper": "AMD Threadripper CPUs",
    "cpu_intel": "Intel CPUs",
    "gpu_nvidia": "NVIDIA GPUs", "gpu_amd": "AMD Radeon GPUs", "gpu_intel": "Intel Arc GPUs",
    **{f"ram_{key}": f"{label} RAM" for key, (label, _) in RAM_MANUFACTURERS.items()},
    "storage_nvme_m2": "NVMe SSDs", "storage_sata_2_5": "SATA SSDs",
    **{f"motherboard_{key}": f"{label} motherboards" for key, (label, _) in MOTHERBOARD_MANUFACTURERS.items()},
    "psu_atx_standard": "ATX power supplies",
    "cooling_air_tower": "Air CPU coolers",
}


def media_family(category, title):
    category = "storage" if category == "storage_secondary" else category
    return None if category == "case" or category.startswith("os") else classify_family(category, title)


def media_key(category, title, listing_id):
    category = "storage" if category == "storage_secondary" else category
    return (category, f"case:{listing_id}" if category == "case" else media_family(category, title) or f"{category}_unclassified")


def family_label(key):
    return FAMILY_LABELS.get(key, key.replace("_", " ").capitalize())


def group_media_inventory(rows, family_assets=()):
    groups = {}
    for row in rows:
        if row["category"].startswith("os"):
            continue
        groups.setdefault(media_key(row["category"], row["title"], row["listing_id"]), []).append(row)
    result = []
    for (category, key), members in groups.items():
        if category == "case":
            result.extend({**row, "media_scope": "product", "product_count": 1} for row in members)
            continue
        owner = next((row for row in members if (row.get("asset_media_review") or {}).get("media_family_key") == key), members[0])
        assets = [a for a in family_assets if a.get("category") == category and a.get("family_key") == key]
        assets.extend(row["asset"] for row in members if row.get("asset"))
        asset = next((a for a in assets if a.get("is_active") and a.get("status") == "final"), next((a for a in assets if a.get("glb_ref")), assets[0] if assets else None))
        result.append({**owner, "title": family_label(key), "sample_product_title": owner["title"],
            "media_scope": "family", "media_family_key": key,
            "product_count": len({row["listing_id"] for row in members}),
            "variant_ids": list(dict.fromkeys(v for row in members for v in row["variant_ids"])),
            "member_listing_ids": list(dict.fromkeys(row["listing_id"] for row in members)),
            "main_photo_approved": bool(owner.get("main_photo_approved") and (owner.get("asset_media_review") or {}).get("media_family_key") == key),
            "asset": asset})
    return sorted(result, key=lambda row: (row["category"], row["title"]))


async def media_members(db, variant, *, lock=False):
    slot = await db.get(PlaybookSlot, variant.slot_id)
    listing = await db.get(Listing, variant.listing_id)
    category, key = media_key(slot.slot_type, listing.title, listing.id)
    if lock:
        number = zlib.crc32(f"{category}:{key}".encode()) & 0x7fffffff
        await db.execute(text("SELECT pg_advisory_xact_lock(61312, :key)"), {"key": number})
    rows = (await db.execute(select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .where(PlaybookSlot.slot_type.in_(("storage", "storage_secondary") if category == "storage" else (category,)))
        .order_by(CatalogueVariant.id))).all()
    members = [v for v, item, s in rows if media_key(s.slot_type, item.title, item.id) == (category, key)
        and not (item.raw_specs or {}).get("catalogue_deleted")]
    if lock and members:
        members = list((await db.execute(select(CatalogueVariant).where(CatalogueVariant.id.in_([v.id for v in members]))
            .order_by(CatalogueVariant.id).with_for_update().execution_options(populate_existing=True))).scalars())
    return category, key, members


def media_asset_filter(category, family_key, variant_ids):
    legacy = and_(Component3DAsset.subject_type == AssetSubjectType.VARIANT,
        Component3DAsset.subject_id.in_(variant_ids))
    if category == "case":
        return legacy
    return or_(legacy, and_(Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
        Component3DAsset.category == category, Component3DAsset.family_key == family_key))


async def inherit_family_media_reviews(db):
    rows = (await db.execute(select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .where(CatalogueVariant.status.in_(("active", "pending_review")))
        .order_by(CatalogueVariant.id))).all()
    groups = {}
    for variant, listing, slot in rows:
        if slot.slot_type == "case" or slot.slot_type.startswith("os") or (listing.raw_specs or {}).get("catalogue_deleted"):
            continue
        groups.setdefault(media_key(slot.slot_type, listing.title, listing.id), []).append(variant)
    count = 0
    for (_, family), members in groups.items():
        review = next((v.asset_media_review for v in members if (v.asset_media_review or {}).get("media_family_key") == family
            and (v.asset_media_review or {}).get("status") in {"approved", "auto_included"}), None)
        if not review:
            continue
        for variant in members:
            if variant.curated_for_builds and variant.asset_media_review != review:
                variant.asset_media_review = dict(review)
                count += 1
    await db.flush()
    return count
