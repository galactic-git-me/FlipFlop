"""Per-listing scoring pipeline: research (identity -> benchmarks ->
optional Claude, cached across sightings) -> risk -> score (always fresh
against the current price) -> inventory awareness -> watch/seller
intelligence bookkeeping -> ScoredListing.

This is the one place all the gem_radar modules are wired together, so the
"Claude never touches arithmetic", "inventory never touches score", and
"cached research never goes stale on price" invariants are visible in one
spot rather than scattered.
"""
from __future__ import annotations

import asyncio
import time as _time
from collections import defaultdict
from datetime import datetime, timedelta

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar import identity as identity_mod
from app.gem_radar import risk as risk_mod
from app.gem_radar import scoring
from app.gem_radar.adapters.amazon_price import AmazonPriceAdapter
from app.gem_radar.adapters.sold_comps import SoldCompsAdapter
from app.gem_radar.benchmarks import build_price_bundle, normalize_match_key, unavailable_price_bundle
from app.gem_radar.claude_screening import screen_with_claude
from app.gem_radar.inventory_match import fetch_inventory_awareness
from app.gem_radar.marketplace import UNTRUSTED_FOR_PRICE_BENCHMARKS, infer_marketplace
from app.gem_radar.observations import (
    compute_watch_signals,
    get_cached_research,
    get_previous_observation,
    store_cached_research,
    update_observation_category,
)
from app.gem_radar.schemas import ExtractedListing, Identity, RiskFlag, ScoredListing, SellerIntelligence
from app.gem_radar.seller_intelligence import upsert_seller_profile
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing

_diag_log = structlog.get_logger(__name__)

# How long cached identity/benchmark/Claude research stays valid for a given
# listing_id before being re-researched (PRD §24 "researched once,
# referenced twice", §31 caching). Tied to the same freshness window as
# active eBay BIN benchmarks, since that's the most volatile cached input.
RESEARCH_CACHE_MAX_AGE_MINUTES = 120

# BatchPriceIndex: resolved model name -> condition bucket ("new"/"used") ->
# list of (listing_id, delivered_price). Built once per scan (see
# build_batch_price_index below) and threaded through to build_price_bundle
# so a model with several matches already scraped — either in this batch or
# in a past one — doesn't need a fresh eBay Browse API call per listing.
# See benchmarks.fetch_bin_benchmarks.
BatchPriceIndex = dict[str, dict[str, list[tuple[str, float]]]]

# How far back to draw historical same-model prices from
# gem_radar_listing_observations. Every scan already writes to this table
# (record_observation, called for every listing regardless of score) — it's
# a free, ever-growing dataset of real prices we've actually seen, with zero
# external API cost. Long enough to give thin categories a real sample,
# short enough that prices stay representative of the current market.
_HISTORICAL_LOOKBACK_DAYS = 14
_HISTORICAL_QUERY_LIMIT = 20_000

# The 3 historical DB queries in build_batch_price_index (title/observations,
# canonical_model_id/scored_listings, epid/observations) scan up to
# _HISTORICAL_QUERY_LIMIT rows each and regex-parse every title via
# identity.resolve_identity — real cost that scales with how much the tables
# have grown. Submissions land every few seconds per marketplace/page during
# a scan (see scan-orchestrator.ts submitPage), so consecutive submissions
# within this window are looking at the same 14-day window and will not see
# meaningfully different historical data — short-TTL caching this trades a
# small staleness window for skipping the rebuild on every single submission.
_HISTORICAL_INDEX_CACHE_TTL_SECONDS = 60.0

_historical_index_cache: BatchPriceIndex | None = None
_historical_index_cache_built_at: float = 0.0
_historical_index_cache_lock = asyncio.Lock()


def _bucket_for_condition(condition_normalised: str) -> str | None:
    if condition_normalised == "new":
        return "new"
    if condition_normalised in ("used", "refurbished"):
        return "used"
    return None


# Namespaced so canonical-ID-keyed buckets never collide with a
# normalize_match_key(title)-derived key — those only ever contain uppercase
# alphanumerics, never a colon. Canonical keys bypass normalize_match_key
# entirely (the ids are already stable identifiers), so lookups must use
# these exact same prefixes rather than routing through it.
def _epid_key(epid: str) -> str:
    return f"EPID:{epid}"

def _gtin_key(gtin: str) -> str:
    return f"GTIN:{gtin}"

