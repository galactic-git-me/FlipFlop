"""
Relist/recreate + deferred-listing scheduler jobs — Algorithm Playbook rows
1, 2, 3, 5, 6, 9, 36 (freshness/recreate cycle) and the deferred-first-publish
half of row 3.

Two jobs, both registered on the APScheduler instance in app/workers/scheduler.py:

  run_deferred_publish_job() — fires listings whose chosen deferred_publish_at
    has arrived and haven't gone live yet (row 3's scheduler half).

  run_recreate_cycle_job() — ends and republishes listings whose randomized
    ~7-day timer is due: reworded title, swapped main image, a price
    step-down (folded row 6 in, per the playbook spec), landing at a new
    randomized time inside the build's traffic band, never the same clock
    hour twice (rows 1, 2, 5, 9). Row 36 (steady cadence, not bursts) is
    enforced by construction: each flip's own randomized per-cycle timer is
    independent, so cycles naturally spread out rather than batching.

Both use app.services.ebay_oauth.get_valid_access_token(db), which transparently
refreshes the seller's OAuth token or returns None if "Connect eBay" (Settings >
Seller Policies) has never been completed. Either way, the internal state
(recreate_cycle_count, next_recreate_at, listing_price step-down, etc.) still
advances correctly so the rest of the app stays consistent; only the live eBay
API call is skipped and clearly logged when no token is available.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.services import pricing_engine
from app.services.traffic_bands import next_slot_datetime, jittered_recreate_slot, DEFAULT_BAND

log = structlog.get_logger(__name__)

RECREATE_INTERVAL_DAYS = 7
RECREATE_JITTER_DAYS = 1


async def run_deferred_publish_job() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.flip import Flip, FlipStage

    published, skipped_no_token, errors = 0, 0, 0
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Flip).where(
                Flip.stage == FlipStage.ready_for_sale,
                Flip.deferred_publish_at.isnot(None),
                Flip.deferred_publish_at <= now,
                Flip.listed_at.is_(None),
            )
        )
        due = result.scalars().all()

        for flip in due:
            try:
                ok = await publish_flip_now(flip, db)
                if ok:
                    # Commit immediately after each successful eBay post, not
                    # once at the end of the loop — otherwise a crash between
                    # this flip's create-listing call succeeding and the batch
                    # commit leaves flip.listed_at NULL, so the next run's
                    # query selects it again and posts it to eBay a second
                    # time, creating a real duplicate live listing.
                    await db.commit()
                    published += 1
                else:
                    skipped_no_token += 1
            except Exception as exc:
                errors += 1
                log.warning("recreate_cycle.publish_failed", flip_id=flip.id, error=str(exc))
                await db.rollback()

    return {"published": published, "skipped_no_token": skipped_no_token, "errors": errors}


async def run_recreate_cycle_job() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.flip import Flip, FlipStage

    recreated, floor_hit, errors = 0, 0, 0
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Flip).where(
                Flip.stage == FlipStage.ready_for_sale,
                Flip.listed_at.isnot(None),
                Flip.next_recreate_at.isnot(None),
                Flip.next_recreate_at <= now,
            )
        )
        due = result.scalars().all()

        for flip in due:
            try:
                await _recreate_flip(flip, db)
                # Commit immediately, not once at the end of the loop — same
                # reasoning as run_deferred_publish_job above: _recreate_flip
                # calls the real eBay create-listing API, so a crash before a
                # batched commit would leave next_recreate_at unadvanced and
                # get this flip re-processed (and re-posted to eBay) on the
                # next run.
                await db.commit()
                recreated += 1
                if flip.price_floor_hit_review_needed:
                    floor_hit += 1
            except Exception as exc:
                errors += 1
                log.warning("recreate_cycle.recreate_failed", flip_id=flip.id, error=str(exc))
                # Roll back this flip's partial state (price/title mutations
                # made before the failure) rather than letting the next
                # iteration's commit silently persist it half-applied — a
                # committed price step-down with no advanced next_recreate_at
                # would otherwise cause this flip to be re-selected and
                # re-processed (repeated price drops, repeated eBay posts)
                # on every subsequent run.
                await db.rollback()

    return {"recreated": recreated, "floor_hit_review_needed": floor_hit, "errors": errors}


async def publish_flip_now(flip, db) -> bool:
    """
    Shared by the deferred-publish job (when its chosen time arrives) and the
    manual "Publish now" endpoint (POST /flips/{id}/publish-now) — actually
    posts to eBay via _publish_flip, then starts the flip's recreate-cycle
    clock. Returns True only if the listing genuinely went live.
    """
    ok = await _publish_flip(flip, db)
    if ok:
        now = datetime.utcnow()
        flip.listed_at = now
        flip.next_recreate_at = jittered_recreate_slot(
            flip.traffic_band or DEFAULT_BAND, now,
            interval_days=RECREATE_INTERVAL_DAYS, jitter_days=RECREATE_JITTER_DAYS,
        )
    return ok


async def _publish_flip(flip, db) -> bool:
    """Posts a flip's listing to eBay right now. Returns True if actually posted."""
    from app.services import ebay_oauth

    settings = get_settings()
    token = await ebay_oauth.get_valid_access_token(db)
    if not token:
        log.info("recreate_cycle.publish_skipped_no_token", flip_id=flip.id)
        return False

    from app.services.ebay_listing_poster import post_flip_to_ebay

    result = await post_flip_to_ebay(
        title=flip.generated_title or f"Flip #{flip.id}",
        description=flip.generated_description or "",
        price=flip.listing_price or flip.current_estimated_resale or flip.total_cost,
        access_token=token,
        environment=settings.ebay_environment,
    )
    if result.get("success"):
        flip.ebay_listing_id = result.get("listing_id")
        flip.ebay_listing_url = result.get("url")
        return True

    log.warning("recreate_cycle.publish_ebay_error", flip_id=flip.id, error=result.get("error"))
    return False


