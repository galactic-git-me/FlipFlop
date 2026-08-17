"""Five-price benchmark model (PRD §11-14).

New/Used BIN is computed purely from our own scraped listing history
(gem_radar_listing_observations) — no live eBay Browse API call in this path
at all. We already scrape eBay/Vinted/Overclockers/Temu/Amazon continuously;
polling eBay's Browse API separately for "what's currently listed" duplicates
data we're already collecting, and was the single biggest source of avoidable
eBay API traffic before this rewrite. New/Used Sold comes from a scrape of
eBay's public sold-listings search (adapters/sold_comps.py) — the one benchmark
we genuinely have no other source for — persisted to gem_radar_sold_observations
so it's scraped once per model+condition and reused, not re-scraped per listing.
Amazon UK New remains "unavailable" in production today (see adapters/) — this
module treats that as first-class, not a partial failure: it degrades the
benchmark priority chain (PRD §13) explicitly rather than filling the gap
with an invented number.

Both eBay-facing paths only ever fetch/compute the ONE condition side that
matches the listing actually being scored — scoring.compute_deal_score and
pick_condition_benchmark only ever read the same-condition side of a
PriceBundle (a used listing is never compared against new-condition
benchmarks or vice versa), so computing the opposite side was always
discarded work.
"""
from __future__ import annotations

import re
import statistics
import time as _time
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, text

_diag_log = structlog.get_logger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.adapters.sold_comps import SoldCompsAdapter
from app.gem_radar.adapters.amazon_price import AmazonPriceAdapter
from app.gem_radar.schemas import BenchmarkStat, ExclusionReason, PriceBundle
from app.models.gem_radar_sold_observation import GemRadarSoldObservation
from app.models.gem_radar_amazon_observation import GemRadarAmazonObservation

MIN_SAMPLE_FOR_MEDIAN = 2
TRIM_FRACTION = 0.1
_SOLD_LOOKBACK_DAYS = 14

_NOT_NEEDED_REASON = "Not needed — doesn't match this listing's own condition"


def normalize_match_key(model: str) -> str:
    """Collapses cosmetic title-wording differences (case, spacing, hyphens,
    punctuation) that would otherwise fragment the same product into
    different price-index buckets — e.g. "RTX 3080" and "RTX3080" both
    reduce to "RTX3080". Does NOT fix missing/extra descriptive words (e.g.
    "Intel Core i7-10850H" vs "Intel i7 10850H" still differ) — that needs
    category-specific extraction improvements, a separate, larger effort.
    Used only as an index/lookup key; the human-readable identity.model
    string is untouched."""
    return re.sub(r"[^A-Z0-9]", "", model.upper())


def _unavailable_stat(source: str, reason: str) -> BenchmarkStat:
    return BenchmarkStat(
        status="unavailable",
        average=None,
        median=None,
        trimmed_mean=None,
        min=None,
        max=None,
        sample_size=0,
        valid_sample_size=0,
        match_level_counts={},
        exclusions=[],
        source=source,
        source_url=None,
        observed_at=None,
        age_minutes=None,
        unavailable_reason=reason,
    )


def _trimmed_mean(sorted_prices: list[float]) -> float:
    n = len(sorted_prices)
    trim_count = int(n * TRIM_FRACTION)
    trimmed = sorted_prices[trim_count : n - trim_count] if n - 2 * trim_count > 0 else sorted_prices
    return round(statistics.mean(trimmed), 2)


# Below this sample size there's no meaningful basis to call any single
# point an outlier vs. genuine price variance, so filtering is skipped
# rather than risk discarding a real data point on a coin-flip.
_MIN_SAMPLE_FOR_OUTLIER_FILTER = 3
# Iglewicz & Hoaglin's recommended cutoff for the modified z-score test.
# Lowered from 3.5 to 2.0 to aggressively remove outliers on small samples
# (3-8 listings) where scalpers/bundles significantly skew the median.
# Example: [450, 460, 470, 530] → old threshold keeps 530, new threshold removes it.
_MODIFIED_Z_THRESHOLD = 2.0


