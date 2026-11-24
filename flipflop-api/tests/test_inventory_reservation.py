"""Tests for Inventory Reservation Manager (Phase 2, F2.2.4).

Verifies:
1. Reserve inventory
2. Release on withdrawal
3. Prevent overselling
4. Multiple channel reservations
5. Feature flag gating
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild, InventoryReservation
from app.services.inventory_reservation import InventoryReservationManager
from app.services.feature_flags import set_flag_for_testing


@pytest.mark.unit
class TestReserveInventory:
    """Test inventory reservation."""

    async def test_reserve_single_channel(self, db: AsyncSession):
        """Reserve inventory for single channel."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test Build")
        db.add(build)
        await db.commit()

        reservation = await InventoryReservationManager.reserve_inventory(
            db, build.id, "ebay", 1
        )

        assert reservation is not None
        assert reservation.manual_build_id == build.id
        assert reservation.channel == "ebay"
        assert reservation.quantity_reserved == 1
        assert reservation.released_at is None

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_reserve_multiple_channels(self, db: AsyncSession):
        """Reserve on multiple channels."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test Build")
        db.add(build)
        await db.commit()

        # Reserve for ebay
        ebay_res = await InventoryReservationManager.reserve_inventory(
            db, build.id, "ebay"
        )
        assert ebay_res is not None

        # Reserve for storefront
        store_res = await InventoryReservationManager.reserve_inventory(
            db, build.id, "storefront"
        )
        assert store_res is not None

        # Both should exist
        total = await InventoryReservationManager.get_reserved_count(db, build.id)
        assert total == 2

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_reserve_nonexistent_build(self, db: AsyncSession):
        """Fail gracefully on nonexistent build."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        reservation = await InventoryReservationManager.reserve_inventory(
            db, 99999, "ebay"
        )

        assert reservation is None

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_reserve_flag_off(self, db: AsyncSession):
        """Skip reservation when flag disabled."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        reservation = await InventoryReservationManager.reserve_inventory(
            db, build.id, "ebay"
        )

        assert reservation is None

    async def test_duplicate_reservation_same_channel(self, db: AsyncSession):
        """Don't duplicate reservation for same channel."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # First reservation
        res1 = await InventoryReservationManager.reserve_inventory(
            db, build.id, "ebay"
        )

        # Second reservation (should return existing)
        res2 = await InventoryReservationManager.reserve_inventory(
            db, build.id, "ebay"
        )

        assert res1.id == res2.id

        total = await InventoryReservationManager.get_reserved_count(db, build.id)
        assert total == 1

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)


@pytest.mark.unit
class TestGetReservedCount:
    """Test getting reserved inventory count."""

    async def test_no_reservations(self, db: AsyncSession):
        """Count is 0 when no reservations."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        count = await InventoryReservationManager.get_reserved_count(db, build.id)

        assert count == 0

    async def test_count_multiple_channels(self, db: AsyncSession):
        """Count includes all channels."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")
        await InventoryReservationManager.reserve_inventory(db, build.id, "storefront")
        await InventoryReservationManager.reserve_inventory(db, build.id, "amazon")

        count = await InventoryReservationManager.get_reserved_count(db, build.id)

        assert count == 3

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_exclude_released_from_count(self, db: AsyncSession):
        """Released reservations don't count."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")
        await InventoryReservationManager.reserve_inventory(db, build.id, "storefront")

        # Release one
        await InventoryReservationManager.release_reservation(db, build.id, "ebay")

        count = await InventoryReservationManager.get_reserved_count(db, build.id)

        assert count == 1

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)


@pytest.mark.unit
class TestCheckAvailability:
    """Test availability checking."""

    async def test_available_when_unreserved(self, db: AsyncSession):
        """Build is available when no reservations."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        available = await InventoryReservationManager.check_availability(
            db, build.id, 1
        )

        assert available is True

    async def test_unavailable_when_reserved(self, db: AsyncSession):
        """Build unavailable when already reserved."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Reserve once
        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")

        # Should not be available
        available = await InventoryReservationManager.check_availability(
            db, build.id, 1
        )

        assert available is False

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_quantity_check(self, db: AsyncSession):
        """Quantity check works correctly."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Reserve 1
        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")

        # Check for 2 (should fail)
        available = await InventoryReservationManager.check_availability(
            db, build.id, 2
        )

        assert available is False

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)


@pytest.mark.unit
class TestReleaseReservation:
    """Test releasing reservations."""

    async def test_release_reservation(self, db: AsyncSession):
        """Release reservation when withdrawn."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Reserve
        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")

        # Release
        result = await InventoryReservationManager.release_reservation(
            db, build.id, "ebay"
        )

        assert result is True

        # Verify count is 0
        count = await InventoryReservationManager.get_reserved_count(db, build.id)
        assert count == 0

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_release_nonexistent_reservation(self, db: AsyncSession):
        """Fail gracefully when no reservation to release."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        result = await InventoryReservationManager.release_reservation(
            db, build.id, "ebay"
        )

        assert result is False

    async def test_release_multiple_channels(self, db: AsyncSession):
        """Release per-channel."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Reserve multiple
        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")
        await InventoryReservationManager.reserve_inventory(db, build.id, "storefront")

        # Release one
        await InventoryReservationManager.release_reservation(db, build.id, "ebay")

        # Should still have storefront
        count = await InventoryReservationManager.get_reserved_count(db, build.id)
        assert count == 1

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)


@pytest.mark.unit
class TestOversellDetection:
    """Test oversell detection."""

    async def test_not_oversold_when_unreserved(self, db: AsyncSession):
        """Not oversold when unreserved."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        oversold = await InventoryReservationManager.is_oversold(db, build.id)

        assert oversold is False

    async def test_not_oversold_single_reservation(self, db: AsyncSession):
        """Not oversold with single reservation."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")

        oversold = await InventoryReservationManager.is_oversold(db, build.id)

        assert oversold is False

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)

    async def test_oversold_multiple_reservations(self, db: AsyncSession):
        """Oversold when >1 reservation."""
        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", True)

        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        await InventoryReservationManager.reserve_inventory(db, build.id, "ebay")
        await InventoryReservationManager.reserve_inventory(db, build.id, "storefront")

        oversold = await InventoryReservationManager.is_oversold(db, build.id)

        assert oversold is True

        set_flag_for_testing("FEATURE_LISTING_INVENTORY_RESERVATION", False)
