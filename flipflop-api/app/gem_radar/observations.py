"""Listing-sighting ledger: price-history/change detection (PRD §23),
relisting detection (PRD §24), and a research cache for cross-search
dedup/cost-control (PRD §24 "researched once, referenced twice", §31).

Cache granularity note: only the EXPENSIVE, slow-changing research
(identity resolution, benchmark fetch, Claude reasoning) is cached — the
deal score itself is always recomputed against the listing's current price
on every sighting, never served stale, since a price change between
sightings is exactly the signal §23 watchlist mode exists to catch.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.app_settings import AppSettings
from app.gem_radar.marketplace import infer_marketplace
from app.gem_radar.schemas import ExtractedListing, Identity, PriceBundle, PriceObservation, WatchSignals

# Fallbacks used only if the app_settings row doesn't exist yet (fresh
# install, before the extension has ever synced these values) — match the
# extension's own SchedulerConfigSchema/RetentionConfigSchema defaults.
_DEFAULT_SCAN_INTERVAL_MINUTES = 180
_DEFAULT_CONSECUTIVE_MISSES_BEFORE_INACTIVE = 2


async def get_current_scan_interval_minutes(db: AsyncSession) -> int:
    result = await db.execute(select(AppSettings.gem_radar_scan_interval_minutes).where(AppSettings.name == "default"))
    value = result.scalar_one_or_none()
    return value if value is not None else _DEFAULT_SCAN_INTERVAL_MINUTES


async def get_consecutive_misses_before_inactive(db: AsyncSession) -> int:
    result = await db.execute(
        select(AppSettings.gem_radar_consecutive_misses_before_inactive).where(AppSettings.name == "default")
    )
    value = result.scalar_one_or_none()
    return value if value is not None else _DEFAULT_CONSECUTIVE_MISSES_BEFORE_INACTIVE


async def get_active_listing_ids(db: AsyncSession) -> set[str]:
    """Listing IDs observed within the last 24 hours. Simple time-based approach:
    if a listing was seen in the last 24 hours, it's active. If it hasn't been
    seen for 24+ hours, it's inactive (but never deleted — retained for historical
    price benchmarking).

    Based on GemRadarListingObservation.search_run_id, NOT
    GemRadarScoredListing — this is the critical distinction. A listing that
    keeps showing up in scrapes but hasn't changed price gets deduped out of
    re-scoring for 7 days (see submit_scan), so gem_radar_scored_listings
    only gets a new row when something is genuinely new or stale. If "active"
    were based on that table, a listing would silently age out within hours
    even though it never stopped appearing — it just wasn't novel enough to
    re-score. Observations are different: every sighting touches its row
    (see touch_observation for the deduped path, record_observation for the
    fresh path), so observed_at genuinely means "still turning up in scrapes,"
    which is what "active" is supposed to mean.

    Everything in the app (dashboards, tables, charts) should filter through
    this — but historical/inactive rows are NEVER deleted and remain fully
    usable for market-price benchmarking (build_batch_price_index draws on
    ALL historical observations regardless of active status)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await db.execute(
        select(GemRadarListingObservation.listing_id)
        .where(GemRadarListingObservation.observed_at >= cutoff.replace(tzinfo=None))
        .distinct()
    )
    return {row[0] for row in result.all()}


