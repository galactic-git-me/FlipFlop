"""
Amazon UK Scraper - Direct HTTP with realistic browser headers

Uses httpx with User-Agent and browser headers instead of Playwright,
to avoid bot detection while keeping it lightweight.
"""

import asyncio
import httpx
import structlog
import random
from bs4 import BeautifulSoup
from typing import Optional

log = structlog.get_logger(__name__)

# Realistic User-Agent strings to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]


def _get_headers() -> dict:
    """Return headers that mimic a real browser request."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


async def fetch_amazon_listings_http(
    search_terms: list[str] | None = None,
    min_price: float = 10,
    max_price: float = 2500,
) -> list[dict]:
    """
    Fetch Amazon UK listings using direct HTTP with browser-like headers.

    Returns list of dicts with: title, price, url, image_urls, condition
    """
    if not search_terms:
        search_terms = [
            "graphics card", "CPU", "DDR4 RAM", "DDR5 RAM",
            "NVMe SSD", "motherboard", "power supply", "PC case",
        ]

    all_results = []
    seen_urls = set()

    for term in search_terms:
        try:
            items = await _search_amazon_term_http(term, min_price, max_price)
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
        except Exception as exc:
            log.warning("amazon_http.term_error", term=term, error=str(exc))
        await asyncio.sleep(random.uniform(1.0, 2.0))  # Rate limiting

    log.info("amazon_http.done", fetched=len(all_results), terms=len(search_terms))
    return all_results


async def _search_amazon_term_http(
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Search Amazon UK for a single term using direct HTTP."""

    url = f"https://www.amazon.co.uk/s?k={term.replace(' ', '+')}&i=computers"
    items = []

    max_retries = 2
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers=_get_headers())

            if resp.status_code != 200:
                log.debug(
                    "amazon_http.http_error",
                    term=term,
                    status=resp.status_code,
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0 + random.uniform(0, 2.0))
                continue

            html = resp.text
            if len(html) < 5000:  # Amazon pages are typically larger
                log.debug(
                    "amazon_http.small_response",
                    term=term,
                    size=len(html),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                continue

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            items = _extract_amazon_listings_from_html(soup, term, min_price, max_price)

            if items:  # Only log if we found results
                log.debug("amazon_http.fetch_pass", term=term, found=len(items))
                break  # Success

        except Exception as exc:
            log.debug(
                "amazon_http.fetch_error",
                term=term,
                attempt=attempt + 1,
                error=str(exc),
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0)

    log.debug("amazon_http.term_done", term=term, found=len(items))
    return items


def _extract_amazon_listings_from_html(
    soup: BeautifulSoup, term: str, min_price: float, max_price: float
) -> list[dict]:
    """Extract product listings from Amazon search results HTML."""
    items = []
    seen = set()

    # Amazon search results use data-component-type="s-search-result"
    for result in soup.find_all("div", {"data-component-type": "s-search-result"}):
        try:
            # Title
            title_el = result.find("h2")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)[:200]
            if not title:
                continue

            # URL
            link_el = result.find("a", {"class": "a-link-normal"})
            if not link_el:
                continue
            href = link_el.get("href", "")
            if not href.startswith("http"):
                href = "https://www.amazon.co.uk" + href if href.startswith("/") else ""
            if not href.startswith("http"):
                continue

            # Dedup
            url_key = href.split("?")[0]
            if url_key in seen:
                continue
            seen.add(url_key)

            # Price
            price_el = result.find("span", {"class": "a-price-whole"})
            if not price_el:
                continue
            price_text = price_el.get_text(strip=True).replace("£", "").replace(",", "")
            try:
                price = float(price_text)
            except (ValueError, TypeError):
                continue

            if price <= 0 or not (min_price <= price <= max_price):
                continue

            # Image
            img_el = result.find("img", {"class": "s-image"})
            img_url = img_el.get("src", "") if img_el else ""

            items.append(
                {
                    "external_id": url_key,
                    "title": title,
                    "price": price,
                    "url": href,
                    "condition": "new",
                    "image_urls": [img_url] if img_url else [],
                    "seller_name": "Amazon UK",
                    "found_via_term": term,
                }
            )

        except Exception as exc:
            log.debug("amazon_http.parse_error", error=str(exc))
            continue

    return items[:20]  # Return top 20 results
