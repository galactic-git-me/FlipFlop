"""A bounded-query main-photo inventory shared by the grid and bulk approval."""
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.component_3d_asset import Component3DAsset, AssetSubjectType, Component3DAssetStatus
from app.services.curated_media import media_urls
from app.services.component_media_identity import media_key
from app.config import get_settings


async def catalogue_photo_inventory(db: AsyncSession, selected_ids: list[int] | None = None) -> list[dict]:
    query = select(CatalogueVariant, PlaybookSlot.slot_type).join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id).where(
        CatalogueVariant.curated_for_builds.is_(True),
        ~PlaybookSlot.slot_type.in_(("os", "os_secondary")),
        CatalogueVariant.status.in_(("active", "pending_review")),
    )
    if selected_ids is not None:
        query = query.where(CatalogueVariant.listing_id.in_(select(CatalogueVariant.listing_id).where(CatalogueVariant.id.in_(selected_ids))))
    variants = (await db.execute(query.order_by(CatalogueVariant.id))).all()
    if not variants:
        return []
    listings = {item.id: item for item in (await db.execute(select(Listing).where(Listing.id.in_({variant.listing_id for variant, _ in variants})))).scalars()}
    groups: dict[tuple[int, str], list] = {}
    for variant, category in variants:
        if (listings[variant.listing_id].raw_specs or {}).get("catalogue_deleted"):
            continue
        groups.setdefault((variant.listing_id, "storage" if category == "storage_secondary" else category), []).append(variant)
    main_photos, galleries, bestseller_keys, scorer_ids = {}, {}, {}, {}
    for (listing_id, category), aliases in groups.items():
        listing = listings[listing_id]
        specs = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
        best = specs.get("bestseller") or {}
        values = list(listing.image_urls or [])
        values.extend(item.get("url") for item in specs.get("catalogue_imported_photos", []))
        review = aliases[0].asset_media_review or {}
        if review.get("media_scope") == "family":
            values.extend([review.get("family_selected_photo_url"), review.get("main_photo_approved_url"), *(review.get("image_urls") or [])])
        for key in ("playbook_product_capture", "playbook_amazon_catalog_capture"):
            capture = specs.get(key) or {}
            if capture.get("url") == listing.url:
                values.extend(capture.get("product_image_urls") or [])
        images = media_urls(values)
        galleries[(listing_id, category)] = images
        main_photos[(listing_id, category)] = images[0] if images else None
        if best.get("asin"):
            bestseller_keys[(listing_id, category)] = (str(best.get("category") or category), str(best["asin"]))
        if listing.external_id:
            external_id = listing.external_id
            if external_id.startswith("amazon-bestseller:"):
                external_id = external_id.split(":", 1)[1]
            scorer_ids[(listing_id, category)] = external_id.split("|", 1)[-1] if external_id.startswith("ebay_v1|") else external_id
    if bestseller_keys:
        rows = (await db.execute(select(AmazonBestsellerObservation).where(
            AmazonBestsellerObservation.asin.in_({asin for _, asin in bestseller_keys.values()})
        ).distinct(AmazonBestsellerObservation.category, AmazonBestsellerObservation.asin).order_by(
            AmazonBestsellerObservation.category, AmazonBestsellerObservation.asin,
            AmazonBestsellerObservation.captured_at.desc(), AmazonBestsellerObservation.id.desc(),
        ))).scalars().all()
        by_product = {(row.category, row.asin): row for row in rows}
        for key, identity in bestseller_keys.items():
            row = by_product.get(identity)
            if row:
                images = media_urls([row.image_url, *((row.product_capture or {}).get("product_image_urls") or [])])
                galleries[key] = media_urls([*galleries[key], *images])
                main_photos[key] = main_photos[key] or (images[0] if images else None)
    if bestseller_keys:
        # Rank snapshots often have no gallery; retain the last captured exact-ASIN
        # product gallery rather than letting a newer empty snapshot erase it.
        captured = (await db.execute(text("""
            SELECT DISTINCT ON (category, asin) category, asin, product_capture
            FROM amazon_bestseller_observations
            WHERE asin = ANY(:asins)
              AND jsonb_typeof(product_capture::jsonb -> 'product_image_urls') = 'array'
              AND jsonb_array_length(product_capture::jsonb -> 'product_image_urls') > 0
            ORDER BY category, asin, captured_at DESC, id DESC
        """), {"asins": list({asin for _, asin in bestseller_keys.values()})})).mappings().all()
        by_capture = {(row['category'], row['asin']): row['product_capture'] for row in captured}
        for key, identity in bestseller_keys.items():
            capture = by_capture.get(identity) or {}
            galleries[key] = media_urls([*galleries[key], *(capture.get('product_image_urls') or [])])
    if scorer_ids:
        rows = (await db.execute(select(GemRadarScoredListing).where(
            GemRadarScoredListing.listing_id.in_(set(scorer_ids.values()))
        ).distinct(GemRadarScoredListing.listing_id).order_by(
            GemRadarScoredListing.listing_id, GemRadarScoredListing.scored_at.desc(), GemRadarScoredListing.id.desc(),
        ))).scalars().all()
        by_source = {row.listing_id: row for row in rows}
        for key, source_id in scorer_ids.items():
            if source_id in by_source:
                row = by_source[source_id]
                images = media_urls([row.image_url, *(row.image_urls or [])])
                galleries[key] = media_urls([*galleries[key], *images])
                main_photos[key] = main_photos[key] or (images[0] if images else None)
        observations = (await db.execute(select(GemRadarListingObservation).where(
            GemRadarListingObservation.listing_id.in_(set(scorer_ids.values()))
        ).distinct(GemRadarListingObservation.listing_id).order_by(
            GemRadarListingObservation.listing_id, GemRadarListingObservation.observed_at.desc(), GemRadarListingObservation.id.desc(),
        ))).scalars().all()
        by_source = {row.listing_id: row for row in observations}
        for key, source_id in scorer_ids.items():
            row = by_source.get(source_id)
            if row:
                galleries[key] = media_urls([*galleries[key], row.image_url, *(row.image_urls or [])])
    assets = (await db.execute(select(Component3DAsset, CatalogueVariant.listing_id, PlaybookSlot.slot_type).join(
        CatalogueVariant, Component3DAsset.subject_id == CatalogueVariant.id,
    ).join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id).where(
        Component3DAsset.subject_type == AssetSubjectType.VARIANT,
        CatalogueVariant.listing_id.in_(listings),
        Component3DAsset.status != Component3DAssetStatus.REJECTED,
    ).order_by(Component3DAsset.version.desc(), Component3DAsset.id.desc()))).all()
    by_component = {}
    for asset, listing_id, category in assets:
        by_component.setdefault((listing_id, "storage" if category == "storage_secondary" else category), []).append(asset)
    result = []
    for (listing_id, category), aliases in groups.items():
        listing = listings[listing_id]; photo = main_photos[(listing_id, category)]
        images = galleries[(listing_id, category)]
        approved_url = next(((alias.asset_media_review or {}).get('main_photo_approved_url') for alias in aliases
            if (alias.asset_media_review or {}).get('main_photo_approved_url') in images), None)
        chosen = (aliases[0].asset_media_review or {}).get("family_selected_photo_url") or ((listing.raw_specs or {}).get("catalogue_selected_photo") or {}).get("url")
        photo = (chosen if chosen in images else None) or approved_url or photo or (images[0] if images else None)
        candidates = by_component.get((listing_id, category), [])
        asset = next((item for item in candidates if item.is_active and item.status == Component3DAssetStatus.FINAL), next((item for item in candidates if item.glb_ref), candidates[0] if candidates else None))
        result.append({
            "variant_id": aliases[0].id, "variant_ids": [alias.id for alias in aliases], "listing_id": listing_id,
            "title": listing.title, "category": category, "main_photo_url": photo,
            "listing_image_urls": images,
            "range_reason": (listing.raw_specs or {}).get("curated_range"),
            "main_photo_approved": bool(photo and any((alias.asset_media_review or {}).get("main_photo_approved_url") == photo for alias in aliases)),
            "curated_for_builds": any(alias.curated_for_builds for alias in aliases),
            "custom_for_builds": False,
            "automatic_media_preparation_enabled": get_settings().app_env == "dev",
            "asset_media_review": aliases[0].asset_media_review,
            "asset": {"id": asset.id, "status": asset.status.value, "review_decision": asset.review_decision, "is_active": asset.is_active, "glb_ref": asset.glb_ref, "review_batch_id": asset.review_batch_id} if asset else None,
        })
    from app.services.component_media_identity import group_media_inventory
    family_assets = (await db.execute(select(Component3DAsset).where(
        Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
        Component3DAsset.status != Component3DAssetStatus.REJECTED,
    ).order_by(Component3DAsset.version.desc(), Component3DAsset.id.desc()))).scalars().all()
    return group_media_inventory(result, [{"id": a.id, "status": a.status.value, "review_decision": a.review_decision, "is_active": a.is_active,
        "glb_ref": a.glb_ref, "category": a.category, "family_key": a.family_key, "review_batch_id": a.review_batch_id} for a in family_assets])


