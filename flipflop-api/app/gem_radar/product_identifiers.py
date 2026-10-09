"""Shared marketplace identifiers used to link the same product across sources."""
from __future__ import annotations

import re
from urllib.parse import unquote


_ASIN_RE = re.compile(
    r"/(?:dp|gp/product|gp/aw/d|exec/obidos/ASIN)/([A-Z0-9]{10})(?:[/?#]|$)",
    re.IGNORECASE,
)


def extract_asin(value: str | None) -> str | None:
    """Extract an Amazon ASIN from a product URL or a standalone listing ID."""
    if not value:
        return None
    match = _ASIN_RE.search(unquote(value))
    if match:
        return match.group(1).upper()
    # Amazon scrapes commonly use the ASIN itself as listing_id. Do not infer
    # an ASIN from arbitrary descriptive text or a larger vendor identifier.
    if re.fullmatch(r"[A-Z0-9]{10}", value.strip(), re.IGNORECASE):
        return value.strip().upper()
    return None


def categories_compatible(expected: str | None, actual: str | None) -> bool:
    if not expected or not actual:
        return True
    aliases = {
        "storage": {"storage", "ssd"},
        "ssd": {"storage", "ssd"},
        "cooler": {"cooler", "cooling"},
        "cooling": {"cooler", "cooling"},
    }
    return actual.strip().lower() in aliases.get(expected.strip().lower(), {expected.strip().lower()})
