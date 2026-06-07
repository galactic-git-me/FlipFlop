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
APIFY_ACTOR_ID    = "epctex/vinted-scraper"
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

    start_url = (
        f"https://www.vinted.co.uk/catalog"
        f"?search_text={term.replace(' ', '+')}"
        f"&catalog[]=2"          # Electronics category
        f"&price_from={int(min_price)}"
        f"&price_to={int(max_price)}"
        f"&order=newest_first"
    )

    actor_input = {
        "startUrls": [{"url": start_url}],
        "maxItems": MAX_ITEMS_PER_TERM,
        "proxy": {"useApifyProxy": True},
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
    Map an epctex/vinted-scraper output dict → RawListing-compatible dict.

    epctex actor output fields (typical):
      id, title, price, currency, url, photos/image, condition,
      brand, size, seller (username), location, description
    """
    try:
        title = (item.get("title") or item.get("name") or "").strip()
        if not title:
            return None

        # Price — actor may return float or {"amount": x, "currency": "GBP"}
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

        # Images
        photos = item.get("photos") or item.get("images") or []
        if isinstance(photos, list):
            image_urls = [
                (p.get("url") or p.get("full_size_url") or p) if isinstance(p, dict) else p
                for p in photos
            ]
            image_urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")]
        else:
            single = item.get("image") or item.get("photo")
            image_urls = [single] if isinstance(single, str) and single.startswith("http") else []

        condition = (
            item.get("condition")
            or item.get("status")
            or item.get("conditionTitle")
            or "used"
        )

        seller = item.get("seller") or item.get("username") or item.get("user") or {}
        seller_name = seller.get("login") if isinstance(seller, dict) else str(seller)

        location = (
            item.get("location")
            or (item.get("user", {}) or {}).get("location")
            or "UK"
        )

        description = item.get("description") or ""

        return {
            "external_id":   external_id,
            "title":         title,
            "price":         price,
            "url":           url,
            "location":      location,
            "condition":     str(condition).lower() if condition else "used",
            "description":   description,
            "image_urls":    image_urls[:6],
            "source_name":   "Vinted",
            "listing_type":  "buy_it_now",
            "seller_name":   seller_name,
            "found_via_term": found_via_term,
        }

    except Exception as exc:
        log.debug("vinted.parse_error", error=str(exc))
        return None
