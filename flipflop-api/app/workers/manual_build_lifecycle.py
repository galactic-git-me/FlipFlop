"""
Post-listing lifecycle jobs for ManualBuild — offer negotiation, send-to-
watchers, and the recreate/relist cycle. Ported from the retired Flip
system's offer_poll.py + recreate_cycle.py onto ManualBuild's model and its
own eBay auth (app.services.ebay_token_manager, a long-lived refresh token —
no browser consent flow needed, unlike Flip's ebay_oauth.py).

All registered on the APScheduler instance in app/workers/scheduler.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from urllib.parse import urlparse

import structlog
from sqlalchemy import select
from urllib.parse import urlparse
import re

from app.config import get_settings
from app.services import ebay_trading_api, ebay_negotiation, offer_engine, pricing_engine
from app.services.ebay_token_manager import get_valid_ebay_access_token
from app.workers.manual_build_scheduler import post_build_to_ebay

log = structlog.get_logger(__name__)

def _is_legacy_item_id(value: str | None) -> bool:
    return bool(value and value.isdecimal())


async def _get_token(db=None) -> str | None:
    settings = get_settings()
    try:
        return await get_valid_ebay_access_token(settings.ebay_listing_environment, db=db)
    except ValueError:
        return None


async def run_manual_build_offer_poll_job() -> dict:
    """Rows 8/21: poll live listings' Best Offers and run the fixed two-round
    counter-offer rules (app.services.offer_engine) against them."""
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild

    polled, countered, errors = 0, 0, 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.status == "listed",
                ManualBuild.allow_offers.is_(True),
                ManualBuild.ebay_listing_id.isnot(None),
            )
        )
        builds = [build for build in result.scalars().all() if _is_legacy_item_id(build.ebay_listing_id)]
        if not builds:
            return {"polled": 0, "countered": 0, "errors": 0, "note": "No valid eBay listings to poll."}
        token = await _get_token(db)
        if not token:
            return {"polled": 0, "countered": 0, "errors": 0, "note": "Connect the eBay seller account in Settings."}

        for build in builds:
            try:
                offers = await ebay_trading_api.get_best_offers(build.ebay_listing_id, token)
            except Exception as exc:
                errors += 1
                log.warning("manual_build_offer_poll.get_best_offers_failed", build_id=build.id, error=str(exc))
                continue

            polled += 1
            active = [o for o in offers if o.get("status") == "Active"]
            if not active:
                continue

            best = max(active, key=lambda o: o["price"])
            listing_price = build.ebay_price or build.total_cost
            decision = offer_engine.evaluate_buyer_offer(
                buyer_offer=best["price"],
                listing_price=listing_price,
                min_offer_price=build.auto_reject_below_price,
                offers_enabled=build.allow_offers,
                counter_offer_round=build.counter_offer_round,
                last_counter_offer_price=build.last_counter_offer_price,
            )
            if decision.action != "counter" or decision.counter_price is None:
                continue

            try:
                await ebay_trading_api.respond_to_best_offer(
                    build.ebay_listing_id, best["best_offer_id"], "Counter", decision.counter_price, token,
                )
                build.last_counter_offer_price = decision.counter_price
                build.counter_offer_round += 1
                countered += 1
            except Exception as exc:
                errors += 1
                log.warning("manual_build_offer_poll.respond_failed", build_id=build.id, error=str(exc))

        await db.commit()

    return {"polled": polled, "countered": countered, "errors": errors}


async def run_manual_build_send_to_watchers_job() -> dict:
    """Row 45: proactive offers to watchers, twice-daily cadence enforced by offer_engine."""
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild

    sent, errors = 0, 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.status == "listed",
                ManualBuild.allow_offers.is_(True),
                ManualBuild.ebay_listing_id.isnot(None),
                ManualBuild.listed_at.isnot(None),
            )
        )
        builds = [build for build in result.scalars().all() if _is_legacy_item_id(build.ebay_listing_id)]
        if not builds:
            return {"sent": 0, "errors": 0, "note": "No valid eBay listings to contact."}
        token = await _get_token(db)
        if not token:
            return {"sent": 0, "errors": 0, "note": "Connect the eBay seller account in Settings."}

        for build in builds:
            listing_price = build.ebay_price or build.total_cost
            plan = offer_engine.evaluate_send_to_watchers(
                listing_price=listing_price,
                min_offer_price=build.auto_reject_below_price,
                listed_at=build.listed_at,
                last_watcher_offer_sent_at=build.last_watcher_offer_sent_at,
            )
            if not plan.should_send or plan.offer_price is None:
                continue
            try:
                ok = await ebay_negotiation.send_offer_to_watchers(
                    build.ebay_listing_id, plan.offer_price,
                    "Thanks for watching this build — happy to offer you a deal.", token,
                )
                if ok:
                    build.last_watcher_offer_sent_at = datetime.utcnow()
                    sent += 1
            except Exception as exc:
                errors += 1
                log.warning("manual_build_send_to_watchers.failed", build_id=build.id, error=str(exc))

        await db.commit()

    return {"sent": sent, "errors": errors}


async def run_manual_build_recreate_cycle_job() -> dict:
    """Rows 1/2/5/6/9/36: end and republish listings whose randomized ~7-day
    timer is due — reworded title, swapped main image, a price step-down,
    landing at a new randomized time in the build's traffic band."""
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild

    recreated, floor_hit, errors, pending = 0, 0, 0, 0
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManualBuild.id).where(
                ManualBuild.status == "listed",
                ManualBuild.relist_enabled.is_(True),
                (
                    ManualBuild.next_recreate_at.isnot(None)
                    & (ManualBuild.next_recreate_at <= now)
                )
                | (
                    ManualBuild.next_recreate_at.is_(None)
                    & (ManualBuild.listed_at.isnot(None))
                    & (ManualBuild.listed_at <= now - timedelta(days=7))
                )
                | (
                    ManualBuild.next_recreate_at.is_(None)
                    & ManualBuild.listed_at.is_(None)
                    & (ManualBuild.updated_at <= now - timedelta(days=7))
                    & ManualBuild.ebay_listing_url.isnot(None)
                ),
            )
        )
        due_ids = result.scalars().all()

        for build_id in due_ids:
            build = await db.get(ManualBuild, build_id)
            if build is None:
                continue
            try:
                outcome = await _recreate_manual_build(build, db)
                if outcome == "published":
                    # The remote create succeeded. Persist immediately so a
                    # later row failure cannot make the next hourly run post it again.
                    await db.commit()
                    recreated += 1
                    if build.price_floor_hit_review_needed:
                        floor_hit += 1
                else:
                    pending += 1
                    log.warning("manual_build_recreate_cycle.not_published", build_id=build_id, outcome=outcome)
                    await db.rollback()
            except Exception as exc:
                errors += 1
                log.warning("manual_build_recreate_cycle.failed", build_id=build_id, error=str(exc))
                await db.rollback()

    return {"recreated": recreated, "floor_hit_review_needed": floor_hit, "pending": pending, "errors": errors}


