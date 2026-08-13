import structlog
import asyncio
import os
import sys

# Playwright requires ProactorEventLoop on Windows to launch browser subprocesses.
# Must be set before any asyncio usage.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import engine, Base
from app import models as _models  # noqa: F401  Ensures all ORM models are registered before create_all
from app.workers.scheduler import start_scheduler, stop_scheduler, run_startup_bootstrap
from app.api import listings, flips, parts, sources, chat, config, swarms, inventory, inventory_allocations
from app.api import intel, settings_router, debug, logs as logs_api, playbooks, demand, manual_submit, schedule, search_telemetry, source_search_terms
from app.api import alerts, reselling, ebay_listings
from app.api.orders import router as orders_router, admin_router as orders_admin_router
from app.api.ram_watch import router as ram_watch_router
from app.api import ebay_compliance
from app.api import preflight
from app.api import performance as performance_api
from app.api import ebay_oauth as ebay_oauth_api
from app.api.build_wizard import router as build_wizard_router
from app.api.manual_builds import router as manual_builds_router
from app.api.facebook import router as facebook_router
from app.api.benchmarks import router as benchmarks_router
from app.api.companion import router as companion_router
from app.api.price_benchmarks import router as price_benchmarks_router
from app.api.catalogue import router as catalogue_router
from app.api.public_catalogue import router as public_catalogue_router
from app.routes.auth import router as auth_router
from app.routes.oauth import router as oauth_router
from app.routes.quotes import router as quotes_router
from app.routes.payments import router as payments_router
from app.routes.webhooks import router as webhooks_router
from app.routes.guides import router as guides_router
from app.routes.admin import router as admin_router
from app.routes.gems import router as gems_router
from app.api.logs import install_log_capture
from app.services.playwright_scraper import chromium_available
from app.services.antibot_preflight import run_antibot_preflight
from app.services.listing_ingest_queue import start_workers, stop_workers as stop_ingest_workers
from app.services.claude_eval_queue import start_eval_workers, stop_eval_workers
from app.services.part_gem_eval_queue import start_part_eval_workers, stop_part_eval_workers

log = structlog.get_logger(__name__)
settings = get_settings()

# Windows Playwright compatibility:
# ensure subprocess-capable asyncio policy (needed by Playwright driver transport).
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[attr-defined]
    except Exception:
        pass

_CASE_DEFAULT_SOURCES = [
    "eBay",
    "eBay (Worldwide)",
    "Gumtree",
    "Amazon",
    "Temu",
    "AliExpress",
    "BargainHardware",
    "CherryTree Inc",
    "Alibaba",
]

