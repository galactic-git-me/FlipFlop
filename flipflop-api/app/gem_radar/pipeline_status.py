"""In-memory, ephemeral tracker for what Phase 1 ingestion is doing right
now — powers the "Current Scan Run" panel on the Sourcing Dashboard's Stats
tab. Deliberately NOT persisted to the DB: this is real-time operational
state, not historical data, and it resets on every API restart along with
the in-flight work it describes.

Tracked per search_id (a search TERM), not per submission. The extension
submits one queued backend request per page per marketplace for a single
search term (see FlipFlopXtension's scan-orchestrator.ts submitPage()), so
several submissions are normally in flight for the same search_id at once.
This used to track per-submission (keyed by search_run_id) and summed
across whichever submissions happened to still be active at snapshot time
— but a submission disappearing the instant it finished (while a sibling
submission for the same search was still mid-flight) made the summed total
visibly drop and rise again, reading as random noise rather than
progress. Accumulating onto one running total per search_id for the whole
run, and only clearing it at an explicit run boundary (reset_run(), called
once Phase 2 finishes classifying the whole sweep — see queue_processor.py's
_phase2_trigger_loop), fixes that: every number here only ever goes up
until the run genuinely ends.

Safe without locks: FastAPI/uvicorn runs a single event loop, so dict
mutations here never interleave with each other the way they could under
real threading.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from sqlalchemy import select

# Scoring concurrency slot usage — incremented/decremented around the
# semaphore acquire in the (now-dead, zero callers) _score_listings_concurrently.
# Kept only so that dead function doesn't reference undefined names.
_scoring_slots_in_use = 0


def scoring_slot_acquired() -> None:
    global _scoring_slots_in_use
    _scoring_slots_in_use += 1


def scoring_slot_released() -> None:
    global _scoring_slots_in_use
    _scoring_slots_in_use = max(0, _scoring_slots_in_use - 1)


def scoring_slots_in_use() -> int:
    return _scoring_slots_in_use


@dataclass
class SearchRunState:
    search_id: str
    query: str
    started_at: float = field(default_factory=time.monotonic)
    # How many submissions (pages/marketplaces) for this search are
    # currently mid-flight — shown as context ("3 pages in flight") on the
    # dashboard card, not itself a progress metric. Derived from
    # active_submission_ids' length whenever submission ids are used (see
    # start_submission), so a retried submission_id doesn't inflate it.
    active_submissions: int = 0
    # Submission ids (SubmissionQueue.id) currently believed in-flight. A
    # submission that gets reaped/retried (see reap_stale_processing) keeps
    # the SAME id across attempts, so tracking by id — not a plain counter —
    # means a stuck original attempt that eventually finishes late can't
    # double-decrement, and a retried attempt re-adding the same id is a
    # no-op rather than another +1.
    active_submission_ids: set[object] = field(default_factory=set)
    total_listings: int = 0
    # submission_ids already folded into total_listings — see start_submission.
    # A retried submission (same id, reprocessed after a reap/failure) must
    # not add its listing count onto the total a second time: that's what
    # made the "processed" gauge cap out well below 100%, since ingested/
    # processed counts only ever advance once per submission while the
    # naive total kept growing by one full re-add per retry.
    counted_submission_ids: set[object] = field(default_factory=set)
    # Track search_run_ids that belong to THIS run so we can filter by them
    # in the database queries (avoid mixing in observations from previous runs).
    search_run_ids: set[str] = field(default_factory=set)
    # Listings actually recorded as a new observation (a still-live,
    # price-unchanged repeat sighting is touched but doesn't count here —
    # see _submit_scan_body's price_unchanged branch).
    ingested_count: int = 0
    # Of those ingested, how many are brand-new (not cross-run duplicates).
    # Used to display "X ingested (Y new)" in the dashboard.
    ingested_new_count: int = 0
    # Of those ingested, how many got a Canonical Product Key — either a
    # fresh LLM extraction or a lookup of one already assigned. Lags behind
    # ingested_count in real time since CPK extraction is the slow step (an
    # LLM call per genuinely-new listing), which is exactly the granularity
    # the dashboard needs to show visible progress.
    cpk_assigned_count: int = 0
    # New listings whose CPK extraction was attempted and gave up (LLM
    # call raised, timed out, or returned no usable product data). These
    # will never increment cpk_assigned_count this run, so is_complete
    # counts them separately rather than waiting on a count that can
    # never be reached — without this, a single Ollama hiccup mid-run
    # left the dashboard card spinning forever.
    cpk_failed_count: int = 0
    classified_count: int = 0
    excluded_auction_count: int = 0
    # Ingested-listing count per marketplace (ebay/vinted/overclockers/temu/
    # amazon — see app.gem_radar.marketplace.infer_marketplace). A whole
    # submission is one page of one marketplace (see FlipFlopXtension's
    # submitPage()), so every listing in a given submission shares the same
    # vendor.
    by_vendor: dict[str, int] = field(default_factory=dict)
    # listing_ids that got a CPK, for the "market priced" gauge — a listing
    # counts as priced once its CPK has settled (2+ contributing listings,
    # see cpk_market.py), which can happen well after THIS listing was
    # ingested (when a later listing shares its CPK), so it can't be a
    # simple incremental counter — snapshot() re-checks this list against
    # gem_radar_cpk_market_price on every call.
    listing_ids: list[str] = field(default_factory=list)
    # Once a listing_id is confirmed priced/classified, that fact is final —
    # a settled market price or an assigned classification is never revoked.
    # snapshot() is polled every ~1s for the run's whole life (see the
    # Sourcing tab's poll), and listing_ids only grows, so without this cache
    # every poll re-queried the DB for every listing this run has EVER seen,
    # not just the ones still unresolved -- making each poll more expensive
    # than the last as a run goes on. These let snapshot() only ask the DB
    # about listing_ids it hasn't already gotten a definitive answer for.
    resolved_priced_ids: set[str] = field(default_factory=set)
    resolved_classification: dict[str, tuple[str, float]] = field(default_factory=dict)

    def elapsed_s(self) -> float:
        return round(time.monotonic() - self.started_at, 1)


# Search terms with at least one submission processed since the last
# reset_run(), keyed by search_id.
_active: dict[str, SearchRunState] = {}

# Search terms archived by the last reset_run() — gives the dashboard a
# sense of the previous run's throughput even though nothing here is
# persisted to the DB.
_MAX_HISTORY = 20
_history: deque[dict] = deque(maxlen=_MAX_HISTORY)


def start_submission(
    search_id: str,
    query: str,
    total_listings: int,
    search_run_id: str | None = None,
    submission_id: object | None = None,
) -> None:
    """Called once per submission attempt, when it begins ingesting. Adds
    this submission's listing count onto the search's running total rather
    than overwriting it — a search_id normally receives many submissions
    (one per page/marketplace) over the course of a run.

    submission_id (the queue row's stable id) is what makes this idempotent
    across retries: reap_stale_processing/mark_failed can send the SAME
    submission through this function multiple times (same id, new attempt)
    when the first attempt hung or errored. Without keying on it, every
    retry re-added that submission's listing count to total_listings while
    ingested/processed counts only ever advance once — the exact mechanism
    behind the "processed" gauge capping out well short of 100%. Callers
    that don't have a submission_id (the unqueued /scans path) fall back to
    the old always-add behaviour."""
    state = _active.get(search_id)
    if state is None:
        state = SearchRunState(search_id=search_id, query=query)
        _active[search_id] = state
    state.query = query
    if submission_id is None:
        state.total_listings += total_listings
        state.active_submissions += 1
    else:
        if submission_id not in state.counted_submission_ids:
            state.counted_submission_ids.add(submission_id)
            state.total_listings += total_listings
        state.active_submission_ids.add(submission_id)
        state.active_submissions = len(state.active_submission_ids)
    if search_run_id:
        state.search_run_ids.add(search_run_id)


def increment(search_id: str, **deltas: int) -> None:
    state = _active.get(search_id)
    if state is None:
        return
    for key, delta in deltas.items():
        setattr(state, key, getattr(state, key) + delta)


def increment_vendor(search_id: str, vendor: str, count: int) -> None:
    state = _active.get(search_id)
    if state is None:
        return
    state.by_vendor[vendor] = state.by_vendor.get(vendor, 0) + count


def increment_ingested_new(search_id: str) -> None:
    """Increment the count of NEW (non-duplicate) ingested listings."""
    state = _active.get(search_id)
    if state is None:
        return
    state.ingested_new_count += 1


def track_listing(search_id: str, listing_id: str) -> None:
    """Records a CPK-assigned listing so snapshot() can later check whether
    its CPK has settled into a market price."""
    state = _active.get(search_id)
    if state is None:
        return
    state.listing_ids.append(listing_id)


def finish_submission(search_id: str, submission_id: object | None = None) -> None:
    """Called once a submission attempt completes (success, failure, or
    timeout) — only decrements the in-flight counter, never removes the
    search_id from _active, so its accumulated progress survives until
    reset_run().

    With submission_id: discards it from active_submission_ids (a no-op if
    it was already removed, e.g. a stuck original attempt finally returning
    long after its retry already finished) rather than blindly decrementing
    a counter, which could otherwise go negative or under-count when the
    same submission is in flight twice (original hung attempt + its retry)."""
    state = _active.get(search_id)
    if state is None:
        return
    if submission_id is None:
        state.active_submissions = max(0, state.active_submissions - 1)
    else:
        state.active_submission_ids.discard(submission_id)
        state.active_submissions = len(state.active_submission_ids)


def reset_run() -> None:
    """Archives every search's final tally into history and clears the
    board. Called once Phase 2 has classified the whole sweep (see
    queue_processor.py's _phase2_trigger_loop), marking the natural end of
    a run so the next sweep's progress starts from zero instead of visually
    blending with leftover totals from the previous one."""
    for state in _active.values():
        _history.appendleft(
            {
                "query": state.query,
                "total_listings": state.total_listings,
                "ingested_count": state.ingested_count,
                "classified_count": state.classified_count,
                "elapsed_s": state.elapsed_s(),
                "failed": False,
            }
        )
    _active.clear()


async def _vendor_breakdown_from_db(db, search_id_run_ids: list[tuple[str, set[str]]]) -> dict[str, dict[str, int]]:
    """Live vendor-contribution counts per search_id, read from the DB
    rather than the in-memory by_vendor counter. by_vendor only reflects
    submissions this process has itself handled since it started — restart
    the backend mid-run (this session had several) and its memory of
    already-completed vendor contributions is gone, even though the actual
    observations are safely sitting in the DB.

    Only counts observations from search_run_ids that belong to THIS run
    (tracked in the search_run_ids set per SearchRunState) to avoid mixing
    in observations from previous runs that haven't been cleared yet."""
    from sqlalchemy import text

    if not search_id_run_ids:
        return {}

    # Flatten all run_ids from all active searches
    all_run_ids = []
    run_id_to_search_id: dict[str, str] = {}
    search_ids_needing_fallback = []

    for search_id, run_ids in search_id_run_ids:
        if run_ids:
            all_run_ids.extend(run_ids)
            for run_id in run_ids:
                run_id_to_search_id[run_id] = search_id
        else:
            # No run_ids tracked yet for this search, will need fallback query
            search_ids_needing_fallback.append(search_id)

    breakdown: dict[str, dict[str, int]] = {search_id: {} for search_id, _ in search_id_run_ids}

    obs_rows = await db.execute(
        text(
            """
            SELECT search_run_id, source, COUNT(DISTINCT listing_id)
            FROM gem_radar_listing_observations
            WHERE search_run_id = ANY(:run_ids)
            GROUP BY search_run_id, source
            """
        ),
        {"run_ids": all_run_ids},
    )

    breakdown: dict[str, dict[str, int]] = {search_id: {} for search_id, _ in search_id_run_ids}
    for run_id, source, count in obs_rows.fetchall():
        search_id = run_id_to_search_id.get(run_id)
        if search_id is None:
            continue
        vendor = source or "unknown"
        breakdown[search_id][vendor] = breakdown[search_id].get(vendor, 0) + count
    return breakdown


async def snapshot(db) -> dict:
    """Everything the dashboard's "Current Scan Run" panel needs in one call.
    Takes a DB session to look up which CPK-assigned listings now have a
    settled market price and classification — that can only be answered by the DB.

    Every figure returned here is scoped to THIS run's listing_ids (the
    _active state accumulated since the last reset_run()) -- never to the
    whole DB. Phase 2 (see phase2_runner.py) re-classifies EVERY CPK-tagged
    listing in the entire database on every pass under one constant,
    never-changing search_run_id ("cpk-phase2-classify"), so anything that
    queried gem_radar_scored_listings by that run_id (as the dashboard used
    to, via /scored-listings-latest-run) was actually reading whole-database
    totals mislabeled as "this run" -- e.g. showing thousands of SUPER_GEMs
    for a run that had only ingested a few hundred listings. Intersecting
    every query below against all_listing_ids is what actually scopes it."""
    from sqlalchemy import text
    from app.gem_radar.cpk_market import MIN_LISTINGS_FOR_SETTLED_PRICE

    states = sorted(_active.values(), key=lambda s: s.started_at)

    configured_vendors_by_search: dict[str, list[str]] = {}

    all_listing_ids = [lid for s in states for lid in s.listing_ids]
    priced_listing_ids: set[str] = set()
    classified_listing_ids: set[str] = set()
    classification_counts: dict[str, int] = {}
    classification_avg_score: dict[str, float] = {}
    bin_prices_count = 0
    sold_prices_count = 0

    # Which listing_id belongs to which state, so a freshly-resolved id can
    # be written back into that state's cache below.
    owning_state_by_listing_id: dict[str, "SearchRunState"] = {}
    for s in states:
        for lid in s.listing_ids:
            owning_state_by_listing_id[lid] = s
            if lid in s.resolved_priced_ids:
                priced_listing_ids.add(lid)
            cached_classification = s.resolved_classification.get(lid)
            if cached_classification is not None:
                classified_listing_ids.add(lid)

    unresolved_priced_ids = [
        lid for s in states for lid in s.listing_ids if lid not in s.resolved_priced_ids
    ]
    unresolved_classified_ids = [
        lid for s in states for lid in s.listing_ids if lid not in s.resolved_classification
    ]

    if unresolved_priced_ids:
        # Get listings with market price (non-null median price). Threshold
        # matches cpk_market.py's actual settlement rule exactly (imported,
        # not hardcoded) -- a stale hardcoded ">= 2" here previously
        # undercounted "priced" listings after that threshold was lowered
        # to 1, making M Prices lag CPK-assigned for no real reason.
        #
        # Only asks about listing_ids not already confirmed priced in a
        # past snapshot() call -- see resolved_priced_ids on SearchRunState.
        result = await db.execute(
            text(
                """
                SELECT lc.listing_id
                FROM gem_radar_listing_cpk lc
                JOIN gem_radar_cpk_market_price mp ON lc.cpk = mp.cpk
                WHERE lc.listing_id = ANY(:ids) AND mp.listing_count >= :min_listings
                AND mp.median_price IS NOT NULL
                """
            ),
            {"ids": unresolved_priced_ids, "min_listings": MIN_LISTINGS_FOR_SETTLED_PRICE},
        )
        for (lid,) in result.fetchall():
            priced_listing_ids.add(lid)
            owning_state_by_listing_id[lid].resolved_priced_ids.add(lid)

    if unresolved_classified_ids:
        # Get listings with classification (GEM, SUPER_GEM, etc.), plus a
        # breakdown by classification + avg deal_score per class -- this
        # replaces the frontend's earlier use of /scored-listings-latest-run
        # (whole-DB, mislabeled as "this run") for the SUPER GEM/GEM/Avg
        # Gem/Avg Super Gem header stats.
        #
        # Only asks about listing_ids with no cached classification yet --
        # see resolved_classification on SearchRunState.
        result = await db.execute(
            text(
                """
                SELECT listing_id, classification, deal_score
                FROM gem_radar_scored_listings
                WHERE listing_id = ANY(:ids) AND classification IS NOT NULL
                """
            ),
            {"ids": unresolved_classified_ids},
        )
        for lid, classification, deal_score in result.fetchall():
            classified_listing_ids.add(lid)
            owning_state_by_listing_id[lid].resolved_classification[lid] = (classification, deal_score)

    # classification_counts / classification_avg_score are derived fresh
    # each call from the (now mostly-cached) resolved_classification maps --
    # cheap, pure-Python bookkeeping, not a DB round-trip.
    scores_by_class: dict[str, list[float]] = {}
    for s in states:
        for classification, deal_score in s.resolved_classification.values():
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
            scores_by_class.setdefault(classification, []).append(deal_score)
    classification_avg_score = {
        cls: round(sum(scores) / len(scores), 1) for cls, scores in scores_by_class.items()
    }

    if all_listing_ids:
        # BIN prices: this run's listings that have their own recorded BIN
        # price (one row per listing_id in gem_radar_cpk_listing_price).
        # Sold prices: sold comps recorded against any CPK that appears
        # among this run's listings -- sold observations are comps for a
        # CPK, not rows keyed by this run's own listing_ids, so they're
        # scoped via the CPK rather than a direct listing_id match.
        price_counts_result = await db.execute(
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
            {"ids": all_listing_ids},
        )
        price_counts_row = price_counts_result.fetchone()
        bin_prices_count = price_counts_row[0] if price_counts_row else 0
        sold_prices_count = price_counts_row[1] if price_counts_row else 0

    active_scans = []
    for s in states:
        priced_count = sum(1 for lid in s.listing_ids if lid in priced_listing_ids)
        classified_count = sum(1 for lid in s.listing_ids if lid in classified_listing_ids)

        # ``listing_ids`` only fills after CPK assignment. It is therefore a
        # progress numerator, never a valid denominator: using it here made the
        # CPK gauge show 100% while the remaining submitted listings waited.
        # Auctions are excluded before ingestion and should not hold a fixed-price
        # scan short of completion.
        actual_total_listings = max(
            s.total_listings - s.excluded_auction_count,
            s.ingested_count,
            0,
        )

        # By_vendor: aggregate vendor counts from the listing_ids we've tracked,
        # counting observations per source. This gives us the true vendor breakdown
        # for only the listings THIS run has processed.
        if all_listing_ids and s.listing_ids:
            # Count observations per vendor for only THIS search's listing_ids
            vendor_obs_result = await db.execute(
                text(
                    """
                    SELECT source, COUNT(DISTINCT listing_id) as cnt
                    FROM gem_radar_listing_observations
                    WHERE listing_id = ANY(:ids)
                    GROUP BY source
                    """
                ),
                {"ids": s.listing_ids},
            )
            by_vendor = {}
            for source, cnt in vendor_obs_result.fetchall():
                by_vendor[source or "unknown"] = cnt
        else:
            by_vendor = dict(s.by_vendor)

        # Processed: listings that completed full pipeline (ingested → CPK → market/classified)
        processed_count = sum(1 for lid in s.listing_ids if lid in priced_listing_ids or lid in classified_listing_ids)
        processed_pct = round(
            (processed_count / actual_total_listings * 100) if actual_total_listings else 0,
            1,
        )

        # Complete only once:
        # 1. No submissions still in flight
        # 2. At least one listing was encountered
        # 3. CPK assignment has caught up with ingested count (not total, which
        #    includes cross-run dupes that already have CPKs from prior runs).
        #    cpk_failed_count covers listings that were attempted and gave up
        #    (Ollama error, low-confidence extraction) -- without adding those
        #    in, a single failed extraction made cpk_assigned_count
        #    permanently unreachable and the card spun forever.
        # Classification and market-price enrichment are Phase 2 outcomes,
        # not prerequisites for declaring Phase 1 finished. Some legitimate
        # terminal outcomes (insufficient comparable evidence, identity
        # pending, or an intentionally ineligible listing) never acquire a
        # settled price. Requiring every listing to appear in one of those
        # two tables left otherwise-finished cards spinning at 99.x%.
        is_complete = (
            s.active_submissions == 0
            and s.ingested_count > 0
            and (s.cpk_assigned_count + s.cpk_failed_count) >= s.ingested_count
        )

        active_scans.append(
            {
                "searchId": s.search_id,
                "query": s.query,
                "elapsedSeconds": s.elapsed_s(),
                "activeSubmissions": s.active_submissions,
                "totalListings": actual_total_listings,
                "ingestedCount": s.ingested_count,
                "ingestedNewCount": s.ingested_new_count,
                "cpkAssignedCount": s.cpk_assigned_count,
                # DB-derived (classified_count local var, computed above from
                # a live query against listing_ids) — not the raw in-memory
                # counter, which only ever incremented for cross-run
                # duplicates that ALREADY had a score before this run started.
                # It never reflected listings Phase 2 scores as a result of
                # THIS run, so it permanently undercounted.
                "classifiedCount": classified_count,
                "marketPricedCount": priced_count,
                "processedPercent": processed_pct,
                "excludedAuctionCount": s.excluded_auction_count,
                "byVendor": by_vendor,
                "configuredVendors": configured_vendors_by_search.get(s.search_id),
                "isComplete": is_complete,
            }
        )

    return {
        "activeScans": active_scans,
        "recentHistory": list(_history),
        "binPricesCount": bin_prices_count,
        "soldPricesCount": sold_prices_count,
        # Classification breakdown scoped to THIS run's listing_ids only
        # (see snapshot()'s docstring) -- superGemCount/gemCount/avg scores
        # replace the frontend's old whole-DB-derived numbers.
        "superGemCount": classification_counts.get("SUPER_GEM", 0),
        "gemCount": classification_counts.get("GEM", 0),
        "avgGemScore": classification_avg_score.get("GEM", 0.0),
        "avgSuperGemScore": classification_avg_score.get("SUPER_GEM", 0.0),
        "totalsAcrossActive": {
            "listings": sum(s["totalListings"] for s in active_scans),
            "ingestedCount": sum(s["ingestedCount"] for s in active_scans),
            "cpkAssignedCount": sum(s["cpkAssignedCount"] for s in active_scans),
            "classifiedInternalCount": sum(s["classifiedCount"] for s in active_scans),
            "marketPricedCount": sum(s["marketPricedCount"] for s in active_scans),
            "processedCount": sum(s["processedPercent"] for s in active_scans),
        },
    }
