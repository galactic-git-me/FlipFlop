"""Fuzzy matching between a favourite's saved search term and listing
titles. Shared by the favourites API (live search + saved-favourites
matrix) and the phase2 classification hook (background gem-match
detection) so both use identical matching behaviour.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from rapidfuzz import fuzz

# The live modal search (user typing, wants generous recall) uses a lower
# bar than the background alert hook (wants precision — a false positive
# here fires an unwanted toast).
SEARCH_THRESHOLD = 55.0
ALERT_THRESHOLD = 72.0


def fuzzy_score(query: str, title: str) -> float:
    if not query or not title:
        return 0.0
    return fuzz.WRatio(query, title)


def filter_matches(query: str, listings: list[dict[str, Any]], threshold: float = SEARCH_THRESHOLD) -> list[dict[str, Any]]:
    scored = []
    for listing in listings:
        score = fuzzy_score(query, listing.get("title") or "")
        if score >= threshold:
            scored.append({**listing, "_score": score})
    scored.sort(key=lambda item: item["_score"], reverse=True)
    return scored


def best_category(matches: list[dict[str, Any]]) -> str | None:
    categories = [m["category"] for m in matches if m.get("category")]
    if not categories:
        return None
    return Counter(categories).most_common(1)[0][0]


def build_vendor_matrix(matches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One entry per vendor: the cheapest matching listing for that vendor."""
    matrix: dict[str, dict[str, Any]] = {}
    for m in matches:
        vendor = m.get("source") or "unknown"
        price = m.get("delivered_price")
        if price is None:
            continue
        current = matrix.get(vendor)
        if current is None or price < current["lowest_price"]:
            matrix[vendor] = {
                "lowest_price": price,
                "listing_id": m.get("listing_id"),
                "url": m.get("url"),
                "classification": m.get("classification") or "",
            }
    return matrix


def find_matching_favourite(title: str, cpk: str | None, favourites: list[Any], threshold: float = ALERT_THRESHOLD) -> Any | None:
    """Best-scoring favourite: exact CPK match first, or fuzzy term match, or None.

    For each favourite, check: if it has a saved CPK and this listing's CPK
    matches, return that favourite immediately (highest priority). Otherwise
    check term-based fuzzy matching. If multiple favourites match via term,
    return the highest-scoring one.
    """
    best_fav = None
    best_score = 0.0

    for fav in favourites:
        # CPK match: highest priority, exact match, no threshold needed
        if fav.cpk and cpk and fav.cpk == cpk:
            return fav

        # Term match: fuzzy, must pass threshold
        if fav.term:
            score = fuzzy_score(fav.term, title)
            if score >= threshold and score > best_score:
                best_fav = fav
                best_score = score

    return best_fav
