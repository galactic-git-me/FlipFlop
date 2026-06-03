"""
eBay Sales Tracking Service - Monitor sold listings and update flip records.

Polls eBay's Sales API periodically to:
1. Fetch completed/sold listings
2. Match to FlipFlop flip records
3. Update actual sale prices & profits
4. Trigger notifications
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import structlog

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


@dataclass
class SaleRecord:
    """A sold eBay listing matched to a flip."""
    flip_id: int
    ebay_listing_id: str
    buyer_id: str
    sale_price: float
    sold_at: datetime
    platform_fee: float
    actual_profit: float


class eBaySalesTracker:
    """
    Tracks sold items from eBay and updates flip records.
    """

    def __init__(self):
        self.poll_interval_seconds = 300  # Check every 5 minutes
        self.max_lookback_hours = 24  # Only look at sales from last 24 hours
        self._is_running = False

    async def start_polling(self) -> None:
        """Start background polling for sales."""
        if self._is_running:
            log.warning("ebay_sales_tracker.already_running")
            return

        self._is_running = True
        log.info("ebay_sales_tracker.started", poll_interval=self.poll_interval_seconds)

        try:
            while self._is_running:
                try:
                    await self.poll_sales()
                except Exception as e:
                    log.error("ebay_sales_tracker.poll_error", error=str(e))

                await asyncio.sleep(self.poll_interval_seconds)
        finally:
            self._is_running = False
            log.info("ebay_sales_tracker.stopped")

    async def stop_polling(self) -> None:
        """Stop background polling."""
        self._is_running = False

    async def poll_sales(self) -> dict:
        """
        Poll eBay for recently sold listings and update flip records.

        Returns:
            Dict with:
            - found: number of sold listings found
            - matched: number matched to flips
            - updated: number of flips updated
            - sales: list of SaleRecord objects
        """
        from app.database import AsyncSessionLocal
        from app.models.flip import Flip, FlipStage

        result = {
            "found": 0,
            "matched": 0,
            "updated": 0,
            "sales": [],
            "timestamp": datetime.utcnow(),
        }

        try:
            # Fetch sold listings from eBay
            sold_listings = await self._fetch_sold_listings()
            result["found"] = len(sold_listings)

            if not sold_listings:
                log.debug("ebay_sales_tracker.no_sales_found")
                return result

            # Match to flips and update
            async with AsyncSessionLocal() as db:
                for listing in sold_listings:
                    flip = await self._match_to_flip(db, listing["listing_id"])

                    if flip:
                        result["matched"] += 1
                        sale_record = await self._update_flip_with_sale(db, flip, listing)

                        if sale_record:
                            result["updated"] += 1
                            result["sales"].append(sale_record)

                            # Log the sale
                            log.info(
                                "ebay_sales_tracker.sale_detected",
                                flip_id=flip.id,
                                ebay_listing_id=listing["listing_id"],
                                sale_price=listing["sale_price"],
                                actual_profit=sale_record.actual_profit,
                            )

                await db.commit()

            log.info(
                "ebay_sales_tracker.poll_complete",
                found=result["found"],
                matched=result["matched"],
                updated=result["updated"],
            )

        except Exception as e:
            log.error("ebay_sales_tracker.poll_failed", error=str(e))

        return result

    async def _fetch_sold_listings(self) -> list[dict]:
        """
        Fetch recently sold listings from eBay API.

        Returns list of dicts with:
        - listing_id: eBay listing ID
        - sale_price: final sale price
        - sold_at: timestamp
        - buyer_id: eBay buyer ID
        - fees_paid: platform fees paid
        """
        # TODO: Implement eBay GetOrders API call
        # For now, return empty list (would be populated by real API)
        # This would call eBay's Trading API or REST API

        # Example implementation structure:
        # 1. Get eBay auth token from .env
        # 2. Call GetOrders API with timestamp filter (last 24 hours)
        # 3. Parse response and return sold listings

        log.debug(
            "ebay_sales_tracker.fetch_sold_listings",
            lookback_hours=self.max_lookback_hours,
        )

        # Placeholder - would be replaced with real API call
        return []

    async def _match_to_flip(self, db: AsyncSession, ebay_listing_id: str):
        """
        Match an eBay listing ID to a flip record.

        Returns the Flip if found, None otherwise.
        """
        from app.models.flip import Flip

        result = await db.execute(
            select(Flip).where(Flip.ebay_listing_id == ebay_listing_id)
        )
        flip = result.scalar_one_or_none()

        if not flip:
            log.debug(
                "ebay_sales_tracker.flip_not_found",
                ebay_listing_id=ebay_listing_id,
            )

        return flip

    async def _update_flip_with_sale(
        self, db: AsyncSession, flip, sale_listing: dict
    ) -> Optional[SaleRecord]:
        """
        Update a flip record with actual sale data.

        Returns SaleRecord if successful, None otherwise.
        """
        from app.models.flip import Flip, FlipStage

        try:
            sale_price = float(sale_listing["sale_price"])
            platform_fee = float(sale_listing.get("fees_paid", 0))
            actual_profit = sale_price - flip.total_cost - platform_fee

            # Update flip with sale data
            flip.actual_sale_price = sale_price
            flip.actual_profit = actual_profit
            flip.sale_platform = "ebay"
            flip.sold_at = sale_listing.get("sold_at", datetime.utcnow())
            flip.stage = FlipStage.sold
            flip.actual_selling_fee = platform_fee

            await db.flush()
            await db.refresh(flip)

            sale_record = SaleRecord(
                flip_id=flip.id,
                ebay_listing_id=flip.ebay_listing_id,
                buyer_id=sale_listing.get("buyer_id", "unknown"),
                sale_price=sale_price,
                sold_at=flip.sold_at,
                platform_fee=platform_fee,
                actual_profit=actual_profit,
            )

            log.info(
                "ebay_sales_tracker.flip_updated",
                flip_id=flip.id,
                actual_profit=actual_profit,
            )

            return sale_record

        except Exception as e:
            log.error(
                "ebay_sales_tracker.update_failed",
                flip_id=flip.id,
                error=str(e),
            )
            return None

    async def get_active_sales(self, db: AsyncSession, limit: int = 50) -> list[dict]:
        """
        Get flips that are currently listed for sale.

        Returns:
            List of flip dicts with listing details and metadata
        """
        from app.models.flip import Flip, FlipStage

        result = await db.execute(
            select(Flip)
            .where(Flip.stage == FlipStage.ready_for_sale)
            .order_by(Flip.created_at.desc())
            .limit(limit)
        )

        flips = result.scalars().all()

        return [
            {
                "id": flip.id,
                "ebay_listing_id": flip.ebay_listing_id,
                "title": flip.generated_title or "Untitled",
                "price": flip.current_estimated_resale or 0,
                "estimated_profit": flip.current_estimated_profit or 0,
                "listed_at": flip.created_at,
                "days_listed": (datetime.utcnow() - flip.created_at).days,
                "status": "active",
            }
            for flip in flips
        ]

    async def get_sales_dashboard(self, db: AsyncSession) -> dict:
        """
        Get sales dashboard metrics.

        Returns:
            Dashboard data with totals, averages, and trends
        """
        from app.models.flip import Flip, FlipStage
        from sqlalchemy import func

        # Get sold flips
        result = await db.execute(
            select(Flip).where(Flip.stage == FlipStage.sold).order_by(Flip.sold_at.desc())
        )
        sold_flips = result.scalars().all()

        # Calculate metrics
        total_sold = len(sold_flips)
        total_revenue = sum(f.actual_sale_price or 0 for f in sold_flips)
        total_profit = sum(f.actual_profit or 0 for f in sold_flips)
        total_invested = sum(f.total_cost for f in sold_flips)

        avg_profit = total_profit / total_sold if total_sold > 0 else 0
        avg_sale_price = total_revenue / total_sold if total_sold > 0 else 0

        # Time to sell calculation
        times_to_sell = []
        for flip in sold_flips:
            if flip.created_at and flip.sold_at:
                time_to_sell = (flip.sold_at - flip.created_at).days
                if time_to_sell >= 0:
                    times_to_sell.append(time_to_sell)

        avg_time_to_sell = sum(times_to_sell) / len(times_to_sell) if times_to_sell else 0

        # Get active listings count
        result = await db.execute(
            select(func.count(Flip.id)).where(Flip.stage == FlipStage.ready_for_sale)
        )
        active_listings = result.scalar() or 0

        # Get success rate (sold / total flips)
        result = await db.execute(select(func.count(Flip.id)))
        total_flips = result.scalar() or 1
        success_rate = (total_sold / total_flips * 100) if total_flips > 0 else 0

        # Recent sales (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await db.execute(
            select(Flip)
            .where(Flip.stage == FlipStage.sold)
            .where(Flip.sold_at >= seven_days_ago)
            .order_by(Flip.sold_at.desc())
        )
        recent_sales = recent_result.scalars().all()

        return {
            "summary": {
                "total_flips_sold": total_sold,
                "total_revenue": round(total_revenue, 2),
                "total_profit": round(total_profit, 2),
                "total_invested": round(total_invested, 2),
                "active_listings": active_listings,
                "success_rate": round(success_rate, 1),
            },
            "averages": {
                "profit_per_flip": round(avg_profit, 2),
                "sale_price": round(avg_sale_price, 2),
                "time_to_sell_days": round(avg_time_to_sell, 1),
            },
            "recent_sales": [
                {
                    "id": flip.id,
                    "title": flip.generated_title or "Untitled",
                    "sale_price": flip.actual_sale_price,
                    "profit": flip.actual_profit,
                    "sold_at": flip.sold_at.isoformat() if flip.sold_at else None,
                    "profit_margin_pct": round(
                        (flip.actual_profit / flip.total_cost * 100)
                        if flip.total_cost > 0
                        else 0,
                        1,
                    ),
                }
                for flip in recent_sales
            ],
        }

    async def get_sale_details(self, db: AsyncSession, flip_id: int) -> dict:
        """Get detailed information about a specific sale."""
        from app.models.flip import Flip

        flip = await db.get(Flip, flip_id)
        if not flip:
            return {}

        return {
            "id": flip.id,
            "title": flip.generated_title or "Untitled",
            "base_item": flip.listing.title if flip.listing else "Unknown",
            "cost": {
                "base_cost": flip.base_cost,
                "upgrade_cost": flip.upgrade_cost,
                "total_cost": flip.total_cost,
            },
            "sale": {
                "sale_price": flip.actual_sale_price,
                "platform": flip.sale_platform,
                "sold_at": flip.sold_at.isoformat() if flip.sold_at else None,
            },
            "profit": {
                "estimated": flip.initial_estimated_profit,
                "actual": flip.actual_profit,
                "fees": flip.actual_selling_fee,
                "margin_pct": round(
                    (flip.actual_profit / flip.total_cost * 100)
                    if flip.total_cost > 0
                    else 0,
                    1,
                ),
            },
            "ebay": {
                "listing_id": flip.ebay_listing_id,
            },
        }


# Global instance
_tracker: Optional[eBaySalesTracker] = None


def get_tracker() -> eBaySalesTracker:
    """Get or create the global sales tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = eBaySalesTracker()
    return _tracker


def start_sales_polling() -> None:
    """Start background sales polling."""
    tracker = get_tracker()
    # Schedule as background task in app startup
    import asyncio

    asyncio.create_task(tracker.start_polling())
    log.info("ebay_sales_tracker.polling_scheduled")