async def _recreate_flip(flip, db) -> None:
    """Rows 1/2/5/6/9: end current listing, generate a fresh title/image, step price down, reschedule."""
    from app.models.listing import Listing
    from app.services import ai_service

    listing = await db.get(Listing, flip.listing_id)

    # Row 19/20 re-anchor: always fresh sold-comp data, never carried forward stale.
    await pricing_engine.recalculate_pricing(flip, db)

    current_price = flip.listing_price or flip.total_cost
    new_price, floor_hit = pricing_engine.compute_next_drop_price(
        current_price=current_price,
        sold_comp_target=flip.sold_comp_target,
        price_floor=flip.price_floor or pricing_engine.compute_price_floor(flip.total_cost),
        step_pct=flip.recreate_price_step_pct,
    )
    flip.listing_price = new_price
    flip.price_floor_hit_review_needed = floor_hit

    # Row 5: reword title, swap (not crop) the main image.
    try:
        titles, description = await ai_service.generate_listing_content(
            cpu=listing.cpu if listing else None,
            ram_gb=listing.ram_gb if listing else None,
            ram_type=listing.ram_type if listing else None,
            storage_gb=listing.storage_gb if listing else None,
            storage_type=listing.storage_type if listing else None,
            gpu=listing.gpu if listing else None,
            location=listing.location if listing else None,
        )
        if titles:
            reworded = next((t for t in titles if t != flip.generated_title), titles[0])
            flip.generated_title = reworded
            flip.generated_description = description
    except Exception as exc:
        log.warning("recreate_cycle.reword_failed", flip_id=flip.id, error=str(exc))

    images = flip.generated_images_urls or []
    if len(images) > 1:
        # Swap main image: rotate so a different image leads.
        flip.generated_images_urls = images[1:] + images[:1]

    # End + republish on eBay if a seller token is available (auto-refreshed
    # via ebay_oauth.get_valid_access_token); otherwise this cycle's state
    # (price/title/schedule) still advances so the app stays internally
    # consistent, and gets applied on the next successful publish.
    await _publish_flip(flip, db)

    last_hour = flip.next_recreate_at.hour if flip.next_recreate_at else None
    flip.last_recreate_at = datetime.utcnow()
    flip.recreate_cycle_count += 1
    flip.next_recreate_at = jittered_recreate_slot(
        flip.traffic_band or DEFAULT_BAND,
        datetime.utcnow(),
        interval_days=RECREATE_INTERVAL_DAYS,
        jitter_days=RECREATE_JITTER_DAYS,
        avoid_hour=last_hour,
    )
