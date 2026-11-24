"""
Functional tests for the offer-poll / send-to-watchers / message-poll
scheduler jobs (rows 8, 21, 45, 47). Runs against a real SQLite DB via
DATABASE_URL, same pattern as test_recreate_cycle_job.py, with eBay HTTP
calls mocked.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.database import AsyncSessionLocal
from app.models.flip import Flip, FlipStage
from app.models.listing import Listing
from app.models.app_settings import AppSettings
from app.workers.offer_poll import run_offer_poll_job, run_send_to_watchers_job
from app.workers.message_poll import run_message_poll_job


@pytest.fixture(autouse=True)
async def _clean_tables():
    async with AsyncSessionLocal() as db:
        await db.execute(Flip.__table__.delete())
        await db.execute(Listing.__table__.delete())
        await db.execute(AppSettings.__table__.delete())
        await db.commit()
    yield


async def _connect_ebay():
    async with AsyncSessionLocal() as db:
        db.add(AppSettings(
            name="default",
            ebay_seller_access_token="AT-live",
            ebay_seller_access_token_expires_at=datetime.utcnow() + timedelta(hours=1),
            ebay_seller_refresh_token="RT-live",
            ebay_seller_refresh_token_expires_at=datetime.utcnow() + timedelta(days=300),
            ebay_seller_connected_at=datetime.utcnow(),
        ))
        await db.commit()


async def _make_flip(**overrides) -> int:
    async with AsyncSessionLocal() as db:
        listing = Listing(
            external_id=f"op-{uuid.uuid4()}", source_id=1, title="Gaming PC",
            price=800.0, url="https://example.com", source_name="eBay UK",
        )
        db.add(listing)
        await db.flush()
        defaults = dict(
            listing_id=listing.id, stage=FlipStage.ready_for_sale, total_cost=800.0,
            listing_price=1000.0, offers_enabled=True, ebay_listing_id="item-1",
        )
        defaults.update(overrides)
        flip = Flip(**defaults)
        db.add(flip)
        await db.commit()
        return flip.id


async def test_offer_poll_skips_without_connected_ebay():
    await _make_flip()
    result = await run_offer_poll_job()
    assert result["polled"] == 0
    assert "note" in result


async def test_offer_poll_counters_active_offer():
    await _connect_ebay()
    flip_id = await _make_flip(min_offer_price=700.0)

    with patch("app.workers.offer_poll.ebay_trading_api.get_best_offers", new=AsyncMock(return_value=[
        {"best_offer_id": "5001", "buyer_id": "buyer1", "price": 720.0, "status": "Active"},
    ])), patch("app.workers.offer_poll.ebay_trading_api.respond_to_best_offer", new=AsyncMock(return_value=True)) as mock_respond:
        result = await run_offer_poll_job()

    assert result["polled"] == 1
    assert result["countered"] == 1
    mock_respond.assert_called_once()
    call_args = mock_respond.call_args.args
    assert call_args[0] == "item-1"
    assert call_args[1] == "5001"
    assert call_args[2] == "Counter"

    async with AsyncSessionLocal() as db:
        refreshed = await db.get(Flip, flip_id)
        assert refreshed.counter_offer_round == 1
        assert refreshed.last_counter_offer_price is not None


async def test_offer_poll_no_offers_no_op():
    await _connect_ebay()
    await _make_flip()

    with patch("app.workers.offer_poll.ebay_trading_api.get_best_offers", new=AsyncMock(return_value=[])):
        result = await run_offer_poll_job()

    assert result["polled"] == 1
    assert result["countered"] == 0


async def test_send_to_watchers_sends_when_due():
    await _connect_ebay()
    flip_id = await _make_flip(
        listed_at=datetime.utcnow() - timedelta(days=6), min_offer_price=700.0,
    )

    with patch("app.workers.offer_poll.ebay_negotiation.send_offer_to_watchers", new=AsyncMock(return_value=True)) as mock_send:
        result = await run_send_to_watchers_job()

    assert result["sent"] == 1
    mock_send.assert_called_once()

    async with AsyncSessionLocal() as db:
        refreshed = await db.get(Flip, flip_id)
        assert refreshed.last_watcher_offer_sent_at is not None


async def test_send_to_watchers_not_due_yet():
    await _connect_ebay()
    await _make_flip(listed_at=datetime.utcnow() - timedelta(days=1))

    with patch("app.workers.offer_poll.ebay_negotiation.send_offer_to_watchers", new=AsyncMock(return_value=True)) as mock_send:
        result = await run_send_to_watchers_job()

    assert result["sent"] == 0
    mock_send.assert_not_called()


async def test_message_poll_skips_without_connected_ebay():
    result = await run_message_poll_job()
    assert result["checked"] == 0
    assert "note" in result


async def test_message_poll_flags_old_unanswered_message():
    await _connect_ebay()
    old_time = (datetime.utcnow() - timedelta(hours=5)).isoformat() + "Z"

    with patch("app.workers.message_poll.ebay_trading_api.get_member_messages", new=AsyncMock(return_value=[
        {"message_id": "m1", "sender": "buyer1", "subject": "Is this still available?",
         "item_id": "item-1", "received_at": old_time},
    ])):
        result = await run_message_poll_job()

    assert result["checked"] == 1
    assert result["flagged"] == 1


async def test_message_poll_ignores_recent_message():
    await _connect_ebay()
    recent_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat() + "Z"

    with patch("app.workers.message_poll.ebay_trading_api.get_member_messages", new=AsyncMock(return_value=[
        {"message_id": "m2", "sender": "buyer2", "subject": "Quick question",
         "item_id": "item-1", "received_at": recent_time},
    ])):
        result = await run_message_poll_job()

    assert result["checked"] == 1
    assert result["flagged"] == 0
