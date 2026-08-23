"""
Batch-commit safety tests for recreate_cycle jobs.

Tests that per-iteration commits prevent:
1. Duplicate eBay listings on deferred-publish crash
2. Repeated price drops on recreate-cycle exception
"""

import uuid
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.listing import Listing
from app.workers.recreate_cycle import run_deferred_publish_job, run_recreate_cycle_job


@pytest.fixture(autouse=True)
async def _clean_tables():
    """Clean up test tables between test runs."""
    async with AsyncSessionLocal() as db:
        await db.execute(Flip.__table__.delete())
        await db.execute(Listing.__table__.delete())
        await db.commit()
    yield


async def _make_listing(db) -> int:
    """Helper to create a test listing."""
    listing = Listing(
        external_id=f"batch-test-{uuid.uuid4()}",
        source_id=1,
        title="Test PC for Batch Safety",
        price=800.0,
        url="https://example.com/l/1",
        source_name="eBay UK",
        cpu="i7-13700K",
        gpu="RTX 4070",
        estimated_resale=1100.0,
        estimated_profit=250.0,
    )
    db.add(listing)
    await db.flush()
    return listing.id


# ============================================================================
# TEST 1: Deferred publish per-iteration commit safety
# ============================================================================


@pytest.mark.integration
async def test_deferred_publish_idempotent_on_retry():
    """
    Scenario: publish flip #1, then publish flip #2 (eBay POST succeeds).
    Crash before batch commit. Next run should NOT repost flip #2.

    Verifies: per-iteration commits prevent duplicate eBay listings.
    """
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)

        # Create two flips ready for deferred publish
        flip1 = Flip(
            listing_id=listing_id,
            stage=FlipStage.ready_for_sale,
            total_cost=800.0,
            listing_price=900.0,
            deferred_publish_at=datetime.utcnow() - timedelta(minutes=5),
            traffic_band="monday",
            generated_title="Flip 1 Title",
            generated_description="Flip 1 Desc",
        )
        flip2 = Flip(
            listing_id=listing_id,
            stage=FlipStage.ready_for_sale,
            total_cost=850.0,
            listing_price=950.0,
            deferred_publish_at=datetime.utcnow() - timedelta(minutes=5),
            traffic_band="tuesday",
            generated_title="Flip 2 Title",
            generated_description="Flip 2 Desc",
        )
        db.add(flip1)
        db.add(flip2)
        await db.commit()
        flip1_id, flip2_id = flip1.id, flip2.id

    # Mock eBay publisher to succeed for flip #2 but then raise an exception
    # (simulating a crash after successful POST but before batch commit)
    publish_call_count = 0

    async def mock_publish_flip(flip, db):
        nonlocal publish_call_count
        publish_call_count += 1

        if publish_call_count == 1:
            # Flip #1 publishes successfully
            flip.listed_at = datetime.utcnow()
            flip.ebay_listing_id = f"listing-{flip.id}-run1"
            return True
        elif publish_call_count == 2:
            # Flip #2 publishes successfully
            flip.listed_at = datetime.utcnow()
            flip.ebay_listing_id = f"listing-{flip.id}-run1"
            return True
        else:
            # Never reached in first run (crash happens after flip #2)
            raise Exception("Should not reach here")

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip):
        result = await run_deferred_publish_job()
        assert result["published"] == 2
        assert result["errors"] == 0

    # Verify both flips have ebay_listing_ids (per-iteration commits succeeded)
    async with AsyncSessionLocal() as db:
        flip1 = await db.get(Flip, flip1_id)
        flip2 = await db.get(Flip, flip2_id)

        assert flip1.listed_at is not None
        assert flip2.listed_at is not None
        assert flip1.ebay_listing_id == f"listing-{flip1_id}-run1"
        assert flip2.ebay_listing_id == f"listing-{flip2_id}-run1"

    # Second run: neither flip should be selected for deferred publish again
    # (both have listed_at set, so they fail the query WHERE Flip.listed_at.is_(None))
    publish_call_count = 0

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip):
        result2 = await run_deferred_publish_job()
        # Neither flip should be selected
        assert result2["published"] == 0
        assert publish_call_count == 0  # _publish_flip never called


