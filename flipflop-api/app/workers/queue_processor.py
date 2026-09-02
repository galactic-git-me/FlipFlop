"""Background worker to process gem-radar submission queue."""
import asyncio
import json
import os
import re
import threading
import structlog
from datetime import datetime
from urllib.parse import urlparse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.submission_queue_service import SubmissionQueueService
from app.gem_radar.schemas import ScanSubmitRequest, ExtractedListing
from app.config import get_settings

logger = structlog.get_logger(__name__)

# Every timeout added elsewhere tonight (per-listing scoring, vision check,
# deep-research batch) only bounds a piece INSIDE _submit_scan_body — nothing
# bounds the submission as a whole. A hang anywhere outside those guarded
# sections (dedup, eBay Browse API lookups before scoring even starts, etc.)
# blocks this coroutine forever. This used to starve the whole queue under
# the old fixed-batch-of-10-then-gather design (see git history); the
# persistent worker pool below limits a hang's blast radius to the one
# worker that claimed it, and _stale_reaper_loop provides an external
# backstop for submissions whose internal timeout doesn't fire cleanly.
#
# 900s, not 600s: cheap scoring (up to ~240s for a large batch at
# _SCORING_CONCURRENCY=25 with the 60s per-listing cap) + the deep-research
# batch (up to 480s, see _score_listings_concurrently's overall_deadline_s
# in api/gem_radar.py) + the 120s vision-check timeout can legitimately sum
# past 600s in the worst case — a submission-level timeout tighter than the
# sum of its own inner budgets would cut deep research off before it gets
# its full allowance, defeating the point of raising that budget at all.
_SUBMISSION_TIMEOUT_S = 900.0

# Number of persistent workers claiming submissions independently. Each
# worker's own scoring load is bounded by the shared process-wide
# _scoring_semaphore (see app/api/gem_radar.py, capped at 25) — raising this
# doesn't increase outbound request pressure on eBay/Claude, it just means
# more submissions can be IN FLIGHT (most of them waiting on that shared
# semaphore) instead of queued behind a fixed-size batch.
_WORKER_COUNT = 15
_EMPTY_QUEUE_POLL_SECONDS = 5

# Track actively-processing search_ids to enforce concurrent search term limit
_active_search_ids: set[str] = set()
_active_search_lock = asyncio.Lock()


def _start_stall_watchdog() -> threading.Event:
    """Start an independent queue-stall watchdog.

    The ordinary stale reaper is an asyncio task.  It cannot run when the
    event loop is wedged, which is precisely the failure mode it is intended
    to recover from.  This thread uses its own synchronous PostgreSQL
    connection and deliberately exits the worker process when it sees a
    submission older than the overall submission timeout. Docker's restart
    policy then starts a clean worker, whose startup recovery puts those rows
    back into the pending queue and clears the in-memory search-term slots.
    """
    settings = get_settings()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_stall_watchdog_loop,
        args=(stop_event, settings.sync_database_url, settings.queue_stall_watchdog_seconds,
              settings.queue_stall_watchdog_poll_seconds),
        name="submission-queue-stall-watchdog",
        daemon=True,
    )
    thread.start()
    return stop_event


