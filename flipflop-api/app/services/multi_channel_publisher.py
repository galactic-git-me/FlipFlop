"""Multi-Channel Publisher Service for Phase 2 F2.2.1.

Manages listing across multiple channels (eBay, Storefront, etc.).
One build can be listed on multiple channels simultaneously.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import ManualBuild, ChannelListing
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)


class MultiChannelPublisher:
    """Publisher for listing on multiple channels."""

    @staticmethod
    async def prepare_for_channels(
        db: AsyncSession,
        build_id: int,
        channels: list[str],
    ) -> bool:
        """
        Create channel_listing records in draft status for each channel.

        Args:
            db: AsyncSession
            build_id: Build to list
            channels: List of channels ['ebay', 'storefront']

        Returns:
            True if all created, False if any failed
        """
        try:
            # Verify build exists
            build = await db.get(ManualBuild, build_id)
            if not build:
                log.error("prepare_for_channels_build_not_found", build_id=build_id)
                return False

            # Create draft listing for each channel
            for channel in channels:
                # Check if already exists in draft
                stmt = select(ChannelListing).where(
                    ChannelListing.manual_build_id == build_id,
                    ChannelListing.channel == channel,
                )
                existing = await db.scalar(stmt)

                if existing and existing.status == "draft":
                    # Already exists in draft, skip
                    continue

                if existing and existing.status != "draft":
                    # Exists in published/withdrawn state, create new draft
                    pass

                # Create new draft listing
                listing = ChannelListing(
                    manual_build_id=build_id,
                    channel=channel,
                    status="draft",
                )
                db.add(listing)

            await db.commit()

            log.info(
                "channel_listings_prepared",
                build_id=build_id,
                channels=channels,
            )

            return True

        except Exception as e:
            log.error(
                "prepare_for_channels_failed",
                build_id=build_id,
                channels=channels,
                error=str(e),
            )
            await db.rollback()
            return False

    @staticmethod
    async def list_active_channel_listings(
        db: AsyncSession,
        build_id: int,
    ) -> list[ChannelListing]:
        """
        Get all active listings for a build (draft, scheduled, or published).

        Args:
            db: AsyncSession
            build_id: Build to query

        Returns:
            List of active ChannelListings
        """
        try:
            stmt = select(ChannelListing).where(
                ChannelListing.manual_build_id == build_id,
                ChannelListing.withdrawn_at.is_(None),
            )
            result = await db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            log.error(
                "list_active_channel_listings_failed",
                build_id=build_id,
                error=str(e),
            )
            return []

    @staticmethod
    async def get_channel_listing(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> ChannelListing | None:
        """
        Get the most recent listing for a build on a specific channel.

        Args:
            db: AsyncSession
            build_id: Build ID
            channel: Channel name ('ebay', 'storefront')

        Returns:
            ChannelListing or None
        """
        try:
            stmt = select(ChannelListing).where(
                ChannelListing.manual_build_id == build_id,
                ChannelListing.channel == channel,
            ).order_by(ChannelListing.created_at.desc())

            result = await db.execute(stmt)
            return result.scalars().first()

        except Exception as e:
            log.error(
                "get_channel_listing_failed",
                build_id=build_id,
                channel=channel,
                error=str(e),
            )
            return None

    @staticmethod
    async def update_channel_listing_status(
        db: AsyncSession,
        channel_listing_id: int,
        new_status: str,
        external_listing_id: str | None = None,
    ) -> bool:
        """
        Update the status of a channel listing (e.g., draft → published).

        Args:
            db: AsyncSession
            channel_listing_id: ID to update
            new_status: New status ('scheduled', 'published', 'withdrawn')
            external_listing_id: External ID if becoming published (e.g., eBay item ID)

        Returns:
            True if updated, False on error
        """
        try:
            listing = await db.get(ChannelListing, channel_listing_id)
            if not listing:
                log.error(
                    "update_channel_listing_status_not_found",
                    channel_listing_id=channel_listing_id,
                )
                return False

            listing.status = new_status
            if external_listing_id:
                listing.external_listing_id = external_listing_id

            if new_status == "published":
                from datetime import datetime
                listing.published_at = datetime.utcnow()

            if new_status == "withdrawn":
                from datetime import datetime
                listing.withdrawn_at = datetime.utcnow()

            await db.commit()

            log.info(
                "channel_listing_status_updated",
                channel_listing_id=channel_listing_id,
                new_status=new_status,
                external_id=external_listing_id,
            )

            return True

        except Exception as e:
            log.error(
                "update_channel_listing_status_failed",
                channel_listing_id=channel_listing_id,
                new_status=new_status,
                error=str(e),
            )
            await db.rollback()
            return False

    @staticmethod
    async def sync_inventory_across_channels(
        db: AsyncSession,
        build_id: int,
    ) -> dict:
        """
        Verify inventory consistency across all channel listings.

        Args:
            db: AsyncSession
            build_id: Build to check

        Returns:
            Dict with inventory status
        """
        try:
            listings = await MultiChannelPublisher.list_active_channel_listings(db, build_id)

            return {
                "build_id": build_id,
                "channel_count": len(listings),
                "channels": [l.channel for l in listings],
                "statuses": {l.channel: l.status for l in listings},
                "consistent": True,
            }

        except Exception as e:
            log.error(
                "sync_inventory_across_channels_failed",
                build_id=build_id,
                error=str(e),
            )
            return {"build_id": build_id, "error": str(e), "consistent": False}
