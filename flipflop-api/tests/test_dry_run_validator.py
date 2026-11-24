"""Tests for Dry-Run Validator (Phase 2, F2.2.2).

Verifies:
1. Validate listing without publishing
2. Pricing validation
3. Inventory availability
4. Preview generation
5. No state changes during dry-run
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild
from app.services.dry_run_validator import DryRunValidator
from app.services.feature_flags import set_flag_for_testing


@pytest.mark.unit
class TestValidateListings:
    """Test listing validation."""

    async def test_valid_listing_ebay(self, db: AsyncSession):
        """Validate complete eBay listing."""
        build = ManualBuild(
            name="Valid Build",
            status="built",
            generated_title="Gaming PC",
            generated_description="High-performance gaming build",
            ebay_price=999.99,
            ebay_condition="NEW",
            photos=[{"url": "photo.jpg", "kind": "photo"}],
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "ebay")

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.channel == "ebay"

    async def test_missing_title(self, db: AsyncSession):
        """Validation fails without title."""
        build = ManualBuild(
            name="Incomplete",
            status="built",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "ebay")

        assert result.valid is False
        assert any("title" in e.lower() for e in result.errors)

    async def test_missing_price(self, db: AsyncSession):
        """Validation fails without price."""
        build = ManualBuild(
            name="No Price",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "ebay")

        assert result.valid is False
        assert any("price" in e.lower() for e in result.errors)

    async def test_invalid_price_zero(self, db: AsyncSession):
        """Validation fails with zero price."""
        build = ManualBuild(
            name="Zero Price",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=0,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "ebay")

        assert result.valid is False
        assert any("price" in e.lower() for e in result.errors)

    async def test_build_not_found(self, db: AsyncSession):
        """Validation fails for nonexistent build."""
        result = await DryRunValidator.validate_listing(db, 99999, "ebay")

        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    async def test_invalid_channel(self, db: AsyncSession):
        """Validation fails for unknown channel."""
        build = ManualBuild(
            name="Valid",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "amazon")

        assert result.valid is False
        assert any("unknown" in e.lower() for e in result.errors)

    async def test_warning_no_photos(self, db: AsyncSession):
        """Validation passes but warns without photos."""
        build = ManualBuild(
            name="No Photos",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            ebay_condition="NEW",
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "ebay")

        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("photo" in w.lower() for w in result.warnings)

    async def test_invalid_status(self, db: AsyncSession):
        """Validation fails if build not ready."""
        build = ManualBuild(
            name="In Progress",
            status="in_progress",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "ebay")

        assert result.valid is False
        assert any("status" in e.lower() for e in result.errors)


@pytest.mark.unit
class TestStorefrontValidation:
    """Test Storefront-specific validation."""

    async def test_storefront_without_product_id(self, db: AsyncSession):
        """Storefront warns without product ID."""
        build = ManualBuild(
            name="Storefront Build",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            # No storefront_product_id
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "storefront")

        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("storefront" in w.lower() for w in result.warnings)

    async def test_storefront_with_product_id(self, db: AsyncSession):
        """Storefront passes with product ID."""
        build = ManualBuild(
            name="Storefront",
            status="built",
            generated_title="PC",
            generated_description="Gaming PC",
            ebay_price=999.99,
            storefront_product_id=123,
        )
        db.add(build)
        await db.commit()

        result = await DryRunValidator.validate_listing(db, build.id, "storefront")

        assert result.valid is True


@pytest.mark.unit
class TestPreviewGeneration:
    """Test preview generation."""

    async def test_generate_preview(self, db: AsyncSession):
        """Generate listing preview."""
        build = ManualBuild(
            name="RTX 4090 Build",
            generated_title="High-Performance Gaming PC",
            generated_description="This is a high-performance gaming build",
            ebay_price=2999.99,
            ebay_condition="NEW",
            photos=[{"url": "photo1.jpg"}, {"url": "photo2.jpg"}],
        )
        db.add(build)
        await db.commit()

        preview = await DryRunValidator.preview_publication(db, build.id, "ebay")

        assert preview["build_id"] == build.id
        assert preview["channel"] == "ebay"
        assert preview["title"] == "High-Performance Gaming PC"
        assert preview["price"] == 2999.99
        assert preview["condition"] == "NEW"
        assert preview["photo_count"] == 2

    async def test_preview_nonexistent_build(self, db: AsyncSession):
        """Preview for nonexistent build returns error."""
        preview = await DryRunValidator.preview_publication(db, 99999, "ebay")

        assert "error" in preview


@pytest.mark.unit
class TestInventorySimulation:
    """Test inventory change simulation."""

    async def test_simulate_single_channel(self, db: AsyncSession):
        """Simulate inventory for single channel."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        simulation = await DryRunValidator.simulate_inventory_change(
            db, build.id, ["ebay"]
        )

        assert simulation["build_id"] == build.id
        assert simulation["would_reserve"] == 1
        assert simulation["current_reserved"] == 0

    async def test_simulate_multiple_channels(self, db: AsyncSession):
        """Simulate inventory for multiple channels."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        simulation = await DryRunValidator.simulate_inventory_change(
            db, build.id, ["ebay", "storefront"]
        )

        assert simulation["would_reserve"] == 2
        assert simulation["total_after_listing"] == 2
        assert simulation["safe"] is False  # Would oversell

    async def test_simulate_oversell_detection(self, db: AsyncSession):
        """Simulation detects oversell scenario."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        simulation = await DryRunValidator.simulate_inventory_change(
            db, build.id, ["ebay", "storefront", "amazon"]
        )

        assert simulation["total_after_listing"] == 3
        assert simulation["safe"] is False


@pytest.mark.unit
class TestNoStateChanges:
    """Test that dry-run doesn't modify state."""

    async def test_validate_doesnt_create_listings(self, db: AsyncSession):
        """Validation doesn't create channel listings."""
        from app.models import ChannelListing
        from sqlalchemy import select

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

        # Validate
        await DryRunValidator.validate_listing(db, build.id, "ebay")

        # Check no listing was created
        stmt = select(ChannelListing).where(
            ChannelListing.manual_build_id == build.id
        )
        result = await db.execute(stmt)
        listings = result.scalars().all()

        assert len(listings) == 0

    async def test_validate_doesnt_reserve_inventory(self, db: AsyncSession):
        """Validation doesn't reserve inventory."""
        from app.models import InventoryReservation
        from sqlalchemy import select

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

        # Enable reservation feature
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        # Validate
        await DryRunValidator.validate_listing(db, build.id, "ebay")

        # Check no reservation created
        stmt = select(InventoryReservation).where(
            InventoryReservation.manual_build_id == build.id
        )
        result = await db.execute(stmt)
        reservations = result.scalars().all()

        assert len(reservations) == 0

        # Clean up
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)