def _remove_price_outliers(sorted_prices: list[float]) -> tuple[list[float], int]:
    """Median-absolute-deviation (MAD) outlier removal via the modified
    z-score test (0.6745 * (x - median) / MAD, flagged at |z| > 3.5) —
    chosen over a standard IQR/Tukey fence because IQR breaks down exactly
    on the small samples (4-8 listings) this benchmark actually sees: with
    only 6 points, Q3 itself sits on/near the top 1-2 values, so a single
    extreme outlier drags Q3 (and therefore the fence) up to absorb itself,
    e.g. a 6-item sample of [500, 510, 520, 658, 700, 1075] computes an IQR
    upper fence of ~1223 — the 1075 outlier passes straight through it. MAD
    anchors to the median instead, which a single outlier can't drag, so it
    still flags that same 1075 correctly. This exists because the prior
    "trimmed mean" (_trimmed_mean, TRIM_FRACTION=0.1) trims int(n*0.1) items
    from each end — 0 for any n<10, a no-op on the small samples that make
    up the overwhelming majority of real benchmark batches. That gap let a
    single scalper/bundle/mis-scraped £1074.99 "New BIN" ask sit unfiltered
    in a 6-item sample where the other 5 clustered near £500, producing a
    false "market price" of £684 for a CPU actually retailing at £380-450 —
    the bug this function exists to fix. Returns (filtered_prices, excluded_count).
    """
    n = len(sorted_prices)
    if n < _MIN_SAMPLE_FOR_OUTLIER_FILTER:
        return sorted_prices, 0
    median = statistics.median(sorted_prices)
    deviations = [abs(p - median) for p in sorted_prices]
    mad = statistics.median(deviations)
    if mad == 0:
        # Every point at/near the median — fall back to mean absolute
        # deviation so a single genuine outlier doesn't get an infinite
        # z-score purely because MAD collapsed to zero.
        mad = statistics.mean(deviations)
        if mad == 0:
            return sorted_prices, 0
    filtered = [
        p for p, dev in zip(sorted_prices, deviations)
        if (0.6745 * dev / mad) <= _MODIFIED_Z_THRESHOLD
    ]
    # Never let filtering collapse the sample below what a median needs —
    # an aggressive/buggy filter should degrade to "unfiltered", not to "no data".
    if len(filtered) < MIN_SAMPLE_FOR_MEDIAN:
        return sorted_prices, 0
    return filtered, n - len(filtered)


def _stat_from_prices(
    prices: list[float],
    source: str,
    source_url: str | None,
    match_level: str,
) -> BenchmarkStat:
    if len(prices) == 0:
        return _unavailable_stat(source, "No comparable listings found")

    raw_sorted = sorted(prices)
    sorted_prices, excluded_count = _remove_price_outliers(raw_sorted)
    valid_n = len(sorted_prices)
    status = "ok" if valid_n >= MIN_SAMPLE_FOR_MEDIAN else "insufficient_sample"
    exclusions = (
        [ExclusionReason(reason="price statistically anomalous vs. rest of comparable sample (likely bundle, scalper listing, or mis-scrape)", count=excluded_count)]
        if excluded_count
        else []
    )

    return BenchmarkStat(
        status=status,
        average=round(statistics.mean(sorted_prices), 2),
        median=round(statistics.median(sorted_prices), 2) if valid_n >= MIN_SAMPLE_FOR_MEDIAN else None,
        trimmed_mean=_trimmed_mean(sorted_prices) if valid_n >= MIN_SAMPLE_FOR_MEDIAN else None,
        min=sorted_prices[0],
        max=sorted_prices[-1],
        sample_size=len(raw_sorted),
        valid_sample_size=valid_n,
        match_level_counts={match_level: valid_n},
        exclusions=exclusions,
        source=source,
        source_url=source_url,
        observed_at=datetime.now(timezone.utc),
        age_minutes=0.0,
    )


def _batch_stat(
    entries: list[tuple[str, float]], exclude_listing_id: str, match_level: str
) -> BenchmarkStat | None:
    """Builds a BenchmarkStat from same-model listings already sitting in our
    own scraped history (current scan batch + gem_radar_listing_observations
    lookback — see pipeline.build_batch_price_index), excluding the listing
    being scored itself. Returns None only when there's truly zero same-
    model sample — one real observed price beats no benchmark at all, so this
    no longer requires MIN_SAMPLE_FOR_MEDIAN before trusting the data; a low
    sample count instead just lowers the resulting stat's own status/
    confidence via _stat_from_prices."""
    prices = [price for listing_id, price in entries if listing_id != exclude_listing_id]
    if not prices:
        return None
    return _stat_from_prices(prices, "our own scraped listings", None, match_level)


