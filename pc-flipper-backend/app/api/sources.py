import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, AsyncSessionLocal
from app.models.source import DataSource
from app.schemas.source import DataSourceOut, DataSourceCreate, DataSourceUpdate
from app.services.source_health import compute_health_score

# Only ONE source scrape runs at a time.  Playwright-backed sources each spin up
# a Chrome process; running them concurrently exhausts memory and crashes the
# backend (EOF on the Playwright stdio pipe).
_SOURCE_SCRAPE_SEM = asyncio.Semaphore(1)

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
    await _SOURCE_SCRAPE_SEM.acquire()
    try:
        await _do_scrape(source_id)
    finally:
        _SOURCE_SCRAPE_SEM.release()


async def _do_scrape(source_id: int):
    import structlog
    from datetime import datetime
    from sqlalchemy import select, update
    from app.models.search_config import SearchConfig
    from app.services.scraper import fetch_listings
    from app.services.resale_scraper import clear_cache
    from app.services import scan_state
    from app.services.search_telemetry import begin_source_run, end_source_run
    from app.services.listing_ingest_queue import enqueue_nowait, IngestItem

    log = structlog.get_logger(__name__)

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

        # Build demand score lookup from DB for all terms that appeared in results
        from app.models.source_search_term import SourceSearchTerm as SST
        from sqlalchemy import select as sa_select
        found_terms = {r.found_via_term for r in raw_listings if r.found_via_term}
        term_scores: dict[str, float] = {}
        if found_terms:
            async with AsyncSessionLocal() as db2:
                rows = await db2.execute(
                    sa_select(SST.term, SST.demand_score).where(SST.term.in_(found_terms))
                )
                for t, s in rows.all():
                    term_scores[t] = float(s or 5.0)

        queued = sum(
            1 for raw in raw_listings
            if enqueue_nowait(IngestItem(
                raw=raw,
                source_id=source_id,
                min_price=config.min_price,
                max_price=config.max_price,
                demand_score=term_scores.get(raw.found_via_term, 5.0),
                found_via_term=raw.found_via_term,
            ))
        )
        log.info("source.scrape.queued", source=source.name, queued=queued, total=len(raw_listings))

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(DataSource).where(DataSource.id == source_id).values(
                    last_scraped_at=datetime.utcnow(),
                    listings_found_last_run=len(raw_listings),
                    listings_found_total=DataSource.listings_found_total + len(raw_listings),
                    last_error=None,
                )
            )
            await db.commit()

        scan_state.site_done(source.name, len(raw_listings), 0)
        log.info("source.scrape.done", source=source.name, found=len(raw_listings))

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