async def catalogue_generation_queue(db: AsyncSession) -> list[dict]:
    """Return only generated catalogue jobs, without assembling photo/sales galleries."""
    rows = (await db.execute(
        select(CatalogueVariant, Listing.title, Listing.id, PlaybookSlot.slot_type)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .join(PlaybookSlot, PlaybookSlot.id == CatalogueVariant.slot_id)
        .where(
            CatalogueVariant.curated_for_builds.is_(True),
            CatalogueVariant.status.in_(("active", "pending_review")),
            ~PlaybookSlot.slot_type.in_(("os", "os_secondary")),
        )
        .order_by(CatalogueVariant.id)
    )).all()
    if not rows:
        return []

    variants = [variant for variant, _, _, _ in rows]
    variant_ids = [variant.id for variant in variants]
    assets = (await db.execute(select(Component3DAsset).where(
        Component3DAsset.status != Component3DAssetStatus.REJECTED,
        or_(
            (Component3DAsset.subject_type == AssetSubjectType.VARIANT)
            & Component3DAsset.subject_id.in_(variant_ids),
            Component3DAsset.subject_type == AssetSubjectType.CATEGORY_GENERIC,
        ),
    ).order_by(Component3DAsset.version.desc(), Component3DAsset.id.desc()))).scalars().all()
    variant_assets: dict[int, Component3DAsset] = {}
    family_assets: dict[tuple[str | None, str | None], Component3DAsset] = {}
    for asset in assets:
        if asset.subject_type == AssetSubjectType.VARIANT and asset.subject_id is not None:
            variant_assets.setdefault(asset.subject_id, asset)
        elif asset.subject_type == AssetSubjectType.CATEGORY_GENERIC:
            family_assets.setdefault((asset.category, asset.family_key), asset)

    result: list[dict] = []
    seen: set[str] = set()
    for variant, title, listing_id, slot_type in rows:
        review = variant.asset_media_review or {}
        generation = review.get("generation") or {}
        if not generation.get("status"):
            continue
        category, family_key = media_key(slot_type, title, listing_id)
        asset = variant_assets.get(variant.id)
        if category != "case":
            asset = family_assets.get((category, family_key)) or asset
        if not asset:
            continue
        task_key = generation.get("task_id") or f"{category}:{family_key}"
        if task_key in seen:
            continue
        seen.add(task_key)
        result.append({
            "variant_id": variant.id,
            "listing_id": listing_id,
            "title": title,
            "category": category,
            "media_family_key": family_key,
            "asset_media_review": review,
            "asset": {
                "id": asset.id,
                "status": asset.status.value,
                "review_decision": asset.review_decision,
                "is_active": asset.is_active,
                "glb_ref": asset.glb_ref,
                "review_batch_id": asset.review_batch_id,
            },
        })
    return result