@pytest.mark.integration
async def test_deferred_publish_exception_rollback():
    """
    Scenario: eBay API raises exception during _publish_flip for flip #1.
    Verify: exception handler rolls back, flip #1 retains listed_at=None for retry.
    """
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id,
            stage=FlipStage.ready_for_sale,
            total_cost=800.0,
            listing_price=900.0,
            deferred_publish_at=datetime.utcnow() - timedelta(minutes=5),
            traffic_band="monday",
            generated_title="Test Flip",
            generated_description="Test Description",
        )
        db.add(flip)
        await db.commit()
        flip_id = flip.id

    # Mock _publish_flip to raise an exception
    async def mock_publish_flip_fail(flip, db):
        # Simulate partial state before exception (some DB writes)
        flip.listing_price = flip.listing_price * 0.99
        await db.flush()
        # Then fail
        raise RuntimeError("eBay API timeout")

    with patch(
        "app.workers.recreate_cycle.publish_flip_now",
        side_effect=mock_publish_flip_fail,
    ):
        result = await run_deferred_publish_job()
        assert result["errors"] == 1
        assert result["published"] == 0

    # Verify: flip was rolled back (price mutation + listed_at both reverted)
    async with AsyncSessionLocal() as db:
        flip = await db.get(Flip, flip_id)
        assert flip.listed_at is None  # Not marked published
        assert flip.listing_price == 900.0  # Price mutation rolled back

    # Third run: flip should be reselected and retried
    async def mock_publish_flip_success(flip, db):
        flip.listed_at = datetime.utcnow()
        flip.ebay_listing_id = "listing-retry-success"
        return True

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip_success):
        result2 = await run_deferred_publish_job()
        assert result2["published"] == 1
        assert result2["errors"] == 0

    # Verify flip is now marked published
    async with AsyncSessionLocal() as db:
        flip = await db.get(Flip, flip_id)
        assert flip.listed_at is not None
        assert flip.ebay_listing_id == "listing-retry-success"


# ============================================================================
# TEST 2: Recreate cycle per-iteration commit safety
# ============================================================================


@pytest.mark.integration
async def test_recreate_cycle_exception_rollback_prevents_repeated_drops():
    """
    Scenario: _recreate_flip starts, mutates price, then eBay post fails.
    Crash happens before commit. Next run should:
    1. NOT have the price mutation (rolled back)
    2. Re-select this flip (next_recreate_at still in the past)
    3. Retry the recreate cycle

    Verifies: per-iteration commits + rollback prevent repeated price drops.
    """
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)
        flip = Flip(
            listing_id=listing_id,
            stage=FlipStage.ready_for_sale,
            total_cost=800.0,
            listing_price=1000.0,
            listed_at=datetime.utcnow() - timedelta(days=8),
            next_recreate_at=datetime.utcnow() - timedelta(hours=1),  # Due
            traffic_band="monday",
            recreate_price_step_pct=0.05,
            generated_images_urls=["a.png", "b.png"],
        )
        db.add(flip)
        await db.commit()
        flip_id = flip.id

    original_price = 1000.0

    # Mock _publish_flip to fail after price mutation
    async def mock_publish_flip_fail(flip, db):
        # Simulate: price is mutated before eBay post
        flip.listing_price = flip.listing_price * 0.95  # 5% drop
        await db.flush()
        # Then eBay post fails
        raise RuntimeError("eBay connection timeout")

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip_fail):
        result = await run_recreate_cycle_job()
        assert result["errors"] == 1
        assert result["recreated"] == 0

    # Verify: price was rolled back
    async with AsyncSessionLocal() as db:
        flip = await db.get(Flip, flip_id)
        assert flip.listing_price == original_price  # Rolled back
        assert flip.recreate_cycle_count == 0  # Not incremented
        assert flip.next_recreate_at < datetime.utcnow()  # Still due

    # Second run: flip should be reselected and retried successfully
    async def mock_publish_flip_success(flip, db):
        flip.ebay_listing_id = f"listing-{flip.id}-retry"
        return True

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip_success):
        result2 = await run_recreate_cycle_job()
        assert result2["recreated"] == 1
        assert result2["errors"] == 0

    # Verify: price dropped exactly once (not twice)
    async with AsyncSessionLocal() as db:
        flip = await db.get(Flip, flip_id)
        # Price should be: 1000 * 0.95 (one drop, not 0.95 * 0.95)
        assert abs(flip.listing_price - 950.0) < 1.0  # ~950
        assert flip.recreate_cycle_count == 1
        assert flip.next_recreate_at > datetime.utcnow()