def _mpn_key(mpn: str) -> str:
    return f"MPN:{mpn}"

def _model_number_key(model_number: str) -> str:
    return f"MODELNUM:{model_number}"


def _merge_bucket_dicts(
    a: dict[str, list[tuple[str, float]]] | None, b: dict[str, list[tuple[str, float]]] | None
) -> dict[str, list[tuple[str, float]]] | None:
    """Unions two {bucket -> [(listing_id, price), ...]} dicts, deduping by
    listing_id (first occurrence wins) so a listing that happens to appear
    under both a title-derived key and an epid key doesn't get double-counted
    in the merged sample."""
    if not a:
        return b
    if not b:
        return a
    merged: dict[str, list[tuple[str, float]]] = {}
    for bucket in ("new", "used"):
        seen: dict[str, float] = {}
        for listing_id, price in [*a.get(bucket, []), *b.get(bucket, [])]:
            seen.setdefault(listing_id, price)
        merged[bucket] = list(seen.items())
    return merged


def _make_index_adders(index: BatchPriceIndex):
    """Shared bucket-adding closures over a given index dict — used both for
    the per-request current-batch index and the cached historical index, so
    the two build the exact same bucket shape independently before being
    merged in build_batch_price_index."""

    def _add(key: str, bucket: str, listing_id: str, delivered_price: float) -> None:
        # Normalised so cosmetic title-wording differences (case, spacing,
        # hyphens) don't fragment the same product into separate buckets —
        # see benchmarks.normalize_match_key.
        index[normalize_match_key(key)][bucket].append((listing_id, delivered_price))

    def _add_epid(epid: str, bucket: str, listing_id: str, delivered_price: float) -> None:
        # Bypasses normalize_match_key deliberately — epid is already a
        # stable, canonical eBay identifier, not free text to collapse.
        index[_epid_key(epid)][bucket].append((listing_id, delivered_price))

    def _add_gtin(gtin: str, bucket: str, listing_id: str, delivered_price: float) -> None:
        # GTIN (Global Trade Item Number / UPC barcode) is a canonical product
        # identifier that consolidates the same product across all title variants.
        # Preferred over epid for matching since it works across retailers.
        index[_gtin_key(gtin)][bucket].append((listing_id, delivered_price))

    def _add_mpn(mpn: str, bucket: str, listing_id: str, delivered_price: float) -> None:
        # Manufacturer Part Number is a backup canonical identifier when GTIN
        # is unavailable, still far more stable than title-based matching.
        index[_mpn_key(mpn)][bucket].append((listing_id, delivered_price))

    def _add_model_number(model_number: str, bucket: str, listing_id: str, delivered_price: float) -> None:
        # Product model number from vendor API (eBay productSummary.modelNumber).
        # Stable across title variants, third-priority key after GTIN/MPN.
        index[_model_number_key(model_number)][bucket].append((listing_id, delivered_price))

    def _add_from_title(listing_id: str, title: str, condition_normalised: str, delivered_price: float) -> None:
        if identity_mod.is_likely_accessory(title):
            return
        resolved = identity_mod.resolve_identity(title, delivered_price)
        if not resolved.model:
            return
        bucket = _bucket_for_condition(condition_normalised)
        if bucket is None:
            return
        _add(resolved.model, bucket, listing_id, delivered_price)

    return _add, _add_epid, _add_gtin, _add_mpn, _add_model_number, _add_from_title


