"""Asynchronous margin verification using local Qwen2:7b.

Scored listings are checked against actual resale prices to verify profit margin
exists. Runs in background queue—does not block main screening pipeline.
"""
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

log = structlog.get_logger(__name__)

_VERIFICATION_PROMPT = """You are a flipping margin verification assistant.

Given a PC component listing with purchase price and market data, determine if it's
actually a viable flip opportunity. Look at:
1. Purchase price vs actual resale prices (not just median)
2. Absolute profit margin in GBP (not percentage)
3. Whether comparable items have real demand

CRITICAL — data sourcing rules:
- The market resale figures you are given below come from a live scrape of
  today's actual eBay listings. They are NOT an estimate and NOT your own
  recollection of what this product "usually" costs.
- Component prices (CPUs, GPUs, etc.) move week to week. Whatever price you
  might recall from training data is very likely stale — ignore it entirely
  and reason ONLY from the numbers given to you in this prompt.
- Only eBay, Amazon, and Overclockers are treated as reputable pricing
  sources for this check. If the data provided says a resale price is
  unavailable, say so — do not fill the gap with a guessed "typical" price
  from memory.

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "actual_buy_price_gbp": <number>,
  "realistic_resale_price_gbp": <number>,
  "profit_margin_gbp": <number>,
  "is_viable_flip": <boolean>,
  "reasoning": "<1-2 sentences why or why not, citing the given resale data>"
}}

Viable means: >£30 absolute profit, real market demand, comparable items selling."""


@dataclass
class VerificationResult:
    listing_id: str
    actual_buy_price_gbp: float
    realistic_resale_price_gbp: float
    profit_margin_gbp: float
    is_viable_flip: bool
    reasoning: str
    # The purchase_price passed INTO verify_margin_async, not an LLM-echoed
    # value — used by _downgrade_unviable_listing to confirm the scored row
    # it's about to correct is still the same listing state this result was
    # actually computed against. gem_radar_scored_listings is append-only
    # (a new row per re-score) and this worker runs well after enqueue, so a
    # listing that gets rescanned/rescored at a new price while its old
    # verification is still queued would otherwise have that stale verdict
    # wrongly applied to the new row.
    source_purchase_price: float


