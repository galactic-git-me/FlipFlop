"""
Vinted Scraper (Apify) — Extract PC/gaming deals from Vinted UK

Uses Apify actor: epctex/vinted-scraper
Requires: APIFY_API_TOKEN environment variable

Coverage:
  - Flip Opportunities: gaming PCs, desktops, setups
  - Components: GPUs, CPUs, RAM, SSDs, motherboards, PSUs
  - PC Cases: ATX/mATX/ITX towers
  - Accessories: keyboards, mice, headsets, monitors

Apify free tier ($5/month) easily covers ~20 runs/day.
"""

import asyncio
import os
import structlog
import httpx
from datetime import datetime
from typing import Optional

log = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

APIFY_API_TOKEN   = os.getenv("APIFY_API_TOKEN", "")
APIFY_ACTOR_ID    = "fHbcZlsTaRkK23UeB"   # automation-lab/vinted-scraper
APIFY_BASE_URL    = "https://api.apify.com/v2"

# Search terms covering all four catalogue tabs
# vinted.co.uk uses catalog[]=2 for electronics/tech
VINTED_SEARCH_TERMS = [
    # ── Flip Opportunities (whole systems) ───────────────────────────────
    "gaming PC",
    "gaming computer",
    "desktop PC",
    "workstation PC",
    "gaming setup",
    # ── Components ───────────────────────────────────────────────────────
    "graphics card GPU",
    "CPU processor",
    "RAM memory DDR4 DDR5",
    "SSD NVMe M.2",
    "motherboard",
    "power supply PSU",
    # ── PC Cases ─────────────────────────────────────────────────────────
    "PC case tower ATX",
    # ── Accessories ──────────────────────────────────────────────────────
    "gaming keyboard",
    "gaming mouse",
    "gaming headset",
]

MAX_ITEMS_PER_TERM = 40   # Apify free tier is generous; tune down if needed
POLL_INTERVAL_S    = 2
POLL_MAX_ATTEMPTS  = 60   # 2 min max wait per run


# ── Public entry point ────────────────────────────────────────────────────────

async def fetch_vinted_listings(
    search_terms: list[str] | None = None,
    min_price: float = 10,
    max_price: float = 2500,
) -> list[dict]:
    """
    Fetch active Vinted UK listings via Apify and return a list of
    dicts compatible with the RawListing constructor in scraper.py.

    Falls back to empty list (with a warning) if APIFY_API_TOKEN is missing.
    """
    if not APIFY_API_TOKEN:
        log.warning(
            "vinted.apify_token_missing",
            hint="Set APIFY_API_TOKEN in docker-compose / .env.local",
        )
        return []

    terms = search_terms or VINTED_SEARCH_TERMS
    results: list[dict] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=120.0) as client:
        for term in terms:
            try:
                items = await _run_apify_vinted(client, term, min_price, max_price)
                for item in items:
                    parsed = _parse_item(item, term)
                    if parsed and parsed["external_id"] not in seen_ids:
                        seen_ids.add(parsed["external_id"])
                        results.append(parsed)
            except Exception as exc:
                log.warning("vinted.term_error", term=term, error=str(exc))

    log.info("vinted.done", fetched=len(results), terms=len(terms))
    return results


# ── Apify helpers ─────────────────────────────────────────────────────────────

async def _run_apify_vinted(
    client: httpx.AsyncClient,
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Start an Apify run, poll until SUCCEEDED, return dataset items."""

    actor_input = {
        "searchQuery": term,
        "maxItems": MAX_ITEMS_PER_TERM,
        "domain": "vinted.co.uk",
    }

    # Start run
    resp = await client.post(
        f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR_ID}/runs",
        json=actor_input,
        headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"},
        timeout=30.0,
    )
    if resp.status_code not in (200, 201):
        log.warning("vinted.apify_start_error", term=term, status=resp.status_code, body=resp.text[:200])
        return []

    run_id   = resp.json().get("data", {}).get("id")
    if not run_id:
        log.warning("vinted.no_run_id", term=term)
        return []

    log.debug("vinted.apify_run_started", term=term, run_id=run_id)

    # Poll for completion
    for _ in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_S)
        status_resp = await client.get(
            f"{APIFY_BASE_URL}/actor-runs/{run_id}",
            headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"},
        )
        if status_resp.status_code != 200:
            continue
        run_data = status_resp.json().get("data", {})
        status   = run_data.get("status")

        if status == "SUCCEEDED":
            dataset_id = run_data.get("defaultDatasetId")
            if not dataset_id:
                return []
            items_resp = await client.get(
                f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
                headers={"Authorization": f"Bearer {APIFY_API_TOKEN}"},
                params={"limit": MAX_ITEMS_PER_TERM},
            )
            if items_resp.status_code == 200:
                items = items_resp.json()
                log.debug("vinted.apify_run_done", term=term, items=len(items))
                return items
            return []

        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            log.warning("vinted.apify_run_failed", term=term, status=status)
            return []

    log.warning("vinted.apify_poll_timeout", term=term, run_id=run_id)
    return []


# ── Item parser ───────────────────────────────────────────────────────────────

def _parse_item(item: dict, found_via_term: str) -> Optional[dict]:
    """
    Map an automation-lab/vinted-scraper output dict → RawListing-compatible dict.

    Actor output fields:
      id, title, price, currency, brand, size, condition, url,
      imageUrl, description, category, color, domain, query, page, scrapedAt
    """
    try:
        title = (item.get("title") or item.get("name") or "").strip()
        # Actor returns brand as title when no proper title — skip those
        if not title or title.lower() in ("generic", ""):
            return None

        # Price — actor returns a plain number
        raw_price = item.get("price") or item.get("priceNumeric")
        if isinstance(raw_price, dict):
            raw_price = raw_price.get("amount") or raw_price.get("value")
        price = float(raw_price or 0)
        if price <= 0:
            return None

        url = item.get("url") or item.get("itemUrl") or ""
        if not url:
            return None

        item_id = str(item.get("id") or item.get("itemId") or abs(hash(url)))
        external_id = f"vinted_{item_id}"

        # Images — actor returns a single imageUrl string
        image_url = item.get("imageUrl") or item.get("image") or ""
        image_urls = [image_url] if isinstance(image_url, str) and image_url.startswith("http") else []

        condition = item.get("condition") or item.get("status") or "used"

        description = item.get("description") or ""

        return {
            "external_id":    external_id,
            "title":          title,
            "price":          price,
            "url":            url,
            "location":       "UK",
            "condition":      str(condition).lower() if condition else "used",
            "description":    description,
            "image_urls":     image_urls,
            "source_name":    "Vinted",
            "listing_type":   "buy_it_now",
            "seller_name":    None,
            "found_via_term": found_via_term,
        }

    except Exception as exc:
        log.debug("vinted.parse_error", error=str(exc))
        return None