async def _fetch_historical_price_index(db: AsyncSession) -> BatchPriceIndex:
    """Runs the 3 historical DB queries (title/observations, canonical_model_id
    /scored_listings, epid/observations) that build_batch_price_index used to
    run inline on every call — factored out so the result can be cached (see
    _historical_index_cache) instead of rebuilt from scratch per submission."""
    index: BatchPriceIndex = defaultdict(lambda: {"new": [], "used": []})
    _add, _add_epid, _add_gtin, _add_mpn, _add_model_number, _add_from_title = _make_index_adders(index)

    cutoff = datetime.utcnow() - timedelta(days=_HISTORICAL_LOOKBACK_DAYS)
    result = await db.execute(
        select(
            GemRadarListingObservation.listing_id,
            GemRadarListingObservation.title,
            GemRadarListingObservation.condition_normalised,
            GemRadarListingObservation.delivered_price,
            GemRadarListingObservation.gtin,
            GemRadarListingObservation.mpn,
            GemRadarListingObservation.model_number,
            GemRadarListingObservation.epid,
        )
        .where(
            GemRadarListingObservation.observed_at >= cutoff,
            # NULL source (rows written before this column existed) is
            # "unknown," not "untrusted" — SQL's NOT IN excludes NULLs
            # outright, which would silently drop all pre-migration history
            # from the index. Only positively-identified Temu rows get cut.
            or_(
                GemRadarListingObservation.source.is_(None),
                GemRadarListingObservation.source.not_in(UNTRUSTED_FOR_PRICE_BENCHMARKS),
            ),
        )
        .limit(_HISTORICAL_QUERY_LIMIT)
    )
    for listing_id, title, condition_normalised, delivered_price, gtin, mpn, model_number, epid in result.all():
        _add_from_title(listing_id, title, condition_normalised, delivered_price)
        bucket = _bucket_for_condition(condition_normalised)
        if bucket is not None:
            # Add canonical identifiers from historical observations in priority order
            if gtin:
                _add_gtin(gtin, bucket, listing_id, delivered_price)
            if mpn:
                _add_mpn(mpn, bucket, listing_id, delivered_price)
            if model_number:
                _add_model_number(model_number, bucket, listing_id, delivered_price)
            if epid:
                _add_epid(epid, bucket, listing_id, delivered_price)

    canonical_result = await db.execute(
        select(
            GemRadarScoredListing.listing_id,
            GemRadarScoredListing.canonical_model_id,
            GemRadarScoredListing.condition,
            GemRadarScoredListing.delivered_price,
        )
        .where(
            GemRadarScoredListing.scored_at >= cutoff,
            GemRadarScoredListing.canonical_model_id.is_not(None),
            GemRadarScoredListing.classification.in_(("SUPER_GEM", "GEM")),
            GemRadarScoredListing.source.not_in(UNTRUSTED_FOR_PRICE_BENCHMARKS),
        )
        .limit(_HISTORICAL_QUERY_LIMIT)
    )
    for listing_id, canonical_model_id, condition_normalised, delivered_price in canonical_result.all():
        bucket = _bucket_for_condition(condition_normalised or "")
        if bucket is None:
            continue
        _add(canonical_model_id, bucket, listing_id, delivered_price)

    # Source 4: any listing (any classification tier) observed in the last
    # _HISTORICAL_LOOKBACK_DAYS days with an eBay epid — no GEM/SUPER_GEM
    # restriction, unlike the canonical_model_id source above (see docstring).
    epid_result = await db.execute(
        select(
            GemRadarListingObservation.listing_id,
            GemRadarListingObservation.epid,
            GemRadarListingObservation.condition_normalised,
            GemRadarListingObservation.delivered_price,
        )
        .where(
            GemRadarListingObservation.observed_at >= cutoff,
            GemRadarListingObservation.epid.is_not(None),
            or_(
                GemRadarListingObservation.source.is_(None),
                GemRadarListingObservation.source.not_in(UNTRUSTED_FOR_PRICE_BENCHMARKS),
            ),
        )
        .limit(_HISTORICAL_QUERY_LIMIT)
    )
    for listing_id, epid, condition_normalised, delivered_price in epid_result.all():
        bucket = _bucket_for_condition(condition_normalised)
        if bucket is None:
            continue
        _add_epid(epid, bucket, listing_id, delivered_price)

    return index


async def _get_cached_historical_price_index(db: AsyncSession) -> BatchPriceIndex:
    """Returns _fetch_historical_price_index's result, rebuilding only once
    every _HISTORICAL_INDEX_CACHE_TTL_SECONDS instead of on every call. The
    lock ensures concurrent submissions racing a cold/expired cache trigger
    one rebuild, not one each."""
    global _historical_index_cache, _historical_index_cache_built_at

    now = _time.monotonic()
    if _historical_index_cache is not None and (now - _historical_index_cache_built_at) < _HISTORICAL_INDEX_CACHE_TTL_SECONDS:
        return _historical_index_cache

    async with _historical_index_cache_lock:
        # Re-check after acquiring the lock — another task may have already
        # rebuilt it while this one was waiting.
        now = _time.monotonic()
        if _historical_index_cache is not None and (now - _historical_index_cache_built_at) < _HISTORICAL_INDEX_CACHE_TTL_SECONDS:
            return _historical_index_cache

        fresh = await _fetch_historical_price_index(db)
        _historical_index_cache = fresh
        _historical_index_cache_built_at = _time.monotonic()
        return fresh


