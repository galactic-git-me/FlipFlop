"""Deferred-listing scheduler for Manual Builds ("Your Builds" -> "List on
eBay") — mirrors app/workers/recreate_cycle.py's run_deferred_publish_job()
for Flips, but targets ManualBuild instead. Registered on the APScheduler
instance in app/workers/scheduler.py.

Builds that are due but not actually ready to publish (missing listing
content, item specifics, photos, or a set price) are skipped and logged
rather than erroring the whole job — deferred_publish_at is only cleared on
a real publish, so a build that becomes ready later still fires on the next
tick instead of silently never publishing.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.services.ebay_listing_poster import post_flip_to_ebay
from app.services.ebay_specifics_generator import validate_aspects_for_ebay

log = structlog.get_logger(__name__)


async def run_deferred_manual_build_publish_job() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild

    published, skipped_not_ready, skipped_no_token, errors = 0, 0, 0, 0
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.deferred_publish_at.isnot(None),
                ManualBuild.deferred_publish_at <= now,
                ManualBuild.status != "listed",
                ManualBuild.ebay_listing_id.is_(None),
            )
        )
        due = result.scalars().all()

        for build in due:
            try:
                outcome = await _publish_due_build(build)
                if outcome == "published":
                    published += 1
                elif outcome == "no_token":
                    skipped_no_token += 1
                else:
                    skipped_not_ready += 1
            except Exception as exc:
                errors += 1
                log.warning("manual_build_scheduler.publish_failed", build_id=build.id, error=str(exc))

        await db.commit()

    return {
        "published": published,
        "skipped_not_ready": skipped_not_ready,
        "skipped_no_token": skipped_no_token,
        "errors": errors,
    }


async def _publish_due_build(build) -> str:
    """Returns 'published', 'not_ready', or 'no_token'. Mutates `build`
    in place on success — caller commits."""
    from app.services.traffic_bands import jittered_recreate_slot, DEFAULT_BAND

    outcome = await post_build_to_ebay(build)
    if outcome == "published":
        build.status = "listed"
        build.deferred_publish_at = None
        if build.listed_at is None:
            # Rows 1/2/5/6/9: start the recreate/relist cycle clock the
            # first time this build actually goes live.
            build.listed_at = datetime.utcnow()
            build.next_recreate_at = jittered_recreate_slot(build.traffic_band or DEFAULT_BAND, datetime.utcnow())
    return outcome


async def post_build_to_ebay(build) -> str:
    """
    Shared eBay-publish logic for a ManualBuild — used by the deferred
    first-publish job above and by the recreate-cycle end-and-republish job
    (app/workers/manual_build_lifecycle.py). Returns 'published', 'not_ready',
    or 'no_token'. Mutates `build` in place on success — caller commits.
    Does NOT touch build.status/deferred_publish_at, since the recreate
    cycle re-publishes an already-listed build — callers that care about
    those fields (the deferred job) set them themselves.
    """
    if not build.generated_title or not build.generated_description:
        log.info("manual_build_scheduler.skip_not_ready", build_id=build.id, reason="no_listing_content")
        return "not_ready"

    missing_required = [a for a in ("Brand", "Type") if not (build.generated_aspects or {}).get(a)]
    if missing_required:
        log.info("manual_build_scheduler.skip_not_ready", build_id=build.id, reason="missing_aspects", missing=missing_required)
        return "not_ready"

    if validate_aspects_for_ebay(build.generated_aspects or {}):
        log.info("manual_build_scheduler.skip_not_ready", build_id=build.id, reason="invalid_aspects")
        return "not_ready"

    image_urls = [
        url for url in (
            (p.get("url") if isinstance(p, dict) else p) for p in (build.photos or [])
        ) if url
    ]
    if not image_urls:
        log.info("manual_build_scheduler.skip_not_ready", build_id=build.id, reason="no_photos")
        return "not_ready"

    if not build.ebay_price:
        log.info("manual_build_scheduler.skip_not_ready", build_id=build.id, reason="no_price_set")
        return "not_ready"

    from app.services.ebay_token_manager import get_valid_ebay_access_token

    settings = get_settings()
    listing_environment = settings.ebay_listing_environment

    try:
        oauth_token = await get_valid_ebay_access_token(listing_environment)
    except ValueError:
        log.info("manual_build_scheduler.skip_no_token", build_id=build.id)
        return "no_token"

    if listing_environment == "production":
        payment_policy_id = settings.ebay_production_payment_policy_id
        return_policy_id = settings.ebay_production_return_policy_id
        fulfillment_policy_id = settings.ebay_production_fulfillment_policy_id
    else:
        payment_policy_id = settings.ebay_sandbox_payment_policy_id
        return_policy_id = settings.ebay_sandbox_return_policy_id
        fulfillment_policy_id = settings.ebay_sandbox_fulfillment_policy_id

    if build.fulfillment_policy_id:
        fulfillment_policy_id = build.fulfillment_policy_id

    result = await post_flip_to_ebay(
        title=build.generated_title,
        description=build.generated_description,
        price=build.ebay_price,
        image_urls=image_urls,
        access_token=oauth_token,
        environment=listing_environment,
        condition=build.ebay_condition or "USED_EXCELLENT",
        payment_policy_id=payment_policy_id,
        return_policy_id=return_policy_id,
        fulfillment_policy_id=fulfillment_policy_id,
        aspects=build.generated_aspects or {},
    )

    if result.get("success"):
        build.ebay_listing_id = result["listing_id"]
        build.ebay_listing_url = result["url"]
        build.ebay_sku = result.get("sku")
        build.updated_at = datetime.utcnow()

        # Row 40: promote automatically if opted in — a failure here doesn't
        # undo the listing itself, just logs, since the listing going live
        # is the outcome that actually matters.
        if build.promoted_enabled:
            try:
                from app.services.ebay_marketing import set_promoted_ad

                rate = build.promoted_ad_rate_pct
                if rate is None:
                    from app.services.pricing_engine import suggest_promoted_ad_rate
                    suggestion = suggest_promoted_ad_rate(
                        estimated_profit=(build.ebay_price or 0) - (build.total_cost or 0),
                        total_cost=build.total_cost or 0,
                    )
                    rate = suggestion["suggested_ad_rate_pct"] * 100 if not suggestion["too_thin_to_promote"] else None
                if rate is not None:
                    await set_promoted_ad(build.ebay_listing_id, rate, oauth_token, listing_environment)
            except Exception as exc:
                log.warning("manual_build_scheduler.promote_failed", build_id=build.id, error=str(exc))

        return "published"

    log.warning("manual_build_scheduler.ebay_rejected", build_id=build.id, error=result.get("error"))
    return "not_ready"
