"""
Amazon Best Sellers scraper for PC cases.
Captures bestseller ranking to show which cases are trending.
Uses Playwright to handle JS-rendered content.
Matches by ASIN + fuzzy product name matching.
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory
from app.services.browser_pool import managed_playwright
from app.swarms.cases import _make_pw_context
import structlog
from difflib import SequenceMatcher

log = structlog.get_logger(__name__)


def name_similarity(a: str, b: str) -> float:
    """Calculate similarity between two product names (0-1)"""
    a_lower = a.lower().replace("pc case", "").replace("case", "").strip()
    b_lower = b.lower().replace("pc case", "").replace("case", "").strip()
    return SequenceMatcher(None, a_lower, b_lower).ratio()


async def scrape_amazon_bestsellers() -> dict:
    """
    Scrape Amazon UK bestseller rankings for PC cases.
    URL: https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Computer-Cases/zgbs/computers/430498031/
    Updates bestseller_rank field for matching cases.
    """
    url = "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Computer-Cases/zgbs/computers/430498031/"

    results = {
        "scraped": 0,
        "matched": 0,
        "errors": 0,
    }

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("bestsellers.browser_error", error=str(exc))
            return results

        page = await context.new_page()
        try:
            log.info("bestsellers.scraping", url=url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for bestseller items to load
            try:
                await page.wait_for_selector('[data-component-type="s-search-result"]', timeout=10000)
            except Exception as exc:
                log.debug("bestsellers.wait_timeout", error=str(exc))

            await asyncio.sleep(2)

            # Extract bestseller items using JS (try multiple selectors)
            raw = await page.evaluate("""() => {
                const out = [];

                // Try multiple selector strategies
                let items = document.querySelectorAll('[data-component-type="s-search-result"]');
                if (items.length === 0) items = document.querySelectorAll('div[data-asin]');
                if (items.length === 0) items = document.querySelectorAll('.sg-col-inner');

                items.forEach((item, rank) => {
                    let titleEl = item.querySelector('h2 span') || item.querySelector('h2') || item.querySelector('[data-component-type="s-product-image"] + div a span');
                    let linkEl = item.querySelector('h2 a') || item.querySelector('a[href*="/dp/"]') || item.querySelector('[data-asin] a[href*="/dp/"]');
                    let asin = item.getAttribute('data-asin');

                    if (!titleEl && !linkEl) return;

                    const title = titleEl?.textContent?.trim() || '';
                    let href = linkEl?.href || linkEl?.getAttribute('href') || '';

                    if (!href && asin) {
                        href = 'https://www.amazon.co.uk/dp/' + asin;
                    }

                    if (!title || !href) return;
                    if (href.startsWith('/')) href = 'https://www.amazon.co.uk' + href;

                    // Extract ASIN from URL or element
                    let finalAsin = asin;
                    if (!finalAsin) {
                        const match = href.match(/\\/dp\\/([A-Z0-9]{10})/);
                        finalAsin = match ? match[1] : null;
                    }

                    if (title && finalAsin) {
                        out.push({
                            rank: rank + 1,
                            title: title.slice(0, 200),
                            asin: finalAsin,
                            url: href
                        });
                    }
                });
                return out.slice(0, 75);  // Top 75 bestsellers
            }""")

            log.info("bestsellers.extracted", count=len(raw))

            # Match with database cases
            async with AsyncSessionLocal() as db:
                # Get all Amazon cases
                result = await db.execute(
                    select(Part).where(
                        Part.category == PartCategory.case,
                        Part.source_site == "Amazon",
                    )
                )
                amazon_cases = result.scalars().all()

                for item in raw:
                    results["scraped"] += 1

                    # Try to match by ASIN first (most reliable)
                    matching_case = None

                    # Check if ASIN is in the URL
                    if item["asin"]:
                        for case in amazon_cases:
                            if case.source_url and item["asin"] in case.source_url:
                                matching_case = case
                                break

                    # Fallback: fuzzy match by name
                    if not matching_case:
                        best_similarity = 0.7  # Threshold
                        for case in amazon_cases:
                            sim = name_similarity(item["title"], case.name)
                            if sim > best_similarity:
                                best_similarity = sim
                                matching_case = case

                    if matching_case:
                        # Update bestseller rank
                        await db.execute(
                            update(Part)
                            .where(Part.id == matching_case.id)
                            .values(bestseller_rank=item["rank"])
                        )
                        results["matched"] += 1
                        log.debug(
                            "bestsellers.matched",
                            rank=item["rank"],
                            title=item["title"][:50],
                            case_id=matching_case.id,
                        )
                    else:
                        log.debug("bestsellers.no_match", rank=item["rank"], title=item["title"][:50])

                await db.commit()

            log.info(
                "bestsellers.complete",
                scraped=results["scraped"],
                matched=results["matched"],
            )

        except Exception as exc:
            log.error("bestsellers.error", error=str(exc))
            results["errors"] += 1
        finally:
            await page.close()
            await context.close()
            await browser.close()

    return results
