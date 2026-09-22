"""
Amazon Best Sellers scraper for PC cases.
Captures bestseller ranking to show which cases are trending.
Uses Playwright to handle JS-rendered content.
Matches by ASIN + fuzzy product name matching against the `cases` table
(and `parts` if any case rows still live there).
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import parse_qs, urlparse
from datetime import datetime

from difflib import SequenceMatcher
from sqlalchemy import select, update
import structlog

from app.database import AsyncSessionLocal
from app.models.case import Case
from app.models.part import Part, PartCategory
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.services.browser_pool import managed_playwright
from app.swarms.cases import RawCase, _make_pw_context, _upsert_case, _upsert_case_new

log = structlog.get_logger(__name__)

BESTSELLER_URL = (
    "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Computer-Cases/"
    "zgbs/computers/430498031/"
)
# Amazon's component bestseller pages.  The list name is stored with every
# daily observation so the UI can explain exactly what a rank means.
COMPONENT_BESTSELLER_LISTS = {
    "cpu": ("CPUs", "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-CPUs/zgbs/computers/430515031/"),
    "gpu": ("Graphics Cards", "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Graphics-Cards/zgbs/computers/430500031/"),
    "ram": ("Computer Memory", "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Computer-Memory/zgbs/computers/430511031/"),
    "storage": ("Data Storage", "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Data-Storage/zgbs/computers/17477985031/"),
    "motherboard": ("Motherboards", "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Motherboards/zgbs/computers/430512031/"),
    "psu": ("Power Supplies", "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Power-Supplies/zgbs/computers/430514031/"),
    "case": ("Computer Cases", BESTSELLER_URL),
}

MAX_BESTSELLER_PAGES = 10
ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})", re.I)

_EXTRACT_JS = """(rankOffset = 0) => {
    const out = [];
    const seen = new Set();
    let cards = Array.from(document.querySelectorAll('#gridItemRoot'));
    if (cards.length === 0) {
        cards = Array.from(document.querySelectorAll('.zg-grid-general-faceout'));
    }
    if (cards.length === 0) {
        cards = Array.from(document.querySelectorAll('div[data-asin]'));
    }

    const parseRank = (card, fallbackIndex) => {
        const rankEl = card.querySelector('.zg-bdg-text, .zg-bdg-badge, span.zg-badge-text');
        const raw = (rankEl?.textContent || '').replace(/[^0-9]/g, '');
        const parsed = raw ? parseInt(raw, 10) : NaN;
        return Number.isFinite(parsed) && parsed > 0 ? parsed : rankOffset + fallbackIndex;
    };

    cards.forEach((item, index) => {
        const imgEl = item.querySelector('img');
        const linkEl = item.querySelector('a[href*="/dp/"]') || item.querySelector('a.a-link-normal');
        let title = (imgEl?.alt || '').trim();
        if (!title) {
            const titleEl = item.querySelector('div[class*="line-clamp"], .p13n-sc-truncated, span.a-size-base');
            title = (titleEl?.textContent || '').trim();
        }
        let href = linkEl?.href || linkEl?.getAttribute('href') || '';
        if (!title) title = (linkEl?.textContent || '').trim();
        if (href.startsWith('/')) href = 'https://www.amazon.co.uk' + href;
        const asinAttr = item.getAttribute('data-asin') || '';
        const asinMatch = href.match(/\\/dp\\/([A-Z0-9]{10})/i);
        const asin = asinAttr || (asinMatch ? asinMatch[1] : '');
        if (!title || !asin || seen.has(asin)) return;
        seen.add(asin);
        if (!href) href = 'https://www.amazon.co.uk/dp/' + asin;

        const ratingAlt = item.querySelector('.a-icon-alt')?.textContent || '';
        const ratingMatch = ratingAlt.match(/([0-9.]+)\\s+out of/);
        const reviewText = item.querySelector('a[href*="#customerReviews"] span, span.a-size-small')?.textContent || '';
        const reviewDigits = reviewText.replace(/[^0-9]/g, '');
        const bought = Array.from(item.querySelectorAll('span'))
            .map((el) => (el.textContent || '').trim())
            .find((t) => t.length < 60 && /bought in (the )?past month/i.test(t));
        const strike = item.querySelector('.a-price[data-a-strike="true"] .a-offscreen, .a-text-price .a-offscreen');
        const priceWhole = item.querySelector('.a-price:not([data-a-strike="true"]) .a-offscreen');

        const parseMoney = (text) => {
            if (!text) return null;
            const n = text.replace(/[^0-9.]/g, '');
            const v = parseFloat(n);
            return Number.isFinite(v) && v > 0 ? v : null;
        };

        out.push({
            rank: parseRank(item, index + 1),
            title: title.slice(0, 200),
            asin,
            url: href.split('?')[0],
            image_url: imgEl ? (imgEl.src || '') : '',
            rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
            review_count: reviewDigits ? parseInt(reviewDigits, 10) : null,
            sales_velocity: bought ? bought.slice(0, 80) : null,
            rrp: parseMoney(strike?.textContent),
            price: parseMoney(priceWhole?.textContent),
        });
    });
    return out.slice(0, 50);
}"""


def extract_asin(url: str | None) -> str | None:
    if not url:
        return None
    match = ASIN_RE.search(url)
    return match.group(1).upper() if match else None


def clean_sales_velocity(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = str(text).strip()
    if len(cleaned) < 60 and "bought" in cleaned.lower():
        return cleaned
    return None


def bestseller_page_urls(base_url: str, pagination_urls: list[str]) -> list[str]:
    """Return page one plus Amazon's advertised bestseller pages, capped safely."""
    pages: dict[int, str] = {1: base_url}
    for url in pagination_urls:
        try:
            page = int(parse_qs(urlparse(url).query).get("pg", [""])[0])
        except (TypeError, ValueError):
            continue
        if 2 <= page <= MAX_BESTSELLER_PAGES:
            pages.setdefault(page, url)
    return [pages[page] for page in sorted(pages)]