async def get_active_buy_it_now_listing_ids(db: AsyncSession) -> set[str]:
    """Currently observed fixed-price listings suitable for sourcing cards.

    Auction lots belong in Auction Intel, never Gem-of-Day/component cards.
    This reads the sighting ledger because the scored table does not retain
    listing_type and a bulk rescore can make an old row's scored_at look new.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(GemRadarListingObservation.listing_id)
        .where(
            GemRadarListingObservation.observed_at >= cutoff.replace(tzinfo=None),
            GemRadarListingObservation.listing_type == "buy_it_now",
        )
        .distinct()
    )
    return {row[0] for row in result.all()}

# How similar two titles from the same seller must be (token-overlap ratio)
# before a new listing_id is treated as a likely relisting of an old one.
_RELISTING_TITLE_SIMILARITY_THRESHOLD = 0.6
# A prior listing must have gone quiet for at least this long before a new
# same-seller/same-title listing counts as a relisting rather than just two
# genuinely different concurrent listings (e.g. a seller with 3 identical cards).
_RELISTING_QUIET_PERIOD_DAYS = 3
_STOPWORDS = {"the", "a", "an", "for", "with", "and", "or", "new", "used"}


def _tokenise(title: str) -> set[str]:
    # Split on hyphens too — eBay titles freely alternate "8-core" / "8 core"
    # / "8Core", and a naive whitespace-only split treats those as
    # unrelated tokens, undercounting genuine title similarity.
    normalised = title.lower().replace("-", " ")
    return {w for w in normalised.split() if w not in _STOPWORDS and len(w) > 1}


def _title_similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokenise(a), _tokenise(b)
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return overlap / max(len(tokens_a), len(tokens_b))


@dataclass
class CachedResearch:
    identity: Identity
    prices: PriceBundle
    reasoning_summary: str | None
    release_year: int | None


async def get_cached_research(db: AsyncSession, listing_id: str, max_age_minutes: int) -> CachedResearch | None:
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(
            GemRadarListingObservation.listing_id == listing_id,
            GemRadarListingObservation.scored_result_json.is_not(None),
        )
        .order_by(GemRadarListingObservation.scored_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None or row.scored_at is None:
        await db.commit()
        return None
    age = datetime.now(timezone.utc) - row.scored_at.replace(tzinfo=timezone.utc)
    if age > timedelta(minutes=max_age_minutes):
        await db.commit()
        return None

    data = json.loads(row.scored_result_json)
    cached = CachedResearch(
        identity=Identity.model_validate(data["identity"]),
        prices=PriceBundle.model_validate(data["prices"]),
        reasoning_summary=data.get("reasoningSummary"),
        release_year=data.get("releaseYear"),
    )
    # Ends the transaction this SELECT implicitly opened now — the caller
    # goes on to await external calls (eBay/Amazon/Claude) before its own
    # next DB touch, and leaving this open until then means an idle
    # DB connection for the full duration of those external calls.
    await db.commit()
    return cached


async def store_cached_research(
    db: AsyncSession,
    listing_id: str,
    identity: Identity,
    prices: PriceBundle,
    reasoning_summary: str | None,
    release_year: int | None = None,
) -> None:
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id == listing_id)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return  # record_observation() should always run first in the pipeline
    row.scored_result_json = json.dumps(
        {
            "identity": identity.model_dump(by_alias=True, mode="json"),
            "prices": prices.model_dump(by_alias=True, mode="json"),
            "reasoningSummary": reasoning_summary,
            "releaseYear": release_year,
        }
    )
    row.scored_at = datetime.utcnow()
    await db.commit()


async def get_previous_observation(db: AsyncSession, listing_id: str) -> GemRadarListingObservation | None:
    """Must be called BEFORE record_observation() inserts the current sighting."""
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id == listing_id)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_recent_observation(
    db: AsyncSession, listing_id: str, days: int = 7, exclude_search_run_id: str | None = None
) -> GemRadarListingObservation | None:
    """Most recent observation row for this listing_id within the last N
    days (default 7), or None if it hasn't been seen that recently. Callers
    use this both to decide whether a sighting counts as a dedupeable repeat
    AND to compare the stored price against the new sighting's price — see
    _submit_scan_body, which only treats a repeat as fully deduped (touch
    only, skip re-scoring) when the price is unchanged too. A listing whose
    price moved between sightings is exactly the signal PRD §23 watchlist
    mode exists to catch, so it must flow through to a full re-score rather
    than silently being touched with a stale price forever.

    exclude_search_run_id: the CURRENT submission's own search_run_id, so a
    submission never dedupes a listing against an observation it wrote
    itself moments earlier. Without this, a submission interrupted after the
    dedup loop (which commits each observation immediately) but before the
    listing is scored — e.g. a backend restart mid-submission — gets reset
    to "pending" and retried by recover_stuck_processing(), but the retry's
    own dedup check then finds the observation THIS SAME interrupted attempt
    just wrote, sees an identical price (of course — it's the same data),
    and touches/skips it as an already-seen repeat. The listing is never
    actually scored, ever, while still showing "active" forever (touched on
    every future resighting) — a silent, permanent, hard-to-notice data loss
    that only ever surfaces as "why are there so many active listings with
    no price." NULL-search_run_id rows (pre-migration history) are never
    excluded by this — only a genuine match to the run currently in flight."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        GemRadarListingObservation.listing_id == listing_id,
        GemRadarListingObservation.observed_at >= cutoff.replace(tzinfo=None),
    ]
    if exclude_search_run_id is not None:
        conditions.append(
            or_(
                GemRadarListingObservation.search_run_id.is_(None),
                GemRadarListingObservation.search_run_id != exclude_search_run_id,
            )
        )
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(*conditions)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def find_existing_listing(
    db: AsyncSession,
    listing_id: str,
    title: str,
    source: str,
    seller_name: str | None = None,
) -> GemRadarListingObservation | None:
    """Find an existing listing from a previous run for cross-run deduplication.

    Tries to match by:
    1. listing_id (e.g., eBay item ID) — most reliable
    2. Fallback: source + title exact match (+ seller if available)

    Returns most recent observation for this listing if found, enabling:
    - Price update detection (same price → touch only, skip CPK)
    - Price change detection (new price → update price, skip CPK)
    - Cross-run dedup (avoid reprocessing same listings)
    """
    # Try to find by listing_id first (most reliable)
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(
            GemRadarListingObservation.listing_id == listing_id,
            GemRadarListingObservation.source == source,
        )
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    # Fallback: match by vendor + title (exact) + seller if available
    # Do NOT include price in the match (it may legitimately change)
    conditions = [
        GemRadarListingObservation.source == source,
        GemRadarListingObservation.title == title,
    ]
    if seller_name:
        conditions.append(GemRadarListingObservation.seller_name == seller_name)

    result = await db.execute(
        select(GemRadarListingObservation)
        .where(*conditions)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def record_observation(
    db: AsyncSession,
    listing: ExtractedListing,
    category: str | None,
    search_run_id: str | None = None,
    search_query: str | None = None,
) -> GemRadarListingObservation:
    row = GemRadarListingObservation(
        listing_id=listing.listing_id,
        seller_name=listing.seller,
        title=listing.title,
        image_url=listing.image_url,
        category=category,
        condition_normalised=listing.condition_normalised,
        listing_type=listing.listing_type,
        item_price=listing.item_price,
        postage_price=listing.postage_price,
        delivered_price=listing.current_delivered_price,
        bid_count=listing.bid_count,
        best_offer_enabled=listing.best_offer_enabled,
        observed_at=listing.extracted_at.replace(tzinfo=None) if listing.extracted_at.tzinfo else listing.extracted_at,
        search_run_id=search_run_id,
        search_query=search_query,
        source=infer_marketplace(listing.url),
        epid=listing.epid,
        gtin=listing.gtin,
        mpn=listing.mpn,
        model_number=listing.model_number,
        seller_feedback_percent=listing.seller_feedback_percent,
        seller_feedback_count=listing.seller_feedback_count,
        scan_price=listing.scan_price,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_observation_category(
    db: AsyncSession, listing_id: str, search_run_id: str | None, category: str | None
) -> None:
    """Sets category on the observation row record_observation already wrote
    earlier this same scan (see _submit_scan_body, which calls
    record_observation with category=None before identity resolution has
    even run yet). Used by apply_watchlist_and_seller_intelligence once the
    real category is known, instead of that function inserting its own
    second observation row for the same sighting — which used to happen and
    silently doubled gem_radar_listing_observations' row count for every
    fresh listing."""
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id == listing_id)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        row.category = category
        await db.commit()


async def touch_observation(
    db: AsyncSession,
    listing_id: str,
    search_run_id: str,
    observed_at: datetime,
    search_query: str | None = None,
) -> bool:
    """Lightweight "still here" update for a listing the 7-day dedup window
    skipped from full re-scoring: bumps its most recent observation's
    observed_at/search_run_id/search_query WITHOUT creating a new row or
    touching gem_radar_scored_listings. This is what lets
    get_active_listing_ids tell "still appearing in scrapes, just not novel
    enough to re-score" apart from "genuinely gone quiet" — without this, a
    still-live deduped listing would silently read as inactive within a
    couple of scan cycles.

    Returns False (no-op) if this listing has no prior observation row yet —
    that should only happen if is_recent_observation() and this disagree on
    what counts as "seen before", which would itself be a bug worth knowing
    about rather than silently inserting a row here."""
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id == listing_id)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    row.observed_at = observed_at
    row.search_run_id = search_run_id
    if search_query is not None:
        row.search_query = search_query
    await db.commit()
    return True


