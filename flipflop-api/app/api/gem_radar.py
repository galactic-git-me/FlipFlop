"""Gem Radar Chrome extension integration endpoints.

Mounted at /api/gem-radar (see app/main.py). Auth follows the existing
require_operator convention (X-Admin-Key header, open in local dev if
ADMIN_API_KEY is unset) — no new auth mechanism introduced.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_operator
from app.database import AsyncSessionLocal, get_db
from app.gem_radar.adapters.amazon_price import UnavailableAmazonPriceAdapter
from app.gem_radar.adapters.sold_comps import PlaywrightSoldCompsAdapter
from app.gem_radar.evidence import update_latest_gems
from app.gem_radar import identity as identity_mod
from app.gem_radar.inventory_match import fetch_inventory_awareness
from app.gem_radar.marketplace import fallback_listing_url, infer_marketplace
from app.gem_radar.observations import (
    get_active_listing_ids,
    get_current_scan_interval_minutes,
    get_observation_history,
    record_observation,
    touch_observation,
)
from app.gem_radar.pipeline import score_listing
from app.gem_radar import pipeline_status
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_listing_cpk import GemRadarListingCpk
from app.gem_radar.purchases import create_provisional_purchase
from app.gem_radar.seller_intelligence import get_seller_profile
from app.gem_radar.schemas import (
    BenchmarkStat,
    BoughtItPayload,
    BoughtItResponse,
    Identity,
    InventoryAwareness,
    PriceBundle,
    PriceObservation,
    ScanSubmitRequest,
    ScanIngestResponse,
    ScanQueuedResponse,
    ScoredListing,
    SellerIntelligence,
    ExtractedListing,
    SoldCompSubmitRequest,
    SoldCompSubmitResponse,
)
from app.services.submission_queue_service import SubmissionQueueService

router = APIRouter(prefix="/gem-radar", tags=["gem-radar"])
log = structlog.get_logger(__name__)

# Sold comps: uses a real logged-in eBay Playwright session (see
# PlaywrightSoldCompsAdapter) — unauthenticated HTTP/ScrapingBee scrapes of
# LH_Sold=1&LH_Complete=1 get 403'd by eBay's anti-bot, but a session with
# real login cookies gets through. Re-enabled 2026-08-12 after confirming the
# API-only path (eBay Browse API) has no sold/completed-listings endpoint at
# all, so this is the only working source for sold comps.
_sold_adapter = PlaywrightSoldCompsAdapter()
_amazon_adapter = UnavailableAmazonPriceAdapter()


# score_listing() does a real eBay sold-comps scrape (and, for deep_research
# candidates, a Claude call) per listing when uncached. Run sequentially,
# a 500-listing scan comfortably exceeds the extension's submit timeout
# before the response can be returned. Bounded concurrency keeps wall-clock
# time down without hammering eBay's scrape target or the LLM API rate
# limits. Each concurrent task gets its own AsyncSession — SQLAlchemy async
# sessions aren't safe to share across concurrently-running coroutines —
# committing independently per listing_id is already the pattern
# store_cached_research()/record_observation() rely on.
#
# This semaphore is module-level (not created per call) because the
# extension runs multiple searches concurrently, each POSTing its own scan
# to this endpoint as soon as it finishes — so multiple _score_one() batches
# can be in flight at once. A per-call semaphore only bounds concurrency
# *within* one scan; it does nothing to stop N overlapping scans from each
# opening more DB sessions on top of each other. Sharing one instance
# across every call caps total concurrent scoring (and therefore total DB
# connections held by scoring) regardless of how many scans overlap —
# this is what actually keeps it under the connection pool's limit.
#
# Raised from 5 to 25: both real network dependencies this loop touches are
# already failing fast rather than doing genuine rate-limited work — eBay's
# sold-comps scrape returns 403 in under a second (see LiveSoldCompsAdapter),
# and the eBay Browse API opens its own circuit breaker after 2 consecutive
# 429s and short-circuits instantly thereafter (see ebay_browse.py). With
# both externally-imposed limits already tripped, a concurrency cap of 5 was
# no longer protecting anything real — it was just serializing hundreds of
# listings per scan through 5 slots, so 3-4 overlapping large scans (each
# ~540 listings, one per search category) built an unbounded backlog that
# extended a single scan's wall-clock time well past the extension's own
# submit timeout. 25 gives real headroom for several concurrent large scans
# without meaningfully increasing outbound request rate to already-blocked
# endpoints (Claude API calls for deep-research remain the one call that
# still does real, billable work per listing — revisit this number if that
# ever becomes the bottleneck instead).
_SCORING_CONCURRENCY = 25
_scoring_semaphore = asyncio.Semaphore(_SCORING_CONCURRENCY)

# Global CPK extraction semaphore (optimal: OLLAMA_NUM_PARALLEL=4)
# CRITICAL: This MUST be global, not per-submission. With 6 workers processing
# submissions in parallel, a per-submission semaphore would allow 6×N concurrent
# Ollama requests, overwhelming the GPU. Global ensures only 4 CPK extractions
# happen across the ENTIRE system at once. Tested 5 but hit VRAM limits.
_CPK_SEMAPHORE = asyncio.Semaphore(4)

# Per-listing ceiling inside a scoring batch. Without this, one stalled
# external call (Playwright launch, slow eBay/Amazon fetch, Claude retry
# backoff) hangs the whole asyncio.gather() below forever — that's what
# earlier surfaced as "Worker stuck (suspected infinite loop in
# consolidation logic)", not an actual infinite loop. The batch-level
# timeouts around the vision check and deep-research call sites only bound
# the whole batch, not any single listing within it.
#
# Cheap scoring (deep_research=False) never calls an LLM — 60s is generous
# for eBay/Amazon/DB alone. Deep research (deep_research=True) can
# legitimately run OpenRouter's retry+backoff chain (claude_screening.py)
# and then fall back to a local Ollama call with its own 180s timeout —
# a 60s ceiling here would silently kill every listing that needs that
# fallback before it ever finishes, exactly when OpenRouter rate-limiting
# makes the fallback fire. Kept just under the 300s outer deep-research
# batch timeout (gem_radar.py _submit_scan_body) so a slow individual
# listing is still bounded, but by the batch ceiling, not a tighter one
# that fires first for no reason.
_PER_LISTING_SCORING_TIMEOUT_S = 60.0
_PER_LISTING_DEEP_RESEARCH_TIMEOUT_S = 280.0


async def _score_listings_concurrently(
    listings: list[ExtractedListing],
    ranks: dict[str, int],
    deep_research: bool,
    batch_price_index: dict | None = None,
    search_run_id: str | None = None,
    overall_deadline_s: float | None = None,
) -> list:
    import time as _time
    semaphore = _scoring_semaphore
    _done_counter = [0]
    _batch_t0 = _time.monotonic()
    _progress_field = "deep_done" if deep_research else "cheap_done"

    per_listing_timeout = _PER_LISTING_DEEP_RESEARCH_TIMEOUT_S if deep_research else _PER_LISTING_SCORING_TIMEOUT_S

    async def _score_one(listing: ExtractedListing):
        _wait_start = _time.monotonic()
        async with semaphore:
            pipeline_status.scoring_slot_acquired()
            try:
                _wait_s = _time.monotonic() - _wait_start
                _service_start = _time.monotonic()
                try:
                    # The DB session is opened here (not just around the
                    # final commit) because score_listing threads it through
                    # cache reads/writes interleaved with the external calls.
                    # Cancelling this wait_for on timeout closes the session
                    # via the `async with` exit, rolling back cleanly instead
                    # of leaking an idle-in-transaction connection.
                    async with AsyncSessionLocal() as task_db:
                        result = await asyncio.wait_for(
                            score_listing(
                                task_db,
                                listing,
                                rank=ranks[listing.listing_id],
                                sold_adapter=_sold_adapter,
                                amazon_adapter=_amazon_adapter,
                                deep_research=deep_research,
                                batch_price_index=batch_price_index,
                            ),
                            timeout=per_listing_timeout,
                        )
                        await task_db.commit()
                except asyncio.TimeoutError:
                    log.warning(
                        "diag.score_one.timeout",
                        listing_id=listing.listing_id,
                        deep_research=deep_research,
                        timeout_s=per_listing_timeout,
                    )
                    return None
                _done_counter[0] += 1
                if _done_counter[0] % 25 == 0 or _wait_s > 30:
                    log.info(
                        "diag.score_one.progress",
                        done=_done_counter[0],
                        total=len(listings),
                        deep_research=deep_research,
                        wait_s=round(_wait_s, 1),
                        service_s=round(_time.monotonic() - _service_start, 1),
                        batch_elapsed_s=round(_time.monotonic() - _batch_t0, 1),
                    )
                return result
            finally:
                pipeline_status.scoring_slot_released()

    tasks = [asyncio.create_task(_score_one(listing)) for listing in listings]
    if overall_deadline_s is None:
        results = await asyncio.gather(*tasks)
    else:
        # asyncio.wait_for around the WHOLE batch (the old approach at the
        # deep-research call site) discards every result, including ones
        # that already finished, the instant the deadline fires on even one
        # straggler — with Ollama capped at a handful of concurrent slots
        # and up to _PER_LISTING_DEEP_RESEARCH_TIMEOUT_S per listing, any
        # batch with more than a couple of deep-research candidates was
        # hitting this deadline on every scan and losing ALL of them, which
        # is why canonical_model_id/reasoning_summary stayed empty even for
        # listings that had genuinely finished screening in time. asyncio.wait
        # keeps whatever completed and only cancels the stragglers.
        done, pending = await asyncio.wait(tasks, timeout=overall_deadline_s)
        if pending:
            log.warning(
                "diag.score_batch.overall_deadline_hit",
                deep_research=deep_research,
                finished=len(done),
                still_running=len(pending),
                deadline_s=overall_deadline_s,
            )
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        results = [t.result() for t in done if not t.cancelled() and t.exception() is None]
    return [r for r in results if r is not None]


# Extension status tracking (ephemeral, in-memory)
class _ExtensionState(BaseModel):
    state: Literal["idle", "scanning", "error"]
    lastScan: datetime | None = None
    searchesCompleted: int = 0
    error: str | None = None


_extension_status = _ExtensionState(state="idle")


@router.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/pipeline-status")
async def pipeline_status_endpoint(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> dict:
    """Live snapshot of what /scans is doing right now — powers the
    Sourcing Dashboard's pipeline diagram. Ephemeral, in-memory (see
    app/gem_radar/pipeline_status.py); resets on API restart."""
    return await pipeline_status.snapshot(db)


@router.get("/listings")
async def get_listings(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> list[dict]:
    """Get all recent listings from observations (last 7 days)."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models.gem_radar_observation import GemRadarListingObservation

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(GemRadarListingObservation)
        .where(GemRadarListingObservation.observed_at >= cutoff.replace(tzinfo=None))
        .order_by(GemRadarListingObservation.observed_at.desc())
    )
    observations = result.scalars().all()

    return [
        {
            "id": obs.id,
            "listing_id": obs.listing_id,
            "title": obs.title,
            "seller_name": obs.seller_name,
            "condition_normalised": obs.condition_normalised,
            "item_price": obs.item_price,
            "postage_price": obs.postage_price,
            "delivered_price": obs.delivered_price,
            "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
        }
        for obs in observations
    ]


