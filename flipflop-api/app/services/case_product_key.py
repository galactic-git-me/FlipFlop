"""Stable identity for one PC chassis variant across vendor titles."""
from __future__ import annotations

import hashlib
import re

_COLOURS = ("black", "white", "silver", "grey", "gray", "pink", "red", "blue")
_DESCRIPTION_START = re.compile(
    r"\s+(?:ARGB|RGB|Panoramic|Tempered|Glass|Mid[- ]Tower|Full[- ]Tower|"
    r"Micro[- ]ATX|ATX|PC\s+Case|Computer\s+Case|Gaming\s+Case|"
    r"High\s+Airflow|with|includes?|fits?)\b",
    re.I,
)


def case_product_identity(title: str, brand: str | None = None, model: str | None = None) -> str:
    """Return the short identity that vendors should agree on, including colour."""
    name = f"{brand} {model}" if brand and model else title
    name = re.split(r"\s+[|–—]\s+|\s+-\s+|[,;]", name, maxsplit=1)[0]
    name = _DESCRIPTION_START.split(name, maxsplit=1)[0]
    words = re.findall(r"[a-z0-9]+", name.lower())
    if len(words) < 2 or not any(word not in {"pc", "case", "computer", "gaming", "atx", "mid", "tower"} for word in words):
        words = re.findall(r"[a-z0-9]+", title.lower())[:24]
    colour_words = re.findall(r"[a-z0-9]+", title.lower())
    colour = next((word for word in colour_words if word in _COLOURS), None)
    if colour == "gray":
        colour = "grey"
    if colour and colour not in words:
        words.append(colour)
    # Generic titles still get a stable key of their own. They are not
    # attached to a different vendor until both titles yield the same key.
    return "-".join(words) or "unknown-case"


def case_product_key(title: str, brand: str | None = None, model: str | None = None) -> str:
    identity = case_product_identity(title, brand, model)
    return hashlib.sha256(f"case|{identity}".encode()).hexdigest()[:16]