def fetch_bin_benchmarks(
    listing_condition: str,
    match_level: str,
    batch_entries: dict[str, list[tuple[str, float]]] | None,
    exclude_listing_id: str | None,
) -> tuple[BenchmarkStat, BenchmarkStat]:
    """New/Used Buy-It-Now benchmarks, computed entirely from our own scraped
    listing history — no live eBay Browse API call. Only computes the side
    matching listing_condition; the other side is marked "not needed" without
    even touching batch_entries for it, since nothing ever reads it."""
    is_new = listing_condition in ("new", "new_other")
    relevant_bucket = "new" if is_new else "used"
    relevant_stat = _unavailable_stat("our own scraped listings", "No comparable listings found")
    if batch_entries is not None and exclude_listing_id is not None:
        matched = _batch_stat(batch_entries.get(relevant_bucket, []), exclude_listing_id, match_level)
        if matched is not None:
            relevant_stat = matched

    not_needed_stat = _unavailable_stat("our own scraped listings", _NOT_NEEDED_REASON)
    return (relevant_stat, not_needed_stat) if is_new else (not_needed_stat, relevant_stat)


def _sold_comps_to_stat(comps: list[float], source: str) -> BenchmarkStat:
    return _stat_from_prices(comps, source, None, "exact_model_variant")


async def _get_cpk_for_match_key(db: AsyncSession, match_key: str) -> str | None:
    """Return a CPK only when the canonical model match is exact and unique."""

    # Resolve across canonical extracted identities, not a 100-row recent
    # sample. More importantly, ambiguity or no match must return NULL: an
    # unrelated CPK silently poisons every downstream comparable cohort.
    result = await db.execute(text("""
        SELECT DISTINCT cpk
        FROM gem_radar_listing_cpk
        WHERE regexp_replace(upper(coalesce(cpk_data->>'model', '')), '[^A-Z0-9]', '', 'g') = :match_key
           OR regexp_replace(upper(coalesce(cpk_data->>'brand', '') || coalesce(cpk_data->>'model', '')), '[^A-Z0-9]', '', 'g') = :match_key
    """), {"match_key": match_key})
    cpks = [row[0] for row in result.fetchall()]
    return cpks[0] if len(cpks) == 1 else None


async def _get_stored_sold_prices(db: AsyncSession, match_key: str, condition: str) -> list[float]:
    cutoff = datetime.utcnow() - timedelta(days=_SOLD_LOOKBACK_DAYS)
    result = await db.execute(
        select(GemRadarSoldObservation.price, GemRadarSoldObservation.postage).where(
            GemRadarSoldObservation.match_key == match_key,
            GemRadarSoldObservation.condition == condition,
            GemRadarSoldObservation.observed_at >= cutoff,
        )
    )
    return [price + postage for price, postage in result.all()]


async def fetch_sold_benchmarks(
    db: AsyncSession,
    match_key: str,
    listing_condition: str,
    query: str,
    sold_adapter: SoldCompsAdapter,
) -> tuple[BenchmarkStat, BenchmarkStat]:
    """New/Used Sold benchmarks. Only fetches the side matching
    listing_condition. Checks gem_radar_sold_observations (our own past
    scrapes, averaged over the last _SOLD_LOOKBACK_DAYS days) before ever
    scraping eBay live — a live scrape only happens when we have zero stored
    sold comps for this model+condition yet, and its results get stored for
    every future listing of the same model to reuse."""
    is_new = listing_condition in ("new", "new_other")
    adapter_condition = "new" if is_new else "used"

    stored_prices = await _get_stored_sold_prices(db, match_key, adapter_condition)
    # Ends the transaction the read above opened before the scrape below
    # (a real eBay HTTP request) runs — otherwise the DB connection sits
    # idle-in-transaction for the scrape's whole duration.
    await db.commit()
    if stored_prices:
        relevant_stat = _sold_comps_to_stat(stored_prices, "our own sold-comps history")
    else:
        result = await sold_adapter.fetch(query, adapter_condition)
        if result.available and result.comps:
            cpk = await _get_cpk_for_match_key(db, match_key)
            for comp in result.comps:
                db.add(
                    GemRadarSoldObservation(
                        match_key=match_key,
                        cpk=cpk,
                        condition=adapter_condition,
                        price=comp.price,
                        postage=comp.postage,
                        source_url=comp.url,
                    )
                )
            await db.commit()
            relevant_stat = _sold_comps_to_stat([c.price + c.postage for c in result.comps], "sold-comps adapter (fresh scrape)")
        else:
            relevant_stat = _unavailable_stat(
                "sold-comps adapter", result.unavailable_reason or "unavailable"
            )

    not_needed_stat = _unavailable_stat("our own sold-comps history", _NOT_NEEDED_REASON)
    return (relevant_stat, not_needed_stat) if is_new else (not_needed_stat, relevant_stat)


