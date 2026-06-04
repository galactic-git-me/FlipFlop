"""
Temu Scraper - Extract ultra-cheap NEW components using Apify API

Target: Temu marketplace for GPU DDR5, RAM, SSDs, CPUs, PSUs, PC cases
Expected: 500-1,000 listings/month at 40%+ gem rate (all new)
Strategy: Use Apify Temu scraper for reliable data extraction
Requires: APIFY_API_TOKEN environment variable

Apify Temu Scraper: https://apify.com/drobnikj/temu-scraper
"""

import asyncio
import structlog
import os
from datetime import datetime
from typing import Optional, List
import httpx

log = structlog.get_logger(__name__)

# Generic search term - covers all PC components
# Using single term to stay within Apify free tier (50 runs/month)
# Temu's algorithm returns variety of items matching "PC"
COMPONENT_SEARCH_TERMS = [
    "PC",  # Generic - returns GPUs, RAM, SSDs, CPUs, PSUs, cases, etc.
]


class TemuScraperConfig:
    """Configuration for Temu scraper using Apify - Free Tier Optimized."""

    apify_api_token = os.getenv("APIFY_API_TOKEN", "")
    apify_actor_id = "drobnikj/temu-scraper"
    apify_api_url = "https://api.apify.com/v2/acts"

    # Free tier optimization: limit to 20 items per run
    # Apify free tier = 50 runs/month, so 1 run × 20 items = well within limits
    max_results_per_run = 20

    shipping_filter = "UK only"
    condition_filter = "new"
    price_range_min = 10  # £10
    price_range_max = 200  # £200
    scrape_frequency_hours = 24
    expected_monthly_listings = 20  # Conservative: 1 term × 20 items/month
    expected_gem_rate = 0.40


