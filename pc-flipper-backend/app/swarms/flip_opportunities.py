"""
Flip Opportunities Swarm — runs hourly.
Searches ALL enabled sources simultaneously (async parallel), classifies, scores, upserts to DB.
"""
import asyncio
import structlog
import re
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import AsyncSessionLocal
from app.models.listing import Listing, ListingStatus, Classification
from app.models.source import DataSource
from app.models.search_config import SearchConfig
from app.models.search_telemetry import SearchTelemetry
from app.models.source_search_term import SourceSearchTerm
from app.services.scraper import fetch_listings
from app.services.spec_parser import parse_specs
from app.services.classifier import score_listing
from app.services.estimator import estimate_upgrade_cost, estimate_profit
from app.services.resale_scraper import get_resale_range, clear_cache, get_expected_auction_price, clear_auction_cache
from app.services.component_pricer import clear_component_cache
from app.services import scan_state
from app.services.search_telemetry import begin_source_run, end_source_run
from app.services.source_health import (
    apply_error,
    apply_success,
    should_skip_due_to_cooldown,
)
from app.services.antibot_preflight import should_defer_source_scrape
from app.config import get_settings

log = structlog.get_logger(__name__)
SOURCE_FAILURE_THRESHOLD = 3
_DB_WRITE_LOCK = asyncio.Lock()
_settings = get_settings()
_ENRICH_CONCURRENCY = max(1, min(24, int(getattr(_settings, "max_concurrent_scrapers", 8) or 8)))
_COOLDOWN_BYPASS_SOURCES = {
    "eBay UK",
    "eBay UK Auctions",
    "Facebook Marketplace",
    "Gumtree",
    "Preloved",
    "BidSpotter",
    "i-bidder",
    "Wilsons Auctions",
    "Apex Auctions",
    "Amazon",
    "Temu",
    "AliExpress",
    "Alibaba",
    "BargainHardware",
    "CherryTree Inc",
}
_NO_RETRY_SOURCES = {
    # Consistent transport-level failures; retrying within the same hour adds noise
    # and does not improve yield.
    "John Pye",
}
_NON_RETRYABLE_TERM_ERRORS = {
    "captcha_required",
    "login_required",
}

_SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "ebay": ("eBay UK", "eBay UK Auctions"),
    "ebay uk": ("eBay UK",),
    "ebay uk auctions": ("eBay UK Auctions",),
    "amazon": ("Amazon",),
    "amazon uk": ("Amazon",),
}


def _expand_source_aliases(source_name: str) -> tuple[str, ...]:
    key = str(source_name or "").strip().lower()
    if not key:
        return tuple()
    return _SOURCE_ALIASES.get(key, (source_name,))


def _fingerprint(title: str, price: float, cpu: str | None, gpu: str | None) -> str:
    t = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    t = " ".join(t.split()[:8])
    p = int(round(float(price or 0)))
    return f"{t}|{cpu or ''}|{gpu or ''}|{p}"


async def run_flip_opportunities_swarm(mode: str = "main") -> dict:
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

        fallback_terms = config.keywords or ["PC tower", "desktop computer", "gaming PC"]
        rows = (
            await db.execute(
                select(SourceSearchTerm).where(
                    SourceSearchTerm.scope == "flip_opportunities",
                    SourceSearchTerm.enabled == True,
                )
            )
        ).scalars().all()
        terms_by_source: dict[str, list[str]] = {}
        if rows:
            for row in rows:
                term = str(row.term or "").strip()
                if not term:
                    continue
                src_names = row.source_names or []
                if src_names:
                    for s in src_names:
                        for canonical in _expand_source_aliases(str(s)):
                            terms_by_source.setdefault(canonical, []).append(term)
                else:
                    for src in sources:
                        terms_by_source.setdefault(src.name, []).append(term)
        else:
            for src in sources:
                terms_by_source[src.name] = list(fallback_terms)

        terms_by_source = {k: list(dict.fromkeys(v)) for k, v in terms_by_source.items()}
        batch_terms_by_source = terms_by_source

    # Announce scan started
    scan_state.scan_started(sources)
    clear_cache()             # flush stale whole-system resale cache
    clear_auction_cache()     # flush stale auction buy-price cache
    clear_component_cache()   # flush stale component price cache

    # Run all sources in parallel
    tasks = [_scan_source(source, batch_terms_by_source.get(source.name, []), config) for source in sources]
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

    # Ghost lifecycle transitions — NEVER delete listing history.
    # 3+ days unseen  -> missing
    # 14+ days unseen -> removed
    # Listings marked sold are excluded from these transitions.
    missing_cutoff = datetime.utcnow() - timedelta(days=3)
    removed_cutoff = datetime.utcnow() - timedelta(days=14)
    async with AsyncSessionLocal() as db:
        missing_result = await db.execute(
            update(Listing)
            .where(
                Listing.status == ListingStatus.active,
                Listing.last_seen_at < missing_cutoff,
            )
            .values(status=ListingStatus.missing)
        )

        removed_result = await db.execute(
            update(Listing)
            .where(
                Listing.status == ListingStatus.missing,
                Listing.last_seen_at < removed_cutoff,
            )
            .values(status=ListingStatus.removed)
        )

        await db.commit()

    moved_missing = missing_result.rowcount or 0
    moved_removed = removed_result.rowcount or 0
    if moved_missing or moved_removed:
        log.info(
            "ghost_lifecycle.updated",
            moved_to_missing=moved_missing,
            moved_to_removed=moved_removed,
            missing_cutoff_days=3,
            removed_cutoff_days=14,
        )

    return stats


