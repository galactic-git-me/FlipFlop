"""
Bounded async queue for enriching and persisting scraped listings.

Instead of spawning hundreds of concurrent enrichment tasks (which floods
the event loop and crashes the backend under high listing volume), scrapers
push raw listings here and return immediately.  A fixed pool of workers
drains the queue at a steady, controlled rate.

Architecture:
    Scrapers  →  asyncio.Queue  →  Worker-0  →  enrich → DB
                                →  Worker-1  →  enrich → DB
                                →  Worker-2  →  enrich → DB
                                →  Worker-3  →  enrich → DB
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select, update

from app.database import AsyncSessionLocal

log = structlog.get_logger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULT_WORKERS   = 4
MAX_QUEUE_SIZE    = 5_000   # back-pressure: scrapers get warned if exceeded

# ─── Queue item ───────────────────────────────────────────────────────────────

@dataclass
class IngestItem:
    raw:          Any          # RawListing dataclass from scraper
    source_id:    int
    min_price:    float = 0.0
    max_price:    float = 9999.0
    demand_score: float = 5.0  # 0-10 demand score of the search term that found this listing
    found_via_term: str = ""   # the search term text

# ─── Module-level state ───────────────────────────────────────────────────────

_queue:   asyncio.Queue | None = None
_workers: list[asyncio.Task]   = []
_STOP     = object()            # sentinel to stop a worker

# ─── Public API ───────────────────────────────────────────────────────────────

def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    return _queue


def queue_size() -> int:
    return _queue.qsize() if _queue else 0


def enqueue_nowait(item: IngestItem) -> bool:
    """Non-blocking enqueue.  Returns False (and logs a warning) if full."""
    try:
        get_queue().put_nowait(item)
        return True
    except asyncio.QueueFull:
        log.warning(
            "listing_ingest_queue.full",
            source_id=item.source_id,
            queue_size=MAX_QUEUE_SIZE,
        )
        return False


def start_workers(n: int = DEFAULT_WORKERS) -> None:
    global _workers
    if _workers:
        return  # already running
    for i in range(n):
        task = asyncio.create_task(_worker(i), name=f"ingest-worker-{i}")
        _workers.append(task)
    log.info("listing_ingest_queue.started", workers=n, max_queue=MAX_QUEUE_SIZE)


async def stop_workers() -> None:
    global _workers
    q = get_queue()
    for _ in _workers:
        await q.put(_STOP)
    if _workers:
        await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()
    log.info("listing_ingest_queue.stopped")


# ─── Worker ───────────────────────────────────────────────────────────────────

async def _worker(worker_id: int) -> None:
    q = get_queue()
    log.debug("listing_ingest_queue.worker_ready", worker=worker_id)
    while True:
        item = await q.get()
        if item is _STOP:
            q.task_done()
            break
        try:
            await _process(item)
        except Exception as exc:
            log.error(
                "listing_ingest_queue.worker_error",
                worker=worker_id,
                source_id=item.source_id,
                external_id=getattr(item.raw, "external_id", "?"),
                error=str(exc),
            )
        finally:
            q.task_done()


# ─── Processing ───────────────────────────────────────────────────────────────

_MINI_PC_KW = {
    "mini pc", "mini-pc", "intel nuc", " nuc ", "nuc pc",
    "beelink", "minisforum", "gmktec", "trigkey", "geekom",
    "stick pc", "tiny pc", "mini computer",
}


async def _save_as_part(raw: Any, category: str) -> None:
    from app.models.part import Part, PartCategory, PartCondition
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(Part).where(Part.source_url == raw.url).limit(1)
        )
        if existing.scalar_one_or_none():
            return
        cond_raw = (raw.condition or "used").lower()
        condition = (
            PartCondition.new if "new" in cond_raw
            else PartCondition.refurb if "refurb" in cond_raw
            else PartCondition.used
        )
        image_url = (raw.image_urls[0] if raw.image_urls else None)
        part = Part(
            name=raw.title[:300],
            category=PartCategory(category),
            price=raw.price,
            price_used=raw.price if condition == PartCondition.used else None,
            price_new=raw.price if condition == PartCondition.new else None,
            price_refurb=raw.price if condition == PartCondition.refurb else None,
            source_site=raw.source_name,
            source_url=raw.url,
            condition=condition,
            image_url=image_url,
            last_price_update=datetime.utcnow(),
        )
        db.add(part)
        await db.commit()
        log.info("part.routed_from_flip_scan", title=raw.title[:80], category=category, price=raw.price)


async def _process(item: IngestItem) -> None:
    from app.services.spec_parser import parse_specs, validate_pc_listing
    from app.services.classifier import score_listing, detect_component_category
    from app.services.estimator import estimate_upgrade_cost, estimate_profit
    from app.services.resale_scraper import get_resale_range
    from app.services.claude_eval_queue import enqueue_for_claude, should_queue_for_claude
    from app.models.listing import Listing, ListingStatus, Classification

    raw = item.raw

    # Quick filter — mini PCs are not flippable gaming PCs
    if any(kw in raw.title.lower() for kw in _MINI_PC_KW):
        return

    # Route standalone components/accessories to the parts catalogue
    part_category = detect_component_category(raw.title)
    if part_category:
        await _save_as_part(raw, part_category)
        return

    # ── Validate listing is actually a PC (filter false positives) ──────────────
    is_valid_pc, invalid_reason = validate_pc_listing(raw.title, raw.description or "")
    if not is_valid_pc:
        log.info(
            "listing_ingest_queue.rejected_false_positive",
            title=raw.title[:80],
            reason=invalid_reason,
            source=raw.source_name,
        )
        return

    # ── Enrich ────────────────────────────────────────────────────────────────
    specs        = parse_specs(raw.title, raw.description)
    resale_range = await get_resale_range(
        specs.cpu, specs.ram_gb, specs.ram_type,
        specs.storage_gb, specs.storage_type, specs.gpu,
        buy_price=raw.price,
    )
    _title_lower = raw.title.lower()
    _is_am5 = any(h in _title_lower for h in ("am5", "b650", "x670", "a620"))
    upgrade_cost = estimate_upgrade_cost(
        specs.storage_gb, specs.gpu, specs.has_psu, specs.ram_gb, is_am5=_is_am5
    )
    resale      = resale_range.median
    profit      = estimate_profit(raw.price, resale, upgrade_cost)
    profit_low  = estimate_profit(raw.price, resale_range.low,  upgrade_cost)
    profit_high = estimate_profit(raw.price, resale_range.high, upgrade_cost)
    score_result = score_listing(
        title=raw.title, price=raw.price, estimated_profit=profit,
        cpu=specs.cpu, ram_gb=specs.ram_gb, ram_type=specs.ram_type,
        storage_gb=specs.storage_gb, gpu=specs.gpu, has_psu=specs.has_psu,
        location=raw.location,
        profit_low=profit_low, profit_high=profit_high,
    )

    # ── Upsert ────────────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Listing)
            .where(Listing.external_id == raw.external_id)
            .order_by(Listing.id.desc())
            .limit(1)
        )
        listing = result.scalar_one_or_none()

        if listing:
            listing.last_seen_at          = datetime.utcnow()
            listing.price                 = raw.price
            listing.status                = ListingStatus.active
            listing.estimated_resale      = resale
            listing.resale_low            = resale_range.low
            listing.resale_high           = resale_range.high
            listing.resale_comp_count     = resale_range.count
            listing.estimated_upgrade_cost= upgrade_cost
            listing.estimated_profit      = profit
            listing.classification        = score_result.classification
            listing.gem_score             = score_result.score
            listing.gem_signals           = score_result.signals
        else:
            listing = Listing(
                external_id=raw.external_id,
                source_id=item.source_id,
                source_name=raw.source_name,
                demand_score=item.demand_score,
                found_via_term=item.found_via_term or None,
                title=raw.title,
                description=raw.description,
                price=raw.price,
                url=raw.url,
                image_urls=raw.image_urls,
                location=raw.location,
                condition=raw.condition,
                cpu=specs.cpu, ram_gb=specs.ram_gb, ram_type=specs.ram_type,
                storage_gb=specs.storage_gb, storage_type=specs.storage_type,
                gpu=specs.gpu, has_psu=specs.has_psu,
                gem_score=score_result.score,
                classification=score_result.classification,
                gem_signals=score_result.signals,
                estimated_resale=resale,
                resale_low=resale_range.low,
                resale_high=resale_range.high,
                resale_comp_count=resale_range.count,
                estimated_profit=profit,
                estimated_upgrade_cost=upgrade_cost,
                initial_estimated_profit=profit,
            )
            db.add(listing)

        await db.flush()
        listing_id = listing.id
        needs_claude = listing.claude_judged_at is None and should_queue_for_claude(listing)
        await db.commit()

    # Queue for Claude evaluation (checked inside session while attrs are live)
    if listing_id and needs_claude:
        enqueue_for_claude(listing_id)