async def scrape_temu_components() -> dict:
    """
    Scrape Temu marketplace for component deals using Apify.

    REQUIRES: APIFY_API_TOKEN environment variable set

    Returns:
        dict with 'listings' (list) and 'stats' (dict)
    """
    if not TemuScraperConfig.apify_api_token:
        raise ValueError(
            "APIFY_API_TOKEN not configured. "
            "Set APIFY_API_TOKEN in .env.local to enable Temu scraping. "
            "Get token at https://apify.com"
        )

    log.info("temu_scraper.starting", actor=TemuScraperConfig.apify_actor_id)

    listings = []
    stats = {
        "total_found": 0,
        "valid": 0,
        "errors": 0,
        "terms_searched": len(COMPONENT_SEARCH_TERMS),
        "apify_runs": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for term in COMPONENT_SEARCH_TERMS:
                try:
                    stats["apify_runs"] += 1

                    # Run Apify actor for this search term
                    result = await _run_apify_temu_search(client, term)

                    if result and result.get("items"):
                        for item in result["items"]:
                            listing = _parse_temu_item(item, term)
                            if listing:
                                listings.append(listing)
                                stats["valid"] += 1
                            stats["total_found"] += 1

                    # Apify handles rate limiting internally
                    await asyncio.sleep(0.2)

                except Exception as e:
                    log.warning("temu_scraper.term_error", term=term, error=str(e))
                    stats["errors"] += 1
                    continue

        log.info(
            "temu_scraper.complete",
            total_found=stats["total_found"],
            valid=stats["valid"],
            apify_runs=stats["apify_runs"],
        )

        return {
            "source": "Temu",
            "listings": listings,
            "stats": stats,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.error("temu_scraper.failed", error=str(e))
        raise


async def _run_apify_temu_search(client: httpx.AsyncClient, term: str) -> Optional[dict]:
    """
    Run Apify Temu scraper for a specific component term.

    Uses drobnikj/temu-scraper actor on Apify platform.

    Args:
        client: httpx async client
        term: Search term (e.g., "GPU DDR5")

    Returns:
        Scraped items dict or None if failed
    """
    try:
        # Apify actor run URL
        run_url = f"{TemuScraperConfig.apify_api_url}/{TemuScraperConfig.apify_actor_id}/runs"

        # Input parameters for Apify actor
        # Limited to 20 results per run to stay within free tier (50 runs/month)
        actor_input = {
            "searchQuery": term,
            "maxResults": TemuScraperConfig.max_results_per_run,
            "proxyConfiguration": {"useApifyProxy": True},
        }

        # Start the actor run
        response = await client.post(
            run_url,
            json={"startUrls": [], **actor_input},  # Apify will search based on query
            headers={"Authorization": f"Bearer {TemuScraperConfig.apify_api_token}"},
            timeout=60.0,
        )

        if response.status_code not in [200, 201]:
            log.warning(
                "temu_scraper.apify_error", term=term, status=response.status_code
            )
            return None

        run_data = response.json()
        run_id = run_data.get("data", {}).get("id")

        if not run_id:
            log.warning("temu_scraper.no_run_id", term=term)
            return None

        # Wait for run to complete and get results
        items = await _get_apify_results(client, run_id)

        return {"items": items, "term": term}

    except Exception as e:
        log.warning("temu_scraper.apify_request_failed", term=term, error=str(e))
        return None


async def _get_apify_results(client: httpx.AsyncClient, run_id: str) -> List[dict]:
    """
    Poll Apify run status and fetch results when complete.

    Args:
        client: httpx async client
        run_id: Apify actor run ID

    Returns:
        List of scraped items
    """
    try:
        # Poll for run completion (max 30 seconds)
        status_url = f"{TemuScraperConfig.apify_api_url}/{TemuScraperConfig.apify_actor_id}/runs/{run_id}"

        for attempt in range(30):
            response = await client.get(
                status_url,
                headers={"Authorization": f"Bearer {TemuScraperConfig.apify_api_token}"},
            )

            if response.status_code == 200:
                run_data = response.json().get("data", {})
                status = run_data.get("status")

                if status == "SUCCEEDED":
                    # Get dataset results
                    dataset_id = run_data.get("defaultDatasetId")
                    if dataset_id:
                        dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
                        dataset_response = await client.get(
                            dataset_url,
                            headers={
                                "Authorization": f"Bearer {TemuScraperConfig.apify_api_token}"
                            },
                        )

                        if dataset_response.status_code == 200:
                            return dataset_response.json()

                    return []

                elif status == "FAILED":
                    log.warning("temu_scraper.apify_run_failed", run_id=run_id)
                    return []

            # Wait before polling again
            await asyncio.sleep(1)

        log.warning("temu_scraper.apify_timeout", run_id=run_id)
        return []

    except Exception as e:
        log.warning("temu_scraper.apify_results_failed", error=str(e))
        return []


def _parse_temu_item(item: dict, search_term: str) -> Optional[dict]:
    """
    Parse a Temu item into our listing format.

    Args:
        item: Raw Temu item dict from API
        search_term: The search term that found this item

    Returns:
        Formatted listing dict or None if invalid
    """
    try:
        title = item.get("title", "").strip()
        price = item.get("price", {})

        # Extract price (Temu may use currency codes)
        price_gbp = price.get("gbp") or price.get("value")
        if not price_gbp:
            return None

        # Extract shipping info
        shipping = item.get("shipping", {})
        shipping_cost = shipping.get("cost", 0)
        shipping_days = shipping.get("days_to_uk")

        # Validate: must be new condition
        condition = item.get("condition", "").lower()
        if condition and condition not in ["new", "unused", "factory sealed"]:
            return None

        return {
            "title": title,
            "source_url": item.get("url", ""),
            "price_gbp": float(price_gbp),
            "shipping_cost_gbp": float(shipping_cost),
            "shipping_days": shipping_days,
            "condition": "new",  # Temu components are all new
            "seller": item.get("seller_name", "Temu"),
            "rating": item.get("seller_rating", 0),
            "search_term": search_term,
            "category": _categorize_component(title),
            "component_type": _extract_component_type(title),
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.warning("temu_scraper.parse_error", error=str(e))
        return None


def _categorize_component(title: str) -> str:
    """
    Categorize component by title.

    Returns: CPU, GPU, RAM, SSD, PSU, Case, Other
    """
    title_lower = title.lower()

    if any(x in title_lower for x in ["gpu", "graphics card", "rtx", "gtx", "radeon"]):
        return "GPU"
    elif any(x in title_lower for x in ["ram", "ddr4", "ddr5", "memory", "sodimm"]):
        return "RAM"
    elif any(x in title_lower for x in ["ssd", "nvme", "storage", "m.2"]):
        return "SSD"
    elif any(x in title_lower for x in ["cpu", "processor", "core i", "ryzen", "xeon"]):
        return "CPU"
    elif any(x in title_lower for x in ["psu", "power supply", "650w", "800w", "1000w"]):
        return "PSU"
    elif any(x in title_lower for x in ["case", "tower", "chassis", "atx", "itx"]):
        return "Case"
    elif any(x in title_lower for x in ["motherboard", "mobo", "socket"]):
        return "Motherboard"
    elif any(x in title_lower for x in ["cooling", "fan", "heatsink", "cooler"]):
        return "Cooling"
    else:
        return "Component"


def _extract_component_type(title: str) -> Optional[str]:
    """Extract specific component model/type from title."""
    title_lower = title.lower()

    # Try to extract model number or specific type
    # e.g., "RTX 4060 Ti", "Ryzen 5 5600X", "DDR5 32GB"
    import re

    # GPU models
    gpu_match = re.search(r"(rtx|gtx|radeon)\s+\d+", title_lower)
    if gpu_match:
        return gpu_match.group(0).upper()

    # CPU models
    cpu_match = re.search(r"(core\s+i[357]|ryzen\s+\d|xeon)\s+\d+", title_lower)
    if cpu_match:
        return cpu_match.group(0).upper()

    # RAM specs
    ram_match = re.search(r"(\d+)?\s*(ddr[45]|ddr5|sodimm)", title_lower)
    if ram_match:
        return f"{ram_match.group(1) or ''}GB {ram_match.group(2)}".strip().upper()

    return None


async def get_temu_status() -> dict:
    """Get scraper status and configuration."""
    has_api_token = bool(TemuScraperConfig.apify_api_token)

    return {
        "source": "Temu",
        "enabled": True,
        "api_provider": "Apify",
        "api_configured": has_api_token,
        "tier": "Free (Apify)",
        "actor_id": TemuScraperConfig.apify_actor_id,
        "max_results_per_run": TemuScraperConfig.max_results_per_run,
        "expected_listings_per_month": TemuScraperConfig.expected_monthly_listings,
        "expected_gem_rate": TemuScraperConfig.expected_gem_rate,
        "avg_profit_estimate": 60,
        "scrape_frequency_hours": TemuScraperConfig.scrape_frequency_hours,
        "search_terms": len(COMPONENT_SEARCH_TERMS),
        "search_strategy": "Single generic term 'PC' for variety",
        "apify_monthly_cost": "FREE (within 50 runs/month limit)",
        "setup_required": "CRITICAL: Set APIFY_API_TOKEN in .env.local - scraper requires real API credentials" if not has_api_token else None,
    }
