"""
Bounded async queue for Claude gem evaluations.

After the enrichment pipeline writes a candidate to DB it pushes the
listing's DB id here.  Two workers drain the queue at a rate that respects
API limits (2-second gap between calls per worker).

Claude's verdict is written back to the listing row and becomes the
authoritative classification — overriding the rule-based score.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal

log = structlog.get_logger(__name__)

_MAX_QUEUE     = 2_000
_NUM_WORKERS   = 2     # two workers for parallelism — Ollama queues concurrent requests
_CALL_DELAY    = 2.0   # 2s gap so workers don't fire simultaneously

_queue:   asyncio.Queue | None = None
_workers: list[asyncio.Task]   = []
_STOP = object()


# ── Public API ────────────────────────────────────────────────────────────────

def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    return _queue


def queue_size() -> int:
    return _queue.qsize() if _queue else 0


def enqueue_for_claude(listing_id: int) -> bool:
    """Non-blocking enqueue.  Returns False if the queue is full."""
    try:
        get_queue().put_nowait(listing_id)
        return True
    except asyncio.QueueFull:
        log.warning("claude_eval_queue.full", listing_id=listing_id)
        return False


def start_eval_workers(n: int = _NUM_WORKERS) -> None:
    global _workers
    if _workers:
        return
    for i in range(n):
        task = asyncio.create_task(_worker(i), name=f"claude-eval-worker-{i}")
        _workers.append(task)
    log.info("claude_eval_queue.started", workers=n)


async def stop_eval_workers() -> None:
    global _workers
    q = get_queue()
    for _ in _workers:
        await q.put(_STOP)
    if _workers:
        await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()
    log.info("claude_eval_queue.stopped")


# ── Workers ───────────────────────────────────────────────────────────────────

async def _worker(worker_id: int) -> None:
    q = get_queue()
    # Stagger workers so they don't hit the LLM simultaneously
    if worker_id > 0:
        await asyncio.sleep(worker_id * 25)
    log.debug("claude_eval_queue.worker_ready", worker=worker_id)
    while True:
        item = await q.get()
        if item is _STOP:
            q.task_done()
            break
        try:
            await _evaluate(item)
            await asyncio.sleep(_CALL_DELAY)
        except Exception as exc:
            log.error(
                "claude_eval_queue.worker_error",
                worker=worker_id,
                listing_id=item,
                error=str(exc),
            )
        finally:
            q.task_done()


# ── Pre-filter ────────────────────────────────────────────────────────────────

def should_queue_for_claude(listing) -> bool:
    """
    Lightweight gate — avoid sending clear rejects to Claude.
    Keeps Claude focused on plausible candidates.
    """
    from app.models.listing import Classification
    if not listing.price or listing.price <= 0:
        return False
    # Rule-based system already hard-rejected this (faulty, component-only, etc.)
    if listing.classification == Classification.overpriced:
        return False
    # IT / refurb shops have already priced in the flip margin
    if listing.seller_type == "refurb_shop":
        return False
    return True


# ── Core evaluation ──────────────────────────────────────────────────────────

async def _evaluate(listing_id: int) -> None:
    from app.models.listing import Listing, Classification
    from app.services.claude_evaluator import evaluate_listing

    # Load listing data (read-only session)
    async with AsyncSessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        if not listing:
            return
        if listing.claude_judged_at is not None:
            return   # already judged, skip

        listing_data = {
            "title":                  listing.title,
            "price":                  listing.price,
            "source_name":            listing.source_name,
            "location":               listing.location,
            "condition":              listing.condition,
            "seller_type":            listing.seller_type,
            "listing_type":           listing.listing_type,
            "cpu":                    listing.cpu,
            "ram_gb":                 listing.ram_gb,
            "ram_type":               listing.ram_type,
            "storage_gb":             listing.storage_gb,
            "storage_type":           listing.storage_type,
            "gpu":                    listing.gpu,
            "has_psu":                listing.has_psu,
            "estimated_resale":       listing.estimated_resale,
            "resale_low":             listing.resale_low,
            "resale_high":            listing.resale_high,
            "resale_comp_count":      listing.resale_comp_count,
            "estimated_upgrade_cost": listing.estimated_upgrade_cost,
            "estimated_profit":       listing.estimated_profit,
            "gem_score":              listing.gem_score,
            "gem_signals":            listing.gem_signals,
            "description":            listing.description,
        }

    result = await evaluate_listing(listing_data)
    if not result:
        log.warning("claude_eval_queue.eval_failed", listing_id=listing_id)
        return

    # Map Claude verdict → Classification (backwards-compatible field)
    _verdict_map = {
        "GEM":    Classification.amazing_gem,
        "GOOD":   Classification.gem,
        "MAYBE":  Classification.already_flipped,   # marginal — not a loss, but not a flip
        "REJECT": Classification.overpriced,
    }

    async with AsyncSessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        if not listing:
            return

        listing.claude_verdict            = result.verdict
        listing.claude_flipability_score  = result.flipability_score
        listing.claude_expected_profit    = result.expected_profit
        listing.claude_roi                = result.roi
        listing.claude_confidence         = result.confidence
        listing.claude_capital_efficiency = result.capital_efficiency
        listing.claude_resale_demand      = result.resale_demand
        listing.claude_upgrade_complexity = result.upgrade_complexity
        listing.claude_reasoning          = result.reasoning
        listing.claude_main_risk          = result.main_risk
        listing.claude_judged_at          = datetime.utcnow()
        # Override classification with Claude's authoritative verdict
        listing.classification = _verdict_map.get(result.verdict, listing.classification)
        # Override gem_score with Claude's flipability score (dashboard sorts on this)
        listing.gem_score = result.flipability_score

        await db.commit()

    log.info(
        "claude_eval_queue.judged",
        listing_id=listing_id,
        verdict=result.verdict,
        score=result.flipability_score,
        profit=f"£{result.expected_profit:.0f}",
        model=result.model_used,
    )
