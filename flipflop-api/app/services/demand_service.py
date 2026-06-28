"""
Demand Service — derives category-level demand signals from stored listings.

No external API calls.  All signals come from the listing data we've already
scraped:  volume, gem rate, price trends, time-of-arrival distribution.

Categories mirror the frontend TrendingCategoriesCard buckets so the backend
and UI are always in agreement.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing, Classification, ListingStatus


# ── Category definitions ──────────────────────────────────────────────────────
# Each is a dict with:
#   name      — display name
#   emoji     — for the UI
#   matcher   — lambda(listing) → bool

_GPU_KEYWORDS = {
    "rtx", "gtx", "rx 6", "rx 7", "quadro", "radeon", "nvidia", "amd gpu",
    "graphics card", "gpu", "geforce",
}
_WORKSTATION_KEYWORDS = {
    "elitedesk", "optiplex", "thinkcentre", "thinkstation",
    "hp workstation", "dell workstation", "hp z240", "hp z440", "hp z640",
    "fujitsu esprimo", "hp prodesk", "precision tower",
}
_CLEARANCE_KEYWORDS = {
    "ex office", "office clearance", "it clearance", "job lot", "quick sale",
    "need gone", "clearing out", "no longer needed", "office lot",
}
_HTPC_KEYWORDS = {
    "mini pc", "htpc", "small form factor", "nuc", "sff pc", "minipc",
    "living room", "media pc",
}


def _title_lower(listing: Listing) -> str:
    return (listing.title or "").lower()


def _has_gpu(listing: Listing) -> bool:
    t = _title_lower(listing)
    if listing.gpu:
        return True
    return any(kw in t for kw in _GPU_KEYWORDS)


def _is_workstation(listing: Listing) -> bool:
    t = _title_lower(listing)
    return any(kw in t for kw in _WORKSTATION_KEYWORDS)


def _is_clearance(listing: Listing) -> bool:
    t = _title_lower(listing)
    return any(kw in t for kw in _CLEARANCE_KEYWORDS)


def _is_htpc(listing: Listing) -> bool:
    t = _title_lower(listing)
    return any(kw in t for kw in _HTPC_KEYWORDS)


def _is_no_gpu(listing: Listing) -> bool:
    t = _title_lower(listing)
    if listing.gpu:
        return False
    return (
        "no gpu" in t or "no graphics" in t or "without gpu" in t
        or ("i5" in t or "i7" in t or "i9" in t or "ryzen" in t)
    )


def _is_budget(listing: Listing) -> bool:
    return listing.price <= 60 and not _has_gpu(listing)


# Ordered — a listing is assigned to the FIRST matching category.
_CATEGORY_DEFS = [
    {
        "name": "Gaming PCs",
        "emoji": "🎮",
        "use_case": "gaming",
        "matcher": lambda l: _has_gpu(l),
    },
    {
        "name": "No-GPU Flips",
        "emoji": "🔧",
        "use_case": "gaming",
        "matcher": lambda l: _is_no_gpu(l) and not _is_workstation(l) and not _is_clearance(l),
    },
    {
        "name": "Office Clearance",
        "emoji": "💼",
        "use_case": "office",
        "matcher": lambda l: _is_clearance(l),
    },
    {
        "name": "Workstations",
        "emoji": "🖥️",
        "use_case": "workstation",
        "matcher": lambda l: _is_workstation(l),
    },
    {
        "name": "HTPC / SFF",
        "emoji": "📺",
        "use_case": "htpc",
        "matcher": lambda l: _is_htpc(l),
    },
    {
        "name": "Budget Builders",
        "emoji": "💸",
        "use_case": "budget",
        "matcher": lambda l: _is_budget(l),
    },
]


# ── Core computation ──────────────────────────────────────────────────────────

def _bucket_day(dt: datetime) -> str:
    """Return YYYY-MM-DD for bucketing."""
    return dt.strftime("%Y-%m-%d") if dt else ""


def _assign_categories(listings: list[Listing]) -> dict[str, list[Listing]]:
    """Assign each listing to the first matching category."""
    buckets: dict[str, list[Listing]] = {d["name"]: [] for d in _CATEGORY_DEFS}
    for listing in listings:
        for cat in _CATEGORY_DEFS:
            try:
                if cat["matcher"](listing):
                    buckets[cat["name"]].append(listing)
                    break
            except Exception:
                continue
    return buckets


def _is_gem(listing: Listing) -> bool:
    return listing.classification in (
        Classification.gem, Classification.amazing_gem
    )


def _compute_sparkline(listings: list[Listing], days: int = 7) -> list[int]:
    """Return a list of `days` counts — how many listings arrived each day."""
    now = datetime.utcnow()
    counts = [0] * days
    for l in listings:
        if not l.first_seen_at:
            continue
        delta = (now - l.first_seen_at).days
        if 0 <= delta < days:
            counts[days - 1 - delta] += 1
    return counts


def _trend_dir(sparkline: list[int]) -> str:
    """Compare last 3 days vs prior 3 days."""
    if len(sparkline) < 6:
        return "stable"
    recent = sum(sparkline[-3:])
    prior  = sum(sparkline[-6:-3])
    if prior == 0:
        return "rising" if recent > 0 else "stable"
    ratio = recent / prior
    if ratio >= 1.25:
        return "rising"
    if ratio <= 0.75:
        return "falling"
    return "stable"


def _demand_strength(listings: list[Listing]) -> str:
    """High / Medium / Low based on volume + gem rate."""
    count = len(listings)
    if count == 0:
        return "Low"
    gem_count = sum(1 for l in listings if _is_gem(l))
    gem_rate = gem_count / count
    if count >= 30 and gem_rate >= 0.15:
        return "High"
    if count >= 15 or gem_rate >= 0.08:
        return "Medium"
    return "Low"


def _avg_profit(listings: list[Listing]) -> Optional[float]:
    profits = [l.estimated_profit for l in listings if l.estimated_profit is not None]
    if not profits:
        return None
    return round(sum(profits) / len(profits), 2)


def _avg_price(listings: list[Listing]) -> Optional[float]:
    prices = [l.price for l in listings if l.price is not None]
    if not prices:
        return None
    return round(sum(prices) / len(prices), 2)


def _insight(name: str, trend: str, strength: str, count: int, gem_count: int) -> str:
    """Generate a short, human-readable insight string."""
    if count == 0:
        return "No listings found yet."
    gem_rate_pct = round(gem_count / count * 100) if count else 0

    if trend == "rising" and strength == "High":
        return f"🔥 Hot category — {gem_rate_pct}% gem rate, demand accelerating."
    if trend == "rising" and strength == "Medium":
        return f"📈 Growing — {count} listings, {gem_count} gems. Watch this space."
    if trend == "falling" and strength == "Low":
        return f"❄️ Cooling off — volume dropping. Focus elsewhere for now."
    if strength == "High":
        return f"✅ Consistent demand — {gem_rate_pct}% gem rate across {count} listings."
    if strength == "Medium":
        return f"⚖️ Moderate volume ({count} listings). {gem_count} flip opportunities."
    return f"📊 {count} listings scanned, {gem_count} gems found ({gem_rate_pct}%)."


# ── Public API ────────────────────────────────────────────────────────────────

async def compute_demand(db: AsyncSession) -> list[dict]:
    """
    Compute demand signals for all categories.
    Returns a list of category dicts, sorted by demand strength desc.
    """
    result = await db.execute(
        select(Listing).where(Listing.status == ListingStatus.active)
    )
    listings = list(result.scalars().all())

    buckets = _assign_categories(listings)

    output = []
    for cat_def in _CATEGORY_DEFS:
        name = cat_def["name"]
        cat_listings = buckets[name]
        sparkline = _compute_sparkline(cat_listings, days=7)
        trend = _trend_dir(sparkline)
        strength = _demand_strength(cat_listings)
        gem_count = sum(1 for l in cat_listings if _is_gem(l))

        output.append({
            "name": name,
            "emoji": cat_def["emoji"],
            "use_case": cat_def["use_case"],
            "count": len(cat_listings),
            "gem_count": gem_count,
            "sparkline": sparkline,
            "trend": trend,
            "strength": strength,
            "avg_profit": _avg_profit(cat_listings),
            "avg_price": _avg_price(cat_listings),
            "insight": _insight(name, trend, strength, len(cat_listings), gem_count),
        })

    # Sort: High > Medium > Low, then count desc
    strength_order = {"High": 0, "Medium": 1, "Low": 2}
    output.sort(key=lambda x: (strength_order[x["strength"]], -x["count"]))

    return output


async def compute_auction_intel(db: AsyncSession, limit: int = 20) -> list[dict]:
    """
    Return auction listings ordered by time-to-end (soonest first).
    Only includes listings that are active and have a listing_ends_at.
    """
    now = datetime.utcnow()
    result = await db.execute(
        select(Listing)
        .where(
            and_(
                Listing.status == ListingStatus.active,
                Listing.listing_type == "auction",
                Listing.listing_ends_at > now,
            )
        )
        .order_by(Listing.listing_ends_at.asc())
        .limit(limit)
    )
    auctions = list(result.scalars().all())

    output = []
    for l in auctions:
        ends_at = l.listing_ends_at
        time_left_secs = int((ends_at - now).total_seconds()) if ends_at else None

        # Classify urgency
        if time_left_secs is not None:
            if time_left_secs < 3600:
                urgency = "ending_soon"
            elif time_left_secs < 86400:
                urgency = "today"
            else:
                urgency = "upcoming"
        else:
            urgency = "upcoming"

        output.append({
            "id": l.id,
            "title": l.title,
            "url": l.url,
            "price": l.price,
            "expected_buy_price": l.expected_buy_price,
            "estimated_profit": l.estimated_profit,
            "gem_score": l.gem_score,
            "classification": l.classification.value if l.classification else "unclassified",
            "source_name": l.source_name,
            "listing_ends_at": ends_at.isoformat() if ends_at else None,
            "time_left_secs": time_left_secs,
            "urgency": urgency,
            "image_url": (l.image_urls or [None])[0],
            "cpu": l.cpu,
            "gpu": l.gpu,
        })

    return output