async def detect_relisting(db: AsyncSession, listing: ExtractedListing) -> str | None:
    """Returns the likely previous listing_id if this looks like a relisting
    (PRD §24) — same seller, similar title, and the candidate has gone quiet
    for _RELISTING_QUIET_PERIOD_DAYS. Returns None rather than guessing when
    there's no seller name to match on (can't be confident without it).
    """
    if not listing.seller:
        return None

    quiet_cutoff = datetime.now(timezone.utc) - timedelta(days=_RELISTING_QUIET_PERIOD_DAYS)
    result = await db.execute(
        select(GemRadarListingObservation.listing_id, GemRadarListingObservation.title)
        .where(
            GemRadarListingObservation.seller_name == listing.seller,
            GemRadarListingObservation.listing_id != listing.listing_id,
            GemRadarListingObservation.observed_at < quiet_cutoff.replace(tzinfo=None),
        )
        .distinct()
    )
    candidates = result.all()
    for candidate_id, candidate_title in candidates:
        if _title_similarity(listing.title, candidate_title) >= _RELISTING_TITLE_SIMILARITY_THRESHOLD:
            return candidate_id
    return None


async def compute_watch_signals(
    db: AsyncSession, listing: ExtractedListing, previous: GemRadarListingObservation | None
) -> WatchSignals:
    relisted_from = await detect_relisting(db, listing) if previous is None else None

    history_result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id == listing.listing_id)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(20)
    )
    history_rows = list(reversed(history_result.scalars().all()))
    history = [
        # observed_at is stored naive-UTC by convention (see DB comparisons
        # above) — attach tzinfo only at the API boundary so the wire format
        # is an unambiguous, RFC3339-compliant "Z"-suffixed timestamp.
        PriceObservation(
            observedAt=r.observed_at.replace(tzinfo=timezone.utc),
            price=r.item_price,
            postage=r.postage_price,
            deliveredPrice=r.delivered_price,
            bidCount=r.bid_count,
            bestOfferEnabled=r.best_offer_enabled,
        )
        for r in history_rows
    ]

    if previous is None:
        return WatchSignals(
            observationCount=len(history) + 1,
            priceDropDetected=False,
            priceDropAmount=None,
            priceDropPercent=None,
            postageChanged=False,
            bidCountChanged=False,
            bestOfferNewlyEnabled=False,
            conditionChanged=False,
            relistingDetected=relisted_from is not None,
            likelyPreviousListingId=relisted_from,
            history=history,
        )

    price_drop_amount = previous.delivered_price - listing.current_delivered_price
    return WatchSignals(
        observationCount=len(history) + 1,
        priceDropDetected=price_drop_amount > 0,
        priceDropAmount=round(price_drop_amount, 2) if price_drop_amount > 0 else None,
        priceDropPercent=round(price_drop_amount / previous.delivered_price * 100, 1)
        if price_drop_amount > 0 and previous.delivered_price > 0
        else None,
        postageChanged=previous.postage_price != listing.postage_price,
        bidCountChanged=previous.bid_count != listing.bid_count,
        bestOfferNewlyEnabled=(not previous.best_offer_enabled) and listing.best_offer_enabled,
        conditionChanged=previous.condition_normalised != listing.condition_normalised,
        relistingDetected=False,  # by definition this listing_id was already seen before
        likelyPreviousListingId=None,
        history=history,
    )


