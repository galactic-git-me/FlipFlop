from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_UK_HINTS = (
    "uk warehouse",
    "ship from uk",
    "ships from uk",
    "dispatch from uk",
    "delivered from uk",
    "local warehouse",
    "united kingdom",
    "england",
    "scotland",
    "wales",
    "northern ireland",
)


def _to_days(value: int, unit: str) -> int:
    u = unit.lower().strip()
    if u.startswith("day"):
        return value
    if u.startswith("week"):
        return value * 7
    return 999


def estimate_delivery_days(text: str | None) -> int | None:
    """
    Best-effort parse from listing card text.
    Returns minimum plausible delivery days when found.
    """
    if not text:
        return None
    t = str(text).lower()
    if "same day" in t:
        return 0
    if "next day" in t:
        return 1

    matches = re.findall(r"(\d{1,2})\s*[-–to]{0,3}\s*(\d{1,2})?\s*(day|days|week|weeks)", t)
    vals: list[int] = []
    for a, b, unit in matches:
        try:
            vals.append(_to_days(int(a), unit))
            if b:
                vals.append(_to_days(int(b), unit))
        except Exception:
            continue
    return min(vals) if vals else None


def estimate_listing_delivery_working_days(text: str | None) -> int | None:
    """Extract a conservative working-day estimate from common listing-card text.

    Uses the upper end of explicit ranges. Unsupported date wording returns
    None so the caller can use a vendor default without guessing.
    """
    if not text:
        return None
    value = str(text).lower()
    if "same day" in value or re.search(r"\btoday\b", value):
        return 0
    if "tomorrow" in value or "next day" in value:
        return 1

    matches = re.findall(
        r"\b(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s*(working|business|calendar)?\s*days?\b",
        value,
    )
    if matches:
        upper = max(int(end or start) for start, end, _unit in matches)
        # Calendar-day ranges are converted conservatively to working days.
        calendar_days = any(unit == "calendar" for _start, _end, unit in matches)
        return (upper * 5 + 6) // 7 if calendar_days else upper

    weekday = re.search(r"\b(?:by|arrives?\s+by|delivery\s+by)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", value)
    if weekday:
        day_index = {name: i for i, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}[weekday.group(1)]
        today = datetime.now(ZoneInfo("Europe/London")).date()
        delta = (day_index - today.weekday()) % 7 or 7
        target = today + timedelta(days=delta)
        days = 0
        current = today
        while current < target:
            current += timedelta(days=1)
            if current.weekday() < 5:
                days += 1
        return days
    return None


def has_uk_fulfilment_hint(text: str | None) -> bool:
    if not text:
        return False
    t = str(text).lower()
    return any(h in t for h in _UK_HINTS)


def allow_temu_aliexpress_listing(text: str | None, *, max_days: int = 5) -> bool:
    """
    Hard rule:
    - must have UK fulfilment hint
    - must have estimated delivery <= max_days
    """
    if not has_uk_fulfilment_hint(text):
        return False
    days = estimate_delivery_days(text)
    if days is None:
        return False
    return days <= max_days