async def scroll_bestseller_page_to_end(page) -> None:
    """Trigger Amazon's lazy-loaded lower rankings before parsing a page."""
    previous_height = -1
    for _ in range(12):
        height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)
        current_height = await page.evaluate("document.body.scrollHeight")
        if current_height == height == previous_height:
            break
        previous_height = current_height


def name_similarity(a: str, b: str) -> float:
    """Calculate similarity between two product names (0-1)."""
    a_lower = a.lower().replace("pc case", "").replace("case", "").strip()
    b_lower = b.lower().replace("pc case", "").replace("case", "").strip()
    return SequenceMatcher(None, a_lower, b_lower).ratio()


def match_row_by_bestseller(item: dict, rows: list) -> object | None:
    asin = (item.get("asin") or "").upper()
    if asin:
        for row in rows:
            row_asin = extract_asin(getattr(row, "source_url", None))
            if row_asin == asin:
                return row
            source_url = getattr(row, "source_url", None) or ""
            if asin in source_url.upper():
                return row

    best_similarity = 0.7
    matching = None
    title = item.get("title") or ""
    for row in rows:
        sim = name_similarity(title, getattr(row, "name", "") or "")
        if sim > best_similarity:
            best_similarity = sim
            matching = row
    return matching


async def scrape_amazon_bestsellers() -> dict:
    """
    Scrape Amazon UK bestseller rankings for PC cases and stamp `bestseller_rank`
    onto matching catalogue rows. Unmatched bestsellers are inserted into `cases`
    so the top-30 3D queue is not blocked on an earlier listing scrape.
    """
    results = {
        "scraped": 0,
        "matched": 0,
        "created": 0,
        "errors": 0,
    }

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("bestsellers.browser_error", error=str(exc))
            results["errors"] += 1
            return results

        page = await context.new_page()
        try:
            raw: list[dict] = []
            for page_num in (1, 2):
                url = BESTSELLER_URL if page_num == 1 else f"{BESTSELLER_URL}?pg={page_num}"
                log.info("bestsellers.scraping", url=url, page=page_num)
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_selector(
                        "#gridItemRoot, .zg-grid-general-faceout, div[data-asin]",
                        timeout=15000,
                    )
                except Exception as exc:
                    log.debug("bestsellers.wait_selector_timeout", page=page_num, error=str(exc))
                await asyncio.sleep(3)
                page_items = await page.evaluate(_EXTRACT_JS, (page_num - 1) * 50)
                log.info("bestsellers.extracted", page=page_num, count=len(page_items))
                raw.extend(page_items)

            # Keep the best (lowest) rank per ASIN.
            by_asin: dict[str, dict] = {}
            for item in raw:
                asin = (item.get("asin") or "").upper()
                if not asin:
                    continue
                previous = by_asin.get(asin)
                if previous is None or int(item["rank"]) < int(previous["rank"]):
                    item["asin"] = asin
                    by_asin[asin] = item
            items = sorted(by_asin.values(), key=lambda row: int(row["rank"]))
            results["scraped"] = len(items)

            async with AsyncSessionLocal() as db:
                case_rows = (await db.execute(select(Case))).scalars().all()
                # Do not load the legacy Part ORM model here.  Some deployed
                # databases predate the optional `parts.rrp` column, and an
                # ORM SELECT expands to every model column before the rank
                # update can run.  The component rank path uses the scored
                # CPK table and no longer depends on this legacy case table.
                part_rows = []

                await db.execute(update(Case).values(bestseller_rank=None))
                await db.execute(
                    update(Case)
                    .where(Case.sales_velocity.is_not(None))
                    .where(~Case.sales_velocity.ilike("%bought%"))
                    .values(sales_velocity=None)
                )
                for item in items:
                    matching_case = match_row_by_bestseller(item, case_rows)
                    matching_part = match_row_by_bestseller(item, part_rows)

                    if matching_case:
                        matching_case.bestseller_rank = int(item["rank"])
                        if item.get("rating"):
                            matching_case.rating = item["rating"]
                        if item.get("review_count"):
                            matching_case.review_count = item["review_count"]
                        demand = clean_sales_velocity(item.get("sales_velocity"))
                        if demand:
                            matching_case.sales_velocity = demand
                        if item.get("rrp"):
                            matching_case.rrp = item["rrp"]
                        if item.get("price"):
                            matching_case.price = item["price"]
                            matching_case.price_new = item["price"]
                        matching_case.updated_at = datetime.utcnow()
                        results["matched"] += 1
                    else:
                        created = await _upsert_case_new(db, RawCase(
                            name=item["title"],
                            price=float(item["price"] or 0),
                            source_site="Amazon",
                            source_url=item["url"],
                            image_url=item.get("image_url") or "",
                            theme="Bestseller",
                            rating=item.get("rating"),
                            review_count=item.get("review_count"),
                            sales_velocity=clean_sales_velocity(item.get("sales_velocity")),
                            rrp=item.get("rrp"),
                        ))
                        if created:
                            created.bestseller_rank = int(item["rank"])
                            case_rows.append(created)
                            results["created"] += 1

                    if matching_part:
                        matching_part.bestseller_rank = int(item["rank"])
                    elif not matching_case:
                        await _upsert_case(db, RawCase(
                            name=item["title"],
                            price=float(item["price"] or 0),
                            source_site="Amazon",
                            source_url=item["url"],
                            image_url=item.get("image_url") or "",
                            theme="Bestseller",
                            rating=item.get("rating"),
                            review_count=item.get("review_count"),
                            sales_velocity=item.get("sales_velocity"),
                            rrp=item.get("rrp"),
                        ))

                await db.commit()

            log.info(
                "bestsellers.complete",
                scraped=results["scraped"],
                matched=results["matched"],
                created=results["created"],
            )

        except Exception as exc:
            log.error("bestsellers.error", error=str(exc))
            results["errors"] += 1
        finally:
            await page.close()
            await context.close()
            await browser.close()

    return results


