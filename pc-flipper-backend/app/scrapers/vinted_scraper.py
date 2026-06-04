"""
Vinted Scraper - Extract tech deals from European online marketplace

Target: Vinted electronics marketplace for PCs and PC components
Expected: 100-200 listings/month at 28%+ gem rate
Strategy: Search tech section, filter for PC/gaming keywords, extract price/condition
Focus: Vintage PC niche + used components from tech enthusiasts
"""

import asyncio
import structlog
from datetime import datetime
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup
import re

log = structlog.get_logger(__name__)

# Vinted tech search keywords
TECH_SEARCH_KEYWORDS = [
    "PC",
    "desktop",
    "gaming computer",
    "gaming parts",
    "vintage computer",
    "workstation",
    "gaming setup",
    "computer parts",
    "GPU",
    "motherboard",
]


class VintedScraperConfig:
    """Configuration for Vinted scraper."""

    base_url = "https://www.vinted.co.uk"
    search_api = "https://www.vinted.co.uk/api/v2/catalog/items"
    min_price_gbp = 20
    max_price_gbp = 400
    condition_filters = ["good", "excellent", "like new"]
    scrape_frequency_hours = 24
    expected_monthly_listings = 150
    expected_gem_rate = 0.28
    avg_profit_estimate = 110  # £80-£140 range average


