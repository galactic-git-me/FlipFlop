"""Growth Engine Marketing MVP: publishing, approvals, flags, analytics."""
import pytest
from sqlalchemy import select
from urllib.parse import parse_qsl, urlparse

from app.models.growth import ContentAsset, SocialAccount, SocialPublication, SocialPost, SocialPostRevision
from app.models.product import Product, ProductStatus, ProductType
from app.services.growth_connectors import publish_fixture
from app.services.growth_release import FeatureNotEnabled, get_active_release, require_capability
from app.services import growth_social as social


@pytest.mark.asyncio
async def test_fixture_publisher_is_idempotent():
    first = publish_fixture(platform="x", account_id=1, copy="hello", idempotency_key="post:1:rev:1:x")
    second = publish_fixture(platform="x", account_id=1, copy="hello again", idempotency_key="post:1:rev:1:x")
    assert first["simulation_id"] == second["simulation_id"]
    assert first["status"] == "simulated"
    assert first["provider_post_id"] == ""


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
    await social.set_dispatch_pause(db, paused=False, actor="owner")
    accounts = (await db.execute(select(SocialAccount))).scalars().all()
    for account in accounts:
        account.status = "connected"
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
    assert post.status == "needs_attention"
    assert "no external publication occurred" in post.needs_attention
    pubs = (await db.execute(select(SocialPublication).where(SocialPublication.post_id == post.id))).scalars().all()
    assert len(pubs) == 2
    assert {row.platform for row in pubs} == {"x", "facebook"}
    assert {row.status for row in pubs} == {"simulated"}
    keys = [row.idempotency_key for row in pubs]
    post = await social.publish_post(db, post)
    pubs_after = (await db.execute(select(SocialPublication).where(SocialPublication.post_id == post.id))).scalars().all()
    assert len(pubs_after) == 2
    assert sorted(row.idempotency_key for row in pubs_after) == sorted(keys)


@pytest.mark.asyncio
async def test_global_pause_blocks_approved_dispatch(db):
    await social.ensure_seed(db)
    post = await social.create_post(db, {"platforms": ["facebook"], "copy": "A factual draft."})
    post = await social.submit_for_review(db, post)
    post = await social.decide_approval(db, post, approve=True, actor="owner")
    assert post.status == "approved"

    post = await social.publish_post(db, post)

    assert post.status == "approved"
    assert "paused" in post.needs_attention.lower()
    pubs = (await db.execute(select(SocialPublication).where(SocialPublication.post_id == post.id))).scalars().all()
    assert pubs == []


@pytest.mark.asyncio
async def test_new_listed_build_creates_idempotent_meta_drafts(db):
    product = Product(
        product_type=ProductType.PREBUILT,
        title="Verified test build",
        description="An existing listed build.",
        price=799.0,
        status=ProductStatus.LISTED,
        hero_photo_url="https://assets.example.test/build.jpg",
    )
    db.add(product)
    await db.flush()

    first = await social.create_build_launch_drafts(db, product, build_id=42)
    replay = await social.create_build_launch_drafts(db, product, build_id=42)

    assert len(first) == 2
    assert replay == []
    assert {platform for post in first for platform in post.platforms} == {"facebook", "instagram"}
    revisions = (await db.execute(select(SocialPostRevision).where(SocialPostRevision.post_id.in_([p.id for p in first])))).scalars().all()
    assert all("£799.00" in revision.copy for revision in revisions)
    assert all("utm_campaign=build-launch-42" in revision.link_url for revision in revisions)
    assert all("build-42-product-" in revision.link_url for revision in revisions)
    for revision in revisions:
        asset = await db.get(ContentAsset, revision.media_asset_ids[0])
        assert asset is not None and not asset.approved

    first[0] = await social.submit_for_review(db, first[0])
    assert first[0].status == "validation_failed"
    asset = await db.get(ContentAsset, revisions[0].media_asset_ids[0])
    asset.approved = True
    first[0] = await social.submit_for_review(db, first[0])
    assert first[0].status == "review"


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


@pytest.mark.asyncio
async def test_tracking_link_preserves_repeated_query_values_and_fragment(db):
    link = await social.create_tracking_link(
        db,
        destination_url="https://www.theflipflop.shop/ready-to-ship/1?keep=first&keep=second&utm_source=old#specs",
        campaign="build-launch-1",
        content="build-1-variant-a",
    )

    tracked = urlparse(social.tracked_url(link))
    params = parse_qsl(tracked.query, keep_blank_values=True)

    assert [value for key, value in params if key == "keep"] == ["first", "second"]
    assert dict(params)["utm_campaign"] == "build-launch-1"
    assert dict(params)["utm_content"] == "build-1-variant-a"
    assert tracked.fragment == "specs"