def _best_scored_match(item: dict, rows: list[dict], category: str) -> dict | None:
    """Match an Amazon product to the strongest current CPK row."""
    # The identity/scoring pipeline calls SSDs ``ssd`` and coolers ``cooler``;
    # the Amazon bestseller list configuration historically used the broader
    # ``storage``/``cooling`` labels.  Treat those as aliases or the whole
    # bestseller list is scraped successfully but never attached to a CPK.
    category_aliases = {
        "storage": {"storage", "ssd"},
        "ssd": {"storage", "ssd"},
        "cooler": {"cooler", "cooling"},
        "cooling": {"cooler", "cooling"},
    }
    accepted_categories = category_aliases.get(category, {category})
    candidates = [
        row for row in rows
        if (row["category"] or "").lower() in accepted_categories
    ]
    # Scored rows currently retain marketplace URLs, not Amazon ASINs, so an
    # ASIN cannot be used as a reliable join key here.  Keep the title match
    # conservative rather than claiming an ASIN match or attaching a rank to
    # an ambiguous product variant.
    scored = []
    for row in candidates:
        similarity = name_similarity(item.get("title") or "", row["title"] or "")
        scored.append((similarity, row))
    scored.sort(key=lambda value: value[0], reverse=True)
    if not scored or scored[0][0] <= 0.66:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.05:
        return None
    return scored[0][1]


