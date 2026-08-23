"""Tests for Live Publisher (Phase 2, F2.2.3).

Verifies:
1. Publish to single channel
2. Publish to multiple channels
3. Feature flag enforcement
4. Validation before publish
5. External listing IDs
6. Withdrawal
7. Audit trail
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, ChannelListing, ListingPublishEvent
from app.services.live_publisher import LivePublisher
from app.services.feature_flags import set_flag_for_testing


@pytest.mark.asyncio
class TestPublishToChannel:
    """Test publishing to single channel."""

    async def test_publish_requires_valid_build(self, db: AsyncSession):
        """Can't publish invalid build."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(name="Incomplete")  # Missing required fields
        db.add(build)
        await db.commit()

        result = await LivePublisher.publish_to_channel(db, build.id, "ebay")

        assert result.success is False
        assert result.error is not None

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_publish_valid_build(self, db: AsyncSession):
        """Publish valid build to channel."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Complete Build",
            status="built",
            generated_title="Gaming PC",
            generated_description="High-performance gaming build",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await LivePublisher.publish_to_channel(db, build.id, "ebay")

        assert result.success is True
        assert result.external_listing_id is not None
        assert result.channel == "ebay"

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_publish_creates_external_id(self, db: AsyncSession):
        """Publishing generates external listing ID."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await LivePublisher.publish_to_channel(db, build.id, "ebay")

        assert result.external_listing_id is not None
        assert "ebay" in result.external_listing_id.lower() or "EBAY" in result.external_listing_id

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_publish_updates_channel_listing(self, db: AsyncSession):
        """Publishing updates channel listing status."""
        from sqlalchemy import select

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        await LivePublisher.publish_to_channel(db, build.id, "ebay")

        # Verify listing was created and published
        stmt = select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
            ChannelListing.channel == "ebay",
        )
        result = await db.execute(stmt)
        listing = result.scalars().first()

        assert listing is not None
        assert listing.status == "published"
        assert listing.external_listing_id is not None
        assert listing.published_at is not None

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_publish_flag_disabled(self, db: AsyncSession):
        """Can't publish when feature flag disabled."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY", False)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await LivePublisher.publish_to_channel(db, build.id, "ebay")

        assert result.success is False
        assert "disabled" in result.error.lower()


@pytest.mark.asyncio
class TestPublishMultipleChannels:
    """Test publishing to multiple channels."""

    async def test_publish_to_all_channels(self, db: AsyncSession):
        """Publish to multiple channels simultaneously."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
            storefront_product_id=123,
        )
        db.add(build)
        await db.commit()

        results = await LivePublisher.publish_to_all_channels(
            db, build.id, ["ebay", "storefront"]
        )

        assert len(results) == 2
        assert results["ebay"].success is True
        assert results["storefront"].success is True

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_multi_channel_independent(self, db: AsyncSession):
        """Failure in one channel doesn't block others."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
            # storefront_product_id missing (will fail storefront validation)
        )
        db.add(build)
        await db.commit()

        results = await LivePublisher.publish_to_all_channels(
            db, build.id, ["ebay", "storefront"]
        )

        # eBay should succeed, storefront should fail
        assert results["ebay"].success is True
        assert results["storefront"].success is False

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)


@pytest.mark.asyncio
class TestWithdraw:
    """Test withdrawing listings."""

    async def test_withdraw_published_listing(self, db: AsyncSession):
        """Withdraw a published listing."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        # Publish
        await LivePublisher.publish_to_channel(db, build.id, "ebay")

        # Withdraw
        result = await LivePublisher.withdraw_from_channel(db, build.id, "ebay")

        assert result is True

        # Verify status changed
        from sqlalchemy import select
        stmt = select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
            ChannelListing.channel == "ebay",
        )
        listing = await db.scalar(stmt)

        assert listing.status == "withdrawn"
        assert listing.withdrawn_at is not None

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_withdraw_nonexistent_listing(self, db: AsyncSession):
        """Withdraw fails gracefully for nonexistent listing."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        result = await LivePublisher.withdraw_from_channel(db, build.id, "ebay")

        assert result is False

    async def test_withdraw_already_withdrawn(self, db: AsyncSession):
        """Can't withdraw already withdrawn listing."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        # Publish and withdraw
        await LivePublisher.publish_to_channel(db, build.id, "ebay")
        await LivePublisher.withdraw_from_channel(db, build.id, "ebay")

        # Try to withdraw again
        result = await LivePublisher.withdraw_from_channel(db, build.id, "ebay")

        assert result is False

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)


@pytest.mark.asyncio
class TestAuditTrail:
    """Test audit trail of publish events."""

    async def test_publish_creates_event(self, db: AsyncSession):
        """Publishing creates audit event."""
        from sqlalchemy import select

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        await LivePublisher.publish_to_channel(db, build.id, "ebay")

        # Get listing
        stmt = select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
            ChannelListing.channel == "ebay",
        )
        listing = await db.scalar(stmt)

        # Verify event exists
        stmt = select(ListingPublishEvent).where(
            ListingPublishEvent.channel_listing_id == listing.id,
            ListingPublishEvent.event_type == "published",
        )
        event = await db.scalar(stmt)

        assert event is not None
        assert event.message is not None

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)

    async def test_withdraw_creates_event(self, db: AsyncSession):
        """Withdrawing creates audit event."""
        from sqlalchemy import select

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        await LivePublisher.publish_to_channel(db, build.id, "ebay")
        await LivePublisher.withdraw_from_channel(db, build.id, "ebay")

        # Get listing and verify withdraw event
        stmt = select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
            ChannelListing.channel == "ebay",
        )
        listing = await db.scalar(stmt)

        stmt = select(ListingPublishEvent).where(
            ListingPublishEvent.channel_listing_id == listing.id,
            ListingPublishEvent.event_type == "withdrawn",
        )
        event = await db.scalar(stmt)

        assert event is not None

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)


@pytest.mark.asyncio
class TestDryRunMode:
    """Test dry-run mode."""

    async def test_dry_run_only_mode(self, db: AsyncSession):
        """Dry-run only mode allows validation but not publish."""
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_ENABLED", False)
        set_flag_for_testing("FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY", True)

        build = ManualBuild(
            name="Test",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await LivePublisher.publish_to_channel(db, build.id, "ebay")

        # Should succeed (dry-run mode)
        assert result.success is True
        assert "dry-run" in result.message.lower() or "DRY-RUN" in result.message

        # But listing should NOT be published
        from sqlalchemy import select
        stmt = select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id,
        )
        result = await db.execute(stmt)
        listings = result.scalars().all()

        # No listing created in dry-run mode
        assert len(listings) == 0

        set_flag_for_testing("FEATURE_LISTING_PUBLISH_DRY_RUN_ONLY", False)