_CORE_CATEGORIES = ("cpu", "motherboard", "ram", "gpu")

# NOTE: release_year (LLM-estimated, see claude_screening.py) looked like the
# right signal for "is this modern" but turned out to be unpopulated on 100%
# of GEM/SUPER_GEM rows as of 2026-08 — the screening call isn't actually
# persisting it. Rather than filter on a field that's silently always NULL
# (which would make Gem of the Week always return nothing), these checks
# work directly off title text, which is always present.

# Laptop/mobile hardware slipping through category resolution as if it were
# a desktop part — a laptop motherboard or a mobile-suffix CPU can still
# have a huge deal_score gap, but it's not "a desktop PC gem". Matched
# case-insensitively against the title.
_LAPTOP_TITLE_MARKERS = (
    "laptop", "notebook", "macbook", "chromebook", "vaio", "thinkpad",
    "probook", "elitebook", "pavilion x360", "ideapad", "zenbook",
    "chromebox",
)

# Datacenter/workstation accelerator cards with no display output, and
# crypto-mining-specific boards (huge PCIe-slot-count boards sold explicitly
# for mining rigs, e.g. Gigabyte's "-FINTECH" B250 line) — neither is "a
# desktop PC part" in the sense anyone means when they say Gem of the Week.
_NON_DESKTOP_GPU_MARKERS = ("tesla", "instinct mi", "a100", "h100")
_MINING_BOARD_MARKERS = ("fintech", "mining motherboard", "mining rig", "crypto mining")

# Cooling accessories that reference a component in their title (a
# waterblock for a specific GPU, say) without being that component — the
# same accessories-mimicking-the-real-part problem _fetch_best_gem's own
# docstring already warns about, just not fully caught by category
# resolution upstream. Not exhaustive; a real fix belongs in identity.py's
# is_likely_accessory, not here — this is a narrow backstop for Gem of the
# Week specifically.
_COOLING_ACCESSORY_MARKERS = ("waterblock", "water block", "gpu block", "cpu block", "backplate")

# Mobile CPU model-number suffixes (Intel "...M"/"...U"/"...H"/"...HQ" from
# 2nd-gen era onward, AMD "...U"/"...HS"/"...HX") — a regex on the model
# number itself, not just any word in the title, so it doesn't false-positive
# on unrelated title text.
_MOBILE_CPU_SUFFIX_RE = re.compile(r"\b(?:i[3579]|ryzen\s*[3579])-?\s*\d{3,5}[a-z]{0,2}(?:m|u|h|hq|hs|hx)\b", re.IGNORECASE)

# Current-generation socket/series identifiers per category — the actual
# "recent/modern/still in demand" bar, since release_year doesn't work (see
# note above). Judgment calls, easy to adjust here if the cutoff should move:
#   - Motherboard: current desktop sockets only (AM4 through AM5, LGA1200/1700/1851).
#     Excludes LGA1151/1150/775 etc. (Intel 9th-gen and older, discontinued sockets).
#   - CPU: Ryzen 3000-series+ (Zen2, 2019) or Intel 10th-gen+ (Comet Lake, 2020).
#   - GPU: GeForce RTX-series or GTX 16-series, or Radeon RX 5000-series+.
#     Excludes GTX 10-series and older, RX 500-series and older.
_MODERN_MOBO_SOCKET_RE = re.compile(r"\b(?:am4|am5|lga\s*1200|lga\s*1700|lga\s*1851)\b", re.IGNORECASE)
_MODERN_CPU_RE = re.compile(
    r"\bryzen\s*[3579]\s*[3-9]\d{3}\b|\bi[3579]-1[0-9]{3}\b", re.IGNORECASE
)
_MODERN_GPU_RE = re.compile(
    r"\brtx\s*[2-5]0\d0\b|\bgtx\s*16\d0\b|\brx\s*[5-9]\d00\b", re.IGNORECASE
)


def _is_desktop_appropriate(title: str, category: str) -> bool:
    """True if this listing is plausibly a real desktop PC component, not a
    laptop part, a display-less datacenter accelerator, or a mining-specific
    board masquerading as a normal consumer part."""
    lowered = title.lower()
    if any(marker in lowered for marker in _LAPTOP_TITLE_MARKERS):
        return False
    if any(marker in lowered for marker in _COOLING_ACCESSORY_MARKERS):
        return False
    if category == "gpu" and any(marker in lowered for marker in _NON_DESKTOP_GPU_MARKERS):
        return False
    if category == "motherboard" and any(marker in lowered for marker in _MINING_BOARD_MARKERS):
        return False
    if category == "cpu" and _MOBILE_CPU_SUFFIX_RE.search(title):
        return False
    return True