async def get_observation_history(db: AsyncSession, listing_id: str, limit: int = 20) -> list[PriceObservation]:
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.listing_id == listing_id)
        .order_by(GemRadarListingObservation.observed_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [
        PriceObservation(
            observedAt=r.observed_at.replace(tzinfo=timezone.utc),
            price=r.item_price,
            postage=r.postage_price,
            deliveredPrice=r.delivered_price,
            bidCount=r.bid_count,
            bestOfferEnabled=r.best_offer_enabled,
        )
        for r in rows
    ]


async def cleanup_old_observations(db: AsyncSession, retention_days: int, preserve_listing_ids: set[str]) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(
        select(GemRadarListingObservation).where(GemRadarListingObservation.observed_at < cutoff.replace(tzinfo=None))
    )
    stale = [row for row in result.scalars().all() if row.listing_id not in preserve_listing_ids]
    for row in stale:
        await db.delete(row)
    if stale:
        await db.commit()
    return len(stale)


async def cleanup_old_scored_listings(db: AsyncSession, retention_days: int, preserve_listing_ids: set[str]) -> int:
    """Mirrors cleanup_old_observations above, but for gem_radar_scored_listings
    — previously unpruned entirely, so it grew forever while the observation
    ledger it's derived from was already being capped at the same window.
    Keyed on scored_at (when this row's classification/deal_score was
    computed), not listing_observed_at, since a listing re-scored recently
    off an old sighting should still count as fresh."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(
        select(GemRadarScoredListing).where(GemRadarScoredListing.scored_at < cutoff.replace(tzinfo=None))
    )
    stale = [row for row in result.scalars().all() if row.listing_id not in preserve_listing_ids]
    for row in stale:
        await db.delete(row)
    if stale:
        await db.commit()
    return len(stale)
