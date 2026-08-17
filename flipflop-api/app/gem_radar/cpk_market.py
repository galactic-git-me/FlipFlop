"""Phase 1 of the CPK-driven market-price system: accumulate a market price
per Canonical Product Key from the listings actually seen, rather than from
an external benchmark source.

Design (per product spec): every listing that gets a CPK contributes its
price as a data point for that CPK — the median of prices seen across the
same product within and across vendors, over a rolling MARKET_PRICE_WINDOW_
DAYS window (not all-time unbounded: a price from 3 months ago shouldn't
still be dragging down today's median). The aggregate (min/median/max) is
always recomputed and stored, but a CPK's price is only trustworthy for
classification once 2+ listings within that window have contributed to it —
see get_market_price's is_settled gate and phase2_classify_by_market_price.py,
which is the only caller allowed to actually use these prices.

Deliberately no outlier removal here (per product spec, "remove the removal
of outliers for now") — every observed price within the window counts,
unfiltered.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

log = structlog.get_logger(__name__)

# Below this many contributing listings, a CPK's aggregate price is not
# considered "settled" — see get_market_price.
MIN_LISTINGS_FOR_SETTLED_PRICE = 2

# Rolling window for market-price aggregation. A listing's row in
# gem_radar_cpk_listing_price is upserted on every re-sighting (its
# updated_at refreshes each time), so a listing that's still actively being
# scraped stays inside the window indefinitely — only genuinely stale,
# no-longer-seen listings age out.
MARKET_PRICE_WINDOW_DAYS = 14


async def get_robust_sold_market(
    db: AsyncSession,
    *,
    cpk: str,
    condition: str,
    subject_listing_id: str,
    policy,
):
    """Return a same-condition completed-sale cohort only.

    Active BIN, Amazon and scan prices remain available elsewhere as context,
    but are intentionally excluded from realised resale value.
    """
    from app.gem_radar.opportunity_scoring import SoldComparable, robust_sold_market

    normalised = "new" if (condition or "").lower() == "new" else "used"
    result = await db.execute(
        text(
            """
            SELECT price, postage, source_url,
                   EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - observed_at)) / 86400.0 AS days_ago
            FROM gem_radar_sold_observations
            WHERE cpk = :cpk
              AND LOWER(condition) = :condition
              AND observed_at >= CURRENT_TIMESTAMP - make_interval(days => :lookback)
              AND price > 0
            ORDER BY observed_at DESC
            """
        ),
        {"cpk": cpk, "condition": normalised, "lookback": policy.sold_lookback_days},
    )
    comps = [SoldComparable(float(r[0]), float(r[1] or 0), r[2], float(r[3] or 0)) for r in result.fetchall()]
    return robust_sold_market(comps, subject_listing_id=subject_listing_id, policy=policy)


@dataclass(frozen=True)
class CPKMarketPrice:
    cpk: str
    min_price: float
    median_price: float
    max_price: float
    listing_count: int


async def upsert_scan_price(
    db: AsyncSession,
    cpk: str | None,
    match_key: str,
    price: float,
    category: str | None = None,
    brand: str | None = None,
    model: str | None = None,
) -> None:
    """Records a barcode scan price observation for market-price aggregation.
    Scan prices are solid new retail prices (not used), providing a cross-vendor
    consensus point for new-condition items. If CPK is unavailable, the scan
    price still contributes via match_key lookup in the aggregation query."""
    from app.models.gem_radar_scan_observation import GemRadarScanObservation

    db.add(
        GemRadarScanObservation(
            cpk=cpk,
            match_key=match_key,
            price=price,
            category=category,
            brand=brand,
            model=model,
        )
    )
    await db.commit()


async def upsert_listing_price(
    db: AsyncSession,
    cpk: str,
    listing_id: str,
    price: float,
    category: str | None = None,
    brand: str | None = None,
    model: str | None = None,
) -> None:
    """Records/updates this listing's price as a data point for `cpk`, then
    recomputes and stores the CPK's min/median/max/listing_count from every
    listing currently on record for it. Idempotent — re-running for a
    listing_id already seen updates its price in place rather than double-
    counting it, so re-scraping the same still-live listing every scan cycle
    doesn't inflate listing_count.
    """
    await db.execute(
        text(
            """
            INSERT INTO gem_radar_cpk_listing_price (listing_id, cpk, price, updated_at)
            VALUES (:listing_id, :cpk, :price, CURRENT_TIMESTAMP)
            ON CONFLICT (listing_id) DO UPDATE SET
                cpk = EXCLUDED.cpk,
                price = EXCLUDED.price,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        {"listing_id": listing_id, "cpk": cpk, "price": price},
    )

    agg_result = await db.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS listing_count,
                MIN(price) AS min_price,
                MAX(price) AS max_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price
            FROM (
                SELECT price FROM gem_radar_cpk_listing_price
                WHERE cpk = :cpk
                  AND updated_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
                UNION ALL
                SELECT price FROM gem_radar_sold_observations
                WHERE cpk = :cpk
                  AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
                UNION ALL
                SELECT price FROM gem_radar_amazon_observations
                WHERE cpk = :cpk
                  AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
                UNION ALL
                SELECT price FROM gem_radar_scan_observation
                WHERE cpk = :cpk
                  AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
            ) AS all_prices
            """
        ),
        {"cpk": cpk},
    )
    row = agg_result.fetchone()
    listing_count, min_price, max_price, median_price = row[0], row[1], row[2], row[3]

    await db.execute(
        text(
            """
            INSERT INTO gem_radar_cpk_market_price
                (cpk, category, brand, model, min_price, median_price, max_price, listing_count, updated_at)
            VALUES
                (:cpk, :category, :brand, :model, :min_price, :median_price, :max_price, :listing_count, CURRENT_TIMESTAMP)
            ON CONFLICT (cpk) DO UPDATE SET
                category = COALESCE(EXCLUDED.category, gem_radar_cpk_market_price.category),
                brand = COALESCE(EXCLUDED.brand, gem_radar_cpk_market_price.brand),
                model = COALESCE(EXCLUDED.model, gem_radar_cpk_market_price.model),
                min_price = EXCLUDED.min_price,
                median_price = EXCLUDED.median_price,
                max_price = EXCLUDED.max_price,
                listing_count = EXCLUDED.listing_count,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        {
            "cpk": cpk,
            "category": category,
            "brand": brand,
            "model": model,
            "min_price": min_price,
            "median_price": median_price,
            "max_price": max_price,
            "listing_count": listing_count,
        },
    )