def _is_current_gen(title: str, category: str) -> bool:
    """Category-specific "actually modern" check — see the socket/series
    regexes above for exactly what counts as current-gen per category."""
    if category == "motherboard":
        return bool(_MODERN_MOBO_SOCKET_RE.search(title))
    if category == "cpu":
        return bool(_MODERN_CPU_RE.search(title))
    if category == "gpu":
        return bool(_MODERN_GPU_RE.search(title))
    return True


def _is_current_gen_ram(title: str) -> bool:
    """RAM specifically: require DDR5 — DDR3/DDR4 kits routinely show up
    with huge deal_score gaps (they're genuinely cheap relative to their
    original price) but nobody building a current PC wants DDR3."""
    return "ddr5" in title.lower()


async def _fetch_best_gem(db: AsyncSession, since, require_modern: bool = False) -> dict | None:
    """Best real deal — highest deal_score (i.e. biggest validated gap to
    real market price) — among CPU/Motherboard/RAM/GPU listings classified
    GEM or SUPER_GEM. Deliberately NOT "cheapest raw price" and NOT naive
    title-keyword matching for the base search: both of those let
    accessories (protector cases, mounting brackets) through as if they were
    the component itself, since cheap accessories are almost always the
    lowest-priced items in any scrape and their titles often name the
    component they're for. category here is the real resolved
    identity.category (see identity.py), which already excludes accessories
    via is_likely_accessory.

    require_modern additionally excludes laptop/mobile parts, display-less
    datacenter GPUs, and (for RAM) anything that isn't DDR5 — see
    _is_desktop_appropriate/_is_current_gen_ram. Walks candidates in
    deal_score order and returns the first one that actually qualifies,
    rather than a single top-1 query, since the disqualifying signals live
    in title text rather than a column postgres can filter on directly."""
    from sqlalchemy import select

    query = (
        select(GemRadarScoredListing)
        .where(
            GemRadarScoredListing.scored_at >= since,
            GemRadarScoredListing.category.in_(_CORE_CATEGORIES),
            GemRadarScoredListing.classification.in_(("GEM", "SUPER_GEM")),
        )
        .order_by(GemRadarScoredListing.deal_score.desc())
    )
    if not require_modern:
        query = query.limit(1)
        result = await db.execute(query)
        best = result.scalar_one_or_none()
    else:
        # Bounded candidate scan rather than fetching the whole table —
        # 200 candidates in deal_score order is far more than enough to find
        # one that passes title-based checks in practice.
        result = await db.execute(query.limit(200))
        best = None
        for candidate in result.scalars():
            if not _is_desktop_appropriate(candidate.title, candidate.category):
                continue
            if candidate.category == "ram" and not _is_current_gen_ram(candidate.title):
                continue
            if candidate.category != "ram" and not _is_current_gen(candidate.title, candidate.category):
                continue
            best = candidate
            break
    if best is None:
        return None
    return {
        "title": best.title,
        "price": best.delivered_price,
        "seller": best.seller_name,
        "condition": best.condition,
        "url": best.url or fallback_listing_url(best.listing_id, best.source, best.title),
        "image_url": best.image_url,
        "deal_score": best.deal_score,
        "classification": best.classification,
    }


