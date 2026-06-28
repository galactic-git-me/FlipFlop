from __future__ import annotations

import re

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