_AMAZON_LOOKBACK_DAYS = 14


def _amazon_stat(price: float, source: str, source_url: str | None, observed_at: datetime) -> BenchmarkStat:
    return BenchmarkStat(
        status="ok",
        average=price,
        median=price,
        trimmed_mean=price,
        min=price,
        max=price,
        sample_size=1,
        valid_sample_size=1,
        match_level_counts={"exact_sku": 1},
        exclusions=[ExclusionReason(reason="single retail listing, not a market sample", count=0)],
        source=source,
        source_url=source_url,
        observed_at=observed_at,
        age_minutes=max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds() / 60),
    )


async def _get_stored_amazon_price(db: AsyncSession, match_key: str) -> tuple[float, str | None, datetime] | None:
    cutoff = datetime.utcnow() - timedelta(days=_AMAZON_LOOKBACK_DAYS)
    result = await db.execute(
        select(
            GemRadarAmazonObservation.price,
            GemRadarAmazonObservation.source_url,
            GemRadarAmazonObservation.observed_at,
        )
        .where(GemRadarAmazonObservation.match_key == match_key, GemRadarAmazonObservation.observed_at >= cutoff)
        .order_by(GemRadarAmazonObservation.observed_at.desc())
        .limit(1)
    )
    return result.first()


async def fetch_amazon_benchmark(
    db: AsyncSession, match_key: str, query: str, amazon_adapter: AmazonPriceAdapter
) -> BenchmarkStat:
    """Checks gem_radar_amazon_observations (our own past scrapes, within
    _AMAZON_LOOKBACK_DAYS) before ever launching a live Amazon scrape — a
    real Playwright browser session per listing would be far too slow across
    a scan of hundreds of listings, the same reasoning fetch_sold_benchmarks
    already applies to eBay sold comps.
    """
    stored = await _get_stored_amazon_price(db, match_key)
    # Ends the transaction the read above opened before the scrape below
    # (a real Playwright browser launch, seconds not milliseconds) runs —
    # otherwise the DB connection sits idle-in-transaction for the scrape's
    # whole duration.
    await db.commit()
    if stored is not None:
        price, source_url, observed_at = stored
        return _amazon_stat(price, "Amazon UK (cached scrape)", source_url, observed_at.replace(tzinfo=timezone.utc))

    result = await amazon_adapter.fetch(query)
    if not result.available or result.price is None:
        return _unavailable_stat("Amazon UK", result.unavailable_reason or "unavailable")

    cpk = await _get_cpk_for_match_key(db, match_key)
    db.add(GemRadarAmazonObservation(match_key=match_key, cpk=cpk, price=result.price, source_url=result.url))
    await db.commit()
    observed_at = datetime.fromisoformat(result.observed_at) if result.observed_at else datetime.now(timezone.utc)
    return _amazon_stat(result.price, "Amazon UK (fresh scrape)", result.url, observed_at)


def unavailable_price_bundle(actual_delivered_price: float, reason: str) -> PriceBundle:
    """Explicit all-unavailable bundle for listings we deliberately never
    price-compare against component market data (see
    identity.is_likely_accessory) — skips the network calls entirely rather
    than running a benchmark search that would silently mismatch the listing
    against unrelated products.
    """
    stat = _unavailable_stat("skipped", reason)
    return PriceBundle(
        actual_listing=actual_delivered_price,
        ebay_new_bin=stat,
        ebay_used_bin=stat,
        ebay_new_sold=stat,
        ebay_used_sold=stat,
        amazon_uk_new=stat,
    )


