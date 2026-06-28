"""
Vinted Scraper - Extract component deals using Apify API

Target: Vinted marketplace for GPUs, CPUs, RAM, SSDs, motherboards, PSUs, cases
Strategy: Use Apify marketplace scraper for reliable data extraction
Requires: APIFY_API_TOKEN environment variable
"""

import asyncio
import structlog
import os
from typing import Optional
import httpx

log = structlog.get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

class VintedScraperConfig:
    """Configuration for Vinted scraper using Apify."""

    apify_api_token = os.getenv("APIFY_API_TOKEN", "")
    apify_actor_id = "drobnikj/ecommerce-scraper"
    apify_api_url = "https://api.apify.com/v2/acts"
    timeout_seconds = 60
    max_results_per_run = 100


async def fetch_vinted_listings(
    search_terms: list[str] | None = None,
    min_price: float = 10,
    max_price: float = 2500,
) -> list[dict]:
    """
    Fetch Vinted listings using Apify API.

    Returns list of dicts with: title, price, url, condition, image_urls, seller_name
    """
    if not VintedScraperConfig.apify_api_token:
        log.warning("vinted.apify_token_missing")
        return []

    terms = search_terms or [
        "graphics card", "GPU", "DDR4 RAM", "DDR5 RAM",
        "NVMe SSD", "motherboard", "power supply", "PC case",
    ]

    all_results = []
    seen_urls = set()

    async with httpx.AsyncClient(timeout=VintedScraperConfig.timeout_seconds) as client:
        for term in terms:
            try:
                items = await _run_apify_vinted_search(client, term, min_price, max_price)
                for item in items:
                    url = item.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(item)
            except Exception as exc:
                log.warning("vinted.term_error", term=term, error=str(exc))
            await asyncio.sleep(0.5)

    log.info("vinted.done", fetched=len(all_results), terms=len(terms))
    return all_results