async def build_batch_price_index(db: AsyncSession, listings: list[ExtractedListing]) -> BatchPriceIndex:
    """Groups same-model listings into new/used price buckets, drawing from
    FOUR sources: (1) this scan's own listings, keyed by the regex-derived
    model (no per-listing canonical id exists yet — that's only assigned
    during THIS scan's own deep-research pass, too late to key its own
    lookup); (2) every listing observed in the last _HISTORICAL_LOOKBACK_DAYS
    days via gem_radar_listing_observations, also regex-keyed; (3) every
    GEM/SUPER_GEM-tier listing SCORED in that window with a Claude-assigned
    canonical_model_id (see claude_screening.py), keyed by that stable
    identifier instead; (4) every listing (this scan or historical, ANY
    tier) that carries an eBay-assigned epid (Browse API catalog product
    ID), keyed by that id directly. (3) and (4) are what actually fix
    cross-listing matching — a listing whose title varies from a past
    sighting's title (different word order, "Core" present/absent, SKU code
    placement) now lands in the same bucket, where regex-only matching would
    have fragmented them into separate keys. (4) doesn't need the GEM/
    SUPER_GEM restriction (3) has: canonical_model_id is only ever assigned
    during the deep-research pass reserved for top candidates, but epid comes
    straight from eBay on every Browse-API-sourced listing regardless of
    tier, so its historical pool is far larger. Multiple sources can include
    the same underlying listing_id under different keys; that's fine, each
    source only ever gets consulted by a lookup for its own key type — see
    _get_or_compute_research, which merges the epid-keyed and title/
    canonical-keyed buckets for a given listing rather than picking one.

    Sources (2)-(4) (the historical DB queries) are shared across calls via
    _get_cached_historical_price_index rather than re-queried every time —
    see _HISTORICAL_INDEX_CACHE_TTL_SECONDS. Only source (1), this call's own
    batch, is built fresh every time.

    Marketplaces in UNTRUSTED_FOR_PRICE_BENCHMARKS (Temu: counterfeit/
    drop-ship risk for PC components) are excluded from ALL sources — their
    listings can still be scored as candidates themselves, they just never
    get to set the price bar other listings are measured against."""
    batch_index: BatchPriceIndex = defaultdict(lambda: {"new": [], "used": []})
    _add, _add_epid, _add_gtin, _add_mpn, _add_model_number, _add_from_title = _make_index_adders(batch_index)

    for listing in listings:
        if infer_marketplace(listing.url) in UNTRUSTED_FOR_PRICE_BENCHMARKS:
            continue
        _add_from_title(listing.listing_id, listing.title, listing.condition_normalised, listing.current_delivered_price)
        bucket = _bucket_for_condition(listing.condition_normalised)
        if bucket is not None:
            # Prefer canonical identifiers (GTIN > MPN > model_number > epid) for grouping,
            # as they consolidate the same product across all title variants and retailers.
            # All keys are added (not mutually exclusive) so any lookup path can find matches.
            if listing.gtin:
                _add_gtin(listing.gtin, bucket, listing.listing_id, listing.current_delivered_price)
            if listing.mpn:
                _add_mpn(listing.mpn, bucket, listing.listing_id, listing.current_delivered_price)
            if listing.model_number:
                _add_model_number(listing.model_number, bucket, listing.listing_id, listing.current_delivered_price)
            if listing.epid:
                _add_epid(listing.epid, bucket, listing.listing_id, listing.current_delivered_price)

    historical_index = await _get_cached_historical_price_index(db)
    merged: BatchPriceIndex = defaultdict(lambda: {"new": [], "used": []})
    for key in set(batch_index) | set(historical_index):
        merged[key] = _merge_bucket_dicts(batch_index.get(key), historical_index.get(key)) or {"new": [], "used": []}
    return merged


