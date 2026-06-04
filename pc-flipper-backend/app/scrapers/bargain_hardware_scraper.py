"""
BargainHardware Scraper - UK component retailer with clearance/surplus stock

Target: https://www.bargainhardware.co.uk component categories
Expected: 100-200 listings/month at 35%+ gem rate
Strategy: Daily scrape component categories, extract price+discount, filter for deals >20% off
"""

import asyncio
import structlog
from datetime import datetime
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup
import re

log = structlog.get_logger(__name__)

# BargainHardware component categories
COMPONENT_CATEGORIES = [
    "/components/processors",
    "/components/motherboards",
    "/components/memory",
    "/components/storage",
    "/components/graphics-cards",
    "/components/power-supplies",
    "/components/cases",
]


class BargainHardwareConfig:
    """Configuration for BargainHardware scraper."""

    base_url = "https://www.bargainhardware.co.uk"
    min_discount_pct = 20  # Only grab items with 20%+ discount
    scrape_frequency_hours = 24
    expected_monthly_listings = 150
    expected_gem_rate = 0.35
    avg_profit_estimate = 110  # £70-£150 range average


async def scrape_bargain_hardware_components() -> dict:
    """
    Scrape BargainHardware for component deals.

    Returns:
        dict with 'listings' (list) and 'stats' (dict)
    """
    log.info("bargain_hardware_scraper.starting", categories=len(COMPONENT_CATEGORIES))

    listings = []
    stats = {
        "total_found": 0,
        "valid": 0,
        "errors": 0,
        "categories_scraped": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for category in COMPONENT_CATEGORIES:
                try:
                    stats["categories_scraped"] += 1

                    result = await _scrape_category(client, category)

                    if result and result.get("items"):
                        for item in result["items"]:
                            listing = _parse_bargain_hardware_item(item, category)
                            if listing:
                                listings.append(listing)
                                stats["valid"] += 1
                            stats["total_found"] += 1

                    # Polite rate limiting
                    await asyncio.sleep(1.0)

                except Exception as e:
                    log.warning(
                        "bargain_hardware_scraper.category_error", category=category, error=str(e)
                    )
                    stats["errors"] += 1
                    continue

        log.info(
            "bargain_hardware_scraper.complete",
            total_found=stats["total_found"],
            valid=stats["valid"],
            categories_scraped=stats["categories_scraped"],
        )

        return {
            "source": "BargainHardware",
            "listings": listings,
            "stats": stats,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.error("bargain_hardware_scraper.failed", error=str(e))
        raise


async def _scrape_category(client: httpx.AsyncClient, category: str) -> Optional[dict]:
    """
    Scrape a BargainHardware category page.

    Args:
        client: httpx async client
        category: Category path (e.g., "/components/processors")

    Returns:
        dict with 'items' list or None if failed
    """
    try:
        url = f"{BargainHardwareConfig.base_url}{category}"

        response = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Parse product listings from page
            # NOTE: Selectors below are templates - actual DOM structure may vary
            items = _parse_html_listings(soup)

            return {"items": items, "category": category, "fetched_at": datetime.utcnow()}

        else:
            log.warning(
                "bargain_hardware_scraper.http_error", category=category, status=response.status_code
            )
            return None

    except Exception as e:
        log.warning("bargain_hardware_scraper.scrape_failed", category=category, error=str(e))
        return None


def _parse_html_listings(soup: BeautifulSoup) -> List[dict]:
    """
    Parse product listings from BeautifulSoup parsed HTML.

    Args:
        soup: BeautifulSoup parser

    Returns:
        List of product dicts
    """
    items = []

    try:
        # Selectors are templates - BargainHardware structure may differ
        # Adjust based on actual DOM inspection
        product_elements = soup.find_all("div", class_=["product", "product-item", "card"])

        for element in product_elements:
            try:
                # Extract title
                title_elem = element.find("h2", class_=["product-title", "title"]) or element.find(
                    "a", class_=["product-link"]
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                # Extract price
                price_elem = element.find("span", class_=["price", "product-price"])
                if not price_elem:
                    continue

                price_text = price_elem.get_text(strip=True)
                price = _extract_price(price_text)
                if not price:
                    continue

                # Extract original price (for discount calculation)
                original_elem = element.find("span", class_=["original-price", "was-price"])
                original_price = None
                if original_elem:
                    original_price = _extract_price(original_elem.get_text(strip=True))

                # Calculate discount
                discount_pct = 0
                if original_price and price < original_price:
                    discount_pct = ((original_price - price) / original_price) * 100

                # Only include if meets minimum discount
                if discount_pct < BargainHardwareConfig.min_discount_pct:
                    continue

                # Extract URL
                url_elem = element.find("a", href=True)
                url = url_elem["href"] if url_elem else ""
                if not url.startswith("http"):
                    url = f"{BargainHardwareConfig.base_url}{url}"

                items.append(
                    {
                        "title": title,
                        "url": url,
                        "price_gbp": price,
                        "original_price_gbp": original_price,
                        "discount_pct": discount_pct,
                        "in_stock": _is_in_stock(element),
                    }
                )

            except Exception as e:
                log.debug("bargain_hardware_scraper.element_parse_error", error=str(e))
                continue

        return items

    except Exception as e:
        log.warning("bargain_hardware_scraper.parse_html_error", error=str(e))
        return []


def _parse_bargain_hardware_item(item: dict, category: str) -> Optional[dict]:
    """
    Parse a BargainHardware item into our listing format.

    Args:
        item: Item dict from _parse_html_listings
        category: Category path

    Returns:
        Formatted listing dict or None if invalid
    """
    try:
        title = item.get("title", "").strip()
        if not title:
            return None

        price = item.get("price_gbp")
        if not price or price <= 0:
            return None

        discount = item.get("discount_pct", 0)
        if discount < BargainHardwareConfig.min_discount_pct:
            return None

        return {
            "title": title,
            "source_url": item.get("url", ""),
            "price_gbp": price,
            "original_price_gbp": item.get("original_price_gbp"),
            "discount_pct": discount,
            "in_stock": item.get("in_stock", True),
            "seller": "BargainHardware",
            "category": _categorize_bh_component(title, category),
            "component_type": _extract_component_type_bh(title),
            "source": "BargainHardware",
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.warning("bargain_hardware_scraper.item_parse_error", error=str(e))
        return None


def _extract_price(price_text: str) -> Optional[float]:
    """Extract GBP price from text like '£99.99' or '99.99'."""
    try:
        # Remove currency symbol and extract numbers
        match = re.search(r"£?\s*(\d+(?:\.\d{2})?)", price_text)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return None


def _is_in_stock(element) -> bool:
    """Check if element indicates product is in stock."""
    try:
        text = element.get_text().lower()
        if "out of stock" in text or "unavailable" in text:
            return False
        if "in stock" in text:
            return True
    except Exception:
        pass
    return True  # Default to in stock


def _categorize_bh_component(title: str, category_path: str) -> str:
    """
    Categorize component by title and category path.

    Returns: CPU, GPU, RAM, SSD, PSU, Case, Motherboard, Other
    """
    title_lower = title.lower()
    category_lower = category_path.lower()

    if "graphics" in category_lower or "gpu" in category_lower:
        return "GPU"
    elif "motherboard" in category_lower or "mobo" in category_lower:
        return "Motherboard"
    elif "memory" in category_lower or "ram" in category_lower or "ddr" in title_lower:
        return "RAM"
    elif "storage" in category_lower or "ssd" in title_lower or "nvme" in title_lower:
        return "SSD"
    elif "processor" in category_lower or "cpu" in title_lower:
        return "CPU"
    elif "power" in category_lower or "psu" in title_lower:
        return "PSU"
    elif "case" in category_lower or "chassis" in title_lower:
        return "Case"
    else:
        return "Component"


def _extract_component_type_bh(title: str) -> Optional[str]:
    """Extract specific component model/type from title."""
    title_lower = title.lower()

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
    ram_match = re.search(r"(\d+)?\s*(ddr[45]|sodimm)", title_lower)
    if ram_match:
        return f"{ram_match.group(1) or ''}GB {ram_match.group(2)}".strip().upper()

    return None


async def get_bargain_hardware_status() -> dict:
    """Get scraper status and configuration."""
    return {
        "source": "BargainHardware",
        "enabled": True,
        "expected_listings_per_month": BargainHardwareConfig.expected_monthly_listings,
        "expected_gem_rate": BargainHardwareConfig.expected_gem_rate,
        "avg_profit_estimate": BargainHardwareConfig.avg_profit_estimate,
        "scrape_frequency_hours": BargainHardwareConfig.scrape_frequency_hours,
        "categories": len(COMPONENT_CATEGORIES),
    }
