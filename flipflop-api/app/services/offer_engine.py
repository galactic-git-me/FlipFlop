"""
Counter-offer & send-to-watchers rules engine — Algorithm Playbook rows 8, 21, 45.

Pure, unit-testable rule functions. The actual eBay-side wiring (receiving a
buyer's Best Offer and posting a counter, or pushing an offer to watchers) is
a separate integration concern — see docs/build-details-automation-plan.md,
Part 1, for the flagged API-coverage split (legacy Trading API for buyer-offer
response vs. the REST Negotiation API for offers-to-watchers).

Defaults proposed in the implementation plan, confirm once:
  - counter tolerance = offer within 10% of the minimum-offer floor
  - Rule 1: first counter = roughly the midpoint between offer and listing price
  - Rule 2: second counter = £5 off the first counter, then stop (already
    specified as fixed in the playbook, not a tunable default)
  - send-to-watchers: after 5 days unsold, 10% off, twice daily cadence
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

DEFAULT_OFFER_TOLERANCE_PCT = 0.10
SECOND_COUNTER_STEP_GBP = 5.0
DEFAULT_WATCHER_DAYS_UNSOLD = 5
DEFAULT_WATCHER_DISCOUNT_PCT = 0.10


@dataclass
class CounterOfferResult:
    action: str  # "counter" | "accept" | "decline" | "no_further_rounds"
    counter_price: Optional[float]
    reason: str


def evaluate_buyer_offer(
    buyer_offer: float,
    listing_price: float,
    min_offer_price: Optional[float],
    offers_enabled: bool,
    counter_offer_round: int,
    last_counter_offer_price: Optional[float],
    tolerance_pct: float = DEFAULT_OFFER_TOLERANCE_PCT,
) -> CounterOfferResult:
    """
    Row 8/21: always respond to an offer while offers are enabled — silence
    kills the engagement signal the algorithm rewards — using two fixed rounds.
    """
    if not offers_enabled:
        return CounterOfferResult("decline", None, "Offers are disabled for this build.")

    if min_offer_price is not None and buyer_offer < min_offer_price * (1 - tolerance_pct):
        return CounterOfferResult(
            "counter", round((buyer_offer + listing_price) / 2, 2),
            "Below tolerance of the minimum-offer floor — counter at the midpoint to keep engagement alive without accepting a lowball.",
        )

    if counter_offer_round == 0:
        # Rule 1: within tolerance of the minimum — counter roughly halfway
        # between their offer and the listing price.
        counter_price = round((buyer_offer + listing_price) / 2, 2)
        return CounterOfferResult("counter", counter_price, "Rule 1: first counter at the midpoint.")

    if counter_offer_round == 1:
        # Rule 2: one more counter at £5 off the already-countered price, then stop.
        base = last_counter_offer_price if last_counter_offer_price is not None else listing_price
        counter_price = round(base - SECOND_COUNTER_STEP_GBP, 2)
        if min_offer_price is not None:
            counter_price = max(counter_price, min_offer_price)
        return CounterOfferResult("counter", counter_price, "Rule 2: second and final counter, £5 off.")

    return CounterOfferResult("no_further_rounds", None, "Two counter rounds already used — no further rounds per playbook rule.")


@dataclass
class WatcherOfferPlan:
    should_send: bool
    discount_pct: float
    offer_price: Optional[float]
    reason: str


def evaluate_send_to_watchers(
    listing_price: float,
    min_offer_price: Optional[float],
    listed_at: Optional[datetime],
    last_watcher_offer_sent_at: Optional[datetime],
    now: Optional[datetime] = None,
    days_unsold_threshold: int = DEFAULT_WATCHER_DAYS_UNSOLD,
    discount_pct: float = DEFAULT_WATCHER_DISCOUNT_PCT,
) -> WatcherOfferPlan:
    """Row 45: proactively send offers to watchers after N days unsold, floor-aware."""
    now = now or datetime.utcnow()

    if listed_at is None:
        return WatcherOfferPlan(False, discount_pct, None, "Not yet listed.")

    if now - listed_at < timedelta(days=days_unsold_threshold):
        return WatcherOfferPlan(False, discount_pct, None, "Still within the unsold-days threshold.")

    # Twice-daily cadence: don't send again within 10 hours of the last send.
    if last_watcher_offer_sent_at is not None and now - last_watcher_offer_sent_at < timedelta(hours=10):
        return WatcherOfferPlan(False, discount_pct, None, "Already sent within the twice-daily cadence window.")

    offer_price = round(listing_price * (1 - discount_pct), 2)
    if min_offer_price is not None:
        offer_price = max(offer_price, min_offer_price)

    return WatcherOfferPlan(True, discount_pct, offer_price, f"{days_unsold_threshold}+ days unsold — sending watcher offer.")
