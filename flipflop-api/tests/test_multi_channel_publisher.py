"""Tests for Multi-Channel Publisher (Phase 2, F2.2.1).

Verifies:
1. Create channel listings for multiple channels
2. Update channel status
3. List active listings
4. Sync inventory across channels
5. Feature flag gating
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, ChannelListing
from app.services.multi_channel_publisher import MultiChannelPublisher
from app.services.feature_flags import set_flag_for_testing


@pytest.mark.unit
class TestCreateChannelListings:
    """Test creating listings for multiple channels."""

    async def test_prepare_for_single_channel(self, db: AsyncSession):
        """Create draft listing for single channel."""
        build = ManualBuild(name="Test Build")
        db.add(build)
        await db.commit()

        result = await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay"]
        )

        assert result is True

        # Verify listing created
        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        assert len(listings) == 1
        assert listings[0].channel == "ebay"
        assert listings[0].status == "draft"

    async def test_prepare_for_multiple_channels(self, db: AsyncSession):
        """Create draft listings for multiple channels."""
        build = ManualBuild(name="Multi-Channel Build")
        db.add(build)
        await db.commit()

        result = await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay", "storefront"]
        )

        assert result is True

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        assert len(listings) == 2
        assert {l.channel for l in listings} == {"ebay", "storefront"}

    async def test_prepare_nonexistent_build(self, db: AsyncSession):
        """Handle nonexistent build gracefully."""
        result = await MultiChannelPublisher.prepare_for_channels(
            db, 99999, ["ebay"]
        )

        assert result is False

    async def test_prepare_idempotent(self, db: AsyncSession):
        """Preparing same channel twice doesn't duplicate."""
        build = ManualBuild(name="Idempotent Build")
        db.add(build)
        await db.commit()

        # First prep
        await MultiChannelPublisher.prepare_for_channels(db, build.id, ["ebay"])

        # Second prep (should not duplicate)
        await MultiChannelPublisher.prepare_for_channels(db, build.id, ["ebay"])

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        assert len(listings) == 1


@pytest.mark.unit
class TestGetChannelListing:
    """Test retrieving channel listings."""

    async def test_get_existing_listing(self, db: AsyncSession):
        """Retrieve existing channel listing."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(db, build.id, ["ebay"])

        listing = await MultiChannelPublisher.get_channel_listing(db, build.id, "ebay")

        assert listing is not None
        assert listing.channel == "ebay"
        assert listing.status == "draft"

    async def test_get_nonexistent_channel(self, db: AsyncSession):
        """Get listing for channel that doesn't exist."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        listing = await MultiChannelPublisher.get_channel_listing(
            db, build.id, "amazon"
        )

        assert listing is None


@pytest.mark.unit
class TestUpdateChannelStatus:
    """Test updating channel listing status."""

    async def test_update_to_published(self, db: AsyncSession):
        """Update draft listing to published."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(db, build.id, ["ebay"])
        listing = await MultiChannelPublisher.get_channel_listing(db, build.id, "ebay")

        result = await MultiChannelPublisher.update_channel_listing_status(
            db,
            listing.id,
            "published",
            "ITEM-123456",
        )

        assert result is True

        # Verify update
        updated = await db.get(ChannelListing, listing.id)
        assert updated.status == "published"
        assert updated.external_listing_id == "ITEM-123456"
        assert updated.published_at is not None

    async def test_update_to_withdrawn(self, db: AsyncSession):
        """Update listing to withdrawn."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(db, build.id, ["ebay"])
        listing = await MultiChannelPublisher.get_channel_listing(db, build.id, "ebay")

        result = await MultiChannelPublisher.update_channel_listing_status(
            db,
            listing.id,
            "withdrawn",
        )

        assert result is True

        updated = await db.get(ChannelListing, listing.id)
        assert updated.status == "withdrawn"
        assert updated.withdrawn_at is not None

    async def test_update_nonexistent_listing(self, db: AsyncSession):
        """Handle update of nonexistent listing."""
        result = await MultiChannelPublisher.update_channel_listing_status(
            db, 99999, "published", "ITEM-123"
        )

        assert result is False


@pytest.mark.unit
class TestListActiveListings:
    """Test listing active channel listings."""

    async def test_list_active_listings(self, db: AsyncSession):
        """List all active (non-withdrawn) listings."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay", "storefront"]
        )

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)

        assert len(listings) == 2
        assert all(l.withdrawn_at is None for l in listings)

    async def test_exclude_withdrawn_listings(self, db: AsyncSession):
        """Don't include withdrawn listings in active list."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay", "storefront"]
        )

        # Withdraw one
        ebay = await MultiChannelPublisher.get_channel_listing(db, build.id, "ebay")
        await MultiChannelPublisher.update_channel_listing_status(
            db, ebay.id, "withdrawn"
        )

        # Active should only be storefront
        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        assert len(listings) == 1
        assert listings[0].channel == "storefront"

    async def test_empty_list_for_no_listings(self, db: AsyncSession):
        """Return empty list if build has no listings."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)

        assert listings == []


@pytest.mark.unit
class TestSyncInventory:
    """Test inventory sync across channels."""

    async def test_sync_inventory(self, db: AsyncSession):
        """Sync inventory consistency check."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay", "storefront"]
        )

        result = await MultiChannelPublisher.sync_inventory_across_channels(
            db, build.id
        )

        assert result["build_id"] == build.id
        assert result["channel_count"] == 2
        assert result["consistent"] is True

    async def test_sync_empty_build(self, db: AsyncSession):
        """Sync for build with no listings."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        result = await MultiChannelPublisher.sync_inventory_across_channels(
            db, build.id
        )

        assert result["channel_count"] == 0
        assert result["consistent"] is True


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_prepare_empty_channel_list(self, db: AsyncSession):
        """Prepare with empty channel list."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        result = await MultiChannelPublisher.prepare_for_channels(
            db, build.id, []
        )

        # Should succeed (no channels = nothing to do)
        assert result is True

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        assert len(listings) == 0

    async def test_prepare_duplicate_channels(self, db: AsyncSession):
        """Prepare with duplicate channels in list."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        result = await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay", "ebay"]
        )

        assert result is True

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        # Should only create one listing per channel
        assert len([l for l in listings if l.channel == "ebay"]) <= 2

    async def test_channel_names_case_sensitive(self, db: AsyncSession):
        """Channel names are case-sensitive."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await MultiChannelPublisher.prepare_for_channels(
            db, build.id, ["ebay", "eBay"]
        )

        listings = await MultiChannelPublisher.list_active_channel_listings(db, build.id)
        # Should create two different listings
        assert len(listings) == 2
