"""
Amazon UK Scraper - Extract component deals using Playwright

Target: Amazon UK for GPUs, CPUs, RAM, SSDs, motherboards, PSUs
Strategy: Use Playwright with JS evaluation for client-side rendered content
Requires: Playwright browser environment
"""

import asyncio
import random
import structlog
from typing import Optional
from app.services.playwright_scraper import managed_playwright, _make_pw_context

log = structlog.get_logger(__name__)


async def fetch_amazon_listings(
    search_terms: list[str] | None = None,
    min_price: float = 10,
    max_price: float = 2500,
) -> list[dict]:
    """
    Fetch Amazon UK listings using Playwright JS evaluation.

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
            items = await _search_amazon_term(term, min_price, max_price)
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
        except Exception as exc:
            log.warning("amazon.term_error", term=term, error=str(exc))
        await asyncio.sleep(1.0)  # Rate limiting between searches

    log.info("amazon.done", fetched=len(all_results), terms=len(search_terms))
    return all_results


async def _search_amazon_term(
    term: str,
    min_price: float,
    max_price: float,
) -> list[dict]:
    """Search Amazon UK for a single term using Playwright."""

    url = f"https://www.amazon.co.uk/s?k={term.replace(' ', '+')}&i=computers"
    items = []

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("amazon.browser_error", term=term, error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('[data-component-type="s-search-result"]', timeout=12000)
            except Exception:
                log.debug("amazon.selector_timeout", term=term)

            await asyncio.sleep(random.uniform(1.5, 2.5))

            # JS evaluation to extract results from client-side rendered content
            raw = await page.evaluate("""() => {
                const out = [];
                const seen = new Set();
                document.querySelectorAll('[data-component-type="s-search-result"]').forEach(item => {
                    try {
                        const titleEl = item.querySelector('h2 span') || item.querySelector('h2');
                        const linkEl  = item.querySelector('h2 a') || item.querySelector('a.a-link-normal[href*="/dp/"]');
                        const priceW  = item.querySelector('.a-price-whole');
                        const priceF  = item.querySelector('.a-price-fraction');
                        const imgEl   = item.querySelector('img.s-image');
                        const deliveryEl = item.querySelector('[aria-label*="delivery"], [class*="delivery"]');

                        if (!titleEl || !linkEl) return;

                        const title = titleEl.textContent.trim().slice(0, 200);
                        if (!title) return;

                        let href = linkEl.href || linkEl.getAttribute('href') || '';
                        if (href.startsWith('/')) href = 'https://www.amazon.co.uk' + href;
                        if (!href.startsWith('http')) return;

                        const key = href.split('?')[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        let price = 0;
                        if (priceW) {
                            const whole = priceW.textContent.replace(/[^0-9]/g, '');
                            const frac  = priceF ? priceF.textContent.replace(/[^0-9]/g, '').padEnd(2,'0') : '00';
                            price = parseFloat(whole + '.' + frac.slice(0,2));
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
                        "seller_name": "Amazon UK",
                        "found_via_term": term,
                        "estimated_delivery_days": item.get("deliveryDays"),
                    })
                except (ValueError, TypeError):
                    continue

        except Exception as exc:
            log.warning("amazon.scrape_error", term=term, error=str(exc))
        finally:
            try:
                await page.close()
                await context.close()
            except Exception:
                pass

    log.debug("amazon.term_done", term=term, found=len(items))
    return items
