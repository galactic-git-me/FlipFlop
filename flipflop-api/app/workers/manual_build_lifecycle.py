"""
Post-listing lifecycle jobs for ManualBuild — offer negotiation, send-to-
watchers, and the recreate/relist cycle. Ported from the retired Flip
system's offer_poll.py + recreate_cycle.py onto ManualBuild's model and its
own eBay auth (app.services.ebay_token_manager, a long-lived refresh token —
no browser consent flow needed, unlike Flip's ebay_oauth.py).

All registered on the APScheduler instance in app/workers/scheduler.py.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.services import ebay_trading_api, ebay_negotiation, offer_engine, pricing_engine
from app.services.ebay_token_manager import get_valid_ebay_access_token
from app.services.traffic_bands import jittered_recreate_slot, DEFAULT_BAND
from app.workers.manual_build_scheduler import post_build_to_ebay

log = structlog.get_logger(__name__)

RECREATE_INTERVAL_DAYS = 7
RECREATE_JITTER_DAYS = 1


async def _get_token() -> str | None:
    settings = get_settings()
    try:
        return await get_valid_ebay_access_token(settings.ebay_listing_environment)
    except ValueError:
        return None


async def run_manual_build_offer_poll_job() -> dict:
    """Rows 8/21: poll live listings' Best Offers and run the fixed two-round
    counter-offer rules (app.services.offer_engine) against them."""
    from app.database import AsyncSessionLocal
    from app.models.manual_build import ManualBuild

    polled, countered, errors = 0, 0, 0

    async with AsyncSessionLocal() as db:
        token = await _get_token()
        if not token:
            return {"polled": 0, "countered": 0, "errors": 0, "note": "No eBay refresh token configured."}

        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.status == "listed",
                ManualBuild.allow_offers.is_(True),
                ManualBuild.ebay_listing_id.isnot(None),
            )
        )
        builds = result.scalars().all()

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
        token = await _get_token()
        if not token:
            return {"sent": 0, "errors": 0, "note": "No eBay refresh token configured."}

        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.status == "listed",
                ManualBuild.allow_offers.is_(True),
                ManualBuild.ebay_listing_id.isnot(None),
                ManualBuild.listed_at.isnot(None),
            )
        )
        builds = result.scalars().all()

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

    recreated, floor_hit, errors = 0, 0, 0
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManualBuild).where(
                ManualBuild.status == "listed",
                ManualBuild.listed_at.isnot(None),
                ManualBuild.next_recreate_at.isnot(None),
                ManualBuild.next_recreate_at <= now,
            )
        )
        due = result.scalars().all()

        for build in due:
            try:
                await _recreate_manual_build(build, db)
                recreated += 1
                if build.price_floor_hit_review_needed:
                    floor_hit += 1
            except Exception as exc:
                errors += 1
                log.warning("manual_build_recreate_cycle.failed", build_id=build.id, error=str(exc))

        await db.commit()

    return {"recreated": recreated, "floor_hit_review_needed": floor_hit, "errors": errors}


async def _recreate_manual_build(build, db) -> None:
    """Rows 1/2/5/6/9: end current listing, generate a fresh title/swap main
    photo, step price down, republish, reschedule."""
    from app.api.manual_builds import generate_listing as _generate_listing_endpoint

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

    # End + republish on eBay if a token is available; otherwise this
    # cycle's state (price/title/schedule) still advances so the app stays
    # internally consistent, and gets applied on the next successful publish.
    await post_build_to_ebay(build)

    last_hour = build.next_recreate_at.hour if build.next_recreate_at else None
    build.last_recreate_at = datetime.utcnow()
    build.recreate_cycle_count += 1
    build.next_recreate_at = jittered_recreate_slot(
        build.traffic_band or DEFAULT_BAND,
        datetime.utcnow(),
        interval_days=RECREATE_INTERVAL_DAYS,
        jitter_days=RECREATE_JITTER_DAYS,
        avoid_hour=last_hour,
    )
