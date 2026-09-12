"""Standalone Gem Radar API — mounts only the gem_radar router.

Runs the real scoring pipeline (app/gem_radar/*) with none of the full
app's side effects: no cron scheduler, no AI-eval worker pools, no
dev-data wipe, no antibot preflight. Safe to leave running continuously
for the browser extension to talk to.

Usage: uvicorn app.gem_radar_standalone:app --host 127.0.0.1 --port 18000
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import os

# Load .env.local from parent directory (startup script runs from flipflop-api subdirectory)
# This ensures eBay API credentials and other config are available
_env_path = Path(__file__).parent.parent / ".env.local"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.gem_radar import router as gem_radar_router
from app.routes.cases import router as cases_router
from app.database import Base, engine
from app.config import get_settings
from app.models import case as case_models
from app.workers.queue_processor import process_submission_queue
from app.workers.database_cleaner import run_database_cleaner
from app.services.amazon_bestsellers import scrape_amazon_bestsellers


async def _amazon_bestseller_loop() -> None:
    """Keep production case popularity current when the web-only API disables cron."""
    interval = max(1, get_settings().amazon_case_bestsellers_interval_hours) * 3600
    await asyncio.sleep(120)
    while True:
        try:
            await scrape_amazon_bestsellers()
        except Exception:
            # The scraper logs its own failure; keep the worker alive for the
            # next daily attempt rather than turning a retailer outage into a
            # process restart loop.
            pass
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Drains gem_radar_scan_submissions sequentially so concurrent extension
    # submissions never pile up as overlapping slow /scans requests — see
    # app/workers/queue_processor.py. Without this the queue table just
    # accumulates rows forever since nothing ever reads from it.
    worker_task = None
    cleaner_task = None
    bestseller_task = None
    if not get_settings().web_only:
        worker_task = asyncio.create_task(process_submission_queue())
        cleaner_task = asyncio.create_task(run_database_cleaner())
        bestseller_task = asyncio.create_task(_amazon_bestseller_loop())
    yield
    for task in (worker_task, cleaner_task, bestseller_task):
        if task is not None:
            task.cancel()
    await engine.dispose()


app = FastAPI(title="Gem Radar (standalone)", lifespan=lifespan)

# Allow CORS from Chrome extension (use regex pattern for wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(gem_radar_router, prefix="/api")
app.include_router(cases_router, prefix="/api")