async def build_price_bundle(
    db: AsyncSession,
    actual_delivered_price: float,
    query: str,
    match_level: str,
    listing_condition: str,
    sold_adapter: SoldCompsAdapter,
    amazon_adapter: AmazonPriceAdapter,
    batch_entries: dict[str, list[tuple[str, float]]] | None = None,
    exclude_listing_id: str | None = None,
    cpk: str | None = None,  # Canonical Product Key for cross-vendor consolidation
) -> PriceBundle:
    _t0 = _time.monotonic()

    # CPK-based pricing (cross-vendor consolidation) takes priority
    if cpk:
        from app.gem_radar.cpk_consolidation import get_cpk_price
        try:
            cpk_new = await get_cpk_price(db, cpk, use_new=True)
            cpk_used = await get_cpk_price(db, cpk, use_new=False)
            if cpk_new or cpk_used:
                # Use CPK aggregates if available (these represent cross-vendor consensus)
                return PriceBundle(
                    ebay_new_bin=BenchmarkStat(
                        status="ok" if cpk_new else "unavailable",
                        average=cpk_new,
                        median=cpk_new,
                        trimmed_mean=cpk_new,
                        min=cpk_new,
                        max=cpk_new,
                        sample_size=1,
                        valid_sample_size=1 if cpk_new else 0,
                        match_level_counts={"cpk_consolidation": 1},
                        exclusions=[],
                        source="cpk_consolidation",
                        source_url=None,
                        observed_at=datetime.now(timezone.utc),
                        age_minutes=0,
                    ) if cpk_new else _unavailable_stat("cpk_consolidation", "no_new_price_in_consolidation"),
                    ebay_used_bin=BenchmarkStat(
                        status="ok" if cpk_used else "unavailable",
                        average=cpk_used,
                        median=cpk_used,
                        trimmed_mean=cpk_used,
                        min=cpk_used,
                        max=cpk_used,
                        sample_size=1,
                        valid_sample_size=1 if cpk_used else 0,
                        match_level_counts={"cpk_consolidation": 1},
                        exclusions=[],
                        source="cpk_consolidation",
                        source_url=None,
                        observed_at=datetime.now(timezone.utc),
                        age_minutes=0,
                    ) if cpk_used else _unavailable_stat("cpk_consolidation", "no_used_price_in_consolidation"),
                    ebay_new_sold=_unavailable_stat("cpk_consolidation", "n/a_fallback_to_bin"),
                    ebay_used_sold=_unavailable_stat("cpk_consolidation", "n/a_fallback_to_bin"),
                    amazon_uk_new=_unavailable_stat("cpk_consolidation", "n/a_cross_vendor_only"),
                )
        except Exception as exc:
            # CPK lookup failed, fall through to normal benchmarking
            import structlog
            log = structlog.get_logger(__name__)
            log.debug("cpk_pricing_lookup_failed", cpk=cpk, error=str(exc))

    _s = _time.monotonic()
    new_bin, used_bin = fetch_bin_benchmarks(listing_condition, match_level, batch_entries, exclude_listing_id)
    _bin_s = round(_time.monotonic() - _s, 3)

    match_key = normalize_match_key(query)

    _s = _time.monotonic()
    new_sold, used_sold = await fetch_sold_benchmarks(db, match_key, listing_condition, query, sold_adapter)
    _sold_s = round(_time.monotonic() - _s, 3)

    _s = _time.monotonic()
    amazon_new = await fetch_amazon_benchmark(db, match_key, query, amazon_adapter)
    _amazon_s = round(_time.monotonic() - _s, 3)

    _total_s = round(_time.monotonic() - _t0, 3)
    if _total_s > 2.0:
        # Only log price-bundle stages when they're actually slow enough to
        # matter — this runs once per uncached listing per scan, so logging
        # unconditionally would drown out everything else during a big scan.
        _diag_log.info(
            "diag.price_bundle.timings",
            query=query,
            condition=listing_condition,
            bin_s=_bin_s,
            sold_s=_sold_s,
            amazon_s=_amazon_s,
            total_s=_total_s,
        )
    return PriceBundle(
        actual_listing=actual_delivered_price,
        ebay_new_bin=new_bin,
        ebay_used_bin=used_bin,
        ebay_new_sold=new_sold,
        ebay_used_sold=used_sold,
        amazon_uk_new=amazon_new,
    )