async def scrape_vinted_tech() -> dict:
    """
    Scrape Vinted marketplace for PC and gaming tech.

    Returns:
        dict with 'listings' (list) and 'stats' (dict)
    """
    log.info("vinted_scraper.starting", keywords=len(TECH_SEARCH_KEYWORDS))

    listings = []
    stats = {
        "total_found": 0,
        "valid": 0,
        "errors": 0,
        "keywords_searched": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for keyword in TECH_SEARCH_KEYWORDS:
                try:
                    stats["keywords_searched"] += 1

                    result = await _search_vinted_keyword(client, keyword)

                    if result and result.get("items"):
                        for item in result["items"]:
                            listing = _parse_vinted_item(item, keyword)
                            if listing:
                                listings.append(listing)
                                stats["valid"] += 1
                            stats["total_found"] += 1

                    # Polite rate limiting
                    await asyncio.sleep(0.8)

                except Exception as e:
                    log.warning("vinted_scraper.keyword_error", keyword=keyword, error=str(e))
                    stats["errors"] += 1
                    continue

        log.info(
            "vinted_scraper.complete",
            total_found=stats["total_found"],
            valid=stats["valid"],
            keywords_searched=stats["keywords_searched"],
        )

        return {
            "source": "Vinted",
            "listings": listings,
            "stats": stats,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.error("vinted_scraper.failed", error=str(e))
        raise


async def _search_vinted_keyword(client: httpx.AsyncClient, keyword: str) -> Optional[dict]:
    """
    Search Vinted for a specific tech keyword.

    Args:
        client: httpx async client
        keyword: Search term (e.g., "gaming PC")

    Returns:
        API response dict or None if failed
    """
    try:
        params = {
            "search_text": keyword,
            "catalog_ids": "3",  # Electronics category
            "order_by": "newest_first",
            "page": "1",
            "per_page": "50",
        }

        response = await client.get(
            VintedScraperConfig.search_api,
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        )

        if response.status_code == 200:
            data = response.json()
            return {"items": data.get("items", []), "keyword": keyword}

        else:
            log.warning("vinted_scraper.api_error", keyword=keyword, status=response.status_code)
            return None

    except Exception as e:
        log.warning("vinted_scraper.request_failed", keyword=keyword, error=str(e))
        return None


def _parse_vinted_item(item: dict, search_keyword: str) -> Optional[dict]:
    """
    Parse a Vinted item into our listing format.

    Args:
        item: Raw Vinted item dict from API
        search_keyword: The search keyword that found this item

    Returns:
        Formatted listing dict or None if invalid
    """
    try:
        title = item.get("title", "").strip()
        if not title:
            return None

        # Extract price
        price_data = item.get("price", {})
        price_gbp = price_data.get("amount") if isinstance(price_data, dict) else float(price_data or 0)

        if not price_gbp or price_gbp <= 0:
            return None

        # Validate price range
        if price_gbp < VintedScraperConfig.min_price_gbp:
            return None
        if price_gbp > VintedScraperConfig.max_price_gbp:
            return None

        # Extract condition
        condition = item.get("status", "").lower()
        if condition and condition not in VintedScraperConfig.condition_filters:
            # Allow "unknown" or similar for older listings
            if "unknown" not in condition and "not specified" not in condition:
                return None

        # Extract seller info
        user = item.get("user", {})
        seller_name = user.get("login", "Vinted User")

        # Extract item URL
        url = item.get("url", "")
        if not url.startswith("http"):
            url = f"{VintedScraperConfig.base_url}{url}" if url else ""

        # Extract photo/condition info
        photos = item.get("photos", [])
        photo_count = len(photos)

        return {
            "title": title,
            "source_url": url,
            "price_gbp": float(price_gbp),
            "shipping_cost_gbp": 0,  # Vinted price usually includes shipping negotiation
            "condition": condition or "good",
            "seller": seller_name,
            "seller_rating": user.get("review_count", 0),
            "category": _categorize_vinted_item(title),
            "component_type": _extract_vinted_component_type(title),
            "search_keyword": search_keyword,
            "photo_count": photo_count,
            "item_id": item.get("id"),
            "posted_at": item.get("photo", {}).get("high_resolution", {}).get("timestamp"),
            "source": "Vinted",
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.warning("vinted_scraper.parse_error", error=str(e))
        return None


def _categorize_vinted_item(title: str) -> str:
    """
    Categorize Vinted item type.

    Returns: PC, Component, Peripheral, Gaming Setup, Workstation, Other
    """
    title_lower = title.lower()

    if any(x in title_lower for x in ["desktop", "pc", "tower", "gaming pc", "workstation"]):
        if any(x in title_lower for x in ["workstation", "server", "professional"]):
            return "Workstation"
        elif any(x in title_lower for x in ["gaming", "gamer", "rtx", "high-end"]):
            return "Gaming PC"
        else:
            return "PC"

    elif any(x in title_lower for x in ["gpu", "graphics", "rtx", "gtx", "radeon"]):
        return "Component"
    elif any(x in title_lower for x in ["ram", "memory", "ddr4", "ddr5", "motherboard"]):
        return "Component"
    elif any(x in title_lower for x in ["ssd", "nvme", "storage", "hard drive"]):
        return "Component"
    elif any(x in title_lower for x in ["psu", "power supply", "cooling"]):
        return "Component"

    elif any(x in title_lower for x in ["keyboard", "mouse", "monitor", "headset", "speaker"]):
        return "Peripheral"

    elif any(x in title_lower for x in ["setup", "bundle", "lot", "package"]):
        return "Gaming Setup"

    else:
        return "Other"


def _extract_vinted_component_type(title: str) -> Optional[str]:
    """Extract specific component model/type from title."""
    title_lower = title.lower()

    import re

    # GPU models
    gpu_match = re.search(r"(rtx|gtx|radeon)\s+\d+", title_lower)
    if gpu_match:
        return gpu_match.group(0).upper()

    # CPU models
    cpu_match = re.search(r"(core\s+i[357]|ryzen\s+\d|xeon|pentium)\s+\d+", title_lower)
    if cpu_match:
        return cpu_match.group(0).upper()

    # RAM specs
    ram_match = re.search(r"(\d+)?\s*(ddr[45]|ddr5|sodimm)", title_lower)
    if ram_match:
        return f"{ram_match.group(1) or ''}GB {ram_match.group(2)}".strip().upper()

    # Storage
    ssd_match = re.search(r"(\d+)?\s*(ssd|nvme|m\.2)", title_lower)
    if ssd_match:
        return f"{ssd_match.group(1) or ''}GB {ssd_match.group(2)}".strip().upper()

    return None


async def get_vinted_status() -> dict:
    """Get scraper status and configuration."""
    return {
        "source": "Vinted",
        "enabled": True,
        "expected_listings_per_month": VintedScraperConfig.expected_monthly_listings,
        "expected_gem_rate": VintedScraperConfig.expected_gem_rate,
        "avg_profit_estimate": VintedScraperConfig.avg_profit_estimate,
        "scrape_frequency_hours": VintedScraperConfig.scrape_frequency_hours,
        "search_keywords": len(TECH_SEARCH_KEYWORDS),
        "focus": "Vintage PCs and used components from tech enthusiasts",
    }