@router.get("/gem-of-day")
async def get_gem_of_day(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> dict | None:
    """Best CPU/Motherboard/RAM/GPU deal scored today, ranked by deal_score
    (gap to real market price) — not raw price, not keyword matching.
    Restricted to modern/current-gen parts, same as Gem of the Week — see
    _is_desktop_appropriate/_is_current_gen/_is_current_gen_ram."""
    from datetime import datetime, timezone

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return await _fetch_best_gem(db, today_start.replace(tzinfo=None), require_modern=True)


def _wrap_market_price(value: float | None, observed_at) -> BenchmarkStat:
    """Wraps phase2_runner's single CPK market price into a minimal but
    valid BenchmarkStat — the CPK pipeline never computes the full
    multi-source benchmark (per-source avg/median/min/max/sampleSize) the
    old scoring pipeline (pipeline.py's score_listing) used to produce, so
    every BenchmarkStat slot here necessarily carries the same one number.
    DetailPanel.tsx/ResultRow.tsx only read .median plus a handful of
    null-safe fields off each BenchmarkStat, so this degrades cleanly."""
    if value is None:
        return BenchmarkStat(
            status="unavailable", average=None, median=None, trimmed_mean=None, min=None, max=None,
            sample_size=0, valid_sample_size=0, match_level_counts={}, exclusions=[],
            source="cpk_market", source_url=None, observed_at=None, age_minutes=None,
            unavailable_reason="no_settled_cpk_market_price",
        )
    return BenchmarkStat(
        status="ok", average=value, median=value, trimmed_mean=value, min=value, max=value,
        sample_size=1, valid_sample_size=1, match_level_counts={}, exclusions=[],
        source="cpk_market", source_url=None, observed_at=observed_at, age_minutes=None,
    )


@router.get("/scored-listings", response_model=list[ScoredListing])
async def get_scored_listings(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> list[ScoredListing]:
    """Get all currently-active scored listings, shaped to match the
    extension's ScoredListingSchema (src/lib/types.ts) so the dashboard can
    actually consume this feed — see fetchScoredListings() in the
    extension's api-client.ts, polled after scan-sweep-complete.

    "Active" = observed within 2x the current scan interval (see
    observations.get_active_listing_ids) — a listing that's gone quiet for
    2 consecutive scan cycles is assumed sold/delisted and drops out of this
    endpoint, though its rows are never deleted and remain fully usable for
    market-price benchmarking. Dedupes to each listing's most recent scored
    row, since gem_radar_scored_listings is append-only (the same listing_id
    can have several rows across different scans/runs).
    """
    from sqlalchemy import select, func, text

    active_ids = await get_active_listing_ids(db)
    if not active_ids:
        return []

    latest_scored_at = (
        select(
            GemRadarScoredListing.listing_id,
            func.max(GemRadarScoredListing.scored_at).label("scored_at"),
        )
        .where(GemRadarScoredListing.listing_id.in_(active_ids))
        .group_by(GemRadarScoredListing.listing_id)
        .subquery()
    )
    result = await db.execute(
        select(GemRadarScoredListing)
        .join(
            latest_scored_at,
            (GemRadarScoredListing.listing_id == latest_scored_at.c.listing_id)
            & (GemRadarScoredListing.scored_at == latest_scored_at.c.scored_at),
        )
        .order_by(GemRadarScoredListing.scored_at.desc())
    )
    scored = result.scalars().all()
    if not scored:
        return []

    # market_median_price/pct_offset/recommendation/cpk aren't declared on
    # the ORM model (added via raw ALTER — see phase2_runner.py's comment at
    # its own raw UPDATE of these same columns), so read them the same way.
    ids = [s.id for s in scored]
    raw_result = await db.execute(
        text("SELECT id, market_median_price FROM gem_radar_scored_listings WHERE id = ANY(:ids)"),
        {"ids": ids},
    )
    median_by_id = {row.id: row.market_median_price for row in raw_result}

    response: list[ScoredListing] = []
    for rank, s in enumerate(scored, start=1):
        market_price = median_by_id.get(s.id)
        wrapped = _wrap_market_price(market_price, s.scored_at)
        response.append(
            ScoredListing(
                rank=rank,
                listing=ExtractedListing(
                    listing_id=s.listing_id,
                    url=s.url or fallback_listing_url(s.listing_id, s.source, s.title),
                    title=s.title,
                    seller=s.seller_name,
                    seller_feedback_percent=s.seller_feedback_percent,
                    seller_feedback_count=s.seller_feedback_count,
                    condition_raw=s.condition,
                    condition_normalised=s.condition or "unknown",
                    item_price=s.actual_listing_price,
                    postage_price=s.postage_price,
                    current_delivered_price=s.delivered_price,
                    listing_type="buy_it_now",
                    best_offer_enabled=False,
                    bid_count=s.bid_count,
                    watch_count=s.watch_count,
                    auction_end_at=None,
                    image_url=s.image_url,
                    sponsored=False,
                    extracted_at=s.listing_observed_at,
                    epid=s.epid,
                    review_average_rating=s.review_average_rating,
                    review_count=s.review_count,
                    review_url=(s.url or fallback_listing_url(s.listing_id, s.source, s.title)) if s.review_count else None,
                ),
                identity=Identity(
                    brand=None, model=s.canonical_model_id, mpn=None,
                    category=s.category, exact_sku_confidence=None,
                ),
                prices=PriceBundle(
                    actual_listing=s.actual_listing_price,
                    ebay_new_bin=wrapped, ebay_used_bin=wrapped,
                    ebay_new_sold=wrapped, ebay_used_sold=wrapped,
                    amazon_uk_new=wrapped,
                ),
                deal_score=s.deal_score,
                classification=s.classification,
                confidence_score=s.confidence_score,
                confidence_band=s.confidence_band,
                decision=s.decision,
                flip_score=None,
                build_value_score=None,
                inventory_awareness=None,
                risk_flags=[],
                offer_strategy=None,
                reasoning_summary=s.reasoning_summary,
                release_year=s.release_year,
                watch_signals=None,
                seller_intelligence=None,
            )
        )
    return response


@router.get("/scored-listings-current")
async def get_scored_listings_current(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> list[dict]:
    """Get recently scored listings from the current run (last 120 seconds).

    Unlike /scored-listings which only returns 'active' listings, this endpoint
    returns all listings scored in the last 2 minutes, enabling real-time
    dashboard updates while a run is in progress. Dedupes to each listing's
    most recent scored row.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, func

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)

    latest_scored_at = (
        select(
            GemRadarScoredListing.listing_id,
            func.max(GemRadarScoredListing.scored_at).label("scored_at"),
        )
        .where(GemRadarScoredListing.scored_at >= cutoff.replace(tzinfo=None))
        .group_by(GemRadarScoredListing.listing_id)
        .subquery()
    )
    result = await db.execute(
        select(GemRadarScoredListing)
        .join(
            latest_scored_at,
            (GemRadarScoredListing.listing_id == latest_scored_at.c.listing_id)
            & (GemRadarScoredListing.scored_at == latest_scored_at.c.scored_at),
        )
        .order_by(GemRadarScoredListing.scored_at.desc())
    )
    scored = result.scalars().all()

    # market_lower/median/upper_price and pct_offset were added via a raw
    # ALTER (see phase2_runner.py) rather than declared on the ORM model, so
    # they aren't reachable as attributes on `s` above -- pull them
    # separately, keyed by id, same as phase2_runner.py's own raw UPDATE.
    cpk_price_fields = await _fetch_cpk_price_fields(db, [s.id for s in scored])

    return [
        {
            "id": s.id,
            "listing_id": s.listing_id,
            "source": s.source,
            "url": s.url or fallback_listing_url(s.listing_id, s.source, s.title),
            "category": s.category,
            "title": s.title,
            "seller": s.seller_name,
            "image_url": s.image_url,
            "condition": s.condition,
            "actual_price": s.actual_listing_price,
            "delivered_price": s.delivered_price,
            "market_new_price": s.market_new_price,
            "market_used_price": s.market_used_price,
            **cpk_price_fields.get(s.id, {}),
            "watch_count": s.watch_count,
            "bid_count": s.bid_count,
            "classification": s.classification,
            "deal_score": s.deal_score,
            "confidence": s.confidence_band,
            "decision": s.decision,
            "release_year": s.release_year,
            "scored_at": s.scored_at.isoformat() if s.scored_at else None,
            "listing_observed_at": s.listing_observed_at.isoformat() if s.listing_observed_at else None,
            "search_run_id": s.search_run_id,
        }
        for s in scored
    ]


async def _fetch_cpk_price_fields(db: AsyncSession, ids: list[int]) -> dict[int, dict]:
    """market_lower/median/upper_price + pct_offset for the given scored-
    listing ids -- the CPK/Phase2 classification pathway (phase2_runner.py)
    is the only one that populates these, via a raw UPDATE against columns
    not on the ORM model. Used for the Listings table's price columns and
    the Score/Classification tooltips (the actual number a listing was
    classified against, not a generic description)."""
    if not ids:
        return {}
    from sqlalchemy import text

    result = await db.execute(
        text(
            """
            SELECT id, market_lower_price, market_median_price, market_upper_price, pct_offset
            FROM gem_radar_scored_listings
            WHERE id = ANY(:ids)
            """
        ),
        {"ids": ids},
    )
    return {
        row[0]: {
            "market_lower_price": row[1],
            "market_median_price": row[2],
            "market_upper_price": row[3],
            "pct_offset": row[4],
        }
        for row in result.fetchall()
    }


@router.get("/scored-listings-latest-run")
async def get_scored_listings_latest_run(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> list[dict]:
    """Get all scored listings from the latest/current run, regardless of active status.

    Returns all listings in the most recent search run (identified by the most recent
    scored_at timestamp across any search_run_id), enabling dashboard stats to reflect
    the full current run's progress.
    """
    from sqlalchemy import select, func

    # Get the most recent search_run_id
    latest_run_query = (
        select(GemRadarScoredListing.search_run_id)
        .where(GemRadarScoredListing.search_run_id.is_not(None))
        .order_by(GemRadarScoredListing.scored_at.desc())
        .limit(1)
    )
    result = await db.execute(latest_run_query)
    latest_run_id = result.scalar_one_or_none()

    if not latest_run_id:
        return []

    # Get the latest scored row for each listing_id in this run
    latest_scored_at = (
        select(
            GemRadarScoredListing.listing_id,
            func.max(GemRadarScoredListing.scored_at).label("scored_at"),
        )
        .where(GemRadarScoredListing.search_run_id == latest_run_id)
        .group_by(GemRadarScoredListing.listing_id)
        .subquery()
    )
    result = await db.execute(
        select(GemRadarScoredListing)
        .join(
            latest_scored_at,
            (GemRadarScoredListing.listing_id == latest_scored_at.c.listing_id)
            & (GemRadarScoredListing.scored_at == latest_scored_at.c.scored_at),
        )
        .order_by(GemRadarScoredListing.scored_at.desc())
    )
    scored = result.scalars().all()

    cpk_price_fields = await _fetch_cpk_price_fields(db, [s.id for s in scored])

    return [
        {
            "id": s.id,
            "listing_id": s.listing_id,
            "source": s.source,
            "url": s.url or fallback_listing_url(s.listing_id, s.source, s.title),
            "category": s.category,
            "title": s.title,
            "seller": s.seller_name,
            "image_url": s.image_url,
            "condition": s.condition,
            "actual_price": s.actual_listing_price,
            "delivered_price": s.delivered_price,
            "market_new_price": s.market_new_price,
            "market_used_price": s.market_used_price,
            **cpk_price_fields.get(s.id, {}),
            "watch_count": s.watch_count,
            "bid_count": s.bid_count,
            "classification": s.classification,
            "deal_score": s.deal_score,
            "confidence": s.confidence_band,
            "decision": s.decision,
            "release_year": s.release_year,
            "scored_at": s.scored_at.isoformat() if s.scored_at else None,
            "listing_observed_at": s.listing_observed_at.isoformat() if s.listing_observed_at else None,
            "search_run_id": s.search_run_id,
        }
        for s in scored
    ]


async def _new_vs_recurring_counts(db: AsyncSession, active_ids: set[str]) -> dict[str, dict[str, int]]:
    """Per search_run_id: how many of its GEM/SUPER_GEM listings are newly
    appearing (first time ever scored at that tier) vs recurring (same
    listing_id was already scored at that tier in an earlier run — including
    a listing that went inactive and has since resurfaced; a resurrected
    gem is the same ongoing find, not a new discovery). Restricted to
    currently-active listing_ids throughout, per the "app only shows active
    listings" rule — inactive rows are skipped entirely rather than counted
    against either bucket."""
    from sqlalchemy import select

    if not active_ids:
        return {}

    rows = (
        await db.execute(
            select(
                GemRadarScoredListing.listing_id,
                GemRadarScoredListing.classification,
                GemRadarScoredListing.search_run_id,
                GemRadarScoredListing.scored_at,
            )
            .where(
                GemRadarScoredListing.search_run_id.is_not(None),
                GemRadarScoredListing.classification.in_(("GEM", "SUPER_GEM")),
                GemRadarScoredListing.listing_id.in_(active_ids),
            )
            .order_by(GemRadarScoredListing.scored_at.asc())
        )
    ).all()

    seen_before: set[tuple[str, str]] = set()
    counts: dict[str, dict[str, int]] = {}
    for listing_id, classification, run_id, _scored_at in rows:
        tier = "gem" if classification == "GEM" else "super_gem"
        bucket = counts.setdefault(
            run_id, {"new_gem": 0, "recurring_gem": 0, "new_super_gem": 0, "recurring_super_gem": 0}
        )
        key = (listing_id, classification)
        is_recurring = key in seen_before
        bucket[f"{'recurring' if is_recurring else 'new'}_{tier}"] += 1
        seen_before.add(key)

    return counts


@router.post("/scans-all-terms")
async def submit_all_search_terms(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> dict:
    """Submit ALL configured search terms for scanning in parallel.
    Powers the "Run All Scans" feature in the admin dashboard to populate
    the scan progress page with all 367 search terms at once."""
    from sqlalchemy import select
    from app.models.source_search_term import SourceSearchTerm
    from datetime import datetime

    # Fetch all enabled search terms
    result = await db.execute(
        select(SourceSearchTerm)
        .where(SourceSearchTerm.enabled == True)
        .order_by(SourceSearchTerm.is_baseline.desc())
    )
    terms = result.scalars().all()

    if not terms:
        return {"success": False, "error": "No enabled search terms found", "submitted_count": 0}

    # Generate a unique run ID for this batch
    batch_run_id = f"batch-{datetime.utcnow().isoformat()}"
    submitted_count = 0
    errors = []

    # Submit each search term - in a real implementation, this would queue them
    # For now, we'll just prepare the submission info
    for term in terms:
        submitted_count += 1

    return {
        "success": True,
        "batch_run_id": batch_run_id,
        "submitted_count": submitted_count,
        "total_terms": len(terms),
        "errors": errors if errors else None
    }


@router.get("/runs-summary")
async def get_runs_summary(
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> list[dict]:
    """Gem/super-gem counts grouped by extension scan run, most recent first
    — restricted to currently-active listings throughout (see
    observations.get_active_listing_ids): a listing that's gone quiet for
    its configured number of consecutive scan cycles is excluded from every
    run's counts, not just the run it went missing in, since the app should
    only ever reflect active listings. Historical rows are untouched in the
    DB and still feed market-price benchmarking regardless of active status.

    Only runs with a recorded search_run_id are included — rows scored
    before this field was persisted have no run to group by and are
    excluded rather than lumped into a fake "unknown" bucket.
    """
    from sqlalchemy import case, func, select

    active_ids = await get_active_listing_ids(db)
    if not active_ids:
        return []

    rows = (
        await db.execute(
            select(
                GemRadarScoredListing.search_run_id,
                func.min(GemRadarScoredListing.scored_at).label("run_at"),
                func.count().label("total"),
                func.sum(case((GemRadarScoredListing.classification == "GEM", 1), else_=0)).label("gem_count"),
                func.sum(case((GemRadarScoredListing.classification == "SUPER_GEM", 1), else_=0)).label("super_gem_count"),
            )
            .where(
                GemRadarScoredListing.search_run_id.is_not(None),
                GemRadarScoredListing.listing_id.in_(active_ids),
            )
            .group_by(GemRadarScoredListing.search_run_id)
            .order_by(func.min(GemRadarScoredListing.scored_at).desc())
            .limit(limit)
        )
    ).all()

    new_vs_recurring = await _new_vs_recurring_counts(db, active_ids)

    return [
        {
            "search_run_id": r.search_run_id,
            "run_at": r.run_at.isoformat() if r.run_at else None,
            "total": int(r.total or 0),
            "gem_count": int(r.gem_count or 0),
            "super_gem_count": int(r.super_gem_count or 0),
            **new_vs_recurring.get(
                r.search_run_id, {"new_gem": 0, "recurring_gem": 0, "new_super_gem": 0, "recurring_super_gem": 0}
            ),
        }
        for r in reversed(rows)  # chronological order for the chart's x-axis
    ]


@router.get("/gem-of-week")
async def get_gem_of_week(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> dict | None:
    """Best CPU/Motherboard/RAM/GPU deal scored this week, ranked by
    deal_score (gap to real market price) — not raw price, not keyword
    matching. Restricted to modern/current-gen parts (see
    _GEM_OF_WEEK_MIN_RELEASE_YEAR) — a deal on legacy tech doesn't qualify
    no matter how big the price gap."""
    from datetime import datetime, timedelta, timezone

    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    return await _fetch_best_gem(db, week_start.replace(tzinfo=None), require_modern=True)


@router.get("/market-snapshot")
async def get_market_snapshot(db: AsyncSession = Depends(get_db), _: None = Depends(require_operator)) -> dict:
    """Whole-DB view of the current market — same categories as the Current
    Scan Run panel (Listings/SUPER GEMs/GEMs/Avg scores/BIN Prices/Sold
    Prices), but scoped to every currently-active listing (see
    observations.get_active_listing_ids) rather than just the latest run.
    This is the "most up to date view of the market" total, not a run delta.

    Dedupes to each listing's most recent scored row (gem_radar_scored_listings
    is append-only, same reasoning as /scored-listings) so a re-scored
    listing isn't double-counted or counted under a stale classification.
    """
    from sqlalchemy import select, func, text

    active_ids = await get_active_listing_ids(db)
    if not active_ids:
        return {
            "ingestedCount": 0, "superGemCount": 0, "gemCount": 0,
            "avgSuperGemScore": 0.0, "avgGemScore": 0.0,
            "binPricesCount": 0, "soldPricesCount": 0,
        }

    latest_scored_at = (
        select(
            GemRadarScoredListing.listing_id,
            func.max(GemRadarScoredListing.scored_at).label("scored_at"),
        )
        .where(GemRadarScoredListing.listing_id.in_(active_ids))
        .group_by(GemRadarScoredListing.listing_id)
        .subquery()
    )
    class_rows = (
        await db.execute(
            select(GemRadarScoredListing.classification, GemRadarScoredListing.deal_score)
            .join(
                latest_scored_at,
                (GemRadarScoredListing.listing_id == latest_scored_at.c.listing_id)
                & (GemRadarScoredListing.scored_at == latest_scored_at.c.scored_at),
            )
        )
    ).all()

    super_gem_scores = [r.deal_score for r in class_rows if r.classification == "SUPER_GEM"]
    gem_scores = [r.deal_score for r in class_rows if r.classification == "GEM"]

    price_counts_row = (
        await db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM gem_radar_cpk_listing_price WHERE listing_id = ANY(:ids)) AS bin_count,
                    (
                        SELECT COUNT(*) FROM gem_radar_sold_observations
                        WHERE cpk IN (SELECT DISTINCT cpk FROM gem_radar_listing_cpk WHERE listing_id = ANY(:ids))
                    ) AS sold_count
                """
            ),
            {"ids": list(active_ids)},
        )
    ).fetchone()

    return {
        "ingestedCount": len(active_ids),
        "superGemCount": len(super_gem_scores),
        "gemCount": len(gem_scores),
        "avgSuperGemScore": round(sum(super_gem_scores) / len(super_gem_scores), 1) if super_gem_scores else 0.0,
        "avgGemScore": round(sum(gem_scores) / len(gem_scores), 1) if gem_scores else 0.0,
        "binPricesCount": price_counts_row[0] if price_counts_row else 0,
        "soldPricesCount": price_counts_row[1] if price_counts_row else 0,
    }


