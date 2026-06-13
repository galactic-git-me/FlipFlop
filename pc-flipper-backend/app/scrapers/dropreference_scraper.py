"""
DropReference Scraper — new PC components and peripherals price reference data.

Target: https://dropreference.com/en/stock
Data type: NEW items only — retail pricing aggregated from European market.
Component categories: GPU, CPU, RAM, Storage, PSU, Motherboard, Case, Cooling.
Peripheral categories: Mouse, Keyboard, Headset (fed into accessories catalogue).

No flip opportunities on this source — price data only.

Extraction strategy:
  Components: Angular SSR embeds structured JSON in the #ng-state <script> tag.
              The 'board.entries' key contains [{value, nbr, price}] per model.
  Peripherals: Individual product cards are SSR-rendered in the HTML.
               Anchors with /en/product/{ean} hrefs provide the product URL;
               the nearest h2 gives the title and price text contains the €amount.
  Prices are EUR; converted to GBP via DROPREFERENCE_EUR_GBP_RATE env var
  (default 0.85).
"""

import asyncio
import json
import os
import re
import structlog
from datetime import datetime
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)

BASE_URL = "https://dropreference.com"
_DEFAULT_EUR_GBP = 0.85  # override via DROPREFERENCE_EUR_GBP_RATE

# Category slug → our internal category label (matches _parse_component_type inputs)
COMPONENT_CATEGORIES: dict[str, str] = {
    "gpu":         "GPU",
    "cpu":         "CPU",
    "ram":         "RAM",
    "storage":     "SSD",
    "psu":         "PSU",
    "motherboard": "Motherboard",
    "case":        "Case",
    "cooling":     "Cooling",
}

