"""Evidence capture, SCREENED.json / latest_gems.json outputs, and 24h
retention cleanup (PRD §8, §32-34). flipflop-api plays the "local companion
service" role here (see docs/ARCHITECTURE_GAP_ANALYSIS.md §4) — it already
runs locally on the user's machine and already owns a managed Playwright
pool (app.services.browser_pool), so evidence capture reuses that instead
of spinning up a second browser-automation stack.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from app.services.browser_pool import managed_playwright
from app.gem_radar.schemas import ScoredListing

log = structlog.get_logger(__name__)

# flipflop-api/scrapes — sibling to app/, alembic/, etc. Not the extension
# repo's own (empty) Scrapes/ folder, since the extension has no durable
# filesystem access of its own in Manifest V3 (PRD §4.1 responsibility split).
SCRAPES_DIR = Path(__file__).resolve().parents[2] / "scrapes"

_SUPER_GEM_OR_GEM = {"SUPER_GEM", "GEM"}


def _sanitise(term: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", term).strip("_")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


@dataclass
class EvidenceCaptureResult:
    pdf_path: str | None
    capture_method: str
    error: str | None


async def _do_capture(source_url: str, dest: Path) -> None:
    async with managed_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(source_url, wait_until="networkidle", timeout=20_000)
            await page.pdf(path=str(dest))
        finally:
            await browser.close()


# Hard ceiling on the whole capture (launch + navigate + pdf). page.goto()
# already has its own 20s timeout, but browser launch and PDF rendering have
# none — a stalled subprocess (antivirus, resource contention, Windows
# quirks) would otherwise hang this coroutine, and with it the whole /scans
# request, forever. This is best-effort evidence capture; it must never be
# able to block the scan result from reaching the extension.
_CAPTURE_TIMEOUT_SECONDS = 30


async def capture_evidence_pdf(source_url: str, query: str) -> EvidenceCaptureResult:
    """Captures the search-results page as a timestamped PDF via the shared
    Playwright pool. Returns capture_method="unavailable" (not a fabricated
    path) if Chromium isn't installed, the page fails to load, or capture
    doesn't finish within _CAPTURE_TIMEOUT_SECONDS — PRD §38 treats capture
    failure as a reason to mark the scan PARTIAL, not FAILED.
    """
    SCRAPES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_timestamp()}_{_sanitise(query)}.pdf"
    dest = SCRAPES_DIR / filename

    try:
        await asyncio.wait_for(_do_capture(source_url, dest), timeout=_CAPTURE_TIMEOUT_SECONDS)
        return EvidenceCaptureResult(pdf_path=str(dest), capture_method="playwright_pdf", error=None)
    except Exception as exc:
        log.warning("gem_radar.evidence.capture_failed", url=source_url, error=str(exc))
        return EvidenceCaptureResult(pdf_path=None, capture_method="unavailable", error=str(exc))


def write_screened_json(
    search_run_id: str,
    search_id: str,
    query: str,
    source_url: str,
    evidence_pdf_filename: str | None,
    results: list[ScoredListing],
    deep_researched_count: int,
) -> str:
    """Writes <timestamp>_<term>_SCREENED.json (PRD §32.3/§33) sorted by
    dealScore desc, confidenceScore desc, variancePercent desc.
    """
    SCRAPES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_timestamp()}_{_sanitise(query)}_SCREENED.json"
    dest = SCRAPES_DIR / filename

    def _variance_pct(r: ScoredListing) -> float:
        median = r.prices.ebay_used_sold.median or r.prices.ebay_used_bin.median
        if not median:
            return 0.0
        return (median - r.listing.current_delivered_price) / median * 100

    sorted_results = sorted(
        results, key=lambda r: (r.deal_score, r.confidence_score, _variance_pct(r)), reverse=True
    )

    payload = {
        "schemaVersion": "1.0",
        "searchRunId": search_run_id,
        "search": {"id": search_id, "term": query, "marketplace": "ebay_uk", "url": source_url},
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "evidencePdf": evidence_pdf_filename,
        "resultCount": len(results),
        "deepResearchedCount": deep_researched_count,
        "results": [r.model_dump(by_alias=True, mode="json") for r in sorted_results],
    }
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(dest)


def update_latest_gems(results: list[ScoredListing]) -> str:
    """Maintains scrapes/latest_gems.json — a rolling consolidated view of
    every SUPER_GEM/GEM across recent scans, keyed by listingId so repeat
    sightings update in place rather than duplicating (PRD §32.4).
    """
    SCRAPES_DIR.mkdir(parents=True, exist_ok=True)
    dest = SCRAPES_DIR / "latest_gems.json"

    existing: dict[str, dict] = {}
    if dest.exists():
        try:
            existing = {g["listing"]["listingId"]: g for g in json.loads(dest.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, KeyError):
            log.warning("gem_radar.evidence.latest_gems_corrupted_resetting")
            existing = {}

    for r in results:
        if r.classification in _SUPER_GEM_OR_GEM:
            existing[r.listing.listing_id] = r.model_dump(by_alias=True, mode="json")

    ordered = sorted(existing.values(), key=lambda g: g["dealScore"], reverse=True)
    dest.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
    return str(dest)


def cleanup_old_artifacts(
    retention_hours: int,
    preserve_purchased_listing_ids: set[str],
    preserve_watched_listing_ids: set[str],
) -> int:
    """Deletes scrape artifacts older than retention_hours (PRD §34).
    latest_gems.json and files whose name embeds a preserved listing ID are
    never deleted — a purchased or watched listing's evidence survives even
    after the default 24h window (PRD §34.3 "never delete purchase
    evidence").
    """
    if not SCRAPES_DIR.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    preserved_ids = preserve_purchased_listing_ids | preserve_watched_listing_ids
    removed = 0

    for path in SCRAPES_DIR.iterdir():
        if path.name == "latest_gems.json" or not path.is_file():
            continue
        if any(listing_id in path.name for listing_id in preserved_ids):
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            path.unlink()
            removed += 1

    if removed:
        log.info("gem_radar.evidence.retention_cleanup", removed=removed, cutoff=cutoff.isoformat())
    return removed
