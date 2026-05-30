import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, AsyncSessionLocal
from app.models.source import DataSource
from app.schemas.source import DataSourceOut, DataSourceCreate, DataSourceUpdate
from app.services.source_health import compute_health_score

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/", response_model=list[DataSourceOut])
async def get_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).order_by(DataSource.name))
    return result.scalars().all()


@router.get("/health")
async def source_health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSource).order_by(DataSource.name))
    rows = result.scalars().all()
    items = []
    for s in rows:
        cfg = dict(s.config or {})
        score = int(cfg.get("health_score") or compute_health_score(cfg))
        items.append(
            {
                "id": s.id,
                "name": s.name,
                "enabled": s.enabled,
                "health_score": score,
                "consecutive_failures": int(cfg.get("consecutive_failures", 0) or 0),
                "zero_results_streak": int(cfg.get("zero_results_streak", 0) or 0),
                "cooldown_until": cfg.get("cooldown_until"),
                "last_error": s.last_error,
            }
        )
    avg = round(sum(i["health_score"] for i in items) / len(items), 1) if items else 0.0
    return {"avg_health_score": avg, "items": items}


@router.post("/", response_model=DataSourceOut, status_code=201)
async def create_source(body: DataSourceCreate, db: AsyncSession = Depends(get_db)):
    source = DataSource(**body.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=DataSourceOut)