_CASE_TAXONOMY: dict[str, list[str]] = {
    "Fish Tank / Panoramic Cases": [
        "fish tank pc case", "panoramic pc case", "dual chamber pc case", "wraparound glass case",
        "aquarium pc case", "corner glass pc case", "seamless glass pc case", "infinity glass pc case",
        "tempered glass showcase case", "frameless gaming case",
    ],
    "RGB / Gamer Bait": [
        "argb gaming case", "rgb airflow case", "rgb infinity mirror case", "rgb cyberpunk case",
        "gamer aesthetic case", "streamer setup pc case", "esports gaming case", "neon gaming case",
        "rgb sync case", "addressable rgb case",
    ],
    "Airflow / Performance Style": [
        "mesh airflow case", "high airflow gaming case", "airflow rgb case", "performance airflow chassis",
        "silent airflow case", "mesh front tower", "cooling optimized case", "high static airflow case",
    ],
    "Luxury / Premium Feel": [
        "premium aluminum pc case", "luxury gaming case", "minimalist gaming case", "modern workstation case",
        "creator pc case", "ultra clean build case", "stealth pc case", "matte white gaming case",
        "brushed aluminum pc case",
    ],
    "White Builds": [
        "white fish tank case", "white rgb case", "white gaming tower", "snow white pc case",
        "white panoramic chassis", "white airflow case", "arctic gaming case",
    ],
    "Small But Expensive-Looking": [
        "micro atx fish tank", "compact gaming case", "mini tower rgb case", "compact airflow chassis",
        "sff gaming case", "cube gaming case",
    ],
    "Cyberpunk / Sci-Fi Style": [
        "cyberpunk pc case", "futuristic gaming case", "mech style pc case", "transformer style case",
        "sci fi pc chassis", "spaceship pc case", "tron inspired pc case", "industrial gaming case",
    ],
    "Star Trek Inspired": [
        "federation command build", "starfleet workstation", "LCARS inspired pc", "starship bridge setup",
        "warp core gaming pc", "federation white rgb case", "tactical console build",
    ],
    "Borg Aesthetic": [
        "borg cube pc", "borg collective build", "assimilated gaming rig", "green borg rgb build",
        "nanotech workstation", "tactical starfleet chassis", "borg green rgb", "cybernetic mesh build",
        "hive mind workstation", "assimilation core pc", "industrial sci fi build", "biomechanical pc case",
        "glowing green coolant build", "matrix grid case",
    ],
    "Star Wars Inspired": [
        "galactic empire build", "rebel alliance gaming pc", "jedi workstation", "sith gaming rig",
        "imperial black rgb build", "death star pc", "hyperspace build", "clone trooper white pc",
        "mandalorian inspired build", "bounty hunter gaming pc",
    ],
    "Battlestar Galactica / Cylon": [
        "cylon red eye pc", "battlestar inspired workstation", "colonial fleet build", "resurrection ship aesthetic",
        "tactical military sci fi build", "cylon chrome build", "red scanner rgb pc", "warship command pc",
    ],
    "Babylon 5": [
        "station command build", "diplomatic station workstation", "earth alliance pc", "shadow vessel inspired build",
        "vorlon aesthetic pc", "ancient alien tech build",
    ],
    "Farscape": [
        "leviathan inspired build", "biomechanical spaceship pc", "living ship aesthetic", "peacekeeper tactical build",
        "alien tech workstation", "organic sci fi build",
    ],
    "Transformers": [
        "autobot gaming pc", "decepticon workstation", "cybertron inspired build", "optimus prime rgb pc",
        "megatron tactical build", "transformer mech chassis", "robotic warfare gaming rig", "cybertron command center",
        "metallic mech pc build", "battle mech workstation", "transforming rgb setup", "machine uprising aesthetic",
    ],
    "Anime Inspired": [
        "anime gaming pc", "manga aesthetic workstation", "waifu rgb build", "neon tokyo gaming rig",
        "japanese cyberpunk pc", "mecha anime workstation", "shonen inspired gaming setup", "anime battle station",
        "otaku gaming pc", "kawaii rgb setup",
    ],
    "Naruto Inspired": [
        "hidden leaf gaming pc", "hokage workstation", "akatsuki rgb build", "sharingan gaming rig",
        "ninja tactical pc", "chakra powered setup", "sage mode workstation", "red cloud aesthetic pc",
        "rinnegan rgb build", "shinobi command center",
    ],
    "Pokemon Inspired": [
        "pokedex workstation", "pikachu yellow rgb build", "charizard gaming pc", "team rocket black build",
        "legendary pokemon workstation", "master trainer gaming setup", "pokeball aesthetic pc", "electric type rgb build",
        "psychic type workstation", "elite four command system",
    ],
    "Dragon Ball Inspired": [
        "super saiyan gaming pc", "dragon radar workstation", "capsule corp build", "ultra instinct rgb setup",
        "saiyan warrior pc", "fusion powered workstation", "dragon ball z gaming rig", "energy aura rgb build",
        "kamehameha blue build", "galactic fighter workstation",
    ],
    "Marvel Inspired": [
        "avengers workstation", "shield tactical pc", "stark industries build", "arc reactor rgb build",
        "gamma powered gaming pc", "multiverse gaming rig",
    ],
    "Iron Man / Jarvis": [
        "jarvis ai workstation", "stark industries pc", "arc reactor build", "iron legion gaming pc",
        "red gold rgb build", "holographic ai setup", "ai assistant workstation", "billionaire inventor aesthetic",
    ],
    "Hulk": [
        "gamma core build", "radioactive green rgb pc", "gamma powered workstation", "rage mode gaming rig",
        "toxic green airflow build",
    ],
    "X-Men": [
        "cerebro workstation", "mutant tactical pc", "x-gene gaming build", "blackbird command system",
        "omega level workstation",
    ],
    "Spider-Man": [
        "spiderverse gaming pc", "red blue rgb build", "webcore gaming setup", "spider tech workstation",
        "urban hero aesthetic",
    ],
    "Batman": [
        "batcomputer workstation", "dark knight pc", "stealth tactical build", "gotham command system",
        "matte black rgb case", "vigilante workstation", "cave workstation aesthetic", "black ops gaming pc",
    ],
    "Superman / Supergirl": [
        "kryptonian workstation", "fortress of solitude build", "crystal core pc", "blue red rgb setup",
        "solar powered gaming rig", "alien tech workstation",
    ],
    "High-Performing Brand & Style Searches": [
        "lian li style case", "hyte y60 style case", "nzxt style case", "o11 dynamic style case",
        "corsair crystal style", "y60 panoramic clone", "infinity mirror case",
    ],
    "Cheap Hidden-Gem Brands": [
        "Montech panoramic case", "darkFlash fish tank", "Jonsbo white case", "SAMA dual chamber",
        "GameMax infinity mirror", "CiT gaming case", "Kolink rgb airflow", "Xigmatek panoramic case",
        "Mars Gaming rgb case", "Tecware airflow chassis",
    ],
    "Perceived Value / Listing Booster Keywords": [
        "showcase build", "custom gaming pc", "ultra rgb", "premium airflow", "streamer pc", "creator workstation",
        "high fps gaming pc", "ai workstation", "content creator pc", "liquid cooled aesthetic", "battle station pc",
        "next gen gaming rig", "futuristic ai desktop", "cinematic rgb build", "command center workstation",
    ],
}


