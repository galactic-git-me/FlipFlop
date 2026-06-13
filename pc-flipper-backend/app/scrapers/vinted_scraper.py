"""
Vinted Scraper — Direct API (no Apify required)

Vinted's website calls an internal REST API for all search results.
We replicate the same flow: hit the homepage to pick up session cookies,
then call /api/v2/catalog/items.  No login or API key needed.

Coverage:
  - Flip Opportunities: gaming PCs, desktops, setups
  - Components: GPUs, CPUs, RAM, SSDs, motherboards, PSUs, cases
  - Accessories: keyboards, mice, headsets
"""

import asyncio
import re
import structlog
import httpx
from typing import Optional

log = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

VINTED_BASE    = "https://www.vinted.co.uk"
VINTED_API     = f"{VINTED_BASE}/api/v2/catalog/items"
PER_PAGE       = 96     # Vinted max per page
MAX_PAGES      = 3      # cap to avoid hammering
REQUEST_DELAY  = 1.5    # seconds between requests

# Category IDs on vinted.co.uk — 2187 = Electronics, 2399 = Computers & Networking
ELECTRONICS_CATALOG_ID = "2187"

VINTED_SEARCH_TERMS = [
    # Whole systems (flip opportunities)
    "gaming PC",
    "gaming computer",
    "desktop PC",
    "workstation PC",
    "gaming setup",
    # Components
    "graphics card GPU",
    "CPU processor",
    "RAM DDR4 DDR5",
    "SSD NVMe",
    "motherboard",
    "power supply PSU",
    "PC case tower ATX",
    # Accessories
    "gaming keyboard",
    "gaming mouse",
    "gaming headset",
]

_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
    "Origin": VINTED_BASE,
    "Referer": VINTED_BASE + "/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


# ── Session bootstrap ─────────────────────────────────────────────────────────

async def _get_session_client() -> httpx.AsyncClient:
    """Return an httpx client with Vinted session cookies pre-loaded."""
    client = httpx.AsyncClient(
        headers=_HEADERS,
        follow_redirects=True,
        timeout=30.0,
    )
    try:
        # First visit sets _vinted_fr_session and CSRF cookies
        resp = await client.get(VINTED_BASE)
        resp.raise_for_status()
        log.debug("vinted.session_init", cookies=list(client.cookies.keys()))
    except Exception as exc:
        log.warning("vinted.session_init_failed", error=str(exc))
    return client


# ── Item parser ───────────────────────────────────────────────────────────────

_CONDITION_MAP = {
    1: "new",          # New with tags
    2: "new",          # New without tags
    3: "used",         # Very good
    4: "used",         # Good
    5: "used",         # Satisfactory
    6: "for_parts",    # Not working / for parts
}

def _parse_item(item: dict, term: str) -> Optional[dict]:
    try:
        item_id   = str(item.get("id") or "")
        title     = str(item.get("title") or "").strip()
        if not title or not item_id:
            return None

        price_obj = item.get("price") or item.get("priceNumeric") or {}
        if isinstance(price_obj, dict):
            price_str = price_obj.get("amount") or price_obj.get("value") or "0"
        else:
            price_str = str(price_obj)
        price = float(re.sub(r"[^\d.]", "", str(price_str)) or 0)
        if price <= 0:
            return None

        url = item.get("url") or f"{VINTED_BASE}/items/{item_id}"
        if not url.startswith("http"):
            url = VINTED_BASE + url

        image_url = ""
        photos = item.get("photos") or []
        if photos:
            img = photos[0] if isinstance(photos[0], str) else (photos[0].get("full_size_url") or photos[0].get("url") or "")
            image_url = img
        if not image_url:
            image_url = item.get("photo", {}).get("full_size_url") or item.get("photo", {}).get("url") or ""

        cond_id   = item.get("status_id") or item.get("item_condition_id") or 3
        condition = _CONDITION_MAP.get(int(cond_id), "used")

        seller = (item.get("user") or {})
        seller_name = seller.get("login") or seller.get("name") or None

        return {
            "external_id":    f"vinted_{item_id}",
            "title":          title,
            "price":          price,
            "url":            url,
            "location":       "UK",
            "condition":      condition,
            "description":    str(item.get("description") or ""),
            "image_urls":     [image_url] if image_url else [],
            "source_name":    "Vinted",
            "listing_type":   "buy_it_now",
            "seller_name":    seller_name,
            "found_via_term": term,
        }
    except Exception as exc:
        log.debug("vinted.parse_error", error=str(exc))
        return None


# ── Search ────────────────────────────────────────────────────────────────────

async def _search_term(
    client: httpx.AsyncClient,
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    results: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        params: dict = {
            "search_text":  term,
            "per_page":     PER_PAGE,
            "page":         page,
            "order":        "newest_first",
            "catalog_ids":  ELECTRONICS_CATALOG_ID,
        }
        if min_price > 0:
            params["price_from"] = min_price
        if max_price > 0:
            params["price_to"]   = max_price
        try:
            await asyncio.sleep(REQUEST_DELAY)
            resp = await client.get(VINTED_API, params=params)
            if resp.status_code == 401:
                log.warning("vinted.auth_error", term=term, page=page)
                break
            if resp.status_code != 200:
                log.debug("vinted.bad_status", term=term, page=page, status=resp.status_code)
                break
            data  = resp.json()
            items = data.get("items") or []
            if not items:
                break
            for item in items:
                parsed = _parse_item(item, term)
                if parsed:
                    results.append(parsed)
            # Stop early if fewer items returned than requested (last page)
            if len(items) < PER_PAGE:
                break
        except Exception as exc:
            log.warning("vinted.request_error", term=term, page=page, error=str(exc))
            break
    log.debug("vinted.term_done", term=term, found=len(results))
    return results


# ── Public entry points ───────────────────────────────────────────────────────

async def fetch_vinted_listings(
    search_terms: list[str] | None = None,
    min_price: float = 10,
    max_price: float = 2500,
) -> list[dict]:
    """
    Fetch active Vinted UK listings and return dicts compatible with
    the RawListing constructor in scraper.py.
    """
    terms = search_terms or VINTED_SEARCH_TERMS
    seen_ids: set[str] = set()
    all_results: list[dict] = []

    client = await _get_session_client()
    try:
        for term in terms:
            try:
                items = await _search_term(client, term, min_price, max_price)
                for item in items:
                    if item["external_id"] not in seen_ids:
                        seen_ids.add(item["external_id"])
                        all_results.append(item)
            except Exception as exc:
                log.warning("vinted.term_error", term=term, error=str(exc))
    finally:
        await client.aclose()

    log.info("vinted.done", fetched=len(all_results), terms=len(terms))
    return all_results


async def scrape_vinted_tech() -> dict:
    """
    Called by the components aggregator — returns {"listings": [...]} where
    each entry has price_gbp, title, condition, category and source_url.
    """
    items = await fetch_vinted_listings(
        search_terms=[
            "graphics card GPU",
            "CPU processor",
            "RAM DDR4 DDR5",
            "SSD NVMe M.2",
            "motherboard",
            "power supply PSU",
            "PC case ATX",
        ],
        min_price=5,
        max_price=1500,
    )
    listings = [
        {
            "title":      i["title"],
            "price_gbp":  i["price"],
            "condition":  i["condition"],
            "source_url": i["url"],
            "seller":     i.get("seller_name") or "Vinted User",
            "category":   i.get("found_via_term", ""),
        }
        for i in items
    ]
    return {"listings": listings}
