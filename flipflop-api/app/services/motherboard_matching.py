"""Resolve a free-text listing/product title to a known MotherboardSpec row.

No new fuzzy-matching dependency — difflib (stdlib) is sufficient at this
data scale (a few hundred distinct motherboard models at most) and avoids
the rapidfuzz import chain that's currently broken in this environment
(app/gem_radar/favourite_matching.py fails to import without it installed).
"""
from __future__ import annotations

import difflib
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.motherboard_spec import MotherboardSpec

_MATCH_THRESHOLD = 0.72


def _normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def match_motherboard_spec(title: str, candidates: list[MotherboardSpec]) -> MotherboardSpec | None:
    """Pure in-memory matcher — no DB access. Callers that need to match many
    titles against the same reference set (e.g. compatibility evaluation
    looping over every candidate variant in a slot) should fetch the
    MotherboardSpec list once and call this directly rather than the async
    per-title wrapper below."""
    if not title or not candidates:
        return None

    norm_title = _normalize(title)

    # Exact substring match first (cheap, high-confidence, common case for a
    # well-formed "ASUS ROG STRIX B650-A GAMING WIFI" style listing title).
    for spec in candidates:
        if _normalize(spec.canonical_model) in norm_title:
            return spec

    # Fuzzy fallback for near-misses (typos, reordered words, missing suffix).
    best_spec: MotherboardSpec | None = None
    best_ratio = 0.0
    for spec in candidates:
        ratio = difflib.SequenceMatcher(None, _normalize(spec.canonical_model), norm_title).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_spec = spec

    if best_spec is not None and best_ratio >= _MATCH_THRESHOLD:
        return best_spec
    return None


async def resolve_motherboard_spec(db: AsyncSession, title: str) -> MotherboardSpec | None:
    """Single-title convenience wrapper — fetches the reference table fresh.
    Fine for one-off lookups (e.g. admin tools); use match_motherboard_spec
    directly with a pre-fetched list when matching many titles in a loop."""
    if not title:
        return None
    candidates = (await db.execute(select(MotherboardSpec))).scalars().all()
    return match_motherboard_spec(title, list(candidates))