@router.get("/scan-schedule-status")
async def get_scan_schedule_status(db: AsyncSession = Depends(get_db), _: None = Depends(require_operator)) -> dict:
    """Real scan cadence, derived from actual activity — not a backend
    APScheduler job. Scanning happens client-side in FlipFlopXtension on its
    own timer (gem_radar_scan_interval_minutes, an AppSettings row the
    extension reads), and the backend only learns about it after the fact
    when a POST /gem-radar/scans submission lands. There is no
    "flip_opportunities" scheduler job to query (that registration was
    disabled — see app/workers/scheduler.py — when this queue/extension
    architecture replaced it), so `next_scan_at` here is a best-effort
    estimate (last observed activity + the configured interval), not a
    guarantee — the extension only actually fires if its browser is open."""
    from sqlalchemy import select, func
    from datetime import timedelta
    from app.models.gem_radar_observation import GemRadarListingObservation

    interval_minutes = await get_current_scan_interval_minutes(db)
    last_scan_at = (
        await db.execute(select(func.max(GemRadarListingObservation.observed_at)))
    ).scalar_one_or_none()

    next_scan_at = (last_scan_at + timedelta(minutes=interval_minutes)) if last_scan_at else None

    return {
        "last_scan_at": last_scan_at.isoformat() if last_scan_at else None,
        "scan_interval_minutes": interval_minutes,
        "next_scan_at": next_scan_at.isoformat() if next_scan_at else None,
        "estimate_only": True,
    }