async def scrape_amazon_component_bestsellers() -> dict:
    """Capture daily Amazon bestseller ranks for all supported PC components.

    Ranks are historical observations.  A current scored listing is matched
    to an Amazon item by ASIN where possible, then conservatively by title and
    category.  The CPK is stored on the observation, allowing every
    marketplace listing for that product to inherit the same rank in the
    catalogue.
    """
    results = {"scraped": 0, "matched": 0, "categories": 0, "errors": 0}
    async with managed_playwright() as p:
        browser, context = await _make_pw_context(p)
        page = await context.new_page()
        try:
            async with AsyncSessionLocal() as db:
                scored_rows = (await db.execute(
                    select(
                        GemRadarScoredListing.listing_id,
                        GemRadarScoredListing.category,
                        GemRadarScoredListing.cpk,
                        GemRadarScoredListing.title,
                        GemRadarScoredListing.url,
                    ).where(GemRadarScoredListing.cpk.is_not(None))
                )).mappings().all()
                scored = [dict(row) for row in scored_rows]

                for category, (list_name, base_url) in COMPONENT_BESTSELLER_LISTS.items():
                    try:
                        items: list[dict] = []
                        page_urls = [base_url]
                        for page_num, url in enumerate(page_urls, start=1):
                            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                            try:
                                await page.wait_for_selector(
                                    "#gridItemRoot, .zg-grid-general-faceout, div[data-asin]",
                                    timeout=15000,
                                )
                            except Exception:
                                pass
                            await asyncio.sleep(2)
                            await scroll_bestseller_page_to_end(page)
                            items.extend(await page.evaluate(_EXTRACT_JS, (page_num - 1) * 50))
                            if page_num == 1:
                                pagination_urls = await page.locator("a[href*='pg=']").evaluate_all(
                                    "links => links.map(link => link.href)"
                                )
                                page_urls = bestseller_page_urls(base_url, pagination_urls)

                        unique: dict[str, dict] = {}
                        for item in items:
                            asin = (item.get("asin") or "").upper()
                            if asin and (asin not in unique or item["rank"] < unique[asin]["rank"]):
                                item["asin"] = asin
                                unique[asin] = item

                        for item in sorted(unique.values(), key=lambda value: value["rank"]):
                            match = _best_scored_match(item, scored, category)
                            db.add(AmazonBestsellerObservation(
                                category=category,
                                list_name=list_name,
                                asin=item["asin"],
                                title=item["title"],
                                url=item.get("url"),
                                image_url=item.get("image_url"),
                                rank=int(item["rank"]),
                                cpk=match["cpk"] if match else None,
                                rating=item.get("rating"),
                                review_count=item.get("review_count"),
                            ))
                            results["scraped"] += 1
                            if match:
                                results["matched"] += 1
                        results["categories"] += 1
                    except Exception as exc:
                        log.warning("bestsellers.category_error", category=category, error=str(exc))
                        results["errors"] += 1
                await db.commit()
        finally:
            await page.close()
            await context.close()
            await browser.close()
    log.info("bestsellers.components_complete", **results)
    return results
