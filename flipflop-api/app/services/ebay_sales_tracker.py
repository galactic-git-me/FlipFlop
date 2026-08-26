"""
eBay Sales Tracking Service - polls eBay's Fulfillment (order) API for each
Flip that's currently listed on eBay and marks it sold the moment a paid
order shows up, via app.services.flip_sale_processor.process_flip_sale
(same idempotent "mark sold + write intelligence + fire flip_resale_detected
alert" path used by the manual POST /flips/{id}/sold endpoint).

Runs on a schedule via app.workers.scheduler (settings.ebay_sales_poll_interval_seconds).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
import structlog

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


class eBaySalesTracker:
    """
    Tracks sold items from eBay and updates flip records.
    """

    def __init__(self):
        self.lookback_days = 90  # how far back to search eBay orders per listing

    async def poll_sales(self) -> dict:
        """
        Check every eBay-listed, not-yet-sold Flip against eBay's order API
        and mark it sold if a paid order is found.

        Returns:
            Dict with:
            - found: number of eBay-listed flips checked
            - matched: number with a paid eBay order found
            - updated: number of flips newly marked sold
            - sales: list of {flip_id, ebay_listing_id, ebay_order_id, sale_price, actual_profit}
        """
        from app.database import AsyncSessionLocal
        from app.models.flip import Flip, FlipStage
        from app.services.ebay_order_sync import find_order_for_listing, EbayOrderSyncError
        from app.services.flip_sale_processor import process_flip_sale
        from app.config import get_settings

        settings = get_settings()
        result = {
            "found": 0,
            "matched": 0,
            "updated": 0,
            "sales": [],
            "timestamp": datetime.utcnow(),
        }

        try:
            async with AsyncSessionLocal() as db:
                query = await db.execute(
                    select(Flip).where(
                        Flip.stage == FlipStage.ready_for_sale,
                        Flip.ebay_listing_id.isnot(None),
                    )
                )
                active_flips = query.scalars().all()
                result["found"] = len(active_flips)

                for flip in active_flips:
                    try:
                        order = await find_order_for_listing(
                            flip.ebay_listing_id,
                            environment=settings.ebay_listing_environment,
                            lookback_days=self.lookback_days,
                        )
                    except EbayOrderSyncError as e:
                        log.warning(
                            "ebay_sales_tracker.order_lookup_failed",
                            flip_id=flip.id,
                            ebay_listing_id=flip.ebay_listing_id,
                            error=str(e),
                        )
                        continue

                    if order is None:
                        continue

                    result["matched"] += 1
                    updated_flip = await process_flip_sale(
                        db,
                        flip,
                        sale_price=order.sale_price,
                        sale_platform="ebay",
                        source="ebay_order_api",
                    )
                    if updated_flip:
                        result["updated"] += 1
                        result["sales"].append({
                            "flip_id": flip.id,
                            "ebay_listing_id": flip.ebay_listing_id,
                            "ebay_order_id": order.order_id,
                            "sale_price": order.sale_price,
                            "actual_profit": updated_flip.actual_profit,
                        })

                # Manual builds use the same eBay account but have their own
                # lifecycle model. Reconcile every locally-active/unknown
                # listing so disappeared offers become sold or ended instead
                # of remaining falsely "listed" forever.
                from app.models.manual_build import ManualBuild
                from app.services.ebay_listing_reconciliation import reconcile_manual_build_listing
                manual_rows = (await db.execute(select(ManualBuild).where(
                    ManualBuild.ebay_listing_id.isnot(None),
                    ManualBuild.ebay_listing_status.in_(["active", "unknown"]),
                ))).scalars().all()
                orphaned_local_rows = (await db.execute(select(ManualBuild).where(
                    ManualBuild.status == "listed",
                    ManualBuild.ebay_listing_id.is_(None),
                ))).scalars().all()
                for build in orphaned_local_rows:
                    build.status = "built"
                    build.ebay_listing_status = "never_listed"
                    build.ebay_listing_status_checked_at = datetime.utcnow()
                result["manual_builds_checked"] = len(manual_rows)
                result["manual_builds_changed"] = len(orphaned_local_rows)
                for build in manual_rows:
                    previous = build.ebay_listing_status
                    try:
                        current = await reconcile_manual_build_listing(build, db, force=True)
                        if current != previous:
                            result["manual_builds_changed"] += 1
                    except Exception as exc:
                        log.warning(
                            "ebay_sales_tracker.manual_build_reconcile_failed",
                            build_id=build.id,
                            listing_id=build.ebay_listing_id,
                            error=str(exc),
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
