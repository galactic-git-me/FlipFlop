"""
Flip Opportunities Swarm — runs hourly.
Searches ALL enabled sources simultaneously (async parallel), classifies, scores, upserts to DB.
"""
import asyncio
import structlog
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.database import AsyncSessionLocal
from app.models.listing import Listing, ListingStatus, Classification
from app.models.source import DataSource
from app.models.search_config import SearchConfig
from app.services.scraper import fetch_listings
from app.services.spec_parser import parse_specs
from app.services.classifier import score_listing
from app.services.estimator import estimate_upgrade_cost, estimate_profit
from app.services.resale_scraper import get_resale_range, clear_cache, get_expected_auction_price, clear_auction_cache
from app.services.component_pricer import clear_component_cache
from app.services import scan_state

log = structlog.get_logger(__name__)


async def run_flip_opportunities_swarm() -> dict:
    log.info("flip_opportunities_swarm.start")
    stats = {"sources_scanned": 0, "listings_found": 0, "new_gems": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        config_result = await db.execute(
            select(SearchConfig).where(SearchConfig.is_active == True).limit(1)
        )
        config = config_result.scalar_one_or_none()
        if not config:
            log.warning("No active search config found")
            return stats

        sources_result = await db.execute(
            select(DataSource).where(DataSource.enabled == True)
        )
        sources = sources_result.scalars().all()

        search_terms = config.keywords or ["PC tower", "desktop computer", "gaming PC"]

    # Announce scan started
    scan_state.scan_started(sources)
    clear_cache()             # flush stale whole-system resale cache
    clear_auction_cache()     # flush stale auction buy-price cache
    clear_component_cache()   # flush stale component price cache

    # Run all sources in parallel
    tasks = [_scan_source(source, search_terms, config) for source in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scan_state.scan_finished()

    # Aggregate stats
    for r in results:
        if isinstance(r, Exception):
            stats["errors"] += 1
        else:
            stats["sources_scanned"] += r["scanned"]
            stats["listings_found"] += r["found"]
            stats["new_gems"] += r["gems"]

    log.info("flip_opportunities_swarm.done", **stats)

    # Ghost cleanup — remove active listings not seen in the last 3 days.
    # If a listing hasn't been re-encountered across 3 full scan cycles it's
    # almost certainly gone (sold, removed, or expired by the seller).
    # Listings already flipped (status=sold) are kept for history.
    cutoff = datetime.utcnow() - timedelta(days=3)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Listing).where(
                Listing.status == ListingStatus.active,
                Listing.last_seen_at < cutoff,
            ).returning(Listing.id)
        )
        purged = len(result.fetchall())
        await db.commit()
    if purged:
        log.info("ghost_cleanup.purged", count=purged, cutoff_days=3)

    return stats


async def _scan_source(source, search_terms: list, config) -> dict:
    """Scan a single source and upsert results. Returns stats dict."""
    scan_state.site_started(source.name)
    result = {"scanned": 0, "found": 0, "gems": 0}

    try:
        raw_listings = await fetch_listings(
            source_name=source.name,
            source_url=source.url,
            search_terms=search_terms,
            min_price=config.min_price,
            max_price=config.max_price,
        )
        result["scanned"] = 1
        result["found"] = len(raw_listings)

        async with AsyncSessionLocal() as db:
            gems = await _upsert_listings(db, raw_listings, source.id, config)
            result["gems"] = gems

            await db.execute(
                update(DataSource)
                .where(DataSource.id == source.id)
                .values(
                    last_scraped_at=datetime.utcnow(),
                    listings_found_last_run=len(raw_listings),
                    listings_found_total=DataSource.listings_found_total + len(raw_listings),
                    last_error=None,
                )
            )
            await db.commit()

        scan_state.site_done(source.name, result["found"], result["gems"])
        log.info("source.done", source=source.name, found=result["found"], gems=result["gems"])

    except Exception as exc:
        scan_state.site_error(source.name, str(exc))
        log.error("source.error", source=source.name, error=str(exc))

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(DataSource)
                .where(DataSource.id == source.id)
                .values(last_error=str(exc))
            )
            await db.commit()

    return result