async def _scan_source(source, search_terms: list, config) -> dict:
    """Scan a single source and upsert results. Returns stats dict."""
    scan_state.site_started(source.name)
    result = {"scanned": 0, "found": 0, "gems": 0}

    try:
        if not search_terms:
            scan_state.site_done(source.name, 0, 0)
            return result
        defer, defer_reason = should_defer_source_scrape(source.name)
        if defer:
            scan_state.site_done(source.name, 0, 0)
            log.info("source.deferred.antibot", source=source.name, reason=defer_reason)
            return result
        src_cfg_pre = dict((source.config or {}))
        skip, reason = should_skip_due_to_cooldown(src_cfg_pre)
        if skip and source.name not in _COOLDOWN_BYPASS_SOURCES:
            scan_state.site_done(source.name, 0, 0)
            log.info("source.skipped", source=source.name, reason=reason)
            return result
        if skip and source.name in _COOLDOWN_BYPASS_SOURCES:
            log.info("source.cooldown_ignored", source=source.name, reason=reason)

        run_id = begin_source_run(source.name)
        raw_listings = await fetch_listings(
            source_name=source.name,
            source_url=source.url,
            search_terms=search_terms,
            min_price=config.min_price,
            max_price=config.max_price,
        )
        result["scanned"] = 1
        result["found"] = len(raw_listings)

        # Scrapes can run in parallel, but SQLite writes must be serialized.
        failed_rows = await _failed_terms_for_run_with_errors(run_id, source.name)
        blocker_only_zero = (
            len(raw_listings) == 0
            and len(failed_rows) > 0
            and all(str(err or "") in _NON_RETRYABLE_TERM_ERRORS for _, err in failed_rows)
        )

        async with _DB_WRITE_LOCK:
            async with AsyncSessionLocal() as db:
                gems = await _upsert_listings(db, raw_listings, source.id, config)
                result["gems"] = gems

                source_row = await db.get(DataSource, source.id)
                src_cfg = dict((source_row.config or {})) if source_row else {}
                src_cfg = apply_success(src_cfg, len(raw_listings))
                if blocker_only_zero:
                    # Do not cooldown sources that are blocked by interactive
                    # challenges; they need manual preflight, not backoff loops.
                    src_cfg["zero_results_streak"] = 0
                    src_cfg.pop("cooldown_until", None)

                await db.execute(
                    update(DataSource)
                    .where(DataSource.id == source.id)
                    .values(
                        last_scraped_at=datetime.utcnow(),
                        listings_found_last_run=len(raw_listings),
                        listings_found_total=DataSource.listings_found_total + len(raw_listings),
                        last_error=None,
                        config=src_cfg,
                    )
                )
                await db.commit()

        # Retry only failed terms later in the same hour, while keeping successful data.
        failed_terms = [term for term, err in failed_rows if str(err or "") not in _NON_RETRYABLE_TERM_ERRORS]
        if failed_terms:
            if source.name in _NO_RETRY_SOURCES:
                log.info(
                    "source.retry.skipped",
                    source=source.name,
                    failed_terms=len(failed_terms),
                    reason="no_retry_source",
                )
                scan_state.site_done(source.name, result["found"], result["gems"])
                log.info("source.done", source=source.name, found=result["found"], gems=result["gems"])
                return result
            delay_minutes = max(1, int(getattr(config, "source_retry_delay_minutes", 0) or 0))
            # Pull settings-based retry delay from global settings when config object has no field.
            from app.config import get_settings as _get_settings
            delay_minutes = max(1, int(_get_settings().source_retry_delay_minutes))
            max_terms = max(1, int(_get_settings().source_retry_max_terms))
            failed_terms = failed_terms[:max_terms]
            log.info(
                "source.retry.scheduled",
                source=source.name,
                failed_terms=len(failed_terms),
                delay_minutes=delay_minutes,
            )
            await asyncio.sleep(delay_minutes * 60)
            retry_run_id = begin_source_run(source.name)
            retry_raw = await fetch_listings(
                source_name=source.name,
                source_url=source.url,
                search_terms=failed_terms,
                min_price=config.min_price,
                max_price=config.max_price,
            )
            end_source_run()
            result["found"] += len(retry_raw)
            async with _DB_WRITE_LOCK:
                async with AsyncSessionLocal() as db:
                    retry_gems = await _upsert_listings(db, retry_raw, source.id, config)
                    result["gems"] += retry_gems
                    await db.execute(
                        update(DataSource)
                        .where(DataSource.id == source.id)
                        .values(
                            last_scraped_at=datetime.utcnow(),
                            listings_found_last_run=len(raw_listings) + len(retry_raw),
                            listings_found_total=DataSource.listings_found_total + len(retry_raw),
                        )
                    )
                    await db.commit()
            retry_failed_terms = await _failed_terms_for_run(retry_run_id, source.name)
            if retry_failed_terms:
                log.warning(
                    "source.retry.partial",
                    source=source.name,
                    retried_terms=len(failed_terms),
                    still_failed_terms=len(retry_failed_terms),
                )
            else:
                log.info("source.retry.success", source=source.name, retried_terms=len(failed_terms))

        scan_state.site_done(source.name, result["found"], result["gems"])
        log.info("source.done", source=source.name, found=result["found"], gems=result["gems"])

    except Exception as exc:
        scan_state.site_error(source.name, str(exc))
        log.error("source.error", source=source.name, error=str(exc))

        async with _DB_WRITE_LOCK:
            async with AsyncSessionLocal() as db:
                source_row = await db.get(DataSource, source.id)
                src_cfg = dict((source_row.config or {})) if source_row else {}
                failures = int(src_cfg.get("consecutive_failures", 0)) + 1
                src_cfg = apply_error(src_cfg, failures)
                auto_disabled = failures >= SOURCE_FAILURE_THRESHOLD
                err_msg = str(exc)
                if auto_disabled:
                    err_msg = (
                        f"[auto-disabled after {failures} consecutive failures] {err_msg}"
                    )
                await db.execute(
                    update(DataSource)
                    .where(DataSource.id == source.id)
                    .values(
                        last_error=err_msg,
                        config=src_cfg,
                        enabled=False if auto_disabled else DataSource.enabled,
                    )
                )
                await db.commit()
                if auto_disabled:
                    log.warning(
                        "source.auto_disabled",
                        source=source.name,
                        consecutive_failures=failures,
                        threshold=SOURCE_FAILURE_THRESHOLD,
                    )
    finally:
        end_source_run()

    return result


