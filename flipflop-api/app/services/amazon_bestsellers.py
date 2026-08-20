"""
Amazon Best Sellers scraper for PC cases.
Captures bestseller ranking to show which cases are trending.
Runs daily/weekly to track ranking changes over time.
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory
import structlog
import httpx
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)


async def scrape_amazon_bestsellers() -> dict:
    """
    Scrape Amazon UK bestseller rankings for PC cases.
    Updates bestseller_rank field for matching cases.
    Handles pagination (25 items per page).
    """
    url = "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Computer-Cases/zgbs/computers/430498031/"

    results = {
        "scraped": 0,
        "matched": 0,
        "errors": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            rank = 0
            page = 1
            max_pages = 3  # Top 75 bestsellers (3 pages × 25 items)

            while page <= max_pages:
                try:
                    # Fetch page with delay to avoid blocking
                    params = {"pg": page} if page > 1 else {}
                    resp = await client.get(url, params=params, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })

                    if resp.status_code != 200:
                        log.warning("amazon_bestsellers.page_error", page=page, status=resp.status_code)
                        break

                    soup = BeautifulSoup(resp.text, "lxml")

                    # Find bestseller items
                    items = soup.select('div[data-component-type="s-search-result"]')

                    if not items:
                        log.debug("amazon_bestsellers.no_items_found", page=page)
                        break

                    for item in items:
                        rank += 1
                        results["scraped"] += 1

                        # Extract title and link
                        title_elem = item.select_one('h2 a span')
                        link_elem = item.select_one('h2 a')

                        if not title_elem or not link_elem:
                            continue

                        title = title_elem.text.strip()
                        url_href = link_elem.get("href", "")

                        if not url_href.startswith("http"):
                            url_href = "https://www.amazon.co.uk" + url_href

                        log.debug("amazon_bestsellers.item", rank=rank, title=title[:50])

                        # Try to match with case in database
                        async with AsyncSessionLocal() as db:
                            result = await db.execute(
                                select(Part).where(
                                    Part.category == PartCategory.case,
                                    Part.source_site == "Amazon",
                                    Part.name.ilike(f"%{extract_brand_model(title)}%")
                                )
                            )
                            case = result.scalar_one_or_none()

                            if case:
                                # Update bestseller rank
                                await db.execute(
                                    update(Part)
                                    .where(Part.id == case.id)
                                    .values(bestseller_rank=rank)
                                )
                                await db.commit()
                                results["matched"] += 1
                                log.info("amazon_bestsellers.matched", rank=rank, case=case.name[:50])

                    await asyncio.sleep(1)  # Rate limiting
                    page += 1

                except Exception as e:
                    log.error("amazon_bestsellers.page_error", page=page, error=str(e))
                    results["errors"] += 1
                    break

        log.info("amazon_bestsellers.complete", scraped=results["scraped"], matched=results["matched"])

    except Exception as exc:
        log.error("amazon_bestsellers.error", error=str(exc))
        results["errors"] += 1

    return results


def extract_brand_model(title: str) -> str:
    """Extract brand/model keywords from Amazon title for matching."""
    # Get first 3-4 words (usually brand + model)
    words = title.split()[:4]
    return " ".join(words)
