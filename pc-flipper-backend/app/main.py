import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.workers.scheduler import start_scheduler, stop_scheduler
from app.api import listings, flips, parts, sources, chat, config, swarms
from app.api import intel, settings_router, debug, logs as logs_api
from app.api.logs import install_log_capture

log = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    install_log_capture()          # must be first — before any structlog usage
    log.info("app.startup")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_add_columns()
    await _seed_default_data()
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()
    log.info("app.shutdown")


app = FastAPI(
    title="PC Flip Profit Maximizer API",
    version="5.0.0",
    description="AI-powered PC flipping intelligence platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router, prefix="/api")
app.include_router(flips.router, prefix="/api")
app.include_router(parts.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(swarms.router, prefix="/api")
app.include_router(intel.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(debug.router, prefix="/api")
app.include_router(logs_api.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "5.0.0", "model": settings.ollama_model}


async def _migrate_add_columns():
    """
    Idempotent column migration — adds new nullable columns to existing tables
    without dropping anything. Safe to run every startup.
    """
    new_cols = [
        ("listings", "resale_low",          "FLOAT"),
        ("listings", "resale_high",         "FLOAT"),
        ("listings", "resale_comp_count",   "INTEGER"),
        # Auction intelligence
        ("listings", "listing_type",        "VARCHAR(20)"),
        ("listings", "listing_ends_at",     "DATETIME"),
        ("listings", "expected_buy_price",  "FLOAT"),
        # Seller intelligence
        ("listings", "seller_name",           "VARCHAR(200)"),
        ("listings", "seller_feedback_count", "INTEGER"),
        ("listings", "seller_feedback_pct",   "FLOAT"),
        ("listings", "seller_type",           "VARCHAR(20)"),
        ("listings", "seller_has_shop",       "BOOLEAN DEFAULT 0"),
        ("listings", "listed_at",             "DATETIME"),
    ]
    async with engine.begin() as conn:
        for table, col, col_type in new_cols:
            try:
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                )
                log.info("migration.column_added", table=table, column=col)
            except Exception:
                pass   # column already exists — ignore


# ── Search terms ──────────────────────────────────────────────────────────────
# Sent verbatim to eBay, Gumtree, Preloved and Facebook Marketplace.
#
# PRINCIPLE: profit is made on ENTRY. Search for what messy / uninformed sellers
# list, not what clean sellers list.
#
# Messy listings = opportunity.  Clean listings = competition.
#
# These are grouped by strategy so it's easy to add/remove categories.

_FLIP_SEARCH_TERMS = [

    # ── 1. BROAD SWEEPS ─────────────────────────────────────────────────────
    # Short queries catch listings whose sellers don't know the right words.
    # Noisy but essential — many gems have one-word titles.
    "pc tower",
    "desktop pc",
    "gaming pc",
    "computer tower",

    # ── 2. BRAND WORKSTATIONS (HIGH VALUE / OFTEN UNDERPRICED) ──────────────
    # Office IT clearances dump these for almost nothing.
    # HP EliteDesk / Z-series, Dell OptiPlex / Precision, Lenovo ThinkStation —
    # all frequently have Xeon / i7 / i9 CPUs and zero GPU (easy flip upgrade).
    "HP EliteDesk",
    "HP workstation",
    "HP Z240",
    "HP Z440",
    "HP Z640",
    "Dell OptiPlex",
    "Dell workstation",
    "Dell Precision tower",
    "Lenovo ThinkCentre",
    "Lenovo ThinkStation",
    "HP ProDesk",
    "HP Compaq tower",
    "Dell Vostro tower",
    "Fujitsu Esprimo",
    "Acer Veriton tower",

    # ── 3. TARGETED — MISSING COMPONENTS ────────────────────────────────────
    # Missing a GPU or storage is WHY it's cheap — those are easy, cheap upgrades.
    "gaming pc no gpu",
    "gaming pc no graphics card",
    "pc tower no graphics",
    "desktop no gpu",
    "pc base unit no graphics",
    "gaming pc no hard drive",
    "pc tower no storage",
    "desktop computer no SSD",
    "pc no hard drive",
    "pc base unit",
    "pc no power supply",
    "pc no psu",

    # ── 4. HIGH-EDGE — DISTRESS / FAULT SIGNALS ─────────────────────────────
    # Sellers taking a discount because they can't verify it works.
    # We can test it; they can't be bothered. That's the margin.
    "pc untested",
    "desktop untested",
    "gaming pc untested",
    "pc spares or repair",
    "desktop spares or repair",
    "pc no display",
    "pc boots no display",
    "pc powers on no signal",
    "pc faulty",
    "desktop faulty",
    "gaming pc fault",
    "pc powers up untested",
    "pc no os",
    "desktop no os",
    "pc no operating system",

    # ── 5. CPU-BASED — SELLER DOESN'T KNOW THE VALUE ────────────────────────
    # A seller who writes "i7 tower" instead of "gaming PC i7" almost always
    # underprices, because they don't know what gaming buyers will pay.
    "i5 desktop",
    "i5 tower",
    "i7 desktop",
    "i7 tower",
    "i9 desktop",
    "i9 tower",
    "ryzen 5 desktop",
    "ryzen 7 desktop",
    "ryzen 9 desktop",
    "xeon desktop",
    "xeon tower",
    "i5 10400 desktop",
    "i7 10700 desktop",
    "ryzen 5 3600 desktop",
    "ryzen 7 5800 desktop",

    # ── 6. AUCTION / BULK / OFFICE CLEARANCE ────────────────────────────────
    # Job lots and IT clearances price per-unit very cheaply to move volume.
    "pc job lot",
    "desktop pcs lot",
    "office computers clearance",
    "ex office pc",
    "office pc tower",
    "it clearance desktop",
    "bulk pcs desktop",
    "workstation joblot",
    "office tower pc",

    # ── 7. MISSPELLINGS (eBay gold mine) ────────────────────────────────────
    # These listings get zero competition from normal buyers who search correctly.
    # Low bids / low BIN prices as a result — textbook flip opportunity.
    "gamng pc",
    "gmaing pc",
    "gamnig pc",
    "gaiming pc",
    "deskptop pc",
    "compter tower",
    "pc towre",
    "destop pc",
    "destkop computer",
    "gameing pc",
    "computre tower",

    # ── 8. EMOTIONAL / DISTRESSED SELLER (Gumtree / Facebook) ───────────────
    # Price set by urgency, not market knowledge.
    "pc quick sale",
    "pc need gone today",
    "old pc clearing out",
    "son old pc",
    "unused pc",
    "pc collect today",
    "pc free to good home",
    "old computer quick sale",
    "gaming pc quick sale",
    "pc no longer needed",

    # ── 9. LIQUID COOLER / UPGRADES ALREADY FITTED ──────────────────────────
    # Seller paid for premium cooling but lists the whole system cheaply.
    "pc liquid cooler",
    "desktop liquid cooled",
    "gaming pc water cooled",
    "gaming pc with aio",
]


async def _seed_default_data():
    """Seed default sources, search config, and app settings on first run."""
    from app.database import AsyncSessionLocal
    from app.models.source import DataSource, SourceType
    from app.models.search_config import SearchConfig
    from app.models.app_settings import AppSettings
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        # Seed default sources (first run only)
        count = await db.scalar(select(func.count()).select_from(DataSource))
        if count == 0:
            db.add_all([
                DataSource(name="eBay UK", url="https://www.ebay.co.uk", source_type=SourceType.scrape, enabled=True),
                DataSource(name="Gumtree", url="https://www.gumtree.com", source_type=SourceType.scrape, enabled=False),
                DataSource(name="Facebook Marketplace", url="https://www.facebook.com/marketplace", source_type=SourceType.scrape, enabled=False),
                DataSource(name="Preloved", url="https://www.preloved.co.uk", source_type=SourceType.scrape, enabled=True),
            ])
            log.info("seeded.sources")

        from sqlalchemy import update as _update
        from pathlib import Path as _Path

        # ── Ensure new sources exist on all installs ──────────────────────────
        _new_sources = [
            # eBay Auctions — ending-soonest auctions. This is the real liquidation
            # market: office clearances, IT job lots, untested bulk lots all land here.
            ("eBay UK Auctions",  "https://www.ebay.co.uk",       True),
            # Preloved — UK classifieds, JS-rendered, Playwright scraper working.
            ("Preloved",          "https://www.preloved.co.uk",   True),
            # John Pye — major UK liquidator. Blocks scrapers (HTTP 403).
            # Listed as disabled; a future Playwright + auth approach could unlock it.
            ("John Pye",          "https://www.johnpye.co.uk",    False),
        ]
        for src_name, src_url, src_enabled in _new_sources:
            exists = await db.scalar(
                select(func.count()).select_from(DataSource).where(DataSource.name == src_name)
            )
            if not exists:
                db.add(DataSource(
                    name=src_name, url=src_url,
                    source_type=SourceType.scrape, enabled=src_enabled,
                ))
                log.info("seeded.new_source", name=src_name)

        # ── Disable Gumtree — blocked by Cloudflare (returns 589-byte challenge)
        # Leaving it enabled just wastes 2+ minutes every scan run.
        await db.execute(
            _update(DataSource)
            .where(DataSource.name == "Gumtree")
            .values(enabled=False)
        )

        # ── Facebook Marketplace: enable only if fb_cookies.json exists ───────
        fb_cookies = _Path(__file__).parent.parent / "fb_cookies.json"
        if fb_cookies.exists():
            await db.execute(
                _update(DataSource)
                .where(DataSource.name == "Facebook Marketplace")
                .values(enabled=True)
            )
            log.info("facebook.enabled", hint="fb_cookies.json found")

        # Seed search config — keywords are the actual eBay search strings.
        # Cheap flip opportunities live in INCOMPLETE / UNTESTED / BARE listings,
        # not in "gaming PC" results (those are already complete and priced in).
        cfg_count = await db.scalar(select(func.count()).select_from(SearchConfig))
        if cfg_count == 0:
            db.add(SearchConfig(
                name="default",
                is_active=True,
                keywords=_FLIP_SEARCH_TERMS,
                max_price=500,   # raise ceiling — some i7/i9 bare units fetch £200-400
            ))
            log.info("seeded.search_config")
        else:
            # Update existing installs that still have the old generic terms.
            # Only replace if they haven't customised the keywords already.
            existing_cfg = await db.execute(
                select(SearchConfig).where(SearchConfig.is_active == True).limit(1)
            )
            cfg = existing_cfg.scalar_one_or_none()
            if cfg and set(cfg.keywords or []) <= {"PC tower", "desktop computer",
                                                    "gaming PC", "computer tower"}:
                cfg.keywords  = _FLIP_SEARCH_TERMS
                cfg.max_price = 500
                log.info("migrated.search_config.keywords")

        # Seed app settings
        settings_count = await db.scalar(select(func.count()).select_from(AppSettings))
        if settings_count == 0:
            db.add(AppSettings(
                name="default",
                ollama_model=settings.ollama_model,
                ollama_base_url=settings.ollama_base_url,
            ))
            log.info("seeded.app_settings", model=settings.ollama_model)

        await db.commit()