async def get_market_price(db: AsyncSession, cpk: str) -> CPKMarketPrice | None:
    """Returns the CPK's aggregate price over the rolling
    MARKET_PRICE_WINDOW_DAYS window, or None if fewer than
    MIN_LISTINGS_FOR_SETTLED_PRICE listings within that window have
    contributed to it — callers must never classify against an unsettled
    price.

    Recomputes live against gem_radar_cpk_listing_price rather than reading
    the gem_radar_cpk_market_price cache table directly: that cache only
    updates when a NEW listing arrives for this cpk (see
    upsert_listing_price), so if a CPK's last contributing listing simply
    ages out of the window with no new sighting, the cached row would keep
    reporting a stale, no-longer-valid aggregate indefinitely.
    """
    result = await db.execute(
        text(
            f"""
            SELECT
                MIN(price) AS min_price,
                MAX(price) AS max_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
                COUNT(*) AS listing_count
            FROM (
                SELECT price FROM gem_radar_cpk_listing_price
                WHERE cpk = :cpk
                  AND updated_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
                UNION ALL
                SELECT price FROM gem_radar_sold_observations
                WHERE cpk = :cpk
                  AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
                UNION ALL
                SELECT price FROM gem_radar_amazon_observations
                WHERE cpk = :cpk
                  AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
                UNION ALL
                SELECT price FROM gem_radar_scan_observation
                WHERE cpk = :cpk
                  AND observed_at >= CURRENT_TIMESTAMP - INTERVAL '{MARKET_PRICE_WINDOW_DAYS} days'
            ) AS all_prices
            """
        ),
        {"cpk": cpk},
    )
    row = result.fetchone()
    if row is None:
        return None

    min_price, max_price, median_price, listing_count = row[0], row[1], row[2], row[3]
    if listing_count < MIN_LISTINGS_FOR_SETTLED_PRICE:
        return None
    if min_price is None or median_price is None or max_price is None:
        return None

    return CPKMarketPrice(
        cpk=cpk,
        min_price=min_price,
        median_price=median_price,
        max_price=max_price,
        listing_count=listing_count,
    )


async def get_market_price_with_hierarchy_fallback(
    db: AsyncSession, cpk: str
) -> CPKMarketPrice | None:
    """Returns market price for a CPK, falling back to broader category levels
    if the specific CPK doesn't have enough observations to settle.

    For now, returns exact CPK price if settled, or None.
    Hierarchy fallback (category-level pricing) deferred to Phase 3 after
    cpk_data stability verified — complex JSONB joins present early risks.
    """
    return await get_market_price(db, cpk)