async def _run_apify_vinted_search(
    client: httpx.AsyncClient,
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Run Apify scraper for a single search term on Vinted."""

    run_url = f"{VintedScraperConfig.apify_api_url}/{VintedScraperConfig.apify_actor_id}/runs"

    input_data = {
        "startUrls": [
            {
                "url": f"https://www.vinted.co.uk/catalog?search_text={term}&order=newest_first"
            }
        ],
        "maxItems": VintedScraperConfig.max_results_per_run,
        "maxRequests": 5,
        "proxySettings": {"useApifyProxy": True},
    }

    try:
        # Start Apify run
        response = await client.post(
            run_url,
            headers={"Authorization": f"Bearer {VintedScraperConfig.apify_api_token}"},
            json=input_data,
        )

        if response.status_code != 201:
            log.warning("vinted.apify_run_failed", term=term, status=response.status_code)
            return []

        run_data = response.json()
        run_id = run_data.get("data", {}).get("id")
        if not run_id:
            return []

        # Poll for completion
        items = await _get_apify_results(client, run_id, term, min_price, max_price)
        log.debug("vinted.term_done", term=term, found=len(items))
        return items

    except Exception as exc:
        log.warning("vinted.apify_error", term=term, error=str(exc))
        return []


async def _get_apify_results(
    client: httpx.AsyncClient,
    run_id: str,
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Poll Apify for results and parse them."""

    status_url = f"{VintedScraperConfig.apify_api_url}/{VintedScraperConfig.apify_actor_id}/runs/{run_id}"
    dataset_url = f"https://api.apify.com/v2/datasets"

    items = []
    max_attempts = 30

    for attempt in range(max_attempts):
        try:
            # Check run status
            response = await client.get(
                status_url,
                headers={"Authorization": f"Bearer {VintedScraperConfig.apify_api_token}"},
            )

            if response.status_code != 200:
                await asyncio.sleep(1)
                continue

            run_data = response.json().get("data", {})
            status = run_data.get("status")

            if status == "SUCCEEDED":
                # Get results from dataset
                dataset_id = run_data.get("defaultDatasetId")
                if dataset_id:
                    items = await _fetch_dataset_items(
                        client, dataset_id, term, min_price, max_price
                    )
                break
            elif status in ("FAILED", "ABORTED"):
                log.warning("vinted.apify_run_failed", run_id=run_id, status=status)
                break

            await asyncio.sleep(2)

        except Exception as exc:
            log.warning("vinted.apify_poll_error", run_id=run_id, error=str(exc))
            await asyncio.sleep(2)

    return items


async def _fetch_dataset_items(
    client: httpx.AsyncClient,
    dataset_id: str,
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Fetch items from Apify dataset and parse them."""

    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    items = []

    try:
        response = await client.get(
            dataset_url,
            headers={"Authorization": f"Bearer {VintedScraperConfig.apify_api_token}"},
        )

        if response.status_code != 200:
            return []

        data = response.json()
        raw_items = data if isinstance(data, list) else data.get("items", [])

        for item in raw_items:
            parsed = _parse_vinted_item(item, term, min_price, max_price)
            if parsed:
                items.append(parsed)

    except Exception as exc:
        log.warning("vinted.dataset_fetch_error", dataset_id=dataset_id, error=str(exc))

    return items


def _parse_vinted_item(
    item: dict,
    term: str,
    min_price: float,
    max_price: float,
) -> Optional[dict]:
    """Parse Apify result into our listing format."""

    title = item.get("title", "") or item.get("name", "")
    price_str = item.get("price", "") or ""
    url = item.get("url", "")

    if not title or not url:
        return None

    # Parse price (handle £ symbol and commas)
    try:
        price_val = float(price_str.replace("£", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None

    if not (min_price <= price_val <= max_price):
        return None

    return {
        "external_id": url,
        "title": title,
        "price": price_val,
        "url": url,
        "condition": item.get("condition", "used"),
        "image_urls": [item.get("image", "")] if item.get("image") else [],
        "seller_name": item.get("seller", {}).get("name", "Vinted User") if isinstance(item.get("seller"), dict) else "Vinted User",
        "found_via_term": term,
    }


async def scrape_vinted_tech() -> dict:
    """
    Called by the components aggregator.
    Returns {"listings": [...]} where each entry has price_gbp, title, condition, category, source_url.
    """
    if not VintedScraperConfig.apify_api_token:
        log.warning("vinted.apify_not_configured")
        return {"listings": [], "stats": {"error": "APIFY_API_TOKEN not configured"}}

    items = await fetch_vinted_listings(
        search_terms=[
            "graphics card", "GPU", "RTX", "GTX",
            "Intel Core i5", "Intel Core i7", "AMD Ryzen 5", "AMD Ryzen 7",
            "DDR4 RAM", "DDR5 RAM", "16GB RAM", "32GB RAM",
            "NVMe SSD", "M.2 SSD",
            "motherboard ATX", "motherboard AM4", "motherboard AM5",
            "power supply 650W", "power supply 750W",
            "PC case ATX",
        ],
        min_price=5,
        max_price=1500,
    )

    listings = [
        {
            "title": i["title"],
            "price_gbp": i["price"],
            "condition": i.get("condition", "used"),
            "source_url": i["url"],
            "seller": i.get("seller_name", "Vinted User"),
            "category": i.get("found_via_term", ""),
        }
        for i in items
    ]

    return {
        "listings": listings,
        "stats": {
            "total": len(listings),
            "terms": len([
                "graphics card", "GPU", "RTX", "GTX",
                "Intel Core i5", "Intel Core i7", "AMD Ryzen 5", "AMD Ryzen 7",
                "DDR4 RAM", "DDR5 RAM", "16GB RAM", "32GB RAM",
                "NVMe SSD", "M.2 SSD",
                "motherboard ATX", "motherboard AM4", "motherboard AM5",
                "power supply 650W", "power supply 750W",
                "PC case ATX",
            ]),
        },
    }