async def _upsert_listings(
    db: AsyncSession,
    raw_listings: list,
    source_id: int,
    config: SearchConfig,
) -> int:
    new_gems = 0

    for raw in raw_listings:
        existing = await db.execute(
            select(Listing).where(Listing.external_id == raw.external_id)
        )
        listing = existing.scalar_one_or_none()

        specs = parse_specs(raw.title, raw.description)

        if not _passes_filter(raw.price, specs, config, title=raw.title):
            continue

        # ── For auction listings: estimate the realistic final hammer price ──────
        # raw.price = current bid (almost certainly too low — bidding war still ahead).
        # We use completed eBay auction comps to find what similar hardware actually
        # clears at.  This is used BOTH as the buy-price for profit calculations
        # AND stored as expected_buy_price on the listing so the UI can show it.
        expected_buy_price: float | None = None
        if raw.listing_type == "auction":
            expected_buy_price = await get_expected_auction_price(
                specs.cpu, specs.gpu, raw.price
            )

        # The effective buy cost to use in all profit maths:
        #   - Auction  → expected_buy_price (realistic hammer price)
        #   - BIN / classified → raw.price (already a fixed ask)
        effective_buy_price = expected_buy_price if expected_buy_price else raw.price

        # Live eBay comp scrape — returns market price range from real sold listings.
        # buy_price is passed so the fallback can anchor to the listing's own
        # market price rather than a lookup table.
        resale_range = await get_resale_range(
            specs.cpu, specs.ram_gb, specs.ram_type,
            specs.storage_gb, specs.storage_type, specs.gpu,
            buy_price=effective_buy_price,
        )
        upgrade_cost = estimate_upgrade_cost(specs.storage_gb, specs.gpu, specs.has_psu, specs.ram_gb)

        # Compute the full profit range: profit = resale - total_cost.
        # profit_low (conservative / 25th-pct) drives the REJECT safety gate —
        # if the worst-case market price still produces a loss, the deal is risky.
        resale      = resale_range.median
        profit      = estimate_profit(effective_buy_price, resale,            upgrade_cost)
        profit_low  = estimate_profit(effective_buy_price, resale_range.low,  upgrade_cost)
        profit_high = estimate_profit(effective_buy_price, resale_range.high, upgrade_cost)

        score_result = score_listing(
            title=raw.title,
            price=raw.price,
            estimated_profit=profit,
            cpu=specs.cpu,
            ram_gb=specs.ram_gb,
            ram_type=specs.ram_type,
            storage_gb=specs.storage_gb,
            gpu=specs.gpu,
            has_psu=specs.has_psu,
            location=raw.location,
            profit_low=profit_low,
            profit_high=profit_high,
        )

        if listing:
            listing.last_seen_at = datetime.utcnow()
            listing.price = raw.price
            listing.status = ListingStatus.active
            listing.estimated_resale = resale
            listing.resale_low = resale_range.low
            listing.resale_high = resale_range.high
            listing.resale_comp_count = resale_range.count
            listing.estimated_upgrade_cost = upgrade_cost
            listing.estimated_profit = profit
            listing.classification = score_result.classification
            listing.gem_score = score_result.score
            listing.gem_signals = score_result.signals
            # Auction fields — update on every scan (bid can move, end time is fixed)
            listing.listing_type = raw.listing_type
            if raw.listing_ends_at:
                listing.listing_ends_at = raw.listing_ends_at
            if expected_buy_price:
                listing.expected_buy_price = expected_buy_price
            # Seller intelligence — refresh on each scan
            if raw.seller_name:
                listing.seller_name = raw.seller_name
            if raw.seller_feedback_count is not None:
                listing.seller_feedback_count = raw.seller_feedback_count
            if raw.seller_feedback_pct is not None:
                listing.seller_feedback_pct = raw.seller_feedback_pct
            if raw.seller_type:
                listing.seller_type = raw.seller_type
            listing.seller_has_shop = raw.seller_has_shop
            if raw.listed_at and not listing.listed_at:
                listing.listed_at = raw.listed_at
        else:
            listing = Listing(
                external_id=raw.external_id,
                source_id=source_id,
                source_name=raw.source_name,
                title=raw.title,
                description=raw.description,
                price=raw.price,
                url=raw.url,
                image_urls=raw.image_urls,
                location=raw.location,
                condition=raw.condition,
                cpu=specs.cpu,
                ram_gb=specs.ram_gb,
                ram_type=specs.ram_type,
                storage_gb=specs.storage_gb,
                storage_type=specs.storage_type,
                gpu=specs.gpu,
                has_psu=specs.has_psu,
                gem_score=score_result.score,
                classification=score_result.classification,
                gem_signals=score_result.signals,
                estimated_resale=resale,
                resale_low=resale_range.low,
                resale_high=resale_range.high,
                resale_comp_count=resale_range.count,
                estimated_profit=profit,
                estimated_upgrade_cost=upgrade_cost,
                initial_estimated_profit=profit,
                listing_type=raw.listing_type,
                listing_ends_at=raw.listing_ends_at,
                expected_buy_price=expected_buy_price,
                seller_name=raw.seller_name,
                seller_feedback_count=raw.seller_feedback_count,
                seller_feedback_pct=raw.seller_feedback_pct,
                seller_type=raw.seller_type,
                seller_has_shop=raw.seller_has_shop,
                listed_at=raw.listed_at,
            )
            db.add(listing)
            if score_result.classification in (Classification.amazing_gem, Classification.gem):
                new_gems += 1

    return new_gems


_MINI_PC_EXCLUDE: set[str] = {
    "mini pc", "mini-pc", "mini computer", "mini desktop",
    "intel nuc", " nuc ", "nuc pc", "stick pc", "pc stick",
    "beelink", "minisforum", "gmktec", "trigkey", "geekom",
    "acemagic", "asus nuc", "compute stick", "tiny pc",
    "nano pc", "pico pc", "mele quieter",
}


def _passes_filter(price: float, specs, config: SearchConfig, title: str = "") -> bool:
    if price < config.min_price or price > config.max_price:
        return False
    if config.require_storage and not specs.storage_gb:
        return False
    if config.require_gpu and not specs.gpu:
        return False
    if specs.ram_gb and specs.ram_gb < config.ram_min_gb:
        return False
    # Exclude mini PCs / NUCs — they use laptop CPUs and have no upgrade margin
    if title:
        t = title.lower()
        if any(kw in t for kw in _MINI_PC_EXCLUDE):
            return False
    return True
