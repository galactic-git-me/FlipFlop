"""
Best-Offer polling job — Algorithm Playbook rows 8, 21, 45.

The modern REST Sell APIs don't cover receiving/responding to a buyer's Best
Offer, so this polls the legacy Trading API's GetBestOffers per live
listing and runs FlipFlop's fixed two-round counter-offer rules
(app.services.offer_engine) against whatever it finds, posting the decision
back via RespondToBestOffer. Row 45 (send-to-watchers) uses the REST
Negotiation API separately, since that direction — proactively offering to
watchers — is covered by the modern API.

Simplification: this app tracks one counter-offer thread's state per flip
(counter_offer_round, last_counter_offer_price), not per-buyer — reasonable
for a low-volume, one-off-item store where a listing typically has at most
one active negotiation at a time, but worth flagging as a real limitation if
FlipFlop ever lists at higher volume with concurrent multi-buyer offers.

Not verifiable against live eBay from this environment (no network egress
to any eBay domain here).
"""
from __future__ import annotations

import structlog
from sqlalchemy import select

from app.services import ebay_oauth, ebay_trading_api, ebay_negotiation, offer_engine

log = structlog.get_logger(__name__)


async def run_offer_poll_job() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.flip import Flip, FlipStage

    polled, countered, errors = 0, 0, 0

    async with AsyncSessionLocal() as db:
        token = await ebay_oauth.get_valid_access_token(db)
        if not token:
            return {"polled": 0, "countered": 0, "errors": 0, "note": "No connected eBay seller account."}

        result = await db.execute(
            select(Flip).where(
                Flip.stage == FlipStage.ready_for_sale,
                Flip.offers_enabled.is_(True),
                Flip.ebay_listing_id.isnot(None),
            )
        )
        flips = result.scalars().all()

        for flip in flips:
            try:
                offers = await ebay_trading_api.get_best_offers(flip.ebay_listing_id, token)
            except Exception as exc:
                errors += 1
                log.warning("offer_poll.get_best_offers_failed", flip_id=flip.id, error=str(exc))
                continue

            polled += 1
            active = [o for o in offers if o.get("status") == "Active"]
            if not active:
                continue

            # One thread per flip (see module docstring) — take the highest active offer.
            best = max(active, key=lambda o: o["price"])
            listing_price = flip.listing_price or flip.current_estimated_resale or flip.total_cost
            decision = offer_engine.evaluate_buyer_offer(
                buyer_offer=best["price"],
                listing_price=listing_price,
                min_offer_price=flip.min_offer_price,
                offers_enabled=flip.offers_enabled,
                counter_offer_round=flip.counter_offer_round,
                last_counter_offer_price=flip.last_counter_offer_price,
            )
            if decision.action != "counter" or decision.counter_price is None:
                continue

            try:
                await ebay_trading_api.respond_to_best_offer(
                    flip.ebay_listing_id, best["best_offer_id"], "Counter", decision.counter_price, token,
                )
                flip.last_counter_offer_price = decision.counter_price
                flip.counter_offer_round += 1
                countered += 1
            except Exception as exc:
                errors += 1
                log.warning("offer_poll.respond_failed", flip_id=flip.id, error=str(exc))

        await db.commit()

    return {"polled": polled, "countered": countered, "errors": errors}


async def run_send_to_watchers_job() -> dict:
    """Row 45: proactive offers to watchers, twice-daily cadence enforced by offer_engine."""
    from app.database import AsyncSessionLocal
    from app.models.flip import Flip, FlipStage
    from datetime import datetime

    sent, errors = 0, 0

    async with AsyncSessionLocal() as db:
        token = await ebay_oauth.get_valid_access_token(db)
        if not token:
            return {"sent": 0, "errors": 0, "note": "No connected eBay seller account."}

        result = await db.execute(
            select(Flip).where(
                Flip.stage == FlipStage.ready_for_sale,
                Flip.offers_enabled.is_(True),
                Flip.ebay_listing_id.isnot(None),
                Flip.listed_at.isnot(None),
            )
        )
        flips = result.scalars().all()

        for flip in flips:
            listing_price = flip.listing_price or flip.current_estimated_resale or flip.total_cost
            plan = offer_engine.evaluate_send_to_watchers(
                listing_price=listing_price,
                min_offer_price=flip.min_offer_price,
                listed_at=flip.listed_at,
                last_watcher_offer_sent_at=flip.last_watcher_offer_sent_at,
            )
            if not plan.should_send or plan.offer_price is None:
                continue
            try:
                ok = await ebay_negotiation.send_offer_to_watchers(
                    flip.ebay_listing_id, plan.offer_price,
                    "Thanks for watching this build — happy to offer you a deal.", token,
                )
                if ok:
                    flip.last_watcher_offer_sent_at = datetime.utcnow()
                    sent += 1
            except Exception as exc:
                errors += 1
                log.warning("offer_poll.send_to_watchers_failed", flip_id=flip.id, error=str(exc))

        await db.commit()

    return {"sent": sent, "errors": errors}
