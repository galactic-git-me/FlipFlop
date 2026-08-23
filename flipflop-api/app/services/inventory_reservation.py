"""Inventory Reservation Manager for Phase 2 F2.2.4.

Manages inventory reservations to prevent overselling across channels.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from app.models import InventoryReservation, ManualBuild
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)


class InventoryReservationManager:
    """Manages inventory reservations."""

    @staticmethod
    async def reserve_inventory(
        db: AsyncSession,
        build_id: int,
        channel: str,
        quantity: int = 1,
    ) -> InventoryReservation | None:
        """
        Reserve inventory for a channel.

        Args:
            db: AsyncSession
            build_id: Build to reserve
            channel: Channel name
            quantity: Quantity to reserve (default 1)

        Returns:
            InventoryReservation if created, None on error
        """
        if not is_enabled(FeatureFlags.LISTING_INVENTORY_RESERVATION):
            log.info(
                "inventory_reservation_skipped_flag_off",
                build_id=build_id,
                channel=channel,
            )
            return None

        try:
            # Verify build exists
            build = await db.get(ManualBuild, build_id)
            if not build:
                log.error(
                    "reserve_inventory_build_not_found",
                    build_id=build_id,
                    channel=channel,
                )
                return None

            # Check if already reserved for this channel
            stmt = select(InventoryReservation).where(
                InventoryReservation.manual_build_id == build_id,
                InventoryReservation.channel == channel,
                InventoryReservation.released_at.is_(None),
            )
            existing = await db.scalar(stmt)

            if existing:
                log.warning(
                    "inventory_already_reserved",
                    build_id=build_id,
                    channel=channel,
                )
                return existing

            # Create reservation
            reservation = InventoryReservation(
                manual_build_id=build_id,
                channel=channel,
                quantity_reserved=quantity,
            )
            db.add(reservation)
            await db.commit()

            log.info(
                "inventory_reserved",
                build_id=build_id,
                channel=channel,
                quantity=quantity,
            )

            return reservation

        except Exception as e:
            log.error(
                "reserve_inventory_failed",
                build_id=build_id,
                channel=channel,
                quantity=quantity,
                error=str(e),
            )
            await db.rollback()
            return None

    @staticmethod
    async def get_reserved_count(
        db: AsyncSession,
        build_id: int,
    ) -> int:
        """
        Get total reserved inventory for a build.

        Args:
            db: AsyncSession
            build_id: Build ID

        Returns:
            Total reserved quantity
        """
        try:
            stmt = select(func.sum(InventoryReservation.quantity_reserved)).where(
                InventoryReservation.manual_build_id == build_id,
                InventoryReservation.released_at.is_(None),
            )
            result = await db.scalar(stmt)
            return result or 0

        except Exception as e:
            log.error(
                "get_reserved_count_failed",
                build_id=build_id,
                error=str(e),
            )
            return 0

    @staticmethod
    async def check_availability(
        db: AsyncSession,
        build_id: int,
        quantity_needed: int = 1,
    ) -> bool:
        """
        Check if enough inventory is available (not reserved).

        Args:
            db: AsyncSession
            build_id: Build ID
            quantity_needed: Quantity to check for

        Returns:
            True if available, False if reserved/unavailable
        """
        try:
            reserved = await InventoryReservationManager.get_reserved_count(db, build_id)
            # Assume 1 unit available per build (not reserved = 0, can list once)
            available = max(0, 1 - reserved)
            result = available >= quantity_needed

            log.debug(
                "inventory_availability_checked",
                build_id=build_id,
                quantity_needed=quantity_needed,
                reserved=reserved,
                available=available,
                sufficient=result,
            )

            return result

        except Exception as e:
            log.error(
                "check_availability_failed",
                build_id=build_id,
                quantity_needed=quantity_needed,
                error=str(e),
            )
            return False

    @staticmethod
    async def release_reservation(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> bool:
        """
        Release reservation when listing withdrawn.

        Args:
            db: AsyncSession
            build_id: Build ID
            channel: Channel to release

        Returns:
            True if released, False on error
        """
        try:
            stmt = select(InventoryReservation).where(
                InventoryReservation.manual_build_id == build_id,
                InventoryReservation.channel == channel,
                InventoryReservation.released_at.is_(None),
            )
            reservation = await db.scalar(stmt)

            if not reservation:
                log.warning(
                    "release_reservation_not_found",
                    build_id=build_id,
                    channel=channel,
                )
                return False

            reservation.released_at = datetime.utcnow()
            await db.commit()

            log.info(
                "inventory_reservation_released",
                build_id=build_id,
                channel=channel,
                reservation_id=reservation.id,
            )

            return True

        except Exception as e:
            log.error(
                "release_reservation_failed",
                build_id=build_id,
                channel=channel,
                error=str(e),
            )
            await db.rollback()
            return False

    @staticmethod
    async def is_oversold(
        db: AsyncSession,
        build_id: int,
    ) -> bool:
        """
        Check if reserved > available (inventory bug).

        Args:
            db: AsyncSession
            build_id: Build ID

        Returns:
            True if oversold, False otherwise
        """
        try:
            reserved = await InventoryReservationManager.get_reserved_count(db, build_id)
            oversold = reserved > 1  # More than 1 unit reserved for single build

            if oversold:
                log.warning(
                    "inventory_oversold_detected",
                    build_id=build_id,
                    reserved=reserved,
                )

            return oversold

        except Exception as e:
            log.error(
                "is_oversold_check_failed",
                build_id=build_id,
                error=str(e),
            )
            return False
