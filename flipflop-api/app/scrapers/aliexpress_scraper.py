"""
AliExpress Scraper - Extract budget PC components and cases using Playwright

Target: AliExpress for PC cases, RAM, SSDs, GPUs, PSUs (budget options)
Strategy: Use Playwright with JS evaluation for client-side rendered content
Requires: Playwright browser environment
"""

import asyncio
import random
import structlog
from typing import Optional
from app.services.playwright_scraper import managed_playwright, _make_pw_context

log = structlog.get_logger(__name__)


async def fetch_aliexpress_listings(
    search_terms: list[str] | None = None,
    min_price: float = 5,
    max_price: float = 2500,
) -> list[dict]:
    """
    Fetch AliExpress listings using Playwright JS evaluation.

    Returns list of dicts with: title, price, url, image_urls, condition
    """
    if not search_terms:
        search_terms = [
            "PC case", "motherboard", "DDR4 RAM", "DDR5 RAM",
            "NVMe SSD", "power supply", "GPU cooler",
        ]

    all_results = []
    seen_urls = set()

    for term in search_terms:
        try:
            items = await _search_aliexpress_term(term, min_price, max_price)
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
        except Exception as exc:
            log.warning("aliexpress.term_error", term=term, error=str(exc))
        await asyncio.sleep(1.0)  # Rate limiting between searches

    log.info("aliexpress.done", fetched=len(all_results), terms=len(search_terms))
    return all_results


async def _search_aliexpress_term(
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Search AliExpress for a single term using Playwright."""

    url = f"https://www.aliexpress.com/wholesale?SearchText={term.replace(' ', '+')}"
    items = []

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("aliexpress.browser_error", term=term, error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('[data-testid="organic-list-offer"]', timeout=12000)
            except Exception:
                log.debug("aliexpress.selector_timeout", term=term)

            await asyncio.sleep(random.uniform(1.5, 2.5))

            # JS evaluation to extract results from client-side rendered content
            raw = await page.evaluate("""() => {
                const out = [];
                const seen = new Set();
                document.querySelectorAll('[data-testid="organic-list-offer"]').forEach(item => {
                    try {
                        const titleEl = item.querySelector('[data-testid="organic-list-offer-card-title"]') ||
                                       item.querySelector('h2') ||
                                       item.querySelector('[class*="Title"]');
                        const linkEl = item.querySelector('a[href*="/item/"]') ||
                                      item.querySelector('a.organic-item-link');
                        const priceEl = item.querySelector('[data-testid="price-main"]') ||
                                       item.querySelector('[class*="Price"]');
                        const imgEl = item.querySelector('img[alt]');
                        const deliveryEl = item.querySelector('[class*="delivery"], [class*="Delivery"]');

                        if (!titleEl || !linkEl) return;

                        const title = titleEl.textContent.trim().slice(0, 200);
                        if (!title) return;

                        let href = linkEl.href || linkEl.getAttribute('href') || '';
                        if (!href.startsWith('http')) return;

                        const key = href.split('?')[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        let price = 0;
                        if (priceEl) {
                            const priceText = priceEl.textContent.replace(/[^0-9.]/g, '');
                            price = parseFloat(priceText);
                        }

                        if (price <= 0) return;

                        let deliveryDays = null;
                        if (deliveryEl) {
                            const deliveryText = deliveryEl.textContent;
                            const match = deliveryText.match(/(\d+)/);
                            if (match) deliveryDays = parseInt(match[1]);
                        }

                        out.push({title, price, href, img: imgEl ? imgEl.src : '', deliveryDays});
                    } catch (e) {}
                });
                return out.slice(0, 20);
            }""")

            # Parse results
            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title:
                        continue

                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 10000:
                        continue

                    if not (min_price <= price <= max_price):
                        continue

                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue

                    items.append({
                        "external_id": href.split('?')[0],
                        "title": title,
                        "price": price,
                        "url": href,
                        "condition": "new",
                        "image_urls": [str(item.get("img", ""))] if item.get("img") else [],
                        "seller_name": "AliExpress",
                        "found_via_term": term,
                        "estimated_delivery_days": item.get("deliveryDays"),
                    })
                except (ValueError, TypeError):
                    continue

        except Exception as exc:
            log.warning("aliexpress.scrape_error", term=term, error=str(exc))
        finally:
            try:
                await page.close()
                await context.close()
            except Exception:
                pass

    log.debug("aliexpress.term_done", term=term, found=len(items))
    return items
