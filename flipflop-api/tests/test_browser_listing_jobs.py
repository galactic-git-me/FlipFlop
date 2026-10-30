from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.models.manual_build import ManualBuild
from app.models.channel_listing import ChannelListing
from app.models.browser_listing_job import BrowserListingJob
from app.services.browser_listing_jobs import enqueue_browser_job, complete_browser_job, validate_listing_url
from app.api.browser_listing_jobs import claim, heartbeat, preflight, LeaseIn, require_worker


async def make_build(db):
    build = ManualBuild(name="PROMETHEUS", status="built", generated_title="PROMETHEUS Gaming PC",
        generated_description="A tested PC with its saved specification.", ebay_price=1400,
        photos=[{"url": "https://www.theflipflop.shop/api/uploads/pc.jpg", "kind": "photo"}],
        components=[], is_archived=False)
    db.add(build)
    await db.flush()
    return build


@pytest.mark.asyncio
async def test_duplicate_submit_reuses_pending_job_and_saved_price(db):
    build = await make_build(db)
    build.last_evaluation = {"mid": 1450}
    a = await enqueue_browser_job(db, build.id, "vinted")
    b = await enqueue_browser_job(db, build.id, "vinted")
    assert a.id == b.id
    assert a.payload["listing"]["price"] == 1400
    assert a.payload["listing"]["delivery_only"] is True
    assert a.payload["listing"]["collection_allowed"] is False


@pytest.mark.asyncio
async def test_success_saves_url_and_advances_only_after_browser_evidence(db):
    build = await make_build(db)
    job = await enqueue_browser_job(db, build.id, "vinted", operation="relist")
    row = await db.get(ChannelListing, job.channel_listing_id)
    old_due = datetime.utcnow() - timedelta(days=2)
    row.recreate_enabled, row.next_recreate_at = True, old_due
    row.recreate_count = 0
    with pytest.raises(ValueError, match="evidence"):
        await complete_browser_job(db, job, status="succeeded", message="done", listing_url="https://www.vinted.co.uk/items/123", external_id="123")
    assert row.next_recreate_at == old_due
    url = "https://www.vinted.co.uk/items/123-gaming-pc"
    evidence = {"verified_at": datetime.utcnow().isoformat(), "title": job.payload["listing"]["title"], "price": 1400, "url": url}
    await complete_browser_job(db, job, status="succeeded", message="Confirmed", listing_url=url, external_id="123", evidence=evidence)
    assert row.listing_url == url and row.external_listing_id == "123"
    assert row.status == "published" and row.recreate_count == 1 and row.next_recreate_at > old_due


@pytest.mark.asyncio
async def test_blocked_job_preserves_last_confirmed_listing_and_due_clock(db):
    build = await make_build(db)
    job = await enqueue_browser_job(db, build.id, "vinted", operation="relist")
    row = await db.get(ChannelListing, job.channel_listing_id)
    row.status, row.listing_url, row.external_listing_id = "published", "https://www.vinted.co.uk/items/12", "12"
    old_due = row.next_recreate_at = datetime.utcnow() - timedelta(days=1)
    await complete_browser_job(db, job, status="blocked", message="MFA needed")
    assert row.status == "published" and row.external_listing_id == "12" and row.next_recreate_at == old_due
    assert (await enqueue_browser_job(db, build.id, "vinted")).id == job.id


@pytest.mark.asyncio
async def test_sold_build_cannot_be_queued(db):
    build = await make_build(db)
    build.status = "sold"
    with pytest.raises(ValueError, match="Sold"):
        await enqueue_browser_job(db, build.id, "onbuy")


@pytest.mark.asyncio
async def test_expired_worker_is_not_blindly_retried(db):
    build = await make_build(db)
    job = await enqueue_browser_job(db, build.id, "vinted")
    job.status, job.lease_token, job.lease_until = "running", "x" * 64, datetime.utcnow() - timedelta(minutes=1)
    await db.flush()
    assert await claim(db) is None
    assert job.status == "needs_review"
    with pytest.raises(HTTPException) as error:
        await heartbeat(job.id, LeaseIn(lease_token="x" * 64), db)
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_changed_saved_price_blocks_final_submit(db):
    build = await make_build(db)
    job = await enqueue_browser_job(db, build.id, "vinted")
    claimed = await claim(db)
    build.ebay_price = 1390
    await db.flush()
    with pytest.raises(HTTPException) as error:
        await preflight(job.id, LeaseIn(lease_token=claimed["lease_token"]), db)
    assert error.value.status_code == 409


@pytest.mark.parametrize("url", ["https://vinted.co.uk.evil.test/items/1", "https://www.vinted.co.uk/login", "javascript:alert(1)", "http://www.vinted.co.uk/items/1", "https://user:secret@www.vinted.co.uk/items/1", "https://www.facebook.com/marketplace/item/12"])
def test_result_url_rejects_wrong_host_login_pages_and_unsafe_schemes(url):
    with pytest.raises(ValueError):
        validate_listing_url("vinted", url)


def test_worker_auth_fails_closed_and_is_separate_from_operator(monkeypatch):
    monkeypatch.delenv("CROSS_LISTING_WORKER_KEY", raising=False)
    with pytest.raises(HTTPException): require_worker("anything")
    monkeypatch.setenv("CROSS_LISTING_WORKER_KEY", "worker-secret")
    with pytest.raises(HTTPException): require_worker("operator-secret")
    require_worker("worker-secret")


@pytest.mark.asyncio
async def test_ebay_schedule_uses_saved_canonical_data_and_only_advances_on_success(db, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.workers.manual_build_lifecycle import _recreate_manual_build
    build = await make_build(db)
    build.ebay_price, build.generated_title = 1400, "PROMETHEUS Gaming PC"
    old_due = build.next_recreate_at = datetime.utcnow() - timedelta(days=1)
    post = AsyncMock(return_value=SimpleNamespace(success=False))
    monkeypatch.setattr("app.api.manual_builds.post_to_ebay", post)
    assert await _recreate_manual_build(build, db) == "not_ready"
    assert build.next_recreate_at == old_due and build.ebay_price == 1400
    post.return_value = SimpleNamespace(success=True)
    assert await _recreate_manual_build(build, db) == "published"
    assert build.next_recreate_at > old_due
    assert post.call_args.args[1].price == 1400
    assert post.call_args.args[1].title == "PROMETHEUS Gaming PC"
    assert build.generated_title == "PROMETHEUS Gaming PC" and build.ebay_price == 1400