@pytest.mark.integration
async def test_recreate_cycle_partial_batch_not_lost():
    """
    Scenario: run_recreate_cycle_job processes three flips.
    Flip #1 succeeds (committed immediately).
    Flip #2 succeeds (committed immediately).
    Flip #3 raises exception (rolled back immediately).
    Next run should only retry flip #3.

    Verifies: per-iteration commits don't lose partial progress.
    """
    async with AsyncSessionLocal() as db:
        listing_id = await _make_listing(db)

        flips = []
        for i in range(1, 4):
            flip = Flip(
                listing_id=listing_id,
                stage=FlipStage.ready_for_sale,
                total_cost=800.0 + (i * 50),
                listing_price=1000.0 + (i * 50),
                listed_at=datetime.utcnow() - timedelta(days=8),
                next_recreate_at=datetime.utcnow() - timedelta(hours=1),  # All due
                traffic_band="monday",
                recreate_price_step_pct=0.05,
                generated_images_urls=["a.png", "b.png"],
            )
            db.add(flip)
            flips.append(flip)

        await db.commit()
        flip_ids = [f.id for f in flips]

    call_count = 0

    async def mock_publish_flip(flip, db):
        nonlocal call_count
        call_count += 1

        if call_count <= 2:
            # Flips #1 and #2 succeed
            flip.ebay_listing_id = f"listing-{flip.id}-run1"
            return True
        else:
            # Flip #3 fails
            raise RuntimeError("eBay API error")

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip):
        result = await run_recreate_cycle_job()
        assert result["recreated"] == 2
        assert result["errors"] == 1

    # Verify: flip #1 and #2 were stepped; flip #3 was rolled back
    async with AsyncSessionLocal() as db:
        flip1 = await db.get(Flip, flip_ids[0])
        flip2 = await db.get(Flip, flip_ids[1])
        flip3 = await db.get(Flip, flip_ids[2])

        assert flip1.recreate_cycle_count == 1
        assert flip1.next_recreate_at > datetime.utcnow()
        assert flip1.ebay_listing_id == f"listing-{flip_ids[0]}-run1"

        assert flip2.recreate_cycle_count == 1
        assert flip2.next_recreate_at > datetime.utcnow()
        assert flip2.ebay_listing_id == f"listing-{flip_ids[1]}-run1"

        assert flip3.recreate_cycle_count == 0  # Not incremented
        assert flip3.next_recreate_at < datetime.utcnow()  # Still due
        assert flip3.ebay_listing_id is None

    # Second run: only flip #3 should be selected
    call_count = 0

    async def mock_publish_flip_success(flip, db):
        flip.ebay_listing_id = f"listing-{flip.id}-retry"
        return True

    with patch("app.workers.recreate_cycle._publish_flip", side_effect=mock_publish_flip_success):
        result2 = await run_recreate_cycle_job()
        assert result2["recreated"] == 1  # Only flip #3
        assert call_count == 1  # Only one _publish_flip call