async def _get_last_canonical_model_id(db: AsyncSession, listing_id: str) -> str | None:
    """Whether this exact listing_id already earned a Claude canonical_model_id
    in a past scan — checked beyond the short research-cache window so a
    listing keeps its canonical key permanently once assigned, rather than
    reverting to raw-regex matching the moment the cache entry ages out."""
    result = await db.execute(
        select(GemRadarScoredListing.canonical_model_id)
        .where(
            GemRadarScoredListing.listing_id == listing_id,
            GemRadarScoredListing.canonical_model_id.is_not(None),
        )
        .order_by(GemRadarScoredListing.scored_at.desc())
        .limit(1)
    )
    value = result.scalar_one_or_none()
    # Ends the transaction this SELECT implicitly opened now, not whenever
    # the caller eventually commits — otherwise it stays open across every
    # external call (eBay/Amazon/Claude) still ahead in this request,
    # holding a DB connection idle-in-transaction the whole time.
    await db.commit()
    return value


async def _get_or_compute_research(
    db: AsyncSession,
    listing: ExtractedListing,
    sold_adapter: SoldCompsAdapter,
    amazon_adapter: AmazonPriceAdapter,
    deep_research: bool,
    batch_price_index: BatchPriceIndex | None = None,
    cpk: str | None = None,  # Canonical Product Key for cross-vendor pricing
) -> tuple[Identity, "object", list, str | None, int | None]:  # prices: PriceBundle
    _research_t0 = _time.monotonic()
    _stage_timings: dict[str, float] = {}

    _s = _time.monotonic()
    cached = await get_cached_research(db, listing.listing_id, RESEARCH_CACHE_MAX_AGE_MINUTES)
    _stage_timings["cache_lookup_s"] = round(_time.monotonic() - _s, 3)
    risk_flags = risk_mod.detect_risk_flags(listing.title, listing.condition_raw)

    if cached is not None and not deep_research:
        # A cache hit already satisfies Stage A; Stage B (deep_research=True)
        # always re-runs Claude even on a cache hit, since screening budget
        # is spent deliberately on the current scan's top candidates and a
        # stale reasoning summary from a cheap-pass sighting shouldn't stand
        # in for it.
        _stage_timings["total_s"] = round(_time.monotonic() - _research_t0, 3)
        if _stage_timings["total_s"] > 1.0:
            _diag_log.info("diag.research.timings", listing_id=listing.listing_id, cache_hit=True, **_stage_timings)
        return cached.identity, cached.prices, risk_flags, cached.reasoning_summary, cached.release_year

    if cached is not None and deep_research:
        identity, prices = cached.identity, cached.prices
    else:
        _s = _time.monotonic()
        resolved = identity_mod.resolve_identity(listing.title, listing.current_delivered_price)
        _stage_timings["identity_resolve_s"] = round(_time.monotonic() - _s, 3)
        # A cache miss (>RESEARCH_CACHE_MAX_AGE_MINUTES old, or first sighting
        # this scan) loses the short-lived research cache, but a Claude-
        # assigned canonical_model_id should stick to this listing_id
        # permanently once earned — check for one from any past scan.
        _s = _time.monotonic()
        prior_canonical = await _get_last_canonical_model_id(db, listing.listing_id)
        _stage_timings["prior_canonical_lookup_s"] = round(_time.monotonic() - _s, 3)
        identity = Identity(
            brand=resolved.brand,
            model=resolved.model,
            mpn=resolved.mpn,
            category=resolved.category,
            exact_sku_confidence=resolved.exact_sku_confidence,
            model_canonical=prior_canonical,
        )
        if identity_mod.is_likely_accessory(listing.title):
            # Packaging/protection for a component, not the component itself
            # — comparing its price against real component market data would
            # silently mismatch it against unrelated products (see
            # identity.is_likely_accessory for the observed failure mode).
            prices = unavailable_price_bundle(
                listing.current_delivered_price,
                "Listing looks like component packaging/protection, not the component itself",
            )
        else:
            # Build batch_entries using 5-step canonical identifier priority:
            # Canonical ID consolidation (epid > model_number > title)
            # Check THIS BATCH's price_index for canonical IDs FIRST, then fallback to title
            match_key = identity.model_canonical or identity.model
            query = match_key or listing.title
            match_level = "exact_model_variant" if match_key else "category_comparable"
            batch_entries = None

            # Step 1: eBay epid (most reliable cross-listing consolidation)
            if listing.epid and batch_price_index:
                epid_key = f"EPID:{listing.epid}"
                epid_entries = batch_price_index.get(epid_key)
                if epid_entries:
                    batch_entries = epid_entries
                    match_level = "exact_model_variant"

            # Step 2: Model number (from eBay productSummary)
            if not batch_entries and listing.model_number and batch_price_index:
                model_key = f"MODELNUM:{listing.model_number}"
                model_entries = batch_price_index.get(model_key)
                if model_entries:
                    batch_entries = model_entries
                    match_level = "exact_model_variant"

            # Step 3: Title-based (fallback only if batch_price_index empty or no canonical match)
            if not batch_entries and match_key:
                title_entries = (batch_price_index or {}).get(normalize_match_key(match_key))
                if title_entries:
                    batch_entries = title_entries
            _s = _time.monotonic()
            prices = await build_price_bundle(
                db, listing.current_delivered_price, query, match_level, listing.condition_normalised,
                sold_adapter, amazon_adapter,
                batch_entries=batch_entries, exclude_listing_id=listing.listing_id, cpk=cpk,
            )
            _stage_timings["price_bundle_s"] = round(_time.monotonic() - _s, 3)

    reasoning_summary: str | None = None
    release_year: int | None = None
    if deep_research:
        _s = _time.monotonic()
        claude_result = await screen_with_claude(listing, identity)
        _stage_timings["claude_screening_s"] = round(_time.monotonic() - _s, 3)
        if claude_result is not None:
            reasoning_summary = claude_result.reasoning_summary
            release_year = claude_result.release_year
            use_claude_model = claude_result.identity_confidence > (identity.exact_sku_confidence or 0)
            identity = Identity(
                brand=identity.brand,
                model=(claude_result.canonical_name or identity.model) if use_claude_model else identity.model,
                mpn=identity.mpn,
                category=identity.category,
                exact_sku_confidence=claude_result.identity_confidence if use_claude_model else identity.exact_sku_confidence,
                model_canonical=claude_result.canonical_model_id or identity.model_canonical,
            )
            for note in claude_result.additional_risk_notes:
                risk_flags.append(RiskFlag(code="CLAUDE_NOTED_RISK", severity="low", evidence=note))

    _s = _time.monotonic()
    await store_cached_research(db, listing.listing_id, identity, prices, reasoning_summary, release_year)
    _stage_timings["store_cache_s"] = round(_time.monotonic() - _s, 3)

    _stage_timings["total_s"] = round(_time.monotonic() - _research_t0, 3)
    if _stage_timings["total_s"] > 1.0:
        _diag_log.info("diag.research.timings", listing_id=listing.listing_id, cache_hit=False, **_stage_timings)
    return identity, prices, risk_flags, reasoning_summary, release_year