async def _failed_terms_for_run(run_id: str | None, source_name: str) -> list[str]:
    if not run_id:
        return []
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(SearchTelemetry.term)
            .where(
                SearchTelemetry.run_id == run_id,
                SearchTelemetry.source == source_name,
                SearchTelemetry.error.is_not(None),
            )
        )
        terms = [str(t[0]).strip() for t in rows.all() if t and t[0]]
    # Preserve order, drop duplicates
    return list(dict.fromkeys(terms))


async def _failed_terms_for_run_with_errors(run_id: str | None, source_name: str) -> list[tuple[str, str]]:
    if not run_id:
        return []
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(SearchTelemetry.term, SearchTelemetry.error)
            .where(
                SearchTelemetry.run_id == run_id,
                SearchTelemetry.source == source_name,
                SearchTelemetry.error.is_not(None),
            )
        )
        items = [
            (str(t or "").strip(), str(e or "").strip())
            for t, e in rows.all()
            if str(t or "").strip()
        ]
    # Preserve first occurrence order by term+error combo.
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


async def _upsert_listings(
    db: AsyncSession,
    raw_listings: list,
    source_id: int,
    config: SearchConfig,
) -> int:
    new_gems = 0
    sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def _enrich_listing(raw):
        async with sem:
            try:
                specs = parse_specs(raw.title, raw.description)
                if not _passes_filter(raw.price, specs, config, title=raw.title):
                    return None
                fp = _fingerprint(raw.title, raw.price, specs.cpu, specs.gpu)
                expected_buy_price: float | None = None
                if raw.listing_type == "auction":
                    expected_buy_price = await get_expected_auction_price(specs.cpu, specs.gpu, raw.price)
                effective_buy_price = expected_buy_price if expected_buy_price else raw.price
                resale_range = await get_resale_range(
                    specs.cpu, specs.ram_gb, specs.ram_type,
                    specs.storage_gb, specs.storage_type, specs.gpu,
                    buy_price=effective_buy_price,
                )
                upgrade_cost = estimate_upgrade_cost(specs.storage_gb, specs.gpu, specs.has_psu, specs.ram_gb)
                resale = resale_range.median
                profit = estimate_profit(effective_buy_price, resale, upgrade_cost)
                profit_low = estimate_profit(effective_buy_price, resale_range.low, upgrade_cost)
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
                return {
                    "raw": raw,
                    "specs": specs,
                    "fp": fp,
                    "expected_buy_price": expected_buy_price,
                    "resale_range": resale_range,
                    "upgrade_cost": upgrade_cost,
                    "resale": resale,
                    "profit": profit,
                    "score_result": score_result,
                }
            except Exception as exc:
                log.warning("listing.enrichment_error", source=raw.source_name, external_id=raw.external_id, error=str(exc))
                return None

    enriched = await asyncio.gather(*[_enrich_listing(raw) for raw in raw_listings], return_exceptions=False)

    for item in enriched:
        if not item:
            continue
        raw = item["raw"]
        specs = item["specs"]
        fp = item["fp"]
        expected_buy_price = item["expected_buy_price"]
        resale_range = item["resale_range"]
        upgrade_cost = item["upgrade_cost"]
        resale = item["resale"]
        profit = item["profit"]
        score_result = item["score_result"]

        with db.no_autoflush:
            existing = await db.execute(
                select(Listing)
                .where(
                    (Listing.external_id == raw.external_id)
                    | (Listing.dedupe_fingerprint == fp)
                )
                .order_by(Listing.id.desc())
            )
            dup_rows = existing.scalars().all()
            listing = dup_rows[0] if dup_rows else None
            if len(dup_rows) > 1:
                log.warning(
                    "listing.duplicate_match",
                    external_id=raw.external_id,
                    fingerprint=fp,
                    duplicate_rows=len(dup_rows),
                    source=raw.source_name,
                )

        if listing:
            listing.last_seen_at = datetime.utcnow()
            listing.price = raw.price
            listing.status = ListingStatus.active
            listing.source_confidence = getattr(raw, "source_confidence", listing.source_confidence or "browser_verified")
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
                dedupe_fingerprint=fp,
                source_id=source_id,
                source_name=raw.source_name,
                source_confidence=getattr(raw, "source_confidence", "browser_verified"),
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
        if listing and not listing.dedupe_fingerprint:
            listing.dedupe_fingerprint = fp
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

_AM5_TARGET_KW: set[str] = {
    "am5", "b650", "x670", "ryzen 7700", "ryzen 7700x", "ryzen 9700x", "ryzen 7900",
    "ryzen 9 7900", "ryzen 9 7900x", "7800x3d", "amd ryzen 7 7800x3d",
}

_AM5_RED_FLAGS: set[str] = {
    "for parts", "boots sometimes", "boots some times", "untested because no psu",
    "needs bios update maybe", "collection only cash no testing",
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
        # AM5 quality gate: we still scan broadly, but reject clearly risky AM5 listings.
        is_am5_candidate = any(kw in t for kw in _AM5_TARGET_KW)
        if is_am5_candidate and any(flag in t for flag in _AM5_RED_FLAGS):
            return False
        # A620 is acceptable only when very cheap.
        if "a620" in t and price > 80:
            return False
    return True
