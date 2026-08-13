"""
Functional test for the relist/recreate + deferred-publish scheduler jobs
(Algorithm Playbook rows 1, 2, 3, 5, 6, 9, 36, 46). Runs against a real
SQLite DB (not the FastAPI dependency-override pattern used elsewhere) since
these jobs open their own session via app.database.AsyncSessionLocal, the
same way they do in production under APScheduler.
"""
import uuid
import pytest
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.listing import Listing
from app.workers.recreate_cycle import run_deferred_publish_job, run_recreate_cycle_job
from app.workers.markdown_event import run_markdown_event_scan_job


@pytest.fixture(autouse=True)
async def _clean_tables():
    async with AsyncSessionLocal() as db:
        await db.execute(Flip.__table__.delete())
        await db.execute(Listing.__table__.delete())
        await db.commit()
    yield


async def _make_listing(db) -> int:
    listing = Listing(
        external_id=f"rc-test-{uuid.uuid4()}", source_id=1, title="Gaming PC i7 RTX 4070",
        price=800.0, url="https://example.com/l/1", source_name="eBay UK",
        cpu="i7-13700K", gpu="RTX 4070", estimated_resale=1100.0, estimated_profit=250.0,
    )
    db.add(listing)
    await db.flush()
    return listing.id


async def test_deferred_publish_skips_without_seller_token_but_still_reschedules_check():
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id, stage=FlipStage.ready_for_sale,
            total_cost=800.0, listing_price=900.0,
            deferred_publish_at=datetime.utcnow() - timedelta(minutes=5),
            traffic_band="monday",
        )
        db.add(flip)
        await db.commit()
        flip_id = flip.id

    result = await run_deferred_publish_job()
    assert result["published"] == 0
    assert result["skipped_no_token"] == 1

    async with AsyncSessionLocal() as db:
        refreshed = await db.get(Flip, flip_id)
        assert refreshed.listed_at is None  # not marked listed since it never actually posted


async def test_recreate_cycle_advances_state_without_seller_token():
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id, stage=FlipStage.ready_for_sale,
            total_cost=800.0, listing_price=1000.0,
            listed_at=datetime.utcnow() - timedelta(days=8),
            next_recreate_at=datetime.utcnow() - timedelta(hours=1),
            traffic_band="monday", recreate_price_step_pct=0.05,
            generated_images_urls=["a.png", "b.png", "c.png"],
        )
        db.add(flip)
        await db.commit()
        flip_id = flip.id

    result = await run_recreate_cycle_job()
    assert result["recreated"] == 1
    assert result["errors"] == 0

    async with AsyncSessionLocal() as db:
        refreshed = await db.get(Flip, flip_id)
        assert refreshed.recreate_cycle_count == 1
        assert refreshed.last_recreate_at is not None
        assert refreshed.next_recreate_at > datetime.utcnow()
        # Price stepped down from 1000 (never below floor = cost + 10%)
        assert refreshed.listing_price < 1000.0
        assert refreshed.listing_price >= refreshed.price_floor
        # Image rotated (main image swapped, not cropped)
        assert refreshed.generated_images_urls[0] == "b.png"


async def test_recreate_cycle_ignores_flips_not_due():
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id, stage=FlipStage.ready_for_sale,
            total_cost=800.0, listing_price=1000.0,
            listed_at=datetime.utcnow() - timedelta(days=1),
            next_recreate_at=datetime.utcnow() + timedelta(days=5),
            traffic_band="monday",
        )
        db.add(flip)
        await db.commit()

    result = await run_recreate_cycle_job()
    assert result["recreated"] == 0


async def test_markdown_event_scan_flags_opted_in_stale_candidates():
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id, stage=FlipStage.ready_for_sale,
            total_cost=800.0, listing_price=1000.0,
            markdown_event_opt_in=True, recreate_cycle_count=3,
        )
        db.add(flip)
        await db.commit()

    result = await run_markdown_event_scan_job()
    assert result["flagged"] == 1


async def test_markdown_event_scan_ignores_non_opted_in():
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id, stage=FlipStage.ready_for_sale,
            total_cost=800.0, listing_price=1000.0,
            markdown_event_opt_in=False, recreate_cycle_count=5,
        )
        db.add(flip)
        await db.commit()

    result = await run_markdown_event_scan_job()
    assert result["flagged"] == 0