def _infer_case_attributes(term: str, group_name: str) -> dict:
    t = term.lower()
    attrs: dict[str, list[str] | str] = {
        "group": group_name,
        "colors": [],
        "materials": [],
        "sizes": [],
        "styles": [],
        "franchises": [],
    }
    for color in ("white", "black", "green", "red", "blue", "yellow", "gold", "silver", "chrome", "matte", "neon"):
        if color in t:
            attrs["colors"].append(color)
    for mat in ("glass", "tempered glass", "aluminum", "mesh", "metal", "biomechanical", "crystal"):
        if mat in t:
            attrs["materials"].append(mat)
    for size in ("atx", "micro atx", "mini itx", "sff", "mini tower", "mid tower", "full tower", "compact", "cube"):
        if size in t:
            attrs["sizes"].append(size)
    for style in ("airflow", "rgb", "argb", "panoramic", "dual chamber", "workstation", "gaming", "stealth", "premium"):
        if style in t:
            attrs["styles"].append(style)
    for franchise in (
        "star trek", "borg", "star wars", "battlestar", "cylon", "babylon", "farscape", "transformers",
        "naruto", "pokemon", "dragon ball", "marvel", "iron man", "hulk", "x-men", "spider", "batman", "superman",
    ):
        if franchise in t:
            attrs["franchises"].append(franchise)
    attrs["capture_fields"] = ["color", "material", "size", "form_factor", "theme", "style", "franchise"]
    return attrs




@asynccontextmanager
def _loop_exception_handler(loop, context):
    exc = context.get("exception")
    if exc is not None and type(exc).__name__ in ("TargetClosedError", "ConnectionClosedError"):
        return  # Playwright internal cleanup noise — harmless
    loop.default_exception_handler(context)


