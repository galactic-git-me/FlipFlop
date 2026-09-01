from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timedelta
from ..models.submission_queue import SubmissionQueue
import json
import logging

logger = logging.getLogger(__name__)

class SubmissionQueueService:
    @staticmethod
    async def enqueue_submission(
        db: AsyncSession,
        search_run_id: str,
        search_id: str,
        query: str,
        source_url: str,
        max_candidates_for_deep_research: int,
        listings: list,
    ) -> SubmissionQueue:
        """Enqueue a submission for async processing"""
        submission = SubmissionQueue(
            search_run_id=search_run_id,
            search_id=search_id,
            query=query,
            source_url=source_url,
            max_candidates_for_deep_research=max_candidates_for_deep_research,
            listings_json=listings,
            status="pending",
            first_attempt_at=datetime.utcnow(),
            last_attempt_at=datetime.utcnow(),
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)
        logger.info(f"Enqueued submission {submission.id} for {query}")
        return submission

    @staticmethod
    async def get_pending_submissions(db: AsyncSession, limit: int = 10) -> list[SubmissionQueue]:
        """Get pending submissions, healthiest first. Strict created_at
        ordering meant a submission that hangs and gets reset to "pending"
        (by mark_failed's retry or reap_stale_processing) keeps its
        original, now very old created_at — so it jumps straight back to
        the front of every future batch, permanently crowding out fresh
        submissions behind it for as long as it keeps hanging and retrying.
        Observed in production: 7 chronically-hanging submissions occupied
        7 of 10 concurrent slots on every single batch, starving hundreds
        of healthy pending submissions of any processing time at all.
        Ordering by retry_count first means a submission that has already
        failed gets deprioritized below fresh ones, not re-prioritized
        above them."""
        stmt = (
            select(SubmissionQueue)
            .where(SubmissionQueue.status == "pending")
            .order_by(SubmissionQueue.retry_count, SubmissionQueue.created_at)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def claim_next_pending(
        db: AsyncSession,
        excluded_search_ids: set[str] | None = None,
    ) -> SubmissionQueue | None:
        """Atomically claim and return ONE pending submission, or None if the
        queue is empty. Uses SELECT ... FOR UPDATE SKIP LOCKED so multiple
        concurrent workers can each claim a different row safely without
        two workers ever picking up the same submission.

        This replaces the old pattern of get_pending_submissions(limit=10)
        + asyncio.gather() over the whole batch, which meant the processor
        loop couldn't fetch new work until every submission in that batch
        finished — one slow/hung submission blocked the entire queue from
        making progress. With one-at-a-time atomic claiming, each worker in
        the pool grabs new work the instant it's free, independent of its
        siblings."""
        stmt = (
            select(SubmissionQueue)
            .where(SubmissionQueue.status == "pending")
            .order_by(SubmissionQueue.retry_count, SubmissionQueue.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if excluded_search_ids:
            stmt = stmt.where(SubmissionQueue.search_id.not_in(excluded_search_ids))
        result = await db.execute(stmt)
        submission = result.scalar_one_or_none()
        if submission is None:
            return None
        submission.status = "processing"
        submission.last_attempt_at = datetime.utcnow()
        await db.commit()
        await db.refresh(submission)
        return submission

    @staticmethod
    async def mark_processing(db: AsyncSession, submission_id: int) -> SubmissionQueue:
        """Mark submission as being processed"""
        stmt = select(SubmissionQueue).where(SubmissionQueue.id == submission_id)
        result = await db.execute(stmt)
        submission = result.scalar_one()
        submission.status = "processing"
        submission.last_attempt_at = datetime.utcnow()
        await db.commit()
        await db.refresh(submission)
        return submission

    @staticmethod
    async def mark_completed(db: AsyncSession, submission_id: int) -> SubmissionQueue:
        """Mark submission as successfully completed"""
        stmt = select(SubmissionQueue).where(SubmissionQueue.id == submission_id)
        result = await db.execute(stmt)
        submission = result.scalar_one()
        submission.status = "completed"
        submission.completed_at = datetime.utcnow()
        submission.last_error = None
        # The extracted listings are only needed while the job is pending or
        # processing. Keeping every completed payload duplicated hundreds of
        # megabytes of JSON into the live DB and every subsequent backup.
        submission.listings_json = []
        await db.commit()
        await db.refresh(submission)
        logger.info(f"Completed submission {submission_id}")
        return submission

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        submission_id: int,
        error_message: str,
        max_retries: int = 5,
    ) -> SubmissionQueue:
        """Mark submission as failed and retry if under limit"""
        stmt = select(SubmissionQueue).where(SubmissionQueue.id == submission_id)
        result = await db.execute(stmt)
        submission = result.scalar_one()

        submission.retry_count += 1
        submission.last_error = error_message
        submission.last_attempt_at = datetime.utcnow()

        if submission.retry_count >= max_retries:
            submission.status = "failed"
            logger.error(
                f"Submission {submission_id} failed after {max_retries} retries: {error_message}"
            )
        else:
            submission.status = "pending"
            logger.warning(
                f"Submission {submission_id} failed (attempt {submission.retry_count}/{max_retries}): {error_message}"
            )

    @staticmethod
    async def reap_stale_processing(
        db: AsyncSession, stale_after_seconds: int = 1200, max_retries: int = 5
    ) -> dict:
        """External safety net, run periodically (not just once at startup
        like recover_stuck_processing). Observed in production: a
        submission's internal asyncio.wait_for(timeout=900s) around
        _submit_scan_body sometimes never actually fires — the coroutine
        stays "processing" for 25-30+ minutes with retry_count never
        incrementing, meaning the cancellation got stuck or silently
        absorbed somewhere deep in the score_listing call chain rather than
        propagating. Root cause not fully isolated; this bulk sweep is the
        pragmatic fix so one wedged submission can't permanently occupy a
        queue slot regardless of why the internal timeout didn't fire —
        same philosophy as the idle_in_transaction_session_timeout DB-level
        backstop for the connection-leak issue."""
        from sqlalchemy import update

        cutoff = datetime.utcnow() - timedelta(seconds=stale_after_seconds)
        result = await db.execute(
            select(SubmissionQueue.id, SubmissionQueue.retry_count).where(
                SubmissionQueue.status == "processing",
                SubmissionQueue.last_attempt_at < cutoff,
            )
        )
        rows = result.all()
        retried_ids = [rid for rid, rc in rows if rc + 1 < max_retries]
        failed_ids = [rid for rid, rc in rows if rc + 1 >= max_retries]

        if retried_ids:
            await db.execute(
                update(SubmissionQueue)
                .where(SubmissionQueue.id.in_(retried_ids))
                .values(
                    status="pending",
                    retry_count=SubmissionQueue.retry_count + 1,
                    last_error=f"Reaped: stuck in 'processing' past {stale_after_seconds}s stale threshold (internal timeout never fired)",
                    last_attempt_at=datetime.utcnow(),
                )
            )
        if failed_ids:
            await db.execute(
                update(SubmissionQueue)
                .where(SubmissionQueue.id.in_(failed_ids))
                .values(
                    status="failed",
                    retry_count=SubmissionQueue.retry_count + 1,
                    last_error=f"Reaped: stuck in 'processing' past {stale_after_seconds}s stale threshold, exceeded max_retries",
                    last_attempt_at=datetime.utcnow(),
                )
            )
        if retried_ids or failed_ids:
            await db.commit()
            logger.warning(
                f"reap_stale_processing: retried={len(retried_ids)} failed={len(failed_ids)} ids_retried={retried_ids} ids_failed={failed_ids}"
            )
        return {"retried": len(retried_ids), "failed": len(failed_ids)}

    @staticmethod
    async def get_submission(db: AsyncSession, submission_id: int) -> SubmissionQueue | None:
        """Get a specific submission by ID"""
        stmt = select(SubmissionQueue).where(SubmissionQueue.id == submission_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def recover_stuck_processing(db: AsyncSession) -> int:
        """Reset any rows left in "processing" back to "pending".

        get_pending_submissions() only ever selects status == "pending", so a
        row marked "processing" whose worker coroutine never reached
        mark_completed/mark_failed (backend killed/restarted mid-scoring,
        which happens a lot in dev) is orphaned forever otherwise — it just
        sits there claiming a slot in the stats without ever being retried.
        Call this once at worker startup, before the loop begins picking up
        new work, so anything abandoned by the previous process run gets
        another attempt.
        """
        from sqlalchemy import update

        result = await db.execute(
            update(SubmissionQueue)
            .where(SubmissionQueue.status == "processing")
            .values(status="pending")
            .returning(SubmissionQueue.id)
        )
        recovered_ids = result.scalars().all()
        await db.commit()
        if recovered_ids:
            logger.warning(f"Recovered {len(recovered_ids)} stuck 'processing' submissions: {recovered_ids}")
        return len(recovered_ids)

    @staticmethod
    async def get_queue_stats(db: AsyncSession) -> dict:
        """Get queue statistics.

        Counts only (via SQL COUNT, not fetching+materializing full rows) —
        completed/failed submissions are never deleted, so loading every row
        just to call len() on it gets slower forever as history accumulates,
        including pulling each row's full listings_json blob over the wire
        for no reason.
        """
        result = await db.execute(
            select(SubmissionQueue.status, func.count()).group_by(SubmissionQueue.status)
        )
        counts = dict(result.all())
        return {
            "pending": counts.get("pending", 0),
            "processing": counts.get("processing", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
        }

    @staticmethod
    async def get_live_items(db: AsyncSession, limit: int = 100) -> list[SubmissionQueue]:
        """Return lightweight metadata for work still visible to operators."""
        result = await db.execute(
            select(SubmissionQueue)
            .where(SubmissionQueue.status.in_(("pending", "processing")))
            .order_by(SubmissionQueue.status.desc(), SubmissionQueue.last_attempt_at)
            .limit(limit)
        )
        return list(result.scalars().all())
