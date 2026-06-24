"""
Background queue for AI evaluation of parts catalogue gems.

After the rule-based scorer identifies gem candidates, this queue passes
them to Claude for market price verification. Workers store the verdict
back to all Part records with that name+category.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import structlog

from app.database import AsyncSessionLocal

log = structlog.get_logger(__name__)

_MAX_QUEUE   = 500
_NUM_WORKERS = 2    # fewer parts than listings; Haiku is fast
_CALL_DELAY  = 2.0  # seconds between AI calls per worker

_queue:   asyncio.Queue | None = None
_workers: list[asyncio.Task]   = []
_STOP = object()


# ── Public API ────────────────────────────────────────────────────────────────

def get_part_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    return _queue


def enqueue_part_for_claude(name: str, category: str) -> bool:
    """Non-blocking enqueue.  Returns False if queue is full."""
    try:
        get_part_queue().put_nowait((name, category))
        return True
    except asyncio.QueueFull:
        log.warning("part_gem_eval_queue.full", name=name, category=category)
        return False


def start_part_eval_workers(n: int = _NUM_WORKERS) -> None:
    global _workers
    if _workers:
        return
    for i in range(n):
        task = asyncio.create_task(_worker(i), name=f"part-gem-eval-worker-{i}")
        _workers.append(task)
    log.info("part_gem_eval_queue.started", workers=n)


async def stop_part_eval_workers() -> None:
    global _workers
    q = get_part_queue()
    for _ in _workers:
        await q.put(_STOP)
    if _workers:
        await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()
    log.info("part_gem_eval_queue.stopped")


# ── Workers ───────────────────────────────────────────────────────────────────

async def _worker(worker_id: int) -> None:
    q = get_part_queue()
    if worker_id > 0:
        await asyncio.sleep(worker_id * 10)
    log.debug("part_gem_eval_queue.worker_ready", worker=worker_id)
    while True:
        item = await q.get()
        if item is _STOP:
            q.task_done()
            break
        try:
            name, category = item
            await _evaluate(name, category)
            await asyncio.sleep(_CALL_DELAY)
        except Exception as exc:
            log.error(
                "part_gem_eval_queue.worker_error",
                worker=worker_id,
                item=str(item),
                error=str(exc),
            )
        finally:
            q.task_done()


# ── Core evaluation ───────────────────────────────────────────────────────────

async def _evaluate(name: str, category: str) -> None:
    from sqlalchemy import select
    from app.models.part import Part
    from app.services.part_gem_evaluator import evaluate_part
    from app.services.part_gem_scorer import GOOD_SOURCES, score_groups

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Part).where(
                Part.name == name,
                Part.category == category,
                Part.is_active == True,
            )
        )
        parts = result.scalars().all()

    if not parts:
        return

    # Skip if already judged
    if any(p.claude_judged_at is not None for p in parts):
        return

    # Find cheapest trusted-source price
    priced = [p for p in parts if p.price is not None]
    good_priced = [p for p in priced if p.source_site in GOOD_SOURCES]
    if not good_priced:
        return

    cheapest_good = min(good_priced, key=lambda p: p.price)

    # Re-score just this group to get discount %
    group_data = [{"name": name, "category": category, "cheapest_good_price": cheapest_good.price}]
    scores = score_groups(group_data)
    score_info = scores.get(f"{category}::{name}", {})

    part_data = {
        "name": name,
        "category": category,
        "cheapest_good_price": cheapest_good.price,
        "cheapest_good_source": cheapest_good.source_site,
        "gem_score": score_info.get("gem_score"),
        "gem_classification": score_info.get("gem_classification"),
    }

    result = await evaluate_part(part_data)
    if not result:
        log.warning("part_gem_eval_queue.eval_failed", name=name, category=category)
        return

    # Write verdict back to ALL Part records with this name+category
    async with AsyncSessionLocal() as db:
        db_result = await db.execute(
            select(Part).where(
                Part.name == name,
                Part.category == category,
                Part.is_active == True,
            )
        )
        parts_to_update = db_result.scalars().all()
        now = datetime.utcnow()
        for p in parts_to_update:
            p.claude_verdict    = result.verdict
            p.claude_reasoning  = result.reasoning
            p.claude_confidence = result.confidence
            p.claude_judged_at  = now
        await db.commit()

    log.info(
        "part_gem_eval_queue.judged",
        name=name,
        category=category,
        verdict=result.verdict,
        price=f"£{cheapest_good.price:.0f}",
        model=result.model_used,
    )
