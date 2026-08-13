"""
Deferred-listing traffic-band scheduling — Algorithm Playbook row 3.

Seller-consensus default (default proposed, confirm once): Sunday evening
best, Monday strong, Tue-Thu evenings solid, Friday weakest, weekend traffic
~15-20% above weekday, UK evening peak ~7-10pm. No public, category-specific,
hour-by-hour eBay traffic dataset exists, so this starts from that heuristic
and should be re-weighted from FlipFlop's own sold-listing timestamps once
there's enough sales history (see bias_from_fast_sale-style future work).

Also implements row 3's guardrail from the relist/recreate engine: never the
same clock time twice — each call picks a new random time inside the band.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, time as dtime

# weekday: 0=Monday ... 6=Sunday (Python's datetime.weekday())
# (weekday, hour_start, hour_end) — hour range is the "evening" traffic band in UK local time.
TRAFFIC_BANDS: dict[str, tuple[int, int, int]] = {
    "sunday_evening": (6, 19, 22),
    "monday": (0, 17, 21),
    "tuesday_evening": (1, 19, 22),
    "wednesday_evening": (2, 19, 22),
    "thursday_evening": (3, 19, 22),
    "friday": (4, 17, 20),
    "saturday": (5, 12, 20),
}

DEFAULT_BAND = "sunday_evening"


def next_slot_datetime(traffic_band: str, after: datetime, avoid_hour: int | None = None) -> datetime:
    """
    Finds the next occurrence of the given traffic band's weekday after `after`,
    with a randomized hour inside the band's range. If avoid_hour is given,
    resamples once to avoid picking the exact same clock hour twice in a row
    (row 3's "never the same clock time twice" guardrail).
    """
    weekday, hour_start, hour_end = TRAFFIC_BANDS.get(traffic_band, TRAFFIC_BANDS[DEFAULT_BAND])

    days_ahead = (weekday - after.weekday()) % 7
    candidate_date = (after + timedelta(days=days_ahead)).date()

    hour = random.randint(hour_start, hour_end)
    minute = random.randint(0, 59)
    if avoid_hour is not None and hour == avoid_hour:
        hour = hour_start if hour != hour_start else hour_end

    slot = datetime.combine(candidate_date, dtime(hour=hour, minute=minute))
    if slot <= after:
        candidate_date = candidate_date + timedelta(days=7)
        slot = datetime.combine(candidate_date, dtime(hour=hour, minute=minute))
    return slot


def jittered_recreate_slot(
    traffic_band: str, after: datetime, interval_days: int = 7, jitter_days: int = 1,
    avoid_hour: int | None = None,
) -> datetime:
    """
    Row 5: the recreate cycle's own ~7-8 day cadence — interval_days ± jitter_days,
    with the time-of-day drawn from the traffic band's hour range (never the same
    clock hour twice running). Distinct from next_slot_datetime, which targets a
    specific day-of-week for the *initial* deferred-listing pick (row 3) — the
    recreate cycle instead jitters the day count directly so cadence stays close
    to the playbook's "roughly 7-8 days", rather than snapping to the next
    occurrence of one fixed weekday (which could land 6-13 days out).
    """
    _, hour_start, hour_end = TRAFFIC_BANDS.get(traffic_band, TRAFFIC_BANDS[DEFAULT_BAND])
    day_offset = interval_days + random.randint(-jitter_days, jitter_days)
    hour = random.randint(hour_start, hour_end)
    if avoid_hour is not None and hour == avoid_hour:
        hour = hour_start if hour != hour_start else hour_end
    minute = random.randint(0, 59)
    return (after + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
