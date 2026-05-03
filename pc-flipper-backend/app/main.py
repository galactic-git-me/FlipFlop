import structlog
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.workers.scheduler import start_scheduler, stop_scheduler
from app.api import listings, flips, parts, sources, chat, config, swarms
from app.api import intel, settings_router, debug, logs as logs_api, playbooks, demand, manual_submit
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
    allow_origins=["*"],
    allow_credentials=False,
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
app.include_router(playbooks.router, prefix="/api")
app.include_router(demand.router, prefix="/api")
app.include_router(manual_submit.router, prefix="/api")


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
        # Playbook + demand fit (added with playbook system)
        ("listings", "playbook_match",        "VARCHAR(200)"),
        ("listings", "demand_fit",            "VARCHAR(20)"),
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
                DataSource(name="Gumtree", url="https://www.gumtree.com", source_type=SourceType.scrape, enabled=True),
                DataSource(name="Facebook Marketplace", url="https://www.facebook.com/marketplace", source_type=SourceType.scrape, enabled=True),
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

        # ── Manual submission sources ─────────────────────────────────────────
        for _ms_name in ["Manual Submission", "Manual Photo"]:
            _ms_exists = await db.scalar(
                select(func.count()).select_from(DataSource).where(DataSource.name == _ms_name)
            )
            if not _ms_exists:
                db.add(DataSource(name=_ms_name, url="", source_type=SourceType.scrape, enabled=True))
                log.info("seeded.manual_source", name=_ms_name)

        # ── Auction platform stubs ────────────────────────────────────────────
        _auction_sources = [
            # IT-focused UK liquidation — no bot detection observed, scraper implemented
            ("Apex Auctions",          "https://www.apexauctions.co.uk",          True),
            # Multi-vendor aggregator — JSON API, rate-limited
            ("BidSpotter",             "https://www.bidspotter.co.uk",            False),
            # UK's largest auctioneer — JSON API, high IT clearance volume
            ("Wilsons Auctions",       "https://www.wilsonsauctions.com",         False),
            # Multi-vendor HTML scrape — CF challenge manageable with Playwright
            ("i-bidder",               "https://www.i-bidder.com",                False),
            # B2B wholesale surplus — requires API key registration
            ("Merkandi",               "https://merkandi.co.uk",                  False),
            # B2B pallet lots — requires business account auth
            ("Wholesale Clearance UK", "https://www.wholesaleclearance.co.uk",    False),
            # Largest UK online auctioneer — CF Enterprise WAF blocks all bots
            ("John Pye",               "https://www.johnpye.co.uk",               False),
        ]
        for src_name, src_url, src_enabled in _auction_sources:
            exists = await db.scalar(
                select(func.count()).select_from(DataSource).where(DataSource.name == src_name)
            )
            if not exists:
                db.add(DataSource(
                    name=src_name, url=src_url,
                    source_type=SourceType.scrape, enabled=src_enabled,
                ))
                log.info("seeded.auction_source", name=src_name)

        # ── Ensure Gumtree + Facebook are enabled on existing installs ──────────
        # Both use the Playwright scraper (headless browser with stealth mode).
        # Gumtree: no login required, Playwright bypasses the JS challenge.
        # Facebook: works without cookies (~20 items); add fb_cookies.json for full access.
        for _src_name in ("Gumtree", "Facebook Marketplace", "Apex Auctions"):
            await db.execute(
                _update(DataSource)
                .where(DataSource.name == _src_name)
                .values(enabled=True)
            )
        fb_cookies = _Path(__file__).parent.parent / "fb_cookies.json"
        if fb_cookies.exists():
            log.info("facebook.cookies_found", hint="fb_cookies.json found — full Marketplace access enabled")
        else:
            log.info("facebook.no_cookies", hint="Running without fb_cookies.json — up to ~20 items per scan. Export cookies from your browser for full access.")

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

        # ── Seed default playbooks ────────────────────────────────────────────
        from app.models.playbook import Playbook
        pb_count = await db.scalar(select(func.count()).select_from(Playbook))
        if pb_count == 0:
            _default_playbooks = [
                Playbook(
                    name="Budget Gaming PC",
                    emoji="🎮",
                    description="Buy no-GPU or untested gaming base units, add a mid-range GPU and flip on eBay.",
                    status="active",
                    target_use_case="gaming",
                    activated_at=datetime.utcnow(),
                    requirements={
                        "gpu_required": False,
                        "cpu_min_tier": "i5",
                        "ram_min_gb": 8,
                        "psu_required": True,
                        "form_factor": "ATX",
                    },
                    search_strategy={
                        "keywords": [
                            "gaming pc no gpu", "gaming pc no graphics card",
                            "pc tower no graphics", "desktop no gpu",
                            "i5 tower", "i7 tower", "ryzen 5 desktop", "ryzen 7 desktop",
                            "gaming pc untested", "gaming pc spares",
                        ],
                        "listing_types": ["buy_it_now", "auction"],
                        "price_min": 60,
                        "price_max": 280,
                        "boost_terms": ["untested", "no gpu", "no graphics", "spares"],
                    },
                    upgrade_strategy={
                        "required": [
                            {"component": "GPU", "target": "RTX 3060 / RX 6600", "max_cost": 100},
                        ],
                        "optional": [
                            {"component": "SSD", "target": "500GB NVMe", "max_cost": 25},
                            {"component": "RAM", "target": "16GB DDR4", "max_cost": 20},
                        ],
                    },
                    profit_strategy={
                        "target_margin_pct": 40,
                        "target_profit_gbp": 120,
                        "sell_platform": "eBay",
                        "flip_structure": "buy_upgrade_sell",
                        "notes": "List at £350-400; local pickup adds 5-10%.",
                    },
                ),
                Playbook(
                    name="Office Workstation Flip",
                    emoji="💼",
                    description="IT clearance OptiPlex/EliteDesk units. Minimal upgrades, quick clean resell.",
                    status="active",
                    target_use_case="office",
                    activated_at=datetime.utcnow(),
                    requirements={
                        "gpu_required": False,
                        "cpu_min_tier": "i5",
                        "ram_min_gb": 8,
                        "psu_required": False,
                        "form_factor": "any",
                    },
                    search_strategy={
                        "keywords": [
                            "Dell OptiPlex", "HP EliteDesk", "Lenovo ThinkCentre",
                            "HP ProDesk", "Fujitsu Esprimo", "ex office pc",
                            "office pc tower", "it clearance desktop",
                            "office computers clearance", "pc job lot",
                        ],
                        "listing_types": ["buy_it_now", "auction"],
                        "price_min": 20,
                        "price_max": 150,
                        "boost_terms": ["job lot", "clearance", "collection only", "no hdd"],
                    },
                    upgrade_strategy={
                        "required": [],
                        "optional": [
                            {"component": "SSD", "target": "256GB SSD", "max_cost": 18},
                            {"component": "RAM", "target": "16GB DDR4", "max_cost": 20},
                        ],
                    },
                    profit_strategy={
                        "target_margin_pct": 60,
                        "target_profit_gbp": 60,
                        "sell_platform": "eBay",
                        "flip_structure": "buy_clean_sell",
                        "notes": "Win on volume. Aim for 5+ units per batch at £60 profit each.",
                    },
                ),
                Playbook(
                    name="AI / ML Workstation",
                    emoji="🤖",
                    description="Xeon or Threadripper towers with lots of RAM. Add a used A4000/A5000 and sell to developers.",
                    status="candidate",
                    target_use_case="ai_workstation",
                    requirements={
                        "gpu_required": True,
                        "cpu_min_tier": "Xeon",
                        "ram_min_gb": 32,
                        "psu_required": True,
                        "form_factor": "ATX",
                    },
                    search_strategy={
                        "keywords": [
                            "xeon tower", "HP Z440", "HP Z640", "Dell Precision tower",
                            "Lenovo ThinkStation", "dual xeon desktop",
                            "workstation no gpu", "HP Z240",
                        ],
                        "listing_types": ["buy_it_now", "auction"],
                        "price_min": 80,
                        "price_max": 500,
                        "boost_terms": ["no gpu", "no graphics", "xeon", "threadripper"],
                    },
                    upgrade_strategy={
                        "required": [
                            {"component": "GPU", "target": "Nvidia A4000 / RTX 3090", "max_cost": 250},
                        ],
                        "optional": [
                            {"component": "RAM", "target": "64GB ECC DDR4", "max_cost": 60},
                            {"component": "NVMe", "target": "1TB NVMe", "max_cost": 40},
                        ],
                    },
                    profit_strategy={
                        "target_margin_pct": 35,
                        "target_profit_gbp": 250,
                        "sell_platform": "eBay",
                        "flip_structure": "buy_upgrade_sell",
                        "notes": "Target ML/AI hobbyists and small studios. Market is thin but margins are fat.",
                    },
                ),
                Playbook(
                    name="Budget Builder (Sub-£100)",
                    emoji="💸",
                    description="Anything £20-60 that boots. Clean, list cheaply, volume play.",
                    status="active",
                    target_use_case="budget",
                    activated_at=datetime.utcnow(),
                    requirements={
                        "gpu_required": False,
                        "cpu_min_tier": "i3",
                        "ram_min_gb": 4,
                        "psu_required": False,
                        "form_factor": "any",
                    },
                    search_strategy={
                        "keywords": [
                            "pc tower", "desktop pc", "computer tower",
                            "old pc clearing out", "pc no longer needed",
                            "pc quick sale", "son old pc", "pc free to good home",
                        ],
                        "listing_types": ["buy_it_now", "auction"],
                        "price_min": 10,
                        "price_max": 60,
                        "boost_terms": ["quick sale", "need gone", "free", "clearing out"],
                    },
                    upgrade_strategy={
                        "required": [],
                        "optional": [
                            {"component": "SSD", "target": "120GB SSD", "max_cost": 10},
                        ],
                    },
                    profit_strategy={
                        "target_margin_pct": 80,
                        "target_profit_gbp": 35,
                        "sell_platform": "eBay",
                        "flip_structure": "buy_clean_sell",
                        "notes": "Wipe, Windows reinstall, list at £70-90. Pure volume play.",
                    },
                ),
            ]
            db.add_all(_default_playbooks)
            log.info("seeded.playbooks", count=len(_default_playbooks))

        await db.commit()