async def score_listing(
    db: AsyncSession,
    listing: ExtractedListing,
    rank: int,
    sold_adapter: SoldCompsAdapter,
    amazon_adapter: AmazonPriceAdapter,
    deep_research: bool,
    batch_price_index: BatchPriceIndex | None = None,
) -> ScoredListing:
    _score_t0 = _time.monotonic()

    # Fetch CPK for cross-vendor consolidation (if available)
    cpk: str | None = None
    try:
        from sqlalchemy import text
        cpk_result = await db.execute(
            text("SELECT cpk FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"),
            {"listing_id": listing.listing_id}
        )
        cpk_row = cpk_result.fetchone()
        if cpk_row:
            cpk = cpk_row[0]
    except Exception:
        pass  # CPK lookup failed, proceed without it

    _s = _time.monotonic()
    identity, prices, risk_flags, reasoning_summary, release_year = await _get_or_compute_research(
        db, listing, sold_adapter, amazon_adapter, deep_research, batch_price_index, cpk=cpk
    )
    _research_s = round(_time.monotonic() - _s, 3)

    penalty = risk_mod.risk_penalty(risk_flags)

    _s = _time.monotonic()
    deal_score, benchmark_label = scoring.compute_deal_score(listing, prices, penalty)
    market_stat, _ = scoring.pick_condition_benchmark(listing.condition_normalised, prices)
    classification = scoring.classify(
        deal_score, benchmark_label, identity.category, listing.current_delivered_price, market_stat
    )
    confidence_score, confidence_band = scoring.compute_confidence(
        identity, prices, listing.condition_normalised, listing, benchmark_label
    )
    decision = scoring.compute_decision(classification, confidence_band, risk_flags)
    flip_score = scoring.compute_flip_score(deal_score, prices, listing.condition_normalised)
    build_value_score = scoring.compute_build_value_score(deal_score, identity)
    offer_strategy = scoring.compute_offer_strategy(
        listing.current_delivered_price, prices, listing.condition_normalised, confidence_band
    )
    _scoring_calc_s = round(_time.monotonic() - _s, 3)

    _s = _time.monotonic()
    inventory_awareness = await fetch_inventory_awareness(db, identity.category, identity.model, identity.brand)
    _inventory_s = round(_time.monotonic() - _s, 3)

    scored = ScoredListing(
        rank=rank,
        listing=listing,
        identity=identity,
        prices=prices,
        deal_score=deal_score,
        classification=classification,
        confidence_score=confidence_score,
        confidence_band=confidence_band,
        decision=decision,
        flip_score=flip_score,
        build_value_score=build_value_score,
        inventory_awareness=inventory_awareness,
        risk_flags=risk_flags,
        offer_strategy=offer_strategy,
        reasoning_summary=reasoning_summary,
        release_year=release_year,
        watch_signals=None,
        seller_intelligence=None,
    )

    # Queue high-scoring listings for async margin verification via Qwen2:7b.
    # This ensures only truly profitable flips reach the sourcing page, without
    # blocking the main scoring pipeline.
    _s = _time.monotonic()
    if deal_score >= 7.5 and classification in ("GEM", "SUPER_GEM"):
        from app.gem_radar.margin_verifier import enqueue_verification
        market_resale_median = market_stat.median if market_stat.status == "ok" else None
        market_resale_range = (
            (market_stat.min or market_resale_median or 0, market_stat.max or market_resale_median or 0)
            if market_resale_median
            else None
        )
        await enqueue_verification(
            listing_id=listing.listing_id,
            title=listing.title,
            purchase_price=listing.current_delivered_price,
            condition=listing.condition_normalised,
            market_resale_median=market_resale_median,
            market_resale_range=market_resale_range,
        )
    _verification_enqueue_s = round(_time.monotonic() - _s, 3)

    _total_s = round(_time.monotonic() - _score_t0, 3)
    if _total_s > 1.0:
        _diag_log.info(
            "diag.score_listing.timings",
            listing_id=listing.listing_id,
            deep_research=deep_research,
            research_s=_research_s,
            scoring_calc_s=_scoring_calc_s,
            inventory_s=_inventory_s,
            verification_enqueue_s=_verification_enqueue_s,
            total_s=_total_s,
        )

    return scored


