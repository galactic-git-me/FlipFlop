"""Dry-Run Validator for Phase 2 F2.2.2.

Validates listing without committing changes.
Shows what would happen if listing were published.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass
from app.models import ManualBuild
from app.services.feature_flags import is_enabled, FeatureFlags
from app.services.inventory_reservation import InventoryReservationManager
import structlog

log = structlog.get_logger(__name__)


@dataclass
class DryRunResult:
    """Result of dry-run validation."""
    valid: bool
    build_id: int
    channel: str
    errors: list[str]
    warnings: list[str]
    metadata: dict


class DryRunValidator:
    """Validator for listing without publishing."""

    @staticmethod
    async def validate_listing(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> DryRunResult:
        """
        Validate listing without publishing.

        Args:
            db: AsyncSession
            build_id: Build to validate
            channel: Channel to validate for

        Returns:
            DryRunResult with validation status
        """
        errors = []
        warnings = []
        metadata = {}

        try:
            # Check build exists and is ready
            build = await db.get(ManualBuild, build_id)
            if not build:
                errors.append(f"Build {build_id} not found")
                return DryRunResult(
                    valid=False,
                    build_id=build_id,
                    channel=channel,
                    errors=errors,
                    warnings=warnings,
                    metadata=metadata,
                )

            # Check build status
            if build.status not in ("built", "listed"):
                errors.append(f"Build status is '{build.status}', must be 'built' or 'listed'")

            # Check pricing
            if not build.ebay_price or build.ebay_price <= 0:
                errors.append("Build has no price or invalid price")
            else:
                metadata["price"] = build.ebay_price

            # Check title/description
            if not build.generated_title:
                errors.append("No title generated")
            if not build.generated_description:
                errors.append("No description generated")

            # Check photos
            if not build.photos or len(build.photos) == 0:
                warnings.append("No photos attached")
            else:
                metadata["photo_count"] = len(build.photos)

            # Channel-specific checks
            if channel == "ebay":
                if not build.ebay_condition:
                    errors.append("eBay condition not set")
                metadata["channel"] = "ebay"

            elif channel == "storefront":
                if not build.storefront_product_id:
                    warnings.append("Storefront product ID not set")
                metadata["channel"] = "storefront"

            else:
                errors.append(f"Unknown channel: {channel}")

            # Check inventory availability (if reservation enabled)
            if is_enabled(FeatureFlags.LISTING_INVENTORY_RESERVATION):
                available = await InventoryReservationManager.check_availability(
                    db, build_id, 1
                )
                if not available:
                    errors.append("Insufficient inventory for listing")
                metadata["inventory_available"] = available

            valid = len(errors) == 0

            log.info(
                "dry_run_validation_complete",
                build_id=build_id,
                channel=channel,
                valid=valid,
                error_count=len(errors),
                warning_count=len(warnings),
            )

            return DryRunResult(
                valid=valid,
                build_id=build_id,
                channel=channel,
                errors=errors,
                warnings=warnings,
                metadata=metadata,
            )

        except Exception as e:
            log.error(
                "dry_run_validation_failed",
                build_id=build_id,
                channel=channel,
                error=str(e),
            )
            return DryRunResult(
                valid=False,
                build_id=build_id,
                channel=channel,
                errors=[f"Validation error: {str(e)}"],
                warnings=warnings,
                metadata=metadata,
            )

    @staticmethod
    async def preview_publication(
        db: AsyncSession,
        build_id: int,
        channel: str,
    ) -> dict:
        """
        Show what the listing would look like.

        Args:
            db: AsyncSession
            build_id: Build ID
            channel: Channel

        Returns:
            Preview dict with title, price, description, etc.
        """
        try:
            build = await db.get(ManualBuild, build_id)
            if not build:
                return {"error": f"Build {build_id} not found"}

            preview = {
                "build_id": build_id,
                "channel": channel,
                "title": build.generated_title,
                "price": build.ebay_price,
                "description_length": len(build.generated_description or ""),
                "photo_count": len(build.photos or []),
                "condition": build.ebay_condition,
            }

            log.info(
                "listing_preview_generated",
                build_id=build_id,
                channel=channel,
                title=build.generated_title,
            )

            return preview

        except Exception as e:
            log.error(
                "preview_publication_failed",
                build_id=build_id,
                channel=channel,
                error=str(e),
            )
            return {"error": str(e)}

    @staticmethod
    async def simulate_inventory_change(
        db: AsyncSession,
        build_id: int,
        channels: list[str],
    ) -> dict:
        """
        Simulate inventory changes if listing to multiple channels.

        Args:
            db: AsyncSession
            build_id: Build ID
            channels: Channels to list to

        Returns:
            Inventory change simulation
        """
        try:
            reserved = await InventoryReservationManager.get_reserved_count(db, build_id)

            return {
                "build_id": build_id,
                "channels": channels,
                "current_reserved": reserved,
                "would_reserve": len(channels),
                "total_after_listing": reserved + len(channels),
                "safe": (reserved + len(channels)) <= 1,
            }

        except Exception as e:
            log.error(
                "simulate_inventory_change_failed",
                build_id=build_id,
                channels=channels,
                error=str(e),
            )
            return {"error": str(e)}
