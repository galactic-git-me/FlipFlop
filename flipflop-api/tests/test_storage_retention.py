from unittest.mock import AsyncMock, Mock

import pytest

from app.models.submission_queue import SubmissionQueue
from app.services.submission_queue_service import SubmissionQueueService
from app.workers.database_cleaner import RETENTION


@pytest.mark.asyncio
async def test_mark_completed_releases_submission_payload():
    submission = SubmissionQueue(
        id=42,
        search_run_id="run",
        search_id="search",
        query="gpu",
        source_url="https://example.test",
        listings_json=[{"title": "large payload"}],
    )
    result = Mock()
    result.scalar_one.return_value = submission
    db = AsyncMock()
    db.execute.return_value = result

    completed = await SubmissionQueueService.mark_completed(db, submission.id)

    assert completed.status == "completed"
    assert completed.listings_json == []
    assert completed.completed_at is not None
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(submission)


@pytest.mark.asyncio
async def test_mark_failed_persists_retry_state():
    submission = SubmissionQueue(
        id=43,
        search_run_id="run",
        search_id="search",
        query="gpu",
        source_url="https://example.test",
        listings_json=[],
        retry_count=0,
    )
    result = Mock()
    result.scalar_one.return_value = submission
    db = AsyncMock()
    db.execute.return_value = result

    failed = await SubmissionQueueService.mark_failed(db, submission.id, "network error")

    assert failed.status == "pending"
    assert failed.retry_count == 1
    assert failed.last_error == "network error"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(submission)


def test_high_volume_retention_is_bounded():
    retention = {table: interval for table, _column, interval in RETENTION}

    assert retention["gem_radar_decision_events"] == "72 hours"
    assert retention["gem_radar_listing_demand_history"] == "48 hours"
    assert retention["submission_queue"] == "24 hours"