async def apply_watchlist_and_seller_intelligence(
    db: AsyncSession, result: ScoredListing, search_run_id: str | None = None
) -> ScoredListing:
    """Runs the once-per-scan-per-listing bookkeeping: price-history
    recording, change/relisting detection, and seller-profile aggregation.

    Deliberately kept OUT of score_listing() — a listing can be scored
    twice within one /scans request (once cheap, once with deep_research
    when it makes the top-N cut per PRD §30), and observation/seller-count
    side effects must fire exactly once per listing per scan regardless of
    how many times its price/identity were computed. Call this once, on the
    final chosen result, after cheap-vs-deep resolution.
    """
    listing = result.listing

    previous_observation = await get_previous_observation(db, listing.listing_id)
    watch_signals = await compute_watch_signals(db, listing, previous_observation)
    # The observation row for this sighting was already written by
    # _submit_scan_body's dedup loop, before identity resolution had run —
    # this just fills in the category now that it's known, rather than
    # inserting a second row for the same sighting.
    await update_observation_category(db, listing.listing_id, search_run_id, result.identity.category)

    seller_profile = await upsert_seller_profile(db, listing, result.classification)
    seller_intelligence = (
        SellerIntelligence(
            sellerName=seller_profile.seller_name,
            feedbackPercent=seller_profile.feedback_percent,
            feedbackCount=seller_profile.feedback_count,
            sellerType=seller_profile.seller_type,
            observedListings=seller_profile.observed_listings_count,
            historicalGemCount=seller_profile.historical_gem_count,
            historicalSuperGemCount=seller_profile.historical_super_gem_count,
            historicalPurchaseCount=seller_profile.historical_purchase_count,
            cancellationCount=seller_profile.cancellation_count,
            issueCount=seller_profile.issue_count,
        )
        if seller_profile is not None
        else None
    )

    return result.model_copy(update={"watch_signals": watch_signals, "seller_intelligence": seller_intelligence})