async def update_source(source_id: int, body: DataSourceUpdate, db: AsyncSession = Depends(get_db)):
    source = await db.get(DataSource, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(source, k, v)
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    source = await db.get(DataSource, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    await db.delete(source)


@router.post("/{source_id}/scrape")
async def scrape_source(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate scrape for a single source and return immediately."""
    source = await db.get(DataSource, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    background_tasks.add_task(_scrape_source_bg, source_id)
    return {"ok": True, "queued": True, "source": source.name}


async def _scrape_source_bg(source_id: int):
    """Run a full flip-opportunities scan filtered to a single source."""
    import structlog
    from datetime import datetime
    from sqlalchemy import select, update
    from app.models.search_config import SearchConfig
    from app.services.scraper import fetch_listings
    from app.services.spec_parser import parse_specs
    from app.services.classifier import score_listing
    from app.services.estimator import estimate_upgrade_cost, estimate_profit
    from app.services.resale_scraper import get_resale_range, clear_cache
    from app.models.listing import Listing, ListingStatus, Classification
    from app.services import scan_state
    from app.services.search_telemetry import begin_source_run, end_source_run
    from app.config import get_settings

    log = structlog.get_logger(__name__)
    settings = get_settings()
    enrich_concurrency = max(1, min(24, int(getattr(settings, "max_concurrent_scrapers", 8) or 8)))

    async with AsyncSessionLocal() as db:
        source = await db.get(DataSource, source_id)
        if not source:
            return
        config_result = await db.execute(
            select(SearchConfig).where(SearchConfig.is_active == True).limit(1)
        )
        config = config_result.scalar_one_or_none()
        if not config:
            return
        search_terms = config.keywords or ["gaming PC", "desktop computer"]

    scan_state.scan_started([source])
    scan_state.site_started(source.name)
    clear_cache()

    try:
        begin_source_run(source.name)
        raw_listings = await fetch_listings(
            source_name=source.name,
            source_url=source.url,
            search_terms=search_terms,
            min_price=config.min_price,
            max_price=config.max_price,
        )

        async with AsyncSessionLocal() as db:
            _MINI_PC_KW = {
                "mini pc", "mini-pc", "intel nuc", " nuc ", "nuc pc",
                "beelink", "minisforum", "gmktec", "trigkey", "geekom",
                "stick pc", "tiny pc", "mini computer",
            }
            new_gems = 0
            sem = asyncio.Semaphore(enrich_concurrency)

            async def _enrich_listing(raw):
                async with sem:
                    try:
                        if any(kw in raw.title.lower() for kw in _MINI_PC_KW):
                            return None
                        specs = parse_specs(raw.title, raw.description)
                        resale_range = await get_resale_range(
                            specs.cpu, specs.ram_gb, specs.ram_type,
                            specs.storage_gb, specs.storage_type, specs.gpu,
                            buy_price=raw.price,
                        )
                        upgrade_cost = estimate_upgrade_cost(specs.storage_gb, specs.gpu, specs.has_psu, specs.ram_gb)
                        resale = resale_range.median
                        profit = estimate_profit(raw.price, resale, upgrade_cost)
                        profit_low = estimate_profit(raw.price, resale_range.low, upgrade_cost)
                        profit_high = estimate_profit(raw.price, resale_range.high, upgrade_cost)
                        score_result = score_listing(
                            title=raw.title, price=raw.price, estimated_profit=profit,
                            cpu=specs.cpu, ram_gb=specs.ram_gb, ram_type=specs.ram_type,
                            storage_gb=specs.storage_gb, gpu=specs.gpu, has_psu=specs.has_psu,
                            location=raw.location,
                            profit_low=profit_low, profit_high=profit_high,
                        )
                        return {
                            "raw": raw,
                            "specs": specs,
                            "resale_range": resale_range,
                            "upgrade_cost": upgrade_cost,
                            "resale": resale,
                            "profit": profit,
                            "score_result": score_result,
                        }
                    except Exception as exc:
                        log.warning("source.scrape.listing_enrichment_error", source=source.name, external_id=raw.external_id, error=str(exc))
                        return None

            enriched = await asyncio.gather(*[_enrich_listing(raw) for raw in raw_listings], return_exceptions=False)

            for item in enriched:
                if not item:
                    continue
                raw = item["raw"]
                specs = item["specs"]
                resale_range = item["resale_range"]
                upgrade_cost = item["upgrade_cost"]
                resale = item["resale"]
                profit = item["profit"]
                score_result = item["score_result"]

                existing = await db.execute(
                    select(Listing)
                    .where(Listing.external_id == raw.external_id)
                    .order_by(Listing.id.desc())
                )
                existing_rows = existing.scalars().all()
                listing = existing_rows[0] if existing_rows else None
                if len(existing_rows) > 1:
                    log.warning(
                        "source.scrape.duplicate_external_id",
                        source=source.name,
                        external_id=raw.external_id,
                        duplicate_rows=len(existing_rows),
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
                else:
                    listing = Listing(
                        external_id=raw.external_id, source_id=source_id, source_name=raw.source_name,
                        title=raw.title, description=raw.description, price=raw.price, url=raw.url,
                        image_urls=raw.image_urls, location=raw.location, condition=raw.condition,
                        cpu=specs.cpu, ram_gb=specs.ram_gb, ram_type=specs.ram_type,
                        storage_gb=specs.storage_gb, storage_type=specs.storage_type,
                        gpu=specs.gpu, has_psu=specs.has_psu,
                        gem_score=score_result.score, classification=score_result.classification,
                        gem_signals=score_result.signals, estimated_resale=resale,
                        resale_low=resale_range.low, resale_high=resale_range.high,
                        resale_comp_count=resale_range.count,
                        estimated_profit=profit, estimated_upgrade_cost=upgrade_cost,
                        initial_estimated_profit=profit,
                    )
                    db.add(listing)
                    if score_result.classification in (Classification.amazing_gem, Classification.gem):
                        new_gems += 1

            await db.execute(
                update(DataSource).where(DataSource.id == source_id).values(
                    last_scraped_at=datetime.utcnow(),
                    listings_found_last_run=len(raw_listings),
                    listings_found_total=DataSource.listings_found_total + len(raw_listings),
                    last_error=None,
                )
            )
            await db.commit()

        scan_state.site_done(source.name, len(raw_listings), new_gems)
        log.info("source.scrape.done", source=source.name, found=len(raw_listings), gems=new_gems)

    except Exception as exc:
        scan_state.site_error(source.name, str(exc))
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(DataSource).where(DataSource.id == source_id).values(last_error=str(exc))
            )
            await db.commit()
        log.error("source.scrape.error", source=source.name, error=str(exc))
    finally:
        end_source_run()

    scan_state.scan_finished()
