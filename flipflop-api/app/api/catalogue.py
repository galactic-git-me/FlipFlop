"""
Admin API router for catalogue management.

Prefix: /catalogue  (mounted at /api/catalogue/ in main.py)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalogue import CaseCatalogue, CatalogueVariant, PlaybookSlot
from app.models.listing import Classification, Listing
from app.models.gem_radar_cpk_market_price import GemRadarCpkMarketPrice
from app.schemas.catalogue import (
    CaseCatalogueCreate,
    CaseCatalogueOut,
    CaseCatalogueUpdate,
    PlaybookSlotUpdate,
    RejectBody,
)
from app.services.catalogue_service import approve_variant, reject_variant
from app.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/catalogue", tags=["catalogue"], dependencies=[Depends(get_current_admin)])

# This eBay item was confirmed to be a parts-only listing despite Google
# Shopping reporting it as used. Keep the stale cached result out of the
# catalogue until its observation is replaced by a verified condition.
KNOWN_NON_CATALOGUE_LISTING_IDS = {"206450130546"}


@router.get("/review-queue")
async def get_review_queue(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        .where(CatalogueVariant.status == "pending_review")
        .order_by(CatalogueVariant.auto_published_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": v.id,
            "listing_id": v.listing_id,
            "listing_title": l.title,
            "image_url": (l.image_urls[0] if l.image_urls else None),
            "listing_price": l.price,
            "gem_score": l.gem_score,
            "slot_id": v.slot_id,
            "slot_type": s.slot_type,
            "playbook_id": s.playbook_id,
            "tier": v.tier,
            "display_price": v.display_price,
            "auto_published_at": v.auto_published_at,
        }
        for v, l, s in rows
    ]


# IMPORTANT: approve-all MUST come before {variant_id}/approve — FastAPI matches
# routes in declaration order and "approve-all" would be swallowed by the
# {variant_id} pattern if declared second.
@router.post("/variants/approve-all")
async def approve_all_variants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.status == "pending_review")
    )
    variants = result.scalars().all()
    now = datetime.utcnow().isoformat()
    for v in variants:
        v.status = "active"
        v.reviewed_at = now
        v.reviewed_by = "admin-bulk"
    await db.commit()
    return {"approved": len(variants)}


@router.post("/variants/{variant_id}/approve")
async def approve_one(variant_id: int, db: AsyncSession = Depends(get_db)):
    variant = await approve_variant(db, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"id": variant.id, "status": variant.status}


@router.post("/variants/{variant_id}/reject")
async def reject_one(variant_id: int, body: RejectBody, db: AsyncSession = Depends(get_db)):
    variant = await reject_variant(db, variant_id, reason=body.reason)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"id": variant.id, "status": variant.status, "reject_reason": variant.reject_reason}


@router.get("/variants")
async def list_variants(
    status: Optional[str] = Query(None),
    playbook_id: Optional[int] = Query(None),
    slot_type: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(CatalogueVariant, Listing, PlaybookSlot)
        .join(Listing, CatalogueVariant.listing_id == Listing.id)
        .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
        # Catalogue membership is a curated output of gem detection, not a
        # mirror of the raw listings table.  Legacy variants can outlive a
        # listing's classification, so enforce the contract at read time.
        .where(Listing.classification.in_((Classification.gem, Classification.amazing_gem)))
        # The catalogue is a fixed-price sourcing surface. Auctions and
        # classified listings remain available to their own evidence views,
        # but must never appear here, including legacy rows.
        .where(Listing.listing_type == "buy_it_now")
        # Parts/repair-only listings are not sellable component opportunities.
        # Keep null conditions visible for legacy rows, but never expose an
        # explicit for_parts result in the catalogue.
        .where(or_(Listing.condition.is_(None), Listing.condition.notin_(("for_parts", "parts_only", "untested"))))
        .where(~Listing.title.ilike("%for parts%"), ~Listing.title.ilike("%parts only%"), ~Listing.title.ilike("%not working%"), ~Listing.title.ilike("%spares or repair%"))
        .where(~Listing.external_id.ilike("%206450130546%"))
    )
    if status:
        q = q.where(CatalogueVariant.status == status)
    else:
        # "All statuses" on the admin page means all current catalogue
        # opportunities. Hidden rows are retained for audit/history and are
        # available through the explicit Hidden filter, but must not inflate
        # the headline product count or reintroduce stale legacy products.
        q = q.where(CatalogueVariant.status != "hidden")
    if playbook_id:
        q = q.where(PlaybookSlot.playbook_id == playbook_id)
    if slot_type:
        q = q.where(PlaybookSlot.slot_type == slot_type)
    if tier:
        q = q.where(CatalogueVariant.tier == tier)
    result = await db.execute(q.order_by(CatalogueVariant.auto_published_at.desc()))
    rows = result.all()

    # A listing can be attached to one slot in each playbook.  That is useful
    # for playbook management, but the admin catalogue is a listing catalogue:
    # render each physical listing once.  The query is already newest-first,
    # so retaining the first row gives us the freshest catalogue variant.
    unique_rows: dict[int, tuple[CatalogueVariant, Listing, PlaybookSlot]] = {}
    for row in rows:
        listing = row[1]
        unique_rows.setdefault(listing.id, row)
    rows = list(unique_rows.values())

    # Surface the marketplaces/vendors carrying the same hardware fingerprint
    # so the catalogue can show compact cross-channel badges on each card.
    fingerprints = {l.spec_fingerprint for _, l, _ in rows if l.spec_fingerprint}
    channels_by_fingerprint: dict[str, list[str]] = {}
    if fingerprints:
        channel_rows = await db.execute(
            select(Listing.spec_fingerprint, Listing.source_name)
            .where(Listing.spec_fingerprint.in_(fingerprints))
            .distinct()
        )
        for fingerprint, source_name in channel_rows:
            if fingerprint and source_name:
                channels_by_fingerprint.setdefault(fingerprint, []).append(source_name)

    # The legacy catalogue listings use an external-id format such as
    # ``ebay_v1|123456789|...`` while CPK records use the bare eBay item ID.
    # Aggregate the latest demand observation per matched item so the admin
    # catalogue can show CPK evidence without double-counting historical
    # observations.
    ebay_item_ids = {
        l.external_id.split("|")[1]
        for _, l, _ in rows
        if l.external_id.startswith("ebay_v1|") and "|" in l.external_id
    }
    cpk_metrics: dict[str, dict] = {}
    if ebay_item_ids:
        metrics = await db.execute(
            text("""
                WITH latest_observations AS (
                    SELECT DISTINCT ON (listing_id)
                        listing_id, watch_count, best_offer_enabled
                    FROM gem_radar_listing_observations
                    ORDER BY listing_id, observed_at DESC, id DESC
                ), sold_counts AS (
                    SELECT cpk,
                           COUNT(DISTINCT COALESCE(NULLIF(source_url, ''), 'row:' || id::text)) AS sold_count
                    FROM gem_radar_sold_observations
                    WHERE cpk IS NOT NULL
                      AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '90 days'
                    GROUP BY cpk
                ), active_counts AS (
                    SELECT cpk, COUNT(DISTINCT listing_id) AS active_count
                    FROM gem_radar_cpk_listing_price
                    WHERE updated_at >= CURRENT_TIMESTAMP - INTERVAL '14 days'
                      AND price > 0
                    GROUP BY cpk
                )
                SELECT c.cpk,
                       CASE WHEN COUNT(o.watch_count) > 0
                            THEN SUM(o.watch_count) ELSE NULL END AS watch_count,
                       COUNT(*) FILTER (WHERE o.best_offer_enabled) AS offer_count,
                       COALESCE(MAX(sc.sold_count), 0) AS sold_count,
                       COALESCE(MAX(ac.active_count), 0) AS active_count
                FROM gem_radar_listing_cpk c
                JOIN latest_observations o ON o.listing_id = c.listing_id
                LEFT JOIN sold_counts sc ON sc.cpk = c.cpk
                LEFT JOIN active_counts ac ON ac.cpk = c.cpk
                WHERE c.listing_id = ANY(:listing_ids)
                GROUP BY c.cpk
            """),
            {"listing_ids": list(ebay_item_ids)},
        )
        cpk_metrics = {
            row.cpk: {
                "watch_count": row.watch_count,
                "offer_count": row.offer_count,
                "sold_count": row.sold_count,
                "active_count": row.active_count,
            }
            for row in metrics
        }

    listing_cpks = await db.execute(
        text("""
            SELECT listing_id, cpk
            FROM gem_radar_listing_cpk
            WHERE listing_id = ANY(:listing_ids)
        """),
        {"listing_ids": list(ebay_item_ids)},
    ) if ebay_item_ids else []
    cpk_by_item = {row.listing_id: row.cpk for row in listing_cpks}

    review_result = await db.execute(
        text("""
            SELECT DISTINCT ON (listing_id)
                   listing_id, review_average_rating, review_count
            FROM gem_radar_scored_listings
            WHERE listing_id = ANY(:listing_ids)
            ORDER BY listing_id, scored_at DESC NULLS LAST, id DESC
        """),
        {"listing_ids": list(ebay_item_ids)},
    ) if ebay_item_ids else []
    reviews_by_item = {
        row.listing_id: {
            "review_average_rating": row.review_average_rating,
            "review_count": row.review_count,
        }
        for row in review_result
    }

    # Reuse the sourcing dashboard's latest scored decision surface so the
    # catalogue shows the same condition, economics, class, decision and
    # evidence for each retained listing.
    listing_keys = {
        l.external_id.split("|")[1]
        if l.external_id.startswith("ebay_v1|") and "|" in l.external_id
        else l.external_id
        for _, l, _ in rows
    }
    scored_result = await db.execute(
        text("""
            SELECT DISTINCT ON (listing_id)
                   listing_id, cpk, url, condition, delivered_price,
                   market_lower_price, market_median_price, market_upper_price,
                   pct_offset, classification, decision, confidence_band,
                   evidence_status, evidence_reason, deal_score,
                   delivery_text, delivery_postcode
            FROM gem_radar_scored_listings
            WHERE listing_id = ANY(:listing_ids)
            ORDER BY listing_id, scored_at DESC NULLS LAST, id DESC
        """),
        {"listing_ids": list(listing_keys)},
    ) if listing_keys else []
    scored_by_item = {row.listing_id: row for row in scored_result}
    # The CPK bridge is not limited to legacy eBay external IDs; use the
    # scored row as a fallback so Amazon/Vinted/other marketplace listings can
    # inherit the same product-level review evidence too.
    for listing_id, scored_row in scored_by_item.items():
        if scored_row.cpk:
            cpk_by_item.setdefault(listing_id, scored_row.cpk)

    # Product reviews are shared across equivalent marketplace listings when
    # they resolve to the same CPK. Prefer a non-eBay retailer's review as it
    # is independent of the source listing being displayed.
    cpk_review_result = await db.execute(
        text("""
            SELECT DISTINCT ON (listing_id)
                   listing_id, cpk, source, review_average_rating, review_count,
                   scored_at, id
            FROM gem_radar_scored_listings
            WHERE cpk IS NOT NULL
              AND (review_average_rating IS NOT NULL OR review_count IS NOT NULL)
            ORDER BY listing_id, scored_at DESC NULLS LAST, id DESC
        """)
    )
    reviews_by_vendor: dict[tuple[str, str], tuple[float | None, int | None]] = {}
    for row in cpk_review_result:
        key = (row.cpk, (row.source or "unknown").lower())
        current = reviews_by_vendor.get(key)
        if current is None or (row.review_count or 0) > (current[1] or 0):
            reviews_by_vendor[key] = (row.review_average_rating, row.review_count)
    reviews_by_cpk: dict[str, tuple[float | None, int | None]] = {}
    for (cpk, _vendor), (rating, count) in reviews_by_vendor.items():
        old_rating, old_count = reviews_by_cpk.get(cpk, (None, None))
        if rating is not None and count:
            if old_rating is not None and old_count:
                reviews_by_cpk[cpk] = ((old_rating * old_count + rating * count) / (old_count + count), old_count + count)
            else:
                reviews_by_cpk[cpk] = (rating, (old_count or 0) + count)
        elif count:
            reviews_by_cpk[cpk] = (old_rating, (old_count or 0) + count)

    bestseller_result = await db.execute(
        text("""
            SELECT DISTINCT ON (cpk)
                   cpk, category, list_name, rank, captured_at
            FROM amazon_bestseller_observations
            WHERE cpk IS NOT NULL
            ORDER BY cpk, captured_at DESC, id DESC
        """)
    )
    bestseller_by_cpk = {
        row.cpk: {
            "amazon_bestseller_rank": row.rank,
            "amazon_bestseller_list": row.list_name,
            "amazon_bestseller_captured_at": row.captured_at.isoformat() if row.captured_at else None,
        }
        for row in bestseller_result
    }

    # Older Listing rows may have lost their denormalised image array during
    # a refresh, while the scraper still retained the image on its sighting
    # ledger.  Use the latest non-empty captured image as a read-time repair;
    # never substitute a shared category image.
    observation_images = await db.execute(
        text("""
            SELECT DISTINCT ON (listing_id) listing_id, image_url
            FROM gem_radar_listing_observations
            WHERE listing_id = ANY(:listing_ids)
              AND image_url IS NOT NULL AND image_url <> ''
            ORDER BY listing_id, observed_at DESC, id DESC
        """),
        {"listing_ids": list(listing_keys)},
    ) if listing_keys else []
    observation_image_by_item = {row.listing_id: row.image_url for row in observation_images}

    def item_key(listing: Listing) -> str:
        return (
            listing.external_id.split("|")[1]
            if listing.external_id.startswith("ebay_v1|") and "|" in listing.external_id
            else listing.external_id
        )

    def scored(listing: Listing):
        return scored_by_item.get(item_key(listing))

    market_prices_by_cpk = {}
    cpk_ids = {cpk for cpk in cpk_by_item.values() if cpk}
    if cpk_ids:
        market_result = await db.execute(
            select(GemRadarCpkMarketPrice).where(GemRadarCpkMarketPrice.cpk.in_(cpk_ids))
        )
        market_prices_by_cpk = {row.cpk: row for row in market_result.scalars().all()}

    def cpk_metrics_for(listing: Listing) -> dict:
        return cpk_metrics.get(cpk_by_item.get(item_key(listing)), {})

    def sell_through_rate(sold_count: int | None, active_count: int | None) -> float | None:
        sold = max(0, sold_count or 0)
        active = max(0, active_count or 0)
        total = sold + active
        return None if total == 0 else round(sold / total * 100, 1)

    return [
        {
            "id": v.id,
            "listing_id": v.listing_id,
            "listing_title": l.title,
            "image_url": (
                (l.image_urls[0] if l.image_urls else None)
                or getattr(scored(l), "image_url", None)
                or observation_image_by_item.get(item_key(l))
            ),
            "source_name": l.source_name,
            "channel_sources": channels_by_fingerprint.get(l.spec_fingerprint, [l.source_name]),
            "price_history_listing_id": l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else l.external_id,
            # Fall back to the listing's retained resale band when its scored
            # row has been archived.  These values are already computed from
            # the market evidence captured for the listing.
            "market_lower_price": getattr(market_prices_by_cpk.get(cpk_by_item.get(item_key(l))), "min_price", None) or l.resale_low,
            "market_median_price": getattr(market_prices_by_cpk.get(cpk_by_item.get(item_key(l))), "median_price", None) or l.estimated_resale,
            "market_upper_price": getattr(market_prices_by_cpk.get(cpk_by_item.get(item_key(l))), "max_price", None) or l.resale_high,
            # A catalogue variant can exist before its first scored row (or
            # after the scored row has been archived). Do not fail the entire
            # catalogue response when that optional enrichment is absent.
            "url": (getattr(scored(l), "url", None) or l.url),
            "condition": (getattr(scored(l), "condition", None) or l.condition),
            "delivered_price": (getattr(scored(l), "delivered_price", None) or l.price),
            "delivery_text": getattr(scored(l), "delivery_text", None),
            "delivery_postcode": getattr(scored(l), "delivery_postcode", None),
            "scored_market_lower_price": getattr(scored(l), "market_lower_price", None) or l.resale_low,
            "scored_market_median_price": getattr(scored(l), "market_median_price", None) or l.estimated_resale,
            "scored_market_upper_price": getattr(scored(l), "market_upper_price", None) or l.resale_high,
            "pct_offset": getattr(scored(l), "pct_offset", None),
            "classification": getattr(scored(l), "classification", None) or str(l.classification.value if hasattr(l.classification, "value") else l.classification).upper(),
            "decision": getattr(scored(l), "decision", None),
            "confidence": getattr(scored(l), "confidence_band", None),
            "deal_score": getattr(scored(l), "deal_score", None),
            "evidence_status": getattr(scored(l), "evidence_status", None),
            "evidence_reason": getattr(scored(l), "evidence_reason", None),
            "slot_type": s.slot_type,
            "playbook_id": s.playbook_id,
            "status": v.status,
            "tier": v.tier,
            "display_price": v.display_price,
            "gem_score": l.gem_score,
            "cpk": cpk_by_item.get(l.external_id.split("|")[1]) if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else None,
            "watch_count": cpk_metrics.get(cpk_by_item.get(l.external_id.split("|")[1]), {}).get("watch_count") if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else None,
            "offer_count": cpk_metrics.get(cpk_by_item.get(l.external_id.split("|")[1]), {}).get("offer_count") if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else None,
            "sold_count": cpk_metrics.get(cpk_by_item.get(l.external_id.split("|")[1]), {}).get("sold_count") if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else None,
            "active_count": cpk_metrics_for(l).get("active_count"),
            "sell_through_rate": sell_through_rate(cpk_metrics_for(l).get("sold_count"), cpk_metrics_for(l).get("active_count")),
            "review_average_rating": (reviews_by_cpk.get(cpk_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else "")) or (reviews_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else "", {}).get("review_average_rating"), reviews_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else "", {}).get("review_count")))[0],
            "review_count": (reviews_by_cpk.get(cpk_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else "")) or (reviews_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else "", {}).get("review_average_rating"), reviews_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else "", {}).get("review_count")))[1],
            **bestseller_by_cpk.get(cpk_by_item.get(l.external_id.split("|")[1] if l.external_id.startswith("ebay_v1|") and "|" in l.external_id else ""), {
                "amazon_bestseller_rank": None,
                "amazon_bestseller_list": None,
                "amazon_bestseller_captured_at": None,
            }),
            "consecutive_misses": v.consecutive_misses,
            "last_seen_at": v.last_seen_at,
            "auto_published_at": v.auto_published_at,
            "reviewed_at": v.reviewed_at,
            "reject_reason": v.reject_reason,
        }
        for v, l, s in sorted(rows, key=lambda row: (row[1].gem_score or 0), reverse=True)
    ]


@router.patch("/variants/{variant_id}/toggle-status")
async def toggle_variant_status(variant_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CatalogueVariant).where(CatalogueVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    if variant.status not in ("active", "hidden"):
        raise HTTPException(status_code=400, detail="Can only toggle active or hidden variants")
    variant.status = "hidden" if variant.status == "active" else "active"
    await db.commit()
    return {"id": variant.id, "status": variant.status}


@router.get("/cases", response_model=list[CaseCatalogueOut])
async def list_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CaseCatalogue).order_by(CaseCatalogue.brand, CaseCatalogue.name)
    )
    return result.scalars().all()


@router.post("/cases", response_model=CaseCatalogueOut, status_code=201)
async def create_case(body: CaseCatalogueCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow().isoformat()
    case = CaseCatalogue(**body.model_dump(), created_at=now, updated_at=now)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.patch("/cases/{case_id}", response_model=CaseCatalogueOut)
async def update_case(case_id: int, body: CaseCatalogueUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CaseCatalogue).where(CaseCatalogue.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    case.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    await db.refresh(case)
    return case


@router.get("/slots")
async def list_slots(
    playbook_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)
):
    q = select(PlaybookSlot)
    if playbook_id:
        q = q.where(PlaybookSlot.playbook_id == playbook_id)
    result = await db.execute(q.order_by(PlaybookSlot.playbook_id, PlaybookSlot.slot_type))
    return [
        {
            "id": s.id,
            "playbook_id": s.playbook_id,
            "slot_type": s.slot_type,
            "is_customer_visible": s.is_customer_visible,
            "tier_names": s.tier_names,
            "score_band_budget": s.score_band_budget,
            "score_band_mid": s.score_band_mid,
            "score_band_high": s.score_band_high,
        }
        for s in result.scalars().all()
    ]


@router.patch("/slots/{slot_id}")
async def update_slot(slot_id: int, body: PlaybookSlotUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PlaybookSlot).where(PlaybookSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)
    slot.updated_at = datetime.utcnow().isoformat()
    await db.commit()
    return {"id": slot.id, "slot_type": slot.slot_type, "updated": True}
