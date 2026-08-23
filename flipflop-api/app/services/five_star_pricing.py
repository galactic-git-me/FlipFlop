"""
Five-Star Auto-Pricing Service for Phase 2 (F2.1.3).

Automatically adjusts build price down if seller rating drops below 5 stars.
Principle: High-rated sellers command premium pricing; low ratings need discounts.

Gated by FEATURE_PRICE_ALERTS_FIVE_STAR_AUTO flag.

Example:
- Listing price: £99.99
- Seller rating: 4.5 stars (drops from 5.0)
- Auto reduction: 3% (market standard for <5 star penalty)
- New price: £96.99

Prevents: Stale listings with outdated pricing when seller reputation changes.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ManualBuild
from app.services.money import Money
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)

# Auto-pricing reduction matrix: star_rating → discount percentage
STAR_RATING_DISCOUNTS = {
    5.0: Money(0, "GBP"),      # Perfect rating, no reduction
    4.5: Money(0.03, "GBP"),   # 3% reduction
    4.0: Money(0.05, "GBP"),   # 5% reduction
    3.5: Money(0.08, "GBP"),   # 8% reduction
    3.0: Money(0.10, "GBP"),   # 10% reduction
    2.5: Money(0.15, "GBP"),   # 15% reduction
    2.0: Money(0.20, "GBP"),   # 20% reduction
    1.0: Money(0.25, "GBP"),   # 25% reduction (minimum usable rating)
}


class FiveStarPricingService:
    """Auto-price adjustments based on seller rating."""

    @staticmethod
    def get_discount_for_rating(star_rating: float) -> Money:
        """
        Get price reduction percentage for a seller rating.

        Args:
            star_rating: Seller rating (0.0 to 5.0)

        Returns:
            Money object with discount (e.g., Money(0.05, "GBP") for 5%)
        """
        if star_rating < 0 or star_rating > 5.0:
            raise ValueError(f"Star rating must be 0.0-5.0, got {star_rating}")

        # Find matching or closest lower rating
        matching_rating = None
        for rating in sorted(STAR_RATING_DISCOUNTS.keys(), reverse=True):
            if star_rating >= rating:
                matching_rating = rating
                break

        if matching_rating is None:
            # Below minimum (shouldn't happen with validation above)
            matching_rating = 1.0

        return STAR_RATING_DISCOUNTS[matching_rating]

    @staticmethod
    def calculate_adjusted_price(
        current_price: Money,
        star_rating: float,
    ) -> Money:
        """
        Calculate price after five-star adjustment.

        Args:
            current_price: Current listing price
            star_rating: Seller rating (0.0-5.0)

        Returns:
            Adjusted price (Money object)

        Example:
            current = Money(99.99, "GBP")
            rating = 4.5
            adjusted = calculate_adjusted_price(current, rating)
            # Returns Money(96.99, "GBP") (3% reduction)
        """
        if current_price.currency != "GBP":
            raise ValueError(f"Only GBP prices supported, got {current_price.currency}")

        discount = FiveStarPricingService.get_discount_for_rating(star_rating)

        # Multiply current price by discount (as decimal: 0.03 for 3%)
        reduction = current_price * float(discount.amount)

        adjusted = current_price - reduction

        return adjusted.round()

    @staticmethod
    async def should_auto_price(
        db: AsyncSession,
        manual_build_id: int,
        seller_rating: float,
    ) -> bool:
        """
        Check if auto-pricing should apply to this build.

        Args:
            db: AsyncSession
            manual_build_id: Build to check
            seller_rating: Current seller rating

        Returns:
            True if auto-pricing should run, False otherwise
        """
        # Feature flag must be enabled
        if not is_enabled(FeatureFlags.PRICE_ALERTS_FIVE_STAR_AUTO):
            return False

        # Build must exist and be listed
        build = await db.get(ManualBuild, manual_build_id)
        if not build:
            return False

        # Only apply to active listings
        if build.status not in ("listed", "ready_for_sale"):
            return False

        # Only apply if rating is below 5.0
        if seller_rating >= 5.0:
            return False

        return True

    @staticmethod
    async def apply_auto_pricing(
        db: AsyncSession,
        manual_build_id: int,
        seller_rating: float,
    ) -> bool:
        """
        Apply auto-pricing adjustment to a build.

        Args:
            db: AsyncSession
            manual_build_id: Build to adjust
            seller_rating: Current seller rating

        Returns:
            True if adjusted, False if skipped or error
        """
        # Check if should apply
        if not await FiveStarPricingService.should_auto_price(
            db, manual_build_id, seller_rating
        ):
            return False

        try:
            build = await db.get(ManualBuild, manual_build_id)
            if not build or not build.ebay_price:
                return False

            current_price = Money(build.ebay_price, "GBP")
            adjusted_price = FiveStarPricingService.calculate_adjusted_price(
                current_price, seller_rating
            )

            # Only update if price actually changed
            if adjusted_price == current_price:
                return False

            # Store old price for logging
            old_price = build.ebay_price
            new_price = adjusted_price.to_float()

            # Update build
            build.ebay_price = new_price
            build.price_last_recalculated_at = None  # Force recalculation

            await db.commit()

            log.info(
                "five_star_auto_pricing_applied",
                build_id=manual_build_id,
                old_price=old_price,
                new_price=new_price,
                seller_rating=seller_rating,
                discount_pct=float(FiveStarPricingService.get_discount_for_rating(seller_rating).amount) * 100,
            )

            return True

        except Exception as e:
            log.error(
                "five_star_auto_pricing_failed",
                build_id=manual_build_id,
                seller_rating=seller_rating,
                error=str(e),
            )
            await db.rollback()
            return False

    @staticmethod
    def format_discount_explanation(star_rating: float) -> str:
        """
        Generate human-readable explanation of discount.

        Args:
            star_rating: Seller rating

        Returns:
            Explanation string (e.g., "4.5-star seller: 3% reduction")
        """
        if star_rating >= 5.0:
            return "Perfect 5-star rating: No reduction"

        discount = FiveStarPricingService.get_discount_for_rating(star_rating)
        discount_pct = float(discount.amount) * 100

        return f"{star_rating}-star seller: {discount_pct:.0f}% reduction"
