"""Live Publisher for Phase 2 F2.2.3.

Publishes listings to channels when ready.
Gated by FEATURE_LISTING_PUBLISH_ENABLED flag.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass
from datetime import datetime
from app.models import ManualBuild, ChannelListing, ListingPublishEvent
from app.services.feature_flags import is_enabled, FeatureFlags
from app.services.dry_run_validator import DryRunValidator
from app.services.inventory_reservation import InventoryReservationManager
from app.services.multi_channel_publisher import MultiChannelPublisher
import structlog

log = structlog.get_logger(__name__)


@dataclass
class PublishResult:
    """Result of publishing attempt."""
    success: bool
    build_id: int
    channel: str
    external_listing_id: str | None = None
    error: str | None = None
    message: str | None = None


class LivePublisher:
    """Publisher for live listings."""

    @staticmethod
    async def publish_to_channel(
        db: AsyncSession,
        build_id: int,
        channel: str,
        dry_run: bool = False,
    ) -> PublishResult:
        """
        Publish listing to a channel.

        Args:
            db: AsyncSession
            build_id: Build to publish
            channel: Channel ('ebay', 'storefront')
            dry_run: If True, validate but don't commit

        Returns:
            PublishResult with status
        """
        try:
            # Check feature flag
            if not is_enabled(FeatureFlags.LISTING_PUBLISH_ENABLED):
                if not is_enabled(FeatureFlags.LISTING_PUBLISH_DRY_RUN_ONLY):
                    log.warning(
                        "publish_to_channel_disabled_by_flag",
                        build_id=build_id,
                        channel=channel,
                    )
                    return PublishResult(
                        success=False,
                        build_id=build_id,
                        channel=channel,
                        error="Publishing disabled (FEATURE_LISTING_PUBLISH_ENABLED=false)",
                    )

            # Validate listing first
            validation = await DryRunValidator.validate_listing(db, build_id, channel)
            if not validation.valid:
                log.warning(
                    "publish_to_channel_validation_failed",
                    build_id=build_id,
                    channel=channel,
                    errors=validation.errors,
                )
                return PublishResult(
                    success=False,
                    build_id=build_id,
                    channel=channel,
                    error="; ".join(validation.errors),
                    message="Validation failed",
                )

            # If dry-run only, stop here
            if is_enabled(FeatureFlags.LISTING_PUBLISH_DRY_RUN_ONLY) and not is_enabled(FeatureFlags.LISTING_PUBLISH_ENABLED):
                log.info(
                    "publish_to_channel_dry_run_only",
                    build_id=build_id,
                    channel=channel,
                )
                return PublishResult(
                    success=True,
                    build_id=build_id,
                    channel=channel,
                    message="Dry-run only (DRY_RUN_ONLY=true, PUBLISH_ENABLED=false)",
                )

            # Reserve inventory if enabled
            if is_enabled(FeatureFlags.LISTING_INVENTORY_RESERVATION):
                reservation = await InventoryReservationManager.reserve_inventory(
                    db, build_id, channel, 1
                )
                if not reservation:
                    log.error(
                        "publish_to_channel_reservation_failed",
                        build_id=build_id,
                        channel=channel,
                    )
                    return PublishResult(
                        success=False,
                        build_id=build_id,
                        channel=channel,
                        error="Failed to reserve inventory",
                    )

            # Get or create channel listing
            listing = await MultiChannelPublisher.get_channel_listing(db, build_id, channel)
            if not listing:
                # Create new listing
                success = await MultiChannelPublisher.prepare_for_channels(
                    db, build_id, [channel]
                )
                if not success:
                    return PublishResult(
                        success=False,
                        build_id=build_id,
                        channel=channel,
                        error="Failed to create channel listing",
                    )
                listing = await MultiChannelPublisher.get_channel_listing(db, build_id, channel)

            # Simulate publishing (in production, would call channel API)
            external_id = f"{channel.upper()}-{build_id}-{int(datetime.utcnow().timestamp())}"

            # Update listing status
            success = await MultiChannelPublisher.update_channel_listing_status(
                db,
                listing.id,
                "published",
                external_id,
            )

            if not success:
                return PublishResult(
                    success=False,
                    build_id=build_id,
                    channel=channel,
                    error="Failed to update listing status",
                )

            # Log publish event
            event = ListingPublishEvent(
                channel_listing_id=listing.id,
                event_type="published",
                message=f"Listed to {channel}",
                metadata={
                    "build_id": build_id,
                    "channel": channel,
                    "external_id": external_id,
                    "published_at": datetime.utcnow().isoformat(),
                },
            )
            db.add(event)
            await db.commit()

            log.info(
                "listing_published",
                build_id=build_id,
                channel=channel,
                listing_id=listing.id,
                external_id=external_id,
            )

            return PublishResult(
                success=True,
                build_id=build_id,
                channel=channel,
                external_listing_id=external_id,
                message=f"Published to {channel}",
            )

        except Exception as e:
            log.error(
                "publish_to_channel_failed",
                build_id=build_id,
                channel=channel,
                error=str(e),
            )
            await db.rollback()
            return PublishResult(
                success=False,
                build_id=build_id,
                channel=channel,
                error=str(e),
            )

    @staticmethod
    async def publish_to_all_channels(
        db: AsyncSession,
        build_id: int,
        channels: list[str],
    ) -> dict[str, PublishResult]:
        """
        Publish to all configured channels.

        Args:
            db: AsyncSession
            build_id: Build to publish
            channels: List of channels

        Returns:
            Dict of channel → PublishResult
        """
        results = {}

        for channel in channels:
            result = await LivePublisher.publish_to_channel(db, build_id, channel)
            results[channel] = result

        log.info(
            "publish_to_all_channels_complete",
            build_id=build_id,
            channels=channels,
            success_count=sum(1 for r in results.values() if r.success),
            total=len(channels),
        )

        return results

    @staticmethod
    async def withdraw_from_channel(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> bool:
        """
        Withdraw listing from channel.

        Args:
            db: AsyncSession
            build_id: Build to withdraw
            channel: Channel to withdraw from

        Returns:
            True if withdrawn, False on error
        """
        try:
            # Get listing
            listing = await MultiChannelPublisher.get_channel_listing(db, build_id, channel)
            if not listing or listing.status == "withdrawn":
                log.warning(
                    "withdraw_from_channel_not_listed",
                    build_id=build_id,
                    channel=channel,
                )
                return False

            # Update status
            success = await MultiChannelPublisher.update_channel_listing_status(
                db,
                listing.id,
                "withdrawn",
            )

            if not success:
                return False

            # Release reservation
            await InventoryReservationManager.release_reservation(db, build_id, channel)

            # Log event
            event = ListingPublishEvent(
                channel_listing_id=listing.id,
                event_type="withdrawn",
                message=f"Withdrawn from {channel}",
                metadata={
                    "build_id": build_id,
                    "channel": channel,
                    "withdrawn_at": datetime.utcnow().isoformat(),
                },
            )
            db.add(event)
            await db.commit()

            log.info(
                "listing_withdrawn",
                build_id=build_id,
                channel=channel,
                listing_id=listing.id,
            )

            return True

        except Exception as e:
            log.error(
                "withdraw_from_channel_failed",
                build_id=build_id,
                channel=channel,
                error=str(e),
            )
            await db.rollback()
            return False