def _stall_watchdog_loop(
    stop_event: threading.Event,
    database_url: str,
    stale_after_seconds: int,
    poll_seconds: int,
) -> None:
    """Exit the process when queue work is stale, even if asyncio is stuck."""
    import psycopg2

    while not stop_event.wait(poll_seconds):
        try:
            with psycopg2.connect(database_url, connect_timeout=10) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM submission_queue
                        WHERE status = 'processing'
                          AND last_attempt_at < (
                              (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                              - make_interval(secs => %s)
                          )
                        ORDER BY last_attempt_at
                        LIMIT 10
                        """,
                        (stale_after_seconds,),
                    )
                    stale_ids = [row[0] for row in cursor.fetchall()]
            if stale_ids:
                logger.critical(
                    "queue_processor.stall_watchdog_restarting_worker",
                    stale_submission_ids=stale_ids,
                    stale_after_seconds=stale_after_seconds,
                )
                # Do not try to cancel tasks from this thread: an event-loop
                # stall may prevent cancellation/finally handlers from ever
                # running. A fresh process is the reliable recovery point.
                os._exit(75)
        except Exception as exc:
            # The watchdog must not make a transient DB outage fatal; the
            # normal worker and Docker health checks retain responsibility for
            # that case. Keep checking on the next interval.
            logger.warning("queue_processor.stall_watchdog_error", error=str(exc))


def _case_brand(title: str) -> str:
    known = ("Lian Li", "Fractal Design", "NZXT", "Corsair", "Phanteks", "Montech", "be quiet!", "HYTE", "Cooler Master", "Thermaltake", "Antec", "DeepCool", "ASUS", "MSI", "Kolink")
    lowered = title.lower()
    return next((brand for brand in known if brand.lower() in lowered), "Other")


def _case_form_factor(title: str) -> str:
    lowered = title.lower()
    if "mini-itx" in lowered or "mini itx" in lowered or " itx" in lowered:
        return "itx"
    if "micro-atx" in lowered or "micro atx" in lowered or "matx" in lowered or "m-atx" in lowered:
        return "matx"
    return "atx"


def _is_case_search(search_id: str) -> bool:
    """Accept extension search IDs that clearly represent case searches."""
    normalized = re.sub(r"[^a-z0-9]+", "-", str(search_id or "").lower()).strip("-")
    if any(token in normalized for token in ("case-fan", "case-fans", "case-accessory", "case-accessories")):
        return False
    return "case" in normalized or "chassis" in normalized


def _looks_like_pc_case(title: str) -> bool:
    """Reject peripherals and complete PCs returned by broad case searches."""
    normalized = str(title or "").lower()
    if not re.search(r"\bcase\b|\bchassis\b|\b(?:mid|full|mini)[- ]tower\b", normalized):
        return False
    excluded = (
        "complete pc", "gaming pc", "pre-built", "prebuilt", "desktop computer",
        "case fan", "fan only", "case badge", "case accessory", "carry case",
    )
    return not any(term in normalized for term in excluded)


def _supplier_from_hostname(hostname: str) -> str | None:
    """Map only genuine supplier hosts, never lookalike domains."""
    normalized = str(hostname or "").lower().rstrip(".")
    if normalized == "amazon.co.uk" or normalized.endswith(".amazon.co.uk"):
        return "Amazon"
    if normalized == "overclockers.co.uk" or normalized.endswith(".overclockers.co.uk"):
        return "Overclockers"
    return None


async def _sync_supplier_case_catalogue(db: AsyncSession, payload: ScanSubmitRequest) -> int:
    """Promote verified extension case offers into the customer catalogue."""
    if not _is_case_search(payload.search_id):
        return 0
    from app.models.catalogue import CaseCatalogue

    hostname = urlparse(payload.source_url).hostname or ""
    vendor = _supplier_from_hostname(hostname)
    if not vendor:
        return 0
    now = datetime.utcnow().isoformat()
    upserted = 0
    for offer in payload.listings:
        if offer.sponsored or offer.condition_normalised != "new" or not _looks_like_pc_case(offer.title):
            continue
        if vendor == "Amazon" and not (
            offer.prime_eligible
            and re.sub(r"\s+", "", offer.delivery_postcode or "").upper() == "TW121JQ"
            and re.search(r"tomorrow|overnight|one[- ]day", offer.delivery_text or "", re.I)
        ):
            continue
        name = offer.title.strip()[:200]
        case_images = list(dict.fromkeys(offer.image_urls or ([offer.image_url] if offer.image_url else [])))[:12]
        existing = (await db.execute(select(CaseCatalogue).where(CaseCatalogue.name == name))).scalar_one_or_none()
        supplier = {
            "vendor": vendor,
            "external_id": offer.listing_id,
            "url": offer.url,
            "price_gbp": offer.current_delivered_price,
            "delivery_postcode": "TW12 1JQ",
            "delivery_promise": offer.delivery_text or "Next working day available",
            "prime_eligible": bool(offer.prime_eligible),
            "observed_at": now,
        }
        if existing:
            existing.rrp_gbp = offer.current_delivered_price
            existing.images = case_images or existing.images
            existing.notes = json.dumps({"supplier_offer": supplier})
            existing.status = "active"
            existing.updated_at = now
        else:
            db.add(CaseCatalogue(
                name=name,
                brand=_case_brand(name),
                form_factor=_case_form_factor(name),
                images=case_images,
                rrp_gbp=offer.current_delivered_price,
                is_transparent_panel=bool(re.search(r"glass|tempered|window", name, re.I)),
                status="active",
                notes=json.dumps({"supplier_offer": supplier}),
                updated_at=now,
            ))
        upserted += 1
    await db.flush()
    return upserted


async def process_submission_queue(process_interval_seconds: int = _EMPTY_QUEUE_POLL_SECONDS):
    """
    Run a persistent pool of workers that each continuously claim and
    process ONE pending submission at a time.

    Previous design: fetch a batch of up to 10 pending submissions, then
    asyncio.gather() over the whole batch before fetching more. That meant
    the processor couldn't pull in new work until EVERY submission in the
    current batch finished — one slow or hung submission (internal timeouts
    don't always fire cleanly, see reap_stale_processing) blocked the whole
    queue from making progress, even though 9 other workers might be idle.

    This design: each worker independently loops claim -> process -> claim
    again. A worker that finishes a fast submission immediately grabs the
    next one; a worker stuck on a slow submission doesn't block its
    siblings. Claiming is done atomically via SELECT ... FOR UPDATE SKIP
    LOCKED (see SubmissionQueueService.claim_next_pending) so workers never
    race for the same row.
    """
    logger.info("queue_processor.started", workers=_WORKER_COUNT)

    async with AsyncSessionLocal() as db:
        recovered = await SubmissionQueueService.recover_stuck_processing(db)
        if recovered:
            logger.warning("queue_processor.recovered_stuck_submissions", count=recovered)

    watchdog_stop = _start_stall_watchdog()
    try:
        workers = [
            asyncio.create_task(_worker_loop(worker_id, process_interval_seconds))
            for worker_id in range(_WORKER_COUNT)
        ]
        reaper = asyncio.create_task(_stale_reaper_loop())
        phase2_trigger = asyncio.create_task(_phase2_trigger_loop())
        await asyncio.gather(*workers, reaper, phase2_trigger, return_exceptions=True)
    finally:
        watchdog_stop.set()


async def _stale_reaper_loop() -> None:
    """Runs independently of the worker pool. A submission's own internal
    asyncio.wait_for(900s) around _submit_scan_body sometimes never fires
    (cancellation gets stuck/absorbed somewhere in the score_listing call
    chain), leaving it "processing" indefinitely and — under the old
    batch-gather design — permanently blocking new work behind it. The
    worker-pool design above already limits the blast radius to one worker,
    but this sweep still matters: it frees the DB row so the submission can
    be retried, and it means a fully wedged worker eventually gets new work
    once the row is reaped and the coroutine itself finally unwinds.

    Started here (inside process_submission_queue) rather than left for
    each caller to wire up separately, so every service that starts this
    worker pool — including app/gem_radar_standalone.py, which the browser
    extension talks to — gets this safety net automatically."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await SubmissionQueueService.reap_stale_processing(db, stale_after_seconds=1200)
                if result["retried"] or result["failed"]:
                    logger.warning("queue_processor.stale_reaped", **result)
        except Exception as exc:
            logger.warning("queue_processor.stale_reaper_error", error=str(exc))
        await asyncio.sleep(60)


_PHASE2_TRIGGER_POLL_SECONDS = 5


async def _phase2_trigger_loop() -> None:
    """Watches for FlipFlopXtension's /scan-sweep-complete signal
    (GemRadarSweepSignal, pending=True) and, once the submission_queue has
    genuinely drained (no pending/processing rows left — the signal alone
    doesn't guarantee every fire-and-forget submission from that sweep has
    landed yet), runs Phase 2 classification exactly once, then clears the
    flag. Runs independently of the worker pool so a busy queue never
    delays noticing the signal, it only delays acting on it."""
    from sqlalchemy import select
    from app.models.gem_radar_sweep_signal import GemRadarSweepSignal
    from app.gem_radar.phase2_runner import run_phase2_classification
    from app.gem_radar import pipeline_status

    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(GemRadarSweepSignal).where(GemRadarSweepSignal.id == 1))
                signal = result.scalar_one_or_none()

                if signal is not None and signal.pending:
                    stats = await SubmissionQueueService.get_queue_stats(db)
                    if stats["pending"] == 0 and stats["processing"] == 0:
                        logger.info("phase2_trigger.queue_drained_running_phase2")
                        phase2_result = await run_phase2_classification(db)
                        logger.info(
                            "phase2_trigger.phase2_complete",
                            total_cpk_tagged=phase2_result.total_cpk_tagged,
                            classified=phase2_result.classified_count,
                            unsettled=phase2_result.unsettled_count,
                        )
                        signal.pending = False
                        await db.commit()
                        # Phase 2 classifying the whole sweep is the natural
                        # end of a "run" -- archive the Current Scan Run
                        # panel's totals and clear it so the next sweep's
                        # progress starts from zero instead of blending with
                        # this one's leftover numbers.
                        pipeline_status.reset_run()
        except Exception as exc:
            logger.warning("phase2_trigger.error", error=str(exc))

        await asyncio.sleep(_PHASE2_TRIGGER_POLL_SECONDS)


async def _worker_loop(worker_id: int, poll_interval_seconds: int) -> None:
    """One persistent worker: claim a submission, process it, repeat.
    Sleeps briefly only when the queue is empty or concurrent search limit reached."""
    settings = get_settings()
    while True:
        try:
            # Check-and-reserve the concurrent search term slot atomically
            # under ONE lock hold, spanning the DB claim itself. Previously
            # the length check released the lock before claim_next_pending's
            # DB round-trip, and only re-acquired it afterward (inside
            # _process_single_submission) to add the claimed search_id. That
            # gap let multiple workers all see "under the limit" in the same
            # instant, each claim a DIFFERENT search_id, and each add
            # itself -- overshooting max_concurrent_search_terms (confirmed
            # in practice: 4 distinct search_ids completing submissions
            # concurrently with the limit set to 2). Holding the lock across
            # the claim serializes claiming across workers (fast: one row,
            # SKIP LOCKED) but leaves the actual heavy processing below fully
            # concurrent, since the lock is released before that starts.
            submission = None
            async with _active_search_lock:
                if len(_active_search_ids) < settings.max_concurrent_search_terms:
                    async with AsyncSessionLocal() as db:
                        # Only one page/vendor submission for a search term may
                        # score at once. Previously seven workers could all claim
                        # submissions for the same two active search IDs; the set
                        # still had length two, so the configured limit appeared
                        # satisfied while expensive CPK/pricing work contended
                        # seven ways and the queue stopped completing anything.
                        submission = await SubmissionQueueService.claim_next_pending(
                            db,
                            excluded_search_ids=set(_active_search_ids),
                        )
                    if submission is not None:
                        _active_search_ids.add(submission.search_id)

            if submission is None:
                await asyncio.sleep(poll_interval_seconds)
                continue

            await _process_single_submission(submission)

        except Exception as e:
            logger.exception("queue_processor.worker_error", worker=worker_id, error=str(e))
            # Avoid a tight error loop if something is systematically broken
            # (e.g. DB briefly unreachable) — back off before retrying.
            await asyncio.sleep(poll_interval_seconds)


async def _process_single_submission(submission):
    """Process a single queued submission, on its own DB session — async
    sessions aren't safe to share across concurrently-running coroutines,
    and this runs concurrently with whatever sibling submissions the other
    workers in the pool are independently processing.

    The caller (_worker_loop) has already reserved this search_id in
    _active_search_ids atomically alongside the DB claim -- this function
    only owns releasing that reservation in its finally block."""
    from app.api.gem_radar import _submit_scan_body
    from app.gem_radar import pipeline_status
    import time as _time

    logger.info(
        "queue_processor.processing_submission",
        submission_id=submission.id,
        search_id=submission.search_id,
        query=submission.query,
        n_listings=len(submission.listings_json),
        active_searches=len(_active_search_ids),
    )

    try:
        async with AsyncSessionLocal() as db:
            await SubmissionQueueService.mark_processing(db, submission.id)

            # Reconstruct the ScanSubmitRequest from queued data
            listings = [
                ExtractedListing(**listing) for listing in submission.listings_json
            ]
            payload = ScanSubmitRequest(
                searchRunId=submission.search_run_id,
                searchId=submission.search_id,
                query=submission.query,
                sourceUrl=submission.source_url,
                maxCandidatesForDeepResearch=submission.max_candidates_for_deep_research,
                listings=listings,
            )

            _t0 = _time.monotonic()
            try:
                result = await asyncio.wait_for(
                    _submit_scan_body(payload, db, _t0), timeout=_SUBMISSION_TIMEOUT_S
                )
                catalogue_upserted = await _sync_supplier_case_catalogue(db, payload)
                logger.info(
                    "queue_processor.submission_completed",
                    submission_id=submission.id,
                    ingested=result.ingested_count,
                    cpk_assigned=result.cpk_assigned_count,
                    catalogue_cases_upserted=catalogue_upserted,
                )
                await SubmissionQueueService.mark_completed(db, submission.id)
            except asyncio.TimeoutError:
                logger.warning(
                    "queue_processor.submission_timeout",
                    submission_id=submission.id,
                    timeout_s=_SUBMISSION_TIMEOUT_S,
                )
                # A hung _submit_scan_body can leave db's underlying connection
                # mid-transaction; roll back before reusing the session below,
                # same reasoning as the Exception branch.
                await db.rollback()
                await SubmissionQueueService.mark_failed(
                    db, submission.id, f"Submission exceeded {_SUBMISSION_TIMEOUT_S}s overall timeout", max_retries=5
                )
            except Exception as e:
                logger.exception(
                    "queue_processor.submission_failed",
                    submission_id=submission.id,
                    error=str(e),
                )
                # If the failure was itself a DB/connection error (e.g. the
                # underlying asyncpg connection dropped mid-query), db's session
                # is left with a pending invalid transaction. Reusing it as-is
                # for mark_failed raises PendingRollbackError, which swallows
                # the real failure and skips recording it/incrementing retry_count
                # entirely. Roll back first so mark_failed gets a usable session.
                await db.rollback()
                await SubmissionQueueService.mark_failed(db, submission.id, str(e), max_retries=5)
    finally:
        # Remove from active set once submission fully completes (success/fail/timeout)
        async with _active_search_lock:
            _active_search_ids.discard(submission.search_id)
        logger.info(
            "queue_processor.search_term_released",
            search_id=submission.search_id,
            active_searches_remaining=len(_active_search_ids),
        )
        pipeline_status.finish_submission(payload.search_id)