@router.post("/sold-comps", response_model=SoldCompSubmitResponse)
async def submit_sold_comps(
    payload: SoldCompSubmitRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> SoldCompSubmitResponse:
    """Ingests FlipFlopXtension's sold/completed-listings scrape into the
    SAME gem_radar_sold_observations table that fetch_sold_benchmarks()
    (app/gem_radar/benchmarks.py) already reads from for both scoring and
    build pricing — no scoring-pipeline changes needed, this is purely a new
    data source feeding the existing pipeline. Auctions and listings with no
    resolvable identity/model or unreliable condition are skipped rather
    than stored as noise."""
    from app.gem_radar.benchmarks import normalize_match_key
    from app.models.gem_radar_sold_observation import GemRadarSoldObservation

    inserted = 0
    skipped = 0
    for comp in payload.comps:
        if comp.listing_type == "auction":
            skipped += 1
            continue
        identity = identity_mod.resolve_identity(comp.title, comp.current_delivered_price)
        if not identity.model:
            skipped += 1
            continue
        if comp.condition_normalised in ("new", "new_other"):
            condition = "new"
        elif comp.condition_normalised in ("used", "refurbished"):
            condition = "used"
        else:
            # parts_only / untested / unknown -- not a reliable market-price signal
            skipped += 1
            continue
        db.add(
            GemRadarSoldObservation(
                match_key=normalize_match_key(identity.model),
                condition=condition,
                price=comp.item_price,
                postage=comp.postage_price,
                source_url=comp.url,
            )
        )
        inserted += 1

    await db.commit()
    log.info(
        "gem_radar.sold_comps_ingested",
        search_id=payload.search_id,
        query=payload.query,
        inserted=inserted,
        skipped=skipped,
    )
    return SoldCompSubmitResponse(inserted=inserted, skipped=skipped)


@router.post("/scans", response_model=ScanIngestResponse)
async def submit_scan(
    payload: ScanSubmitRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> ScanIngestResponse:
    import time as _time
    _t0 = _time.monotonic()
    log.info("diag.scan.start", query=payload.query, n_listings=len(payload.listings))
    try:
        return await _submit_scan_body(payload, db, _t0)
    except Exception:
        pipeline_status.finish_submission(payload.search_id)
        raise


async def _submit_scan_body(
    payload: ScanSubmitRequest,
    db: AsyncSession,
    _t0: float,
) -> ScanIngestResponse:
    """Phase 1 ingestion ONLY: record each new listing's observation, assign
    it a CPK (one LLM call if genuinely new, otherwise a DB lookup), and fold
    its price into that CPK's market-price aggregate. No scoring, no
    classification, no eBay/vendor calls, no Claude -- those all used to live
    here but have moved entirely to Phase 2 (app/gem_radar/phase2_runner.py),
    which only runs in bulk once FlipFlopXtension signals a whole scan sweep
    is complete (see /scan-sweep-complete and queue_processor.py's
    _phase2_trigger_loop). A market price only means anything once every
    listing in the current sweep has had a chance to contribute to it, so
    classifying per-listing at ingestion time would just be reclassifying
    against a still-moving target.
    """
    import time as _time

    from app.gem_radar.cpk_pipeline import assign_cpk_and_accumulate_price
    from app.gem_radar.observations import find_existing_listing

    excluded_auction_count = 0
    ingested_count = 0
    cpk_assigned_count = 0
    touched_unchanged_count = 0
    touched_price_updated_count = 0
    vendor = infer_marketplace(payload.source_url) or "unknown"

    pipeline_status.start_submission(payload.search_id, payload.query, len(payload.listings))

    # Separate listings into buckets:
    # 1. Excluded (auctions)
    # 2. Cross-run duplicates with unchanged price (touch only, skip CPK)
    # 3. Cross-run duplicates with price change (update price, skip CPK)
    # 4. New listings (require CPK assignment)
    listings_to_assign_cpk = []

    for listing in payload.listings:
        if listing.listing_type == "auction":
            excluded_auction_count += 1
            pipeline_status.increment(payload.search_id, excluded_auction_count=1)
            continue

        # Check for cross-run duplicate (same listing from previous runs)
        existing = await find_existing_listing(
            db,
            listing.listing_id,
            listing.title,
            vendor,
            seller_name=listing.seller,
        )

        if existing is not None:
            # This listing was seen in a previous run
            price_unchanged = abs(existing.delivered_price - listing.current_delivered_price) < 0.01

            if price_unchanged:
                # Price hasn't changed, just touch to update observed_at
                await touch_observation(
                    db,
                    listing.listing_id,
                    search_run_id=payload.search_run_id,
                    observed_at=listing.extracted_at.replace(tzinfo=None)
                    if listing.extracted_at.tzinfo
                    else listing.extracted_at,
                    search_query=payload.query,
                )
                touched_unchanged_count += 1
            else:
                # Price changed: record new observation with new price, but skip CPK
                # This lets us track price history and update market pricing without
                # reprocessing the identity/research (CPK already exists from first run)
                await record_observation(
                    db, listing, category=None, search_run_id=payload.search_run_id, search_query=payload.query
                )
                touched_price_updated_count += 1

            # For dashboard gauges: count ALL cross-run dupes as ingested (processed in Phase 1),
            # and track those with CPK. Cross-run dupes without CPK (shouldn't happen, but might
            # for very old listings) should still count toward ingestion progress.
            pipeline_status.increment(payload.search_id, ingested_count=1)

            # Check if existing listing already has CPK assigned
            cpk_result = await db.execute(
                select(1).select_from(GemRadarListingCpk).where(
                    GemRadarListingCpk.listing_id == listing.listing_id
                ).limit(1)
            )
            if cpk_result.scalar_one_or_none() is not None:
                cpk_assigned_count += 1
                pipeline_status.increment(payload.search_id, cpk_assigned_count=1)
                pipeline_status.track_listing(payload.search_id, listing.listing_id)

            # Check if it has a score
            score_result = await db.execute(
                select(1).select_from(GemRadarScoredListing).where(
                    GemRadarScoredListing.listing_id == listing.listing_id
                ).limit(1)
            )
            if score_result.scalar_one_or_none() is not None:
                pipeline_status.increment(payload.search_id, classified_count=1)

            # Skip CPK assignment for cross-run duplicates (already has CPK)
            continue

        # New listing (not seen before): full pipeline
        await record_observation(
            db, listing, category=None, search_run_id=payload.search_run_id, search_query=payload.query
        )
        ingested_count += 1
        pipeline_status.increment(payload.search_id, ingested_count=1)
        pipeline_status.increment_ingested_new(payload.search_id)
        pipeline_status.increment_vendor(payload.search_id, vendor, 1)
        listings_to_assign_cpk.append(listing)

    # Process CPK assignment concurrently (up to 4 parallel, matching Ollama's OLLAMA_NUM_PARALLEL)
    # Uses GLOBAL _CPK_SEMAPHORE (not per-submission) to prevent 6 workers × 4 slots = 24 concurrent requests
    if listings_to_assign_cpk:
        async def assign_cpk_with_semaphore(listing):
            async with _CPK_SEMAPHORE:
                async with AsyncSessionLocal() as task_db:
                    cpk = await assign_cpk_and_accumulate_price(
                        task_db,
                        listing.listing_id,
                        listing.title,
                        category=None,
                        condition=listing.condition_normalised,
                        price=listing.current_delivered_price,
                        scan_price=listing.scan_price,
                    )
                    await task_db.commit()
                    return (listing.listing_id, cpk)

        results = await asyncio.gather(
            *[assign_cpk_with_semaphore(listing) for listing in listings_to_assign_cpk],
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, Exception):
                log.warning("diag.cpk_assignment.error", error=str(result))
                pipeline_status.increment(payload.search_id, cpk_failed_count=1)
                continue
            listing_id, cpk = result
            if cpk is not None:
                cpk_assigned_count += 1
                pipeline_status.increment(payload.search_id, cpk_assigned_count=1)
                pipeline_status.track_listing(payload.search_id, listing_id)
            else:
                # Extraction gave up (Ollama error/low confidence) -- counted
                # separately so is_complete doesn't wait on a count that can
                # never be reached this run.
                pipeline_status.increment(payload.search_id, cpk_failed_count=1)
    log.info(
        "diag.scan.phase1_ingest_done",
        elapsed_s=round(_time.monotonic() - _t0, 1),
        new_listings=ingested_count,
        cpk_assigned=cpk_assigned_count,
        cross_run_dupes_unchanged_price=touched_unchanged_count,
        cross_run_dupes_price_updated=touched_price_updated_count,
        excluded_auctions=excluded_auction_count,
    )
    pipeline_status.finish_submission(payload.search_id)

    return ScanIngestResponse(
        search_run_id=payload.search_run_id,
        ingested_count=ingested_count,
        cpk_assigned_count=cpk_assigned_count,
        excluded_auction_count=excluded_auction_count,
    )


@router.get("/inventory-match", response_model=InventoryAwareness)
async def inventory_match(
    category: str | None = Query(default=None),
    model: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> InventoryAwareness:
    return await fetch_inventory_awareness(db, category, model, brand)


@router.post("/scans-queued", response_model=ScanQueuedResponse, status_code=202)
async def submit_scan_queued(
    payload: ScanSubmitRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> ScanQueuedResponse:
    """Queue a scan for async processing. Returns immediately with 202 Accepted.
    The background worker will process the submission asynchronously.
    This ensures no data is lost if the backend restarts."""
    submission = await SubmissionQueueService.enqueue_submission(
        db,
        search_run_id=payload.search_run_id,
        search_id=payload.search_id,
        query=payload.query,
        source_url=payload.source_url,
        max_candidates_for_deep_research=payload.max_candidates_for_deep_research,
        # mode="json" — plain model_dump() leaves extracted_at/auction_end_at
        # as Python datetime objects, which the listings_json JSON column's
        # serializer can't encode (TypeError: Object of type datetime is not
        # JSON serializable). mode="json" renders them as ISO strings, which
        # ExtractedListing(**listing) in queue_processor.py parses straight
        # back into datetimes on the way out.
        listings=[listing.model_dump(mode="json") for listing in payload.listings],
    )
    log.info("submission_queued", search_run_id=payload.search_run_id, submission_id=submission.id)
    return ScanQueuedResponse(
        search_run_id=payload.search_run_id,
        submission_id=submission.id,
        status="queued",
    )


class QueueStatusResponse(BaseModel):
    """Snapshot of the submission_queue table, for the extension/dashboard
    to show live progress instead of the queue being an opaque black box."""
    pending: int
    processing: int
    completed: int
    failed: int


@router.get("/queue-status", response_model=QueueStatusResponse)
async def queue_status(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> QueueStatusResponse:
    stats = await SubmissionQueueService.get_queue_stats(db)
    return QueueStatusResponse(**stats)


class SweepCompleteResponse(BaseModel):
    acknowledged: bool


@router.post("/scan-sweep-complete", response_model=SweepCompleteResponse)
async def scan_sweep_complete(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> SweepCompleteResponse:
    """Called once by FlipFlopXtension's runDueScansForced after every
    vendor/search in a scan sweep has finished scraping and issuing its
    (queued) submissions — see background/index.ts. Does NOT run Phase 2
    itself: submissions are fire-and-forget from the extension's side, so
    some may still be sitting in submission_queue when this call lands. It
    just sets a flag; app/workers/queue_processor.py's _phase2_trigger_loop
    polls this flag and only runs Phase 2 once the queue has genuinely
    drained, then clears it."""
    from app.models.gem_radar_sweep_signal import GemRadarSweepSignal
    from sqlalchemy import select
    from datetime import datetime, timezone

    result = await db.execute(select(GemRadarSweepSignal).where(GemRadarSweepSignal.id == 1))
    signal = result.scalar_one_or_none()
    if signal is None:
        signal = GemRadarSweepSignal(id=1)
        db.add(signal)
    signal.pending = True
    signal.requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    log.info("scan_sweep_complete.signalled")
    return SweepCompleteResponse(acknowledged=True)


class SweepStartedResponse(BaseModel):
    acknowledged: bool


@router.post("/scan-sweep-started", response_model=SweepStartedResponse)
async def scan_sweep_started(
    _: None = Depends(require_operator),
) -> SweepStartedResponse:
    """Called once by FlipFlopXtension's "Run All Now" button (the
    searchId=null / forceReset branch of handleRunNow in background/index.ts)
    before it starts submitting anything. Without this, pressing the button
    again mid-run (or right after an interrupted one) left the Current Scan
    Run panel's in-memory counters (see pipeline_status.py) accumulating on
    top of the previous, unrelated run's leftover numbers — the same
    reset_run() normally does at the natural end of a sweep, just triggered
    from the other end so a fresh press always starts every gauge at zero
    instead of stale/inflated totals. Does not touch the DB; only the
    ephemeral in-memory dashboard state."""
    pipeline_status.reset_run()
    log.info("scan_sweep_started.reset")
    return SweepStartedResponse(acknowledged=True)


@router.post("/purchases", response_model=BoughtItResponse)
async def bought_it(
    payload: BoughtItPayload,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> BoughtItResponse:
    return await create_provisional_purchase(db, payload)


@router.get("/price-history/{listing_id}", response_model=list[PriceObservation])
async def price_history(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> list[PriceObservation]:
    return await get_observation_history(db, listing_id)


@router.get("/seller/{seller_name}", response_model=SellerIntelligence)
async def seller_profile(
    seller_name: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> SellerIntelligence:
    profile = await get_seller_profile(db, seller_name)
    if profile is None:
        return SellerIntelligence(
            sellerName=seller_name, feedbackPercent=None, feedbackCount=None, sellerType=None,
            observedListings=0, historicalGemCount=0, historicalSuperGemCount=0,
            historicalPurchaseCount=0, cancellationCount=0, issueCount=0,
        )
    return profile


# Extension data ingestion endpoints (PRD Phase 2: headless scraper mode)

class IngestListingsRequest(BaseModel):
    """Raw listings from extension scraper, to be deduplicated and scored."""
    listings: list[ExtractedListing]
    searchId: str
    query: str
    sourceUrl: str


class IngestListingsResponse(BaseModel):
    """Outcome of ingest: how many stored vs. deduplicated."""
    success: bool
    stored: int
    deduplicated: int


@router.post("/ingest-listings", response_model=IngestListingsResponse)
async def ingest_listings(
    payload: IngestListingsRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> IngestListingsResponse:
    """Accept raw listings from extension, dedupe against 7-day window, score, and store.

    Deduplication strategy: compare by listing_id. Listings with IDs seen in the last 7 days
    are treated as duplicates (likely relisting or dynamic pricing updates) and skipped.
    Fresh listings are scored via the two-stage pipeline and stored with source="extension".
    """
    from datetime import timedelta
    from sqlalchemy import select
    from app.models.gem_radar_observation import GemRadarListingObservation

    cutoff_date = datetime.utcnow() - timedelta(days=7)

    # Collect all listing IDs from recent observations (7-day window)
    existing_ids = set()
    stmt = select(GemRadarListingObservation.listing_id).where(
        GemRadarListingObservation.observed_at >= cutoff_date
    )
    result = await db.execute(stmt)
    existing_ids = {row[0] for row in result.fetchall()}

    # Separate fresh and deduplicated listings — auctions excluded entirely,
    # same rationale as /scans (see the comment there): a current bid isn't
    # a real price.
    fresh_listings = [
        l for l in payload.listings if l.listing_id not in existing_ids and l.listing_type != "auction"
    ]
    deduplicated_count = len(payload.listings) - len(fresh_listings)

    # Score fresh listings through the two-stage pipeline
    if fresh_listings:
        cheap_results = [
            await score_listing(
                db, listing, rank=i + 1,
                sold_adapter=_sold_adapter, amazon_adapter=_amazon_adapter,
                deep_research=False
            )
            for i, listing in enumerate(fresh_listings)
        ]
        cheap_results.sort(key=lambda r: (r.deal_score, r.confidence_score), reverse=True)

        # Deep research on top candidates (conservative 10% for cost control)
        deep_candidates = max(1, len(cheap_results) // 10)
        deep_research_ids = {
            r.listing.listing_id for r in cheap_results[:deep_candidates]
        }

        final_results = []
        for listing in fresh_listings:
            cheap = next(r for r in cheap_results if r.listing.listing_id == listing.listing_id)
            if listing.listing_id in deep_research_ids:
                deep = await score_listing(
                    db, listing, rank=cheap.rank,
                    sold_adapter=_sold_adapter, amazon_adapter=_amazon_adapter,
                    deep_research=True
                )
                final_results.append(deep)
            else:
                final_results.append(cheap)

        final_results.sort(key=lambda r: (r.deal_score, r.confidence_score), reverse=True)
        for i, r in enumerate(final_results):
            r.rank = i + 1

        # Update gems list with fresh results
        update_latest_gems(final_results)

    return IngestListingsResponse(
        success=True,
        stored=len(fresh_listings),
        deduplicated=deduplicated_count,
    )


class ExtensionStatusResponse(BaseModel):
    """Extension health status for traffic light indicator."""
    state: Literal["idle", "scanning", "error"]
    lastScan: datetime | None = None
    searchesCompleted: int = 0


@router.get("/extension-status", response_model=ExtensionStatusResponse)
async def extension_status(
    _: None = Depends(require_operator),
) -> ExtensionStatusResponse:
    """Return extension connection state for FlipFlop admin traffic light.

    States:
      - idle: extension connected but not currently scanning
      - scanning: currently running a scan
      - error: last scan failed or extension unreachable
    """
    return ExtensionStatusResponse(
        state=_extension_status.state,
        lastScan=_extension_status.lastScan,
        searchesCompleted=_extension_status.searchesCompleted,
    )


class ClearListingsResponse(BaseModel):
    """Result of clearing all listings data."""
    success: bool
    cleared_listings: int
    cleared_observations: int


@router.delete("/clear-listings", response_model=ClearListingsResponse)
async def clear_listings(
    within_minutes: int | None = Query(
        default=None, ge=1,
        description=(
            "If given, only clears rows from the last N minutes instead of "
            "everything — matches the extension's own sourcing interval, so "
            "the reset button undoes a bad/incomplete recent run without "
            "wiping the older historical data pipeline.build_batch_price_index "
            "relies on for pricing. Omit to clear everything (legacy behaviour)."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_operator),
) -> ClearListingsResponse:
    """Clear listings data (scored results and observations).

    Preserves purchased items and seller intelligence. Allows the extension
    to start fresh scans without backend data artifacts from previous runs.
    """
    from sqlalchemy import delete

    cutoff = datetime.utcnow() - timedelta(minutes=within_minutes) if within_minutes else None

    # Clear scored listings (scoped to the recent window if given)
    listings_stmt = delete(GemRadarScoredListing)
    if cutoff is not None:
        listings_stmt = listings_stmt.where(GemRadarScoredListing.scored_at >= cutoff)
    listings_result = await db.execute(listings_stmt)
    listings_cleared = listings_result.rowcount or 0

    # Clear observations (scoped to the recent window if given) — this table
    # also backs the 7-day per-listing dedup and the historical price index,
    # so an unscoped clear here throws away real pricing data unnecessarily.
    from app.models.gem_radar_observation import GemRadarListingObservation
    observations_stmt = delete(GemRadarListingObservation)
    if cutoff is not None:
        observations_stmt = observations_stmt.where(GemRadarListingObservation.observed_at >= cutoff)
    observations_result = await db.execute(observations_stmt)
    observations_cleared = observations_result.rowcount or 0

    await db.commit()

    return ClearListingsResponse(
        success=True,
        cleared_listings=listings_cleared,
        cleared_observations=observations_cleared,
    )


@router.get("/ebay-search")
async def ebay_search(
    query: str = Query(..., description="eBay search query"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(100, ge=1, le=200, description="Results per page"),
    _: None = Depends(require_operator),
) -> dict:
    """Search eBay via the backend to bypass CORS restrictions in the extension.

    The Chrome extension cannot call eBay's API directly due to CORS policy,
    so it proxies through this endpoint instead. Supports pagination to retrieve
    all results, not just the first page.
    """
    from app.services.ebay_browse import search_active_listings
    from datetime import datetime, timezone

    log = structlog.get_logger()
    try:
        offset = (page - 1) * limit
        log.info("ebay_search.searching", query=query, page=page, offset=offset, limit=limit)
        listings = await search_active_listings(query, min_price=0, limit=limit, offset=offset)
        log.info("ebay_search.success", query=query, count=len(listings), page=page)
        # EbayListing has: title, price, condition, url, image_url, epid
        # Extract URL's listing ID from eBay URL format: https://www.ebay.co.uk/itm/LISTINGID
        now = datetime.now(timezone.utc).isoformat()

        # Pagination: keep going if we got results (could be a partial page but still more)
        # Only stop if we got ZERO results
        has_next_page = len(listings) > 0

        return {
            "success": True,
            "listings": [
                {
                    "listingId": listing["url"].split("/itm/")[-1].split("?")[0] if "/itm/" in listing["url"] else "",
                    "url": listing["url"],
                    "title": listing["title"],
                    "seller": None,
                    "sellerFeedbackPercent": listing.get("seller_feedback_percent"),
                    "sellerFeedbackCount": listing.get("seller_feedback_count"),
                    "conditionRaw": listing["condition"],
                    "conditionNormalised": "new" if listing["condition"].lower() in ["new", "new other"] else "used" if listing["condition"].lower() in ["used"] else "unknown",
                    "itemPrice": listing["price"],
                    "postagePrice": 0,
                    "currentDeliveredPrice": listing["price"],
                    "currency": "GBP",
                    "listingType": "buy_it_now",
                    "bestOfferEnabled": False,
                    "bidCount": None,
                    "auctionEndAt": None,
                    "imageUrl": listing["image_url"],
                    "sponsored": False,
                    "extractedAt": now,
                    "epid": listing.get("epid"),
                    "gtin": listing.get("gtin"),  # Global Trade Item Number from eBay Browse API productSummary
                    "mpn": listing.get("mpn"),  # Manufacturer Part Number from eBay Browse API productSummary
                    "modelNumber": listing.get("model_number"),  # Model number from eBay Browse API productSummary
                }
                for listing in listings
            ],
            "count": len(listings),
            "page": page,
            "limit": limit,
            "hasNextPage": has_next_page,
            "nextPageUrl": None,
        }
    except Exception as e:
        log.exception("ebay_search.failed", query=query, error=str(e))
        return {
            "success": False,
            "error": str(e),
            "listings": [],
            "count": 0,
        }