async def verify_margin_async(
    listing_id: str,
    title: str,
    purchase_price: float,
    condition: str,
    market_resale_median: float | None,
    market_resale_range: tuple[float, float] | None,
) -> VerificationResult | None:
    """Verify if listing has real profit margin using Qwen2:7b.

    Returns None if verification fails; result contains is_viable_flip flag.
    Non-blocking—designed for background queue.
    """
    resale_median_str = f"£{market_resale_median:.2f}" if market_resale_median is not None else "unknown"
    resale_range_str = (
        f"£{market_resale_range[0]:.2f}-£{market_resale_range[1]:.2f}" if market_resale_range is not None else "unknown"
    )
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user_prompt = f"""Today's date: {today_str}

Title: {title}
Purchase price: £{purchase_price:.2f}
Condition: {condition}
Market resale median: {resale_median_str} (source: our own eBay listing scrape, {today_str} — NOT your training data)
Market resale range: {resale_range_str} (source: our own eBay listing scrape, {today_str} — NOT your training data)

The resale figures above come from real eBay listings scraped today, not from
your training data. eBay prices for PC components move week to week, so any
price you recall from training is very likely stale — use ONLY the numbers
given above, never a remembered price for this model.

Is this a viable flip?"""

    from app.config import get_settings
    from app.gem_radar.claude_screening import _ollama_semaphore

    settings = get_settings()
    ollama_base_url = settings.ollama_base_url or "http://localhost:11434"
    ollama_model = settings.ollama_model or "qwen2:7b"

    try:
        # Shares claude_screening.py's semaphore — see the comment there.
        # Real observed latency for a trivial prompt on this GPU was 45s
        # under concurrent load (99% GPU util, 6.1/8GB VRAM), so 15s was
        # guaranteed to time out almost every call; 90s gives real headroom
        # while still bounding a genuinely stuck request.
        async with _ollama_semaphore, httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{ollama_base_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": f"{_VERIFICATION_PROMPT}\n\n{user_prompt}",
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()

            data = response.json()
            output_text = data.get("response", "").strip()

            # Extract JSON from output (strip markdown if present)
            if output_text.startswith("```json"):
                output_text = output_text[7:]
            if output_text.startswith("```"):
                output_text = output_text[3:]
            if output_text.endswith("```"):
                output_text = output_text[:-3]

            result_data = json.loads(output_text.strip())

            return VerificationResult(
                listing_id=listing_id,
                actual_buy_price_gbp=float(result_data.get("actual_buy_price_gbp", purchase_price)),
                realistic_resale_price_gbp=float(result_data.get("realistic_resale_price_gbp", market_resale_median or purchase_price)),
                profit_margin_gbp=float(result_data.get("profit_margin_gbp", 0)),
                is_viable_flip=bool(result_data.get("is_viable_flip", False)),
                reasoning=str(result_data.get("reasoning", "No reasoning provided")),
                source_purchase_price=purchase_price,
            )

    except asyncio.TimeoutError:
        log.warning("margin_verifier.qwen_timeout", listing_id=listing_id)
        return None
    except (json.JSONDecodeError, httpx.RequestError) as exc:
        # httpx timeout exceptions frequently stringify to "" — log the
        # exception type too, or a timeout is indistinguishable from a
        # genuinely empty/unhelpful error message in the logs.
        log.warning("margin_verifier.qwen_failed", listing_id=listing_id, error_type=type(exc).__name__, error=str(exc))
        return None


# Background verification queue
_verification_queue: asyncio.Queue[tuple[str, str, float, str, float | None, tuple[float, float] | None]] = asyncio.Queue()
_verification_results: dict[str, VerificationResult] = {}


async def enqueue_verification(
    listing_id: str,
    title: str,
    purchase_price: float,
    condition: str,
    market_resale_median: float | None,
    market_resale_range: tuple[float, float] | None,
) -> None:
    """Queue a listing for background margin verification."""
    await _verification_queue.put((listing_id, title, purchase_price, condition, market_resale_median, market_resale_range))


async def get_verification(listing_id: str) -> VerificationResult | None:
    """Get verification result if completed (non-blocking)."""
    return _verification_results.get(listing_id)


async def start_verification_worker() -> None:
    """Background worker—processes verifications from queue. Non-blocking."""
    log.info("margin_verifier.worker_started")

    while True:
        try:
            listing_id, title, purchase_price, condition, market_resale_median, market_resale_range = await asyncio.wait_for(
                _verification_queue.get(), timeout=300.0
            )

            result = await verify_margin_async(
                listing_id=listing_id,
                title=title,
                purchase_price=purchase_price,
                condition=condition,
                market_resale_median=market_resale_median,
                market_resale_range=market_resale_range,
            )

            if result:
                _verification_results[listing_id] = result
                log.info(
                    "margin_verifier.verified",
                    listing_id=listing_id,
                    viable=result.is_viable_flip,
                    margin=result.profit_margin_gbp,
                )
                if not result.is_viable_flip:
                    await _downgrade_unviable_listing(result)

        except asyncio.TimeoutError:
            log.debug("margin_verifier.worker_idle")
        except Exception as exc:
            log.error("margin_verifier.worker_error", error=str(exc))
            await asyncio.sleep(1)  # Back off on error


async def _downgrade_unviable_listing(result: VerificationResult) -> None:
    """Retroactively corrects the DB row once Qwen2's margin check comes
    back negative — this is the actual gate the deterministic scorer can't
    provide on its own (it only ever compares against a benchmark price, not
    real buy-vs-resale profit, which is what let something like a £332
    i9-9900K score as a "deal" despite reselling for £180-289 used). Runs
    after the scan response has already returned to the extension, so this
    is the only place that classification can still be corrected — the
    scored row itself must be updated, not just the in-memory result cache,
    or the sourcing page keeps showing the original bad classification.
    """
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.gem_radar_scored_listing import GemRadarScoredListing

    async with AsyncSessionLocal() as db:
        query_result = await db.execute(
            select(GemRadarScoredListing)
            .where(GemRadarScoredListing.listing_id == result.listing_id)
            .order_by(GemRadarScoredListing.scored_at.desc())
            .limit(1)
        )
        row = query_result.scalar_one_or_none()
        if row is None or row.classification not in ("SUPER_GEM", "GEM"):
            return
        # gem_radar_scored_listings is append-only — a listing rescanned at a
        # new price gets a NEW row, and this worker can complete well after
        # that happens if the queue was backed up. Only apply a verdict to
        # the exact price it was actually computed against, or a stale
        # "not viable" from an old price could wrongly downgrade a fresh,
        # genuinely-different scoring of the same listing_id.
        if abs(row.delivered_price - result.source_purchase_price) > 0.01:
            log.info(
                "margin_verifier.downgrade_skipped_stale",
                listing_id=result.listing_id,
                verified_price=result.source_purchase_price,
                current_price=row.delivered_price,
            )
            return

        note = (
            f"[Margin verification, qwen2:7b] NOT a viable flip: buy £{result.actual_buy_price_gbp:.2f} "
            f"vs realistic resale £{result.realistic_resale_price_gbp:.2f} "
            f"(margin £{result.profit_margin_gbp:.2f}). {result.reasoning}"
        )
        row.classification = "POOR_DEAL"
        row.decision = "IGNORE"
        row.reasoning_summary = f"{row.reasoning_summary}\n\n{note}" if row.reasoning_summary else note
        await db.commit()
        log.info("margin_verifier.downgraded", listing_id=result.listing_id, margin=result.profit_margin_gbp)