# Peripheral slugs mapped to accessory theme labels
PERIPHERAL_CATEGORIES: dict[str, str] = {
    "mouse":    "Mouse",
    "keyboard": "Keyboard",
    "headset":  "Headset",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


class DropReferenceConfig:
    base_url = BASE_URL
    request_timeout = 20.0
    request_delay = 1.5      # seconds between category requests (polite crawling)
    max_price_eur = 600.0    # filter out ultra-high-end outliers
    min_price_eur = 5.0


def _eur_to_gbp(eur: float) -> float:
    rate = float(os.getenv("DROPREFERENCE_EUR_GBP_RATE", str(_DEFAULT_EUR_GBP)))
    return round(eur * rate, 2)


def _url_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def _fetch_page(client: httpx.AsyncClient, path: str) -> Optional[str]:
    url = f"{BASE_URL}{path}"
    try:
        r = await client.get(url, headers=_HEADERS)
        if r.status_code == 200:
            return r.text
        log.warning("dropreference.http_error", path=path, status=r.status_code)
    except Exception as exc:
        log.warning("dropreference.fetch_error", path=path, error=str(exc))
    return None


def _extract_ng_state(html: str) -> dict:
    """Pull the Angular SSR #ng-state JSON out of the page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", {"id": "ng-state"})
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except Exception as exc:
            log.warning("dropreference.ng_state_parse_error", error=str(exc))
    return {}


# ---------------------------------------------------------------------------
# Component parsing
# ---------------------------------------------------------------------------

def _parse_component_entries(html: str, slug: str) -> List[dict]:
    """
    Extract component model groups from the ng-state transfer state.

    board.entries format: [{"value": "RTX 5060 Ti", "nbr": 108, "price": 319}, ...]
    Each entry represents a model grouping with the lowest available retail price.
    """
    ng = _extract_ng_state(html)
    raw = ng.get("board.entries", [])
    if not raw:
        log.debug("dropreference.components.no_entries", slug=slug)
        return []

    category_label = COMPONENT_CATEGORIES.get(slug, "Other")
    results: List[dict] = []

    for entry in raw:
        name = str(entry.get("value") or "").strip()
        price_eur = entry.get("price") or 0
        nbr = entry.get("nbr") or 0
        if not name or not price_eur:
            continue
        price_eur = float(price_eur)
        if price_eur < DropReferenceConfig.min_price_eur or price_eur > DropReferenceConfig.max_price_eur:
            continue

        results.append({
            "title": name,
            "source_url": f"{BASE_URL}/en/stock/{slug}/{_url_slug(name)}",
            "price_gbp": _eur_to_gbp(price_eur),
            "original_price_eur": price_eur,
            "nbr_listings": nbr,
            "shipping_cost_gbp": 0.0,
            "in_stock": True,
            "condition": "new",
            "seller": "DropReference",
            "category": category_label,
            "component_type": name,
            "source": "DropReference",
            "fetched_at": datetime.utcnow().isoformat(),
        })

    return results


# ---------------------------------------------------------------------------
# Peripheral parsing
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r"([\d,]+)€")


def _parse_peripheral_entries(html: str, slug: str) -> List[dict]:
    """
    Extract individual product listings from a rendered peripheral category page.

    Product anchors carry aria-label="View details for {product name}" and link
    to /en/product/{ean}.  The price (e.g. "177€") lives in a parent container
    reachable within 8 levels above the anchor.
    """
    soup = BeautifulSoup(html, "html.parser")
    theme = PERIPHERAL_CATEGORIES.get(slug, "Accessory")
    results: List[dict] = []
    seen_hrefs: set[str] = set()

    product_anchors = soup.find_all(
        "a",
        href=re.compile(r"/en/product/\d+"),
        attrs={"aria-label": re.compile(r"^View details for ")},
    )
    for anchor in product_anchors:
        href = str(anchor.get("href") or "")
        if not href:
            continue
        if not href.startswith("http"):
            href = f"{BASE_URL}{href}"
        if href in seen_hrefs:
            continue

        aria = str(anchor.get("aria-label") or "")
        title = aria.replace("View details for ", "").strip()
        if not title:
            continue

        # Walk up to find a container that includes the price
        container = anchor.parent
        price_match = None
        for _ in range(8):
            if container is None:
                break
            price_match = _PRICE_RE.search(container.get_text())
            if price_match:
                break
            container = container.parent

        if not price_match:
            continue

        try:
            price_eur = float(price_match.group(1).replace(",", ""))
        except ValueError:
            continue

        if price_eur < DropReferenceConfig.min_price_eur or price_eur > DropReferenceConfig.max_price_eur:
            continue

        seen_hrefs.add(href)
        results.append({
            "title": title,
            "source_url": href,
            "price_gbp": _eur_to_gbp(price_eur),
            "original_price_eur": price_eur,
            "shipping_cost_gbp": 0.0,
            "in_stock": True,
            "condition": "new",
            "seller": "DropReference",
            "theme": theme,
            "source": "DropReference",
            "fetched_at": datetime.utcnow().isoformat(),
        })

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_dropreference_components() -> dict:
    """
    Scrape DropReference for new PC component reference prices.

    Returns dict with 'listings' and 'stats'.
    Each listing represents a model group with the lowest retail EUR price
    converted to GBP — suitable for supplementing the components catalogue.
    """
    log.info("dropreference_scraper.components.starting", categories=len(COMPONENT_CATEGORIES))
    listings: List[dict] = []
    stats: dict = {"total_found": 0, "valid": 0, "errors": 0, "categories_scraped": 0, "by_category": {}}

    async with httpx.AsyncClient(timeout=DropReferenceConfig.request_timeout, follow_redirects=True) as client:
        for slug in COMPONENT_CATEGORIES:
            try:
                html = await _fetch_page(client, f"/en/stock/{slug}")
                if not html:
                    stats["errors"] += 1
                    continue

                entries = _parse_component_entries(html, slug)
                stats["categories_scraped"] += 1
                stats["total_found"] += len(entries)
                stats["valid"] += len(entries)
                stats["by_category"][slug] = len(entries)
                listings.extend(entries)

                log.info("dropreference_scraper.components.category_done", slug=slug, found=len(entries))
                await asyncio.sleep(DropReferenceConfig.request_delay)

            except Exception as exc:
                log.warning("dropreference_scraper.components.category_error", slug=slug, error=str(exc))
                stats["errors"] += 1

    log.info("dropreference_scraper.components.complete", **{k: v for k, v in stats.items() if k != "by_category"})
    return {
        "source": "DropReference",
        "listings": listings,
        "stats": stats,
        "fetched_at": datetime.utcnow().isoformat(),
    }


async def scrape_dropreference_peripherals() -> dict:
    """
    Scrape DropReference peripheral categories for new accessory price data.

    Returns dict with 'listings' and 'stats'.
    Each listing is an individual product suitable for the accessories catalogue.
    """
    log.info("dropreference_scraper.peripherals.starting", categories=len(PERIPHERAL_CATEGORIES))
    listings: List[dict] = []
    stats: dict = {"total_found": 0, "valid": 0, "errors": 0, "categories_scraped": 0, "by_category": {}}

    async with httpx.AsyncClient(timeout=DropReferenceConfig.request_timeout, follow_redirects=True) as client:
        for slug in PERIPHERAL_CATEGORIES:
            try:
                html = await _fetch_page(client, f"/en/stock/{slug}")
                if not html:
                    stats["errors"] += 1
                    continue

                entries = _parse_peripheral_entries(html, slug)
                stats["categories_scraped"] += 1
                stats["total_found"] += len(entries)
                stats["valid"] += len(entries)
                stats["by_category"][slug] = len(entries)
                listings.extend(entries)

                log.info("dropreference_scraper.peripherals.category_done", slug=slug, found=len(entries))
                await asyncio.sleep(DropReferenceConfig.request_delay)

            except Exception as exc:
                log.warning("dropreference_scraper.peripherals.category_error", slug=slug, error=str(exc))
                stats["errors"] += 1

    log.info("dropreference_scraper.peripherals.complete", **{k: v for k, v in stats.items() if k != "by_category"})
    return {
        "source": "DropReference",
        "listings": listings,
        "stats": stats,
        "fetched_at": datetime.utcnow().isoformat(),
    }


async def get_dropreference_status() -> dict:
    rate = float(os.getenv("DROPREFERENCE_EUR_GBP_RATE", str(_DEFAULT_EUR_GBP)))
    return {
        "source": "DropReference",
        "enabled": True,
        "base_url": BASE_URL,
        "component_categories": list(COMPONENT_CATEGORIES.keys()),
        "peripheral_categories": list(PERIPHERAL_CATEGORIES.keys()),
        "eur_gbp_rate": rate,
        "scrape_frequency_hours": DropReferenceConfig.request_timeout,
        "data_type": "new_items_only",
        "note": "EUR prices converted to GBP. Set DROPREFERENCE_EUR_GBP_RATE to override default 0.85.",
    }
