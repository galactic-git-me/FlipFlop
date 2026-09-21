"""Growth Engine Marketing MVP: publishing, approvals, flags, analytics."""
import pytest
from sqlalchemy import select

from app.models.growth import SocialPublication, SocialPost
from app.services.growth_connectors import publish_fixture
from app.services.growth_release import FeatureNotEnabled, get_active_release, require_capability
from app.services import growth_social as social


@pytest.mark.asyncio
async def test_fixture_publisher_is_idempotent():
    first = publish_fixture(platform="x", account_id=1, copy="hello", idempotency_key="post:1:rev:1:x")
    second = publish_fixture(platform="x", account_id=1, copy="hello again", idempotency_key="post:1:rev:1:x")
    assert first["provider_post_id"] == second["provider_post_id"]
    assert first["status"] == "published"


@pytest.mark.asyncio
async def test_release_enables_mvp_and_blocks_paid(db):
    release = await get_active_release(db)
    require_capability(release, "social_publishing")
    with pytest.raises(FeatureNotEnabled) as exc:
        require_capability(release, "paid_advertising")
    assert exc.value.code == "FEATURE_NOT_ENABLED"


@pytest.mark.asyncio
async def test_post_approve_publish_and_duplicate_retry(db):
    await social.ensure_seed(db)
    post = await social.create_post(
        db,
        {
            "platforms": ["x", "facebook"],
            "copy": "FlipFlop mid-towers are in stock this week.",
            "link_url": "https://theflipflop.shop/builds",
            "media_asset_ids": [1],
        },
    )
    post = await social.submit_for_review(db, post)
    assert post.status == "review"
    post = await social.decide_approval(db, post, approve=True, actor="owner")
    assert post.status == "approved"
    post = await social.publish_post(db, post)
    assert post.status == "published"
    pubs = (await db.execute(select(SocialPublication).where(SocialPublication.post_id == post.id))).scalars().all()
    assert len(pubs) == 2
    assert {row.platform for row in pubs} == {"x", "facebook"}
    keys = [row.idempotency_key for row in pubs]
    post = await social.publish_post(db, post)
    pubs_after = (await db.execute(select(SocialPublication).where(SocialPublication.post_id == post.id))).scalars().all()
    assert len(pubs_after) == 2
    assert sorted(row.idempotency_key for row in pubs_after) == sorted(keys)


@pytest.mark.asyncio
async def test_validation_requires_copy_and_approved_media(db):
    await social.ensure_seed(db)
    post = await social.create_post(db, {"platforms": ["x"], "copy": "", "media_asset_ids": []})
    post = await social.submit_for_review(db, post)
    assert post.status == "validation_failed"


@pytest.mark.asyncio
async def test_revision_invalidates_approval(db):
    await social.ensure_seed(db)
    post = await social.create_post(db, {"platforms": ["instagram"], "copy": "A compact dual-chamber case worth a look."})
    post = await social.submit_for_review(db, post)
    post = await social.decide_approval(db, post, approve=True, actor="owner")
    post = await social.revise_post(db, post, {"copy": "Updated copy after approval"})
    assert post.status == "draft"


@pytest.mark.asyncio
async def test_website_analytics_ingestion(db):
    await social.ingest_website_event(
        db,
        {"event_name": "page_view", "session_id": "abc", "path": "/", "utm": {"utm_campaign": "social-post-1"}},
    )
    summary = await social.analytics_summary(db)
    assert summary["website_events"] == 1
    assert summary["website_sessions"] == 1
    assert "Organic" in summary["label"]
