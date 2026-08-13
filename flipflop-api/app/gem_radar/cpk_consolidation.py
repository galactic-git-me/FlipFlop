"""
Canonical Product Key (CPK) consolidation and pricing aggregation.

Groups listings by CPK (derived from LLM extraction) and aggregates pricing
across vendors in the current run. Creates a unified market baseline per
product, improving pricing accuracy beyond EPID-only approach.

Usage:
  await consolidate_cpk_pricing(db)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from sqlalchemy import text

import structlog

log = structlog.get_logger(__name__)


@dataclass
class CPKPricingAggregate:
    """Aggregated pricing for a single CPK."""
    cpk: str
    category: str | None
    brand: str | None
    model: str | None
    listing_count: int
    vendor_count: int
    median_new_price: float | None
    median_used_price: float | None
    min_price: float | None
    max_price: float | None
    price_variance: float  # Coefficient of variation


async def consolidate_cpk_pricing(db) -> dict[str, CPKPricingAggregate]:
    """
    Consolidate pricing by CPK across all vendors in current run.

    Groups listings with the same CPK and aggregates their pricing data.
    Generates a unified market price baseline per product.

    Returns:
        Dict mapping CPK → CPKPricingAggregate
    """
    log.info("cpk_consolidation.start")

    # Fetch all listings with CPK, grouped by CPK
    query = """
    SELECT
        cpk,
        category,
        (cpk_data->>'brand')::text as brand,
        (cpk_data->>'model')::text as model,
        COUNT(*) as listing_count,
        COUNT(DISTINCT source) as vendor_count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY market_new_price) as median_new,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY market_used_price) as median_used,
        MIN(COALESCE(market_new_price, market_used_price)) as min_price,
        MAX(COALESCE(market_new_price, market_used_price)) as max_price
    FROM gem_radar_scored_listings
    WHERE cpk IS NOT NULL
    GROUP BY cpk, category, brand, model
    ORDER BY listing_count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    log.info("cpk_consolidation.fetched", groups=len(rows))

    aggregates: dict[str, CPKPricingAggregate] = {}

    for row in rows:
        # Row is a tuple: (cpk, category, brand, model, listing_count, vendor_count, median_new, median_used, min_price, max_price)
        cpk = row[0]
        category = row[1]
        brand = row[2]
        model = row[3]
        listing_count = row[4]
        vendor_count = row[5]
        median_new = row[6]
        median_used = row[7]
        min_price = row[8]
        max_price = row[9]

        prices = [p for p in [median_new, median_used] if p is not None]

        # Calculate coefficient of variation (price variance)
        price_variance = 0.0
        if prices and max_price and min_price:
            try:
                std_dev = statistics.stdev(prices) if len(prices) > 1 else 0
                mean = statistics.mean(prices)
                if mean > 0:
                    price_variance = (std_dev / mean) * 100
            except Exception:
                pass

        aggregates[cpk] = CPKPricingAggregate(
            cpk=cpk,
            category=category,
            brand=brand,
            model=model,
            listing_count=listing_count,
            vendor_count=vendor_count,
            median_new_price=median_new,
            median_used_price=median_used,
            min_price=min_price,
            max_price=max_price,
            price_variance=price_variance,
        )

    log.info("cpk_consolidation.aggregated", cpks=len(aggregates))

    # Store aggregates in new cpk_pricing_index table for lookup during scoring
    create_table_query = """
    CREATE TABLE IF NOT EXISTS cpk_pricing_index (
        cpk VARCHAR(16) PRIMARY KEY,
        category VARCHAR(50),
        brand VARCHAR(100),
        model VARCHAR(200),
        listing_count INT,
        vendor_count INT,
        median_new_price FLOAT,
        median_used_price FLOAT,
        min_price FLOAT,
        max_price FLOAT,
        price_variance FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    await db.execute(text(create_table_query))

    # Clear old data and insert new aggregates
    await db.execute(text("DELETE FROM cpk_pricing_index"))

    insert_query = """
    INSERT INTO cpk_pricing_index
    (cpk, category, brand, model, listing_count, vendor_count,
     median_new_price, median_used_price, min_price, max_price, price_variance)
    VALUES (:cpk, :category, :brand, :model, :listing_count, :vendor_count,
            :median_new, :median_used, :min_price, :max_price, :price_variance)
    """

    for cpk, agg in aggregates.items():
        await db.execute(
            text(insert_query),
            {
                "cpk": cpk,
                "category": agg.category,
                "brand": agg.brand,
                "model": agg.model,
                "listing_count": agg.listing_count,
                "vendor_count": agg.vendor_count,
                "median_new": agg.median_new_price,
                "median_used": agg.median_used_price,
                "min_price": agg.min_price,
                "max_price": agg.max_price,
                "price_variance": agg.price_variance,
            },
        )

    await db.commit()

    log.info(
        "cpk_consolidation.complete",
        cpks_stored=len(aggregates),
        summary={
            "avg_listings_per_cpk": (
                sum(a.listing_count for a in aggregates.values()) / len(aggregates)
                if aggregates
                else 0
            ),
            "avg_vendors_per_cpk": (
                sum(a.vendor_count for a in aggregates.values()) / len(aggregates)
                if aggregates
                else 0
            ),
            "cpks_with_vendor_diversity": sum(
                1 for a in aggregates.values() if a.vendor_count > 1
            ),
        },
    )

    return aggregates


async def get_cpk_price(db, cpk: str, use_new: bool = True) -> float | None:
    """
    Look up aggregated price for a CPK.

    Args:
        db: Database session
        cpk: Canonical Product Key
        use_new: If True, prefer median_new_price; fall back to median_used_price

    Returns:
        Aggregated price or None if CPK not found
    """
    query = """
    SELECT median_new_price, median_used_price
    FROM cpk_pricing_index
    WHERE cpk = :cpk
    """

    result = await db.execute(text(query), {"cpk": cpk})
    row = result.fetchone()

    if not row:
        return None

    median_new_price = row[0]
    median_used_price = row[1]

    if use_new:
        return median_new_price or median_used_price
    else:
        return median_used_price or median_new_price


async def lookup_cpk_confidence(db, cpk: str) -> dict | None:
    """
    Look up confidence metrics for a CPK consolidation.

    Returns metadata about how reliable the CPK's aggregated pricing is:
    - listing_count: How many listings support this price?
    - vendor_count: How many vendors have this product?
    - price_variance: How consistent is pricing? (low = stable, high = volatile)
    """
    query = """
    SELECT listing_count, vendor_count, price_variance
    FROM cpk_pricing_index
    WHERE cpk = :cpk
    """

    result = await db.execute(text(query), {"cpk": cpk})
    row = result.fetchone()

    if not row:
        return None

    return {
        "listing_count": row[0],
        "vendor_count": row[1],
        "price_variance": row[2],
    }
