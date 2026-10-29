from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.gem_radar.schema_guard import check_scan_schema
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.submission_queue import SubmissionQueue


def inspector_for_models():
    tables = {model.__tablename__: [{"name": c.name} for c in model.__table__.columns]
              for model in (GemRadarListingObservation, GemRadarScoredListing, SubmissionQueue)}
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.side_effect = lambda name: tables[name]
    return inspector, tables


def test_schema_guard_accepts_compatible_database():
    inspector, _ = inspector_for_models()
    with patch("app.gem_radar.schema_guard.inspect", return_value=inspector):
        check_scan_schema(Mock())


@pytest.mark.parametrize("column", ["image_urls", "commercial_source_evidence"])
def test_schema_guard_blocks_both_observed_failures(column):
    inspector, tables = inspector_for_models()
    name = GemRadarListingObservation.__tablename__
    tables[name] = [c for c in tables[name] if c["name"] != column]
    with patch("app.gem_radar.schema_guard.inspect", return_value=inspector):
        with pytest.raises(RuntimeError, match=f"{name}.{column}"):
            check_scan_schema(Mock())


@pytest.mark.asyncio
async def test_worker_does_not_claim_or_spend_retries_on_incompatible_schema():
    from app.workers.queue_processor import _worker_loop
    session = AsyncMock()
    session.__aenter__.return_value = session
    class StopLoop(Exception):
        pass
    claim = AsyncMock()
    with patch("app.workers.queue_processor.AsyncSessionLocal", return_value=session), \
         patch("app.gem_radar.schema_guard.require_scan_schema", AsyncMock(side_effect=RuntimeError("schema incompatible"))), \
         patch("app.workers.queue_processor.SubmissionQueueService.claim_next_pending", claim), \
         patch("app.workers.queue_processor.asyncio.sleep", AsyncMock(side_effect=StopLoop)):
        with pytest.raises(StopLoop):
            await _worker_loop(0, 5)
    claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_web_only_mode_rejects_scans_instead_of_silently_queueing():
    from fastapi import HTTPException
    from app.api.gem_radar import submit_scan_queued
    enqueue = AsyncMock()
    with patch("app.config.get_settings", return_value=Mock(web_only=True, external_gem_radar_worker_enabled=False)), \
         patch("app.api.gem_radar.SubmissionQueueService.enqueue_submission", enqueue):
        with pytest.raises(HTTPException) as error:
            await submit_scan_queued(Mock(), AsyncMock(), None)
    assert error.value.status_code == 503
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_spotlights_do_not_expire_at_twenty_four_hours():
    from datetime import datetime
    from app.api.gem_radar import get_gem_by_component
    fetch = AsyncMock(return_value={"title": "Active gem", "image_url": "https://example.com/photo.jpg"})
    with patch("app.api.gem_radar._fetch_best_gem_for_category", fetch):
        result = await get_gem_by_component(AsyncMock(), None)
    assert len(result) == 5
    assert all(call.args[2] == datetime.min for call in fetch.await_args_list)