async def _recreate_manual_build(build, db) -> str:
    """Rows 1/2/5/6/9: end current listing, generate a fresh title/swap main
    photo, step price down, republish, reschedule."""
    from app.api.manual_builds import generate_listing as _generate_listing_endpoint

    # Legacy builds may retain only the old eBay URL. Recover its numeric item
    # ID, then require eBay to confirm the old offer ended before creating anew.
    if not build.ebay_listing_id and build.ebay_listing_url:
        match = re.search(
            r"/(?:itm/)?(\d{9,15})(?:[/?#]|$)",
            urlparse(build.ebay_listing_url).path,
        )
        if not match:
            match = re.search(r"/itm/[^/]+/(\d{9,15})(?:[/?#]|$)", build.ebay_listing_url)
        if match:
            build.ebay_listing_id = match.group(1)
    if build.ebay_listing_id:
        from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
        try:
            state = await reconcile_manual_build_listing(build, db, force=True)
        except Exception as exc:
            log.warning("manual_build_recreate_cycle.reconcile_failed", build_id=build.id, error=str(exc))
            return "not_ready"
        if state not in {"ended", "missing"}:
            return "not_ready"
    elif not build.ebay_listing_url:
        return "not_ready"

    # Row 19/20 re-anchor: always fresh sold-comp data, never carried forward stale.
    await pricing_engine.recalculate_manual_build_pricing(build, db)

    current_price = build.ebay_price or build.total_cost
    new_price, floor_hit = pricing_engine.compute_next_drop_price(
        current_price=current_price,
        sold_comp_target=build.sold_comp_target,
        price_floor=build.price_floor or pricing_engine.compute_price_floor(build.total_cost or 0.0),
        step_pct=build.recreate_price_step_pct,
    )
    build.ebay_price = new_price
    build.price_floor_hit_review_needed = floor_hit

    # Row 5: reword title (pick a different generated option than the
    # current one), regenerate description to match.
    try:
        previous_title = build.generated_title
        result = await _generate_listing_endpoint(build.id, db)
        if result.titles:
            reworded = next((t for t in result.titles if t != previous_title), result.titles[0])
            build.generated_title = reworded[:80]
    except Exception as exc:
        log.warning("manual_build_recreate_cycle.reword_failed", build_id=build.id, error=str(exc))

    photos = build.photos or []
    if len(photos) > 1:
        # Swap main image: rotate so a different photo leads.
        build.photos = photos[1:] + photos[:1]

    # eBay's prior state was confirmed ended above. Only advance cycle state
    # after the replacement listing is accepted; failures remain due to retry.
    outcome = await post_build_to_ebay(build, db=db)
    if outcome != "published":
        return outcome

    build.last_recreate_at = datetime.utcnow()
    build.recreate_cycle_count += 1
    from app.models.app_settings import AppSettings
    policy = (
        await db.execute(
            select(AppSettings).where(AppSettings.name == "default")
        )
    ).scalar_one_or_none()
    interval_days = policy.relist_interval_days if policy else 7
    build.next_recreate_at = build.last_recreate_at + timedelta(days=interval_days or 7)
    build.listed_at = build.last_recreate_at
    return outcome