async def _wipe_dev_data() -> None:
    """In dev mode: clear all scraped data on every container restart so each
    session starts fresh. Does NOT touch configuration (sources, search terms,
    playbooks, settings, flips) — only ephemeral scraped/telemetry data."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import text
    tables = [
        "listing_archive",
        "listings",
        "search_telemetry",
    ]
    async with AsyncSessionLocal() as db:
        for table in tables:
            try:
                await db.execute(text(f"DELETE FROM {table}"))
                log.info("dev.wipe", table=table)
            except Exception as exc:
                log.warning("dev.wipe.skipped", table=table, error=str(exc))
        await db.commit()
    log.info("dev.wipe.done")


def _install_sigchld_reaper() -> None:
    """
    Prevent headless_shell zombie accumulation.

    Setting SIGCHLD to SIG_IGN tells the Linux kernel to auto-reap child
    processes the moment they exit — no zombie entries are created at all.
    This is the most reliable approach: the periodic waitpid() loop can miss
    children if the task is cancelled or the event loop is busy.

    Side-effect: os.waitpid() calls will raise ChildProcessError because there
    are no zombies to collect.  Playwright manages its own children internally
    and does not rely on the parent calling waitpid(), so this is safe.
    """
    import signal as _signal
    _signal.signal(_signal.SIGCHLD, _signal.SIG_IGN)
    log.info("browser_pool.sigchld_reaper_installed")


async def _reap_zombie_children() -> None:
    """
    Belt-and-braces zombie reaper — runs every 5 s as a backup to the
    SIGCHLD=SIG_IGN approach above.  Catches both ChildProcessError and
    the broader OSError so it never silently dies.
    """
    while True:
        try:
            reaped = 0
            while True:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                reaped += 1
            if reaped:
                log.debug("browser_pool.zombies_reaped", count=reaped)
        except (ChildProcessError, OSError):
            pass
        await asyncio.sleep(5)


async def lifespan(app: FastAPI):
    _install_sigchld_reaper()      # prevent headless_shell zombie accumulation
    install_log_capture()          # must be first — before any structlog usage
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_loop_exception_handler)
    log.info("app.startup", event_loop_type=type(loop).__name__, app_env=settings.app_env)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_add_columns()
    if settings.app_env == "dev":
        await _wipe_dev_data()
    await _seed_default_data()
    await _load_db_settings_into_config()
    if not chromium_available():
        log.warning("runtime.preflight.chromium_missing", impact="playwright-backed vendors will return errors/zero until Chromium is installed")
    # Run preflight asynchronously so API stays responsive while challenge tabs open.
    asyncio.create_task(run_antibot_preflight())
    start_workers(n=4)
    start_eval_workers()       # worker count set in claude_eval_queue._NUM_WORKERS
    start_part_eval_workers()  # AI verification for parts catalogue gems
    start_scheduler()
    asyncio.create_task(run_startup_bootstrap())
    asyncio.create_task(_queue_unevaluated_gems())  # auto-queue gems on startup
    reaper = asyncio.create_task(_reap_zombie_children())
    yield
    reaper.cancel()
    stop_scheduler()
    await stop_ingest_workers()
    await stop_eval_workers()
    await stop_part_eval_workers()
    await engine.dispose()
    log.info("app.shutdown")


async def _queue_unevaluated_gems():
    """
    On startup, queue all rule-based gems that haven't been LLM-evaluated yet.
    This ensures the eval queue survives backend restarts without manual re-triggering.
    """
    import asyncio
    from app.database import AsyncSessionLocal
    from app.models.listing import Listing, ListingStatus, Classification
    from app.services.claude_eval_queue import enqueue_for_claude, should_queue_for_claude
    from sqlalchemy import select

    await asyncio.sleep(3)  # let the DB pool warm up first
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Listing)
                .where(
                    Listing.claude_judged_at == None,
                    Listing.status == ListingStatus.active,
                    Listing.classification.in_([Classification.amazing_gem, Classification.gem]),
                )
                .order_by(Listing.gem_score.desc())
                .limit(2000)
            )
            listings = result.scalars().all()
        queued = sum(1 for l in listings if should_queue_for_claude(l) and enqueue_for_claude(l.id))
        log.info("startup.gem_queue_backfill", queued=queued, candidates=len(listings))
    except Exception as exc:
        log.warning("startup.gem_queue_backfill_failed", error=str(exc))


async def _load_db_settings_into_config():
    """
    Push DB-stored API keys and model config into the live Settings cache
    so ai_service.py picks them up immediately on startup without requiring
    a server restart after the user saves a key in the Settings UI.
    """
    from app.database import AsyncSessionLocal
    from app.models.app_settings import AppSettings
    from app.models.source_search_term import SourceSearchTerm
    from app.models.source_search_term import SourceSearchTerm
    from sqlalchemy import select
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AppSettings).where(AppSettings.name == "default"))
            db_settings = result.scalar_one_or_none()
            if not db_settings:
                return
            cfg = get_settings()
            if db_settings.openrouter_api_key:
                cfg.openrouter_api_key = db_settings.openrouter_api_key
            if db_settings.openrouter_primary_model:
                cfg.openrouter_primary_model = db_settings.openrouter_primary_model
            if db_settings.ollama_model:
                cfg.ollama_model = db_settings.ollama_model
            if db_settings.ollama_base_url:
                cfg.ollama_base_url = db_settings.ollama_base_url
            log.info(
                "config.loaded_from_db",
                has_openrouter_key=bool(db_settings.openrouter_api_key),
                model=cfg.openrouter_primary_model,
            )
    except Exception as exc:
        log.warning("config.db_load_failed", error=str(exc))


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
    expose_headers=["*"],
)

# Chrome Private Network Access: allow pages on localhost:XXXX to fetch
# from localhost:YYYY without being blocked by the PNA preflight check.
@app.middleware("http")
async def private_network_access(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

_uploads_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

app.include_router(listings.router, prefix="/api")
app.include_router(flips.router, prefix="/api")
app.include_router(parts.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(inventory_allocations.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(swarms.router, prefix="/api")
app.include_router(intel.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(debug.router, prefix="/api")
app.include_router(logs_api.router, prefix="/api")
app.include_router(playbooks.router, prefix="/api")
app.include_router(orders_router, prefix="")
app.include_router(orders_admin_router, prefix="")
app.include_router(demand.router, prefix="/api")
app.include_router(manual_submit.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(search_telemetry.router, prefix="/api")
app.include_router(source_search_terms.router, prefix="/api")
app.include_router(facebook_router, prefix="/api")
app.include_router(build_wizard_router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(reselling.router, prefix="/api")
app.include_router(ebay_listings.router, prefix="/api")
app.include_router(ebay_compliance.router, prefix="/api")
app.include_router(preflight.router, prefix="/api")
app.include_router(performance_api.router, prefix="/api")
app.include_router(ebay_oauth_api.router, prefix="/api")
app.include_router(manual_builds_router, prefix="/api")
app.include_router(benchmarks_router, prefix="/api")
app.include_router(companion_router, prefix="/api")
app.include_router(ram_watch_router, prefix="/api")
app.include_router(price_benchmarks_router, prefix="/api")
app.include_router(catalogue_router, prefix="/api")
app.include_router(public_catalogue_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(oauth_router, prefix="/api")
app.include_router(quotes_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(guides_router)
app.include_router(admin_router)
app.include_router(gems_router)


_startup_time: datetime = datetime.now(timezone.utc)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "5.0.0",
        "app_env": settings.app_env,
        "started_at": _startup_time.isoformat(),
    }


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
        ("listings", "dedupe_fingerprint",    "VARCHAR(255)"),
        # Playbook upsell strategy
        ("playbooks", "upsell_strategy",      "JSON"),
        # Claude authoritative evaluation columns
        ("listings", "claude_verdict",            "VARCHAR(10)"),
        ("listings", "claude_flipability_score",  "FLOAT"),
        ("listings", "claude_expected_profit",    "FLOAT"),
        ("listings", "claude_roi",                "FLOAT"),
        ("listings", "claude_confidence",         "FLOAT"),
        ("listings", "claude_capital_efficiency", "INTEGER"),
        ("listings", "claude_resale_demand",      "INTEGER"),
        ("listings", "claude_upgrade_complexity", "INTEGER"),
        ("listings", "claude_reasoning",          "TEXT"),
        ("listings", "claude_main_risk",          "TEXT"),
        ("listings", "claude_judged_at",          "DATETIME"),
        ("listings", "spec_fingerprint",           "VARCHAR(255)"),
        # AI gem verification for parts catalogue
        ("parts", "claude_verdict",    "VARCHAR(10)"),
        ("parts", "claude_reasoning",  "TEXT"),
        ("parts", "claude_confidence", "FLOAT"),
        ("parts", "claude_judged_at",  "TIMESTAMP"),
    ]
    async with engine.begin() as conn:
        for table, col, col_type in new_cols:
            await conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
            )
            log.debug("migration.column_ensured", table=table, column=col)

        # Add 'cooler' to the partcategory enum if not already present
        try:
            await conn.exec_driver_sql(
                "ALTER TYPE partcategory ADD VALUE IF NOT EXISTS 'cooler'"
            )
            log.debug("migration.enum_value_ensured", type="partcategory", value="cooler")
        except Exception:
            pass  # older PostgreSQL versions don't support IF NOT EXISTS; ignore


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
    "gaming pc",
    "gaming pc untested",
    "pc tower",
    "Dell OptiPlex",
    "HP EliteDesk",
]
_FLIP_SEARCH_TERMS_EXTENDED = [
    "gaming pc", "gaming pc untested", "gaming pc fault", "gaming pc no gpu", "gaming pc no hard drive",
    "pc tower", "pc tower no graphics", "pc tower no storage", "desktop pc", "desktop pcs lot",
    "Dell OptiPlex", "HP EliteDesk", "HP workstation", "office pc tower",
    "AM4 motherboard cpu combo", "B550 motherboard", "X570 motherboard",
    "Ryzen 5 5600", "Ryzen 7 5700X", "32GB DDR4 2x16", "1TB NVMe SSD", "650W PSU",
]
from app.services.component_models import CANONICAL_MODELS as _CANONICAL_MODELS

_UPGRADE_SEARCH_TERMS = [
    m["name"]
    for models in _CANONICAL_MODELS.values()
    for m in models
]
_ACCESSORY_SEARCH_TERMS = [
    "gaming keyboard",
    "gaming mouse",
    "gaming headset",
    "usb microphone",
    "pc speakers",
    "gaming controller",
    "24 inch monitor",
    "xl mouse pad",
]


async def _sync_playbook_component_catalogues(db) -> None:
    """
    Populate component_catalogue on every active playbook from the canonical
    component model registry. Maps each playbook's target_use_case to a set
    of appropriate model tiers, then writes the model name lists.

    Runs every startup — idempotent, safe to re-run.
    """
    from sqlalchemy import select
    from app.models.playbook import Playbook
    from app.services.component_models import catalogue_for_use_case

    USE_CASE_MAP = {
        "gaming":          "mid_gaming",
        "office":          "office",
        "workstation":     "content_creation",
        "budget":          "ultra_budget",
        "ai_workstation":  "ai_workstation",
        "htpc":            "budget_gaming",
    }

    NAME_MAP = {
        "ultra-budget flip":    "ultra_budget",
        "budget gamer":         "budget_gaming",
        "gift-from-parents pc": "mid_gaming",
        "family pc":            "office",
        "office station flip":  "office",
        "student build":        "office",
        "mid-level gamer":      "mid_gaming",
        "high-end gamer":       "high_gaming",
        "content creator":      "content_creation",
        "dev workstation":      "content_creation",
        "ai workstation":       "ai_workstation",
    }

    playbooks = (
        await db.execute(
            select(Playbook).where(Playbook.status == "active")
        )
    ).scalars().all()

    updated = 0
    for pb in playbooks:
        use_case_key = NAME_MAP.get(pb.name.lower())
        if not use_case_key:
            use_case_key = USE_CASE_MAP.get(str(pb.target_use_case or ""), "mid_gaming")

        catalogue = catalogue_for_use_case(use_case_key)
        if pb.component_catalogue != catalogue:
            pb.component_catalogue = catalogue
            updated += 1

    if updated:
        await db.commit()
        log.info("playbook.component_catalogue.synced", updated=updated)


async def _seed_default_data():
    """Seed default sources, search config, and app settings on first run."""
    from app.database import AsyncSessionLocal
    from app.models.source import DataSource, SourceType
    from app.models.search_config import SearchConfig
    from app.models.app_settings import AppSettings
    from app.models.source_search_term import SourceSearchTerm
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
            ("Amazon",            "https://www.amazon.co.uk",      True),
            ("Temu",              "https://www.temu.com",          True),
            ("AliExpress",        "https://www.aliexpress.com",    True),
            ("Alibaba",           "https://www.alibaba.com",       True),
            ("BargainHardware",   "https://www.bargainhardware.eu", True),
            ("CherryTree Inc",    "https://www.cherrytreeinc.com", True),
            # Vinted UK — second-hand marketplace, Apify-scraped
            ("Vinted",            "https://www.vinted.co.uk",      True),
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

        # ── Auction platform sources ──────────────────────────────────────────
        _auction_sources = [
            # IT-focused UK liquidation — no bot detection observed, scraper implemented
            ("Apex Auctions",          "https://www.apexauctions.co.uk",          True),
            # Multi-vendor aggregator — JSON API, rate-limited
            ("BidSpotter",             "https://www.bidspotter.co.uk",            False),
            # UK's largest auctioneer — JSON API, high IT clearance volume.
            # Promoted to enabled: broad inventory + stable scraper path.
            ("Wilsons Auctions",       "https://www.wilsonsauctions.com",         True),
            # Multi-vendor HTML scrape — CF challenge manageable with Playwright.
            # Promoted to enabled: broad UK catalogue + stable Playwright selector path.
            ("i-bidder",               "https://www.i-bidder.com",                True),
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

        # ── Ensure selected proven sources are enabled on existing installs ──────
        # Gumtree is intentionally excluded — Reblaze WAF blocks all automation.
        for _src_name in (
            "eBay UK",
            "eBay UK Auctions",
            "Facebook Marketplace",
            "Apex Auctions",
            "Wilsons Auctions",
            "i-bidder",
            "Amazon",
            "Temu",
            "AliExpress",
            "Alibaba",
            "BargainHardware",
            "CherryTree Inc",
        ):
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

            # Remove typo/noise terms that generate low-quality requests and
            # disproportionately trigger anti-bot blocks on eBay.
            _noise_terms = {
                "gamng pc", "gmaing pc", "gamnig pc", "gaiming pc",
                "deskptop pc", "compter tower", "pc towre", "destop pc",
                "destkop computer", "gameing pc", "computre tower",
            }
            if cfg and cfg.keywords:
                before_count = len(cfg.keywords)
                cleaned = [k for k in cfg.keywords if str(k).strip().lower() not in _noise_terms]
                if len(cleaned) != before_count:
                    cfg.keywords = cleaned
                    log.info(
                        "migrated.search_config.removed_noise_terms",
                        removed=before_count - len(cleaned),
                    )

        # Seed app settings
        settings_count = await db.scalar(select(func.count()).select_from(AppSettings))
        if settings_count == 0:
            db.add(AppSettings(
                name="default",
                ollama_model=settings.ollama_model,
                ollama_base_url=settings.ollama_base_url,
            ))
            log.info("seeded.app_settings", model=settings.ollama_model)

        # ── Seed / migrate canonical playbooks ───────────────────────────────
        # Handled by playbook_seeder: retires old playbooks, renames, inserts
        # missing ones, and refreshes live pricing from benchmarks each startup.
        from app.services.playbook_seeder import seed_playbooks
        _pb_created = await seed_playbooks(db)
        if _pb_created:
            log.info("seeded.playbooks", created=_pb_created)

        # ── Populate playbook component_catalogue from canonical model registry ─
        await _sync_playbook_component_catalogues(db)

        if False:  # dead code — kept so git diff is minimal; remove next cleanup
            from app.models.playbook import Playbook
            pb_count = await db.scalar(select(func.count()).select_from(Playbook))
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
                    upsell_strategy={
                        "accessories": ["gaming mouse", "gaming keyboard", "gaming headset", "gaming mousepad"],
                        "note": "Bundle a basic RGB mouse+keyboard set — adds £20-30 to sale price.",
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
                    upsell_strategy={
                        "accessories": ["optical mouse", "keyboard", "webcam"],
                        "note": "Office buyers expect peripherals. A mouse+keyboard adds £10-15 and makes it feel complete.",
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
                    upsell_strategy={
                        "accessories": ["monitor arm", "webcam 1080p"],
                        "note": "Dev buyers want ergonomics. A monitor arm + decent webcam adds £30-40.",
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
                    upsell_strategy={
                        "accessories": ["gaming mouse", "keyboard"],
                        "note": "Basic peripherals make it feel like a full package. Adds £10-15.",
                    },
                ),
            ]
            db.add_all(_default_playbooks)
            log.info("seeded.playbooks", count=len(_default_playbooks))

        # ── Migrate upsell_strategy into existing playbooks ───────────────────
        import json as _json
        _upsell_map = {
            "Budget Gaming PC": {
                "accessories": ["gaming mouse", "gaming keyboard", "gaming headset", "gaming mousepad"],
                "note": "Bundle a basic RGB mouse+keyboard set — adds £20-30 to sale price.",
            },
            "Office Workstation Flip": {
                "accessories": ["optical mouse", "keyboard", "webcam"],
                "note": "Office buyers expect peripherals. A mouse+keyboard adds £10-15 and makes it feel complete.",
            },
            "AI / ML Workstation": {
                "accessories": ["monitor arm", "webcam 1080p"],
                "note": "Dev buyers want ergonomics. A monitor arm + decent webcam adds £30-40.",
            },
            "Budget Builder (Sub-£100)": {
                "accessories": ["gaming mouse", "keyboard"],
                "note": "Basic peripherals make it feel like a full package. Adds £10-15.",
            },
        }
        from app.models.playbook import Playbook
        for _pb_name, _upsell in _upsell_map.items():
            existing_pb = await db.execute(
                select(Playbook).where(Playbook.name == _pb_name)
            )
            _pb = existing_pb.scalar_one_or_none()
            if _pb and not _pb.upsell_strategy:
                _pb.upsell_strategy = _upsell
                log.info("migrated.playbook.upsell_strategy", name=_pb_name)

        # ── Seed source-linked search terms (dynamic settings UX) ─────────────
        case_terms_count = await db.scalar(select(func.count()).select_from(SourceSearchTerm).where(SourceSearchTerm.scope == "cases"))
        if case_terms_count == 0:
            rows: list[SourceSearchTerm] = []
            for group_name, terms in _CASE_TAXONOMY.items():
                for term in terms:
                    rows.append(
                        SourceSearchTerm(
                            scope="cases",
                            group_name=group_name,
                            term=term,
                            source_names=_CASE_DEFAULT_SOURCES,
                            attributes=_infer_case_attributes(term, group_name),
                            notes="seeded_case_taxonomy",
                            enabled=True,
                        )
                    )
            db.add_all(rows)
            log.info("seeded.source_search_terms", scope="cases", count=len(rows))
        flip_terms_count = await db.scalar(select(func.count()).select_from(SourceSearchTerm).where(SourceSearchTerm.scope == "flip_opportunities"))
        if flip_terms_count == 0:
            rows: list[SourceSearchTerm] = []
            for term in _FLIP_SEARCH_TERMS_EXTENDED:
                rows.append(
                    SourceSearchTerm(
                        scope="flip_opportunities",
                        group_name="PC Flip Opportunities",
                        term=term,
                        source_names=["eBay UK", "eBay UK Auctions", "BidSpotter", "Gumtree", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware"],
                        attributes={},
                        notes="seeded_flip_terms",
                        enabled=True,
                    )
                )
            db.add_all(rows)
            log.info("seeded.source_search_terms", scope="flip_opportunities", count=len(rows))
        # Sync upgrade_parts search terms to the canonical model list.
        # Removes old broad terms (e.g. "DDR4 RAM") and ensures all canonical
        # model names are present, one SourceSearchTerm row per model.
        existing_upgrade_terms = {
            str(t).strip().lower()
            for t in (
                await db.execute(
                    select(SourceSearchTerm.term).where(SourceSearchTerm.scope == "upgrade_parts")
                )
            ).scalars().all()
            if str(t).strip()
        }
        canonical_lower = {t.lower() for t in _UPGRADE_SEARCH_TERMS}
        # Remove stale broad terms that are no longer in the canonical list
        stale = (
            await db.execute(
                select(SourceSearchTerm).where(
                    SourceSearchTerm.scope == "upgrade_parts",
                    ~SourceSearchTerm.term.in_(_UPGRADE_SEARCH_TERMS),
                )
            )
        ).scalars().all()
        for row in stale:
            await db.delete(row)
        if stale:
            log.info("upgrade_terms.removed_stale", count=len(stale))
        # Add missing canonical model terms
        missing = [t for t in _UPGRADE_SEARCH_TERMS if t.lower() not in existing_upgrade_terms]
        if missing:
            db.add_all([
                SourceSearchTerm(
                    scope="upgrade_parts",
                    group_name="Canonical Components",
                    term=term,
                    source_names=["eBay UK", "BargainHardware", "Amazon", "Scan", "Overclockers", "Box"],
                    attributes={},
                    notes="canonical_model",
                    enabled=True,
                )
                for term in missing
            ])
            log.info("upgrade_terms.added_canonical", count=len(missing))
        # Ensure accessory scope cannot silently disappear from DB.
        existing_accessory_terms = {
            str(t).strip().lower()
            for t in (
                await db.execute(
                    select(SourceSearchTerm.term).where(SourceSearchTerm.scope == "accessories")
                )
            ).scalars().all()
            if str(t).strip()
        }
        accessory_rows_to_add = []
        for term in _ACCESSORY_SEARCH_TERMS:
            norm = term.strip().lower()
            if norm in existing_accessory_terms:
                continue
            accessory_rows_to_add.append(
                SourceSearchTerm(
                    scope="accessories",
                    group_name="Gaming Accessories",
                    term=term,
                    source_names=["eBay", "Gumtree", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware"],
                    attributes={},
                    notes="seeded_accessory_terms",
                    enabled=True,
                )
            )
        if accessory_rows_to_add:
            db.add_all(accessory_rows_to_add)
            log.info("seeded.source_search_terms", scope="accessories", count=len(accessory_rows_to_add))

        # Normalize legacy/alias source names so eBay + Amazon route correctly
        # across all catalogues.
        _source_aliases = {
            "ebay": "eBay",
            "ebay uk": "eBay UK",
            "ebay uk auctions": "eBay UK Auctions",
            "amazon uk": "Amazon",
            "bargain hardware": "BargainHardware",
        }
        rows = (await db.execute(select(SourceSearchTerm))).scalars().all()
        updated_rows = 0
        flip_allowed = {"eBay UK", "eBay UK Auctions", "BidSpotter", "Gumtree", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware", "Vinted"}
        common_allowed = {"eBay", "Gumtree", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware"}
        cases_allowed = set(common_allowed) | {"eBay (Worldwide)", "CherryTree Inc"}
        upgrade_allowed = set(common_allowed)
        accessories_allowed = set(common_allowed)
        for row in rows:
            names = [str(s).strip() for s in (row.source_names or []) if str(s).strip()]
            if not names:
                continue
            normalized = []
            for s in names:
                normalized.append(_source_aliases.get(s.lower(), s))
            deduped = list(dict.fromkeys(normalized))
            scope = str(row.scope or "").strip().lower()
            if scope == "flip_opportunities":
                deduped = [s for s in deduped if s in flip_allowed]
                if not deduped:
                    deduped = ["eBay UK", "Gumtree", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware", "Vinted"]
                elif "Vinted" not in deduped:
                    deduped = deduped + ["Vinted"]
            elif scope == "cases":
                deduped = [s for s in deduped if s in cases_allowed]
                if not deduped:
                    deduped = list(_CASE_DEFAULT_SOURCES)
            elif scope == "upgrade_parts":
                deduped = [s for s in deduped if s in upgrade_allowed]
                if not deduped:
                    deduped = ["eBay", "Gumtree", "BargainHardware", "Amazon", "Temu", "AliExpress", "Alibaba"]
            elif scope == "accessories":
                deduped = [s for s in deduped if s in accessories_allowed]
                if not deduped:
                    deduped = ["eBay", "Gumtree", "Amazon", "Temu", "AliExpress", "Alibaba", "BargainHardware"]
            if deduped != names:
                row.source_names = deduped
                updated_rows += 1
        if updated_rows:
            log.info("migrated.source_search_terms.source_aliases", rows=updated_rows)

        await db.commit()
