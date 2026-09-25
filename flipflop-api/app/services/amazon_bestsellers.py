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
from datetime import datetime

from difflib import SequenceMatcher
from sqlalchemy import select, update, text
import structlog

from app.database import AsyncSessionLocal
from app.models.case import Case
from app.models.part import Part, PartCategory
from app.models.amazon_bestseller_observation import AmazonBestsellerObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.services.case_product_key import case_product_key
from app.services.browser_pool import managed_playwright
from app.swarms.cases import RawCase, _make_pw_context, _upsert_case

log = structlog.get_logger(__name__)

BESTSELLER_URL = (
    "https://www.amazon.co.uk/Best-Sellers-Computers-Accessories-Computer-Cases/"
    "zgbs/computers/430498031/"
)
# Amazon's component bestseller pages.  The list name is stored with every
# daily observation so the UI can explain exactly what a rank means.
COMPONENT_BESTSELLER_LISTS = {
    "cpu": ("CPUs", "https://www.amazon.co.uk/zgbs/computers/430515031/"),
    "gpu": ("Graphics Cards", "https://www.amazon.co.uk/zgbs/computers/430500031/"),
    "ram": ("Computer Memory", "https://www.amazon.co.uk/zgbs/computers/430511031/"),
    "storage": ("Internal Solid State Drives", "https://www.amazon.co.uk/zgbs/computers/430505031/"),
    "motherboard": ("Motherboards", "https://www.amazon.co.uk/zgbs/computers/430512031/"),
    "psu": ("Power Supplies", "https://www.amazon.co.uk/zgbs/computers/430514031/"),
    "cooler": ("Fans & Cooling", "https://www.amazon.co.uk/zgbs/computers/430499031/"),
    "case": ("Computer Cases", BESTSELLER_URL),
}
ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})", re.I)

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
        const priceWhole = item.querySelector('.a-price:not([data-a-strike="true"]) .a-offscreen, .a-color-price, [class*="p13n-sc-price_"]');

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


async def _load_bestseller_page(page, url: str, rank_offset: int) -> tuple[list[dict], str | None, bool]:
    """Scroll one bestseller page to its end and return products/next URL/completion."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_selector("#gridItemRoot, .zg-grid-general-faceout, div[data-asin]", timeout=15000)
            selector = "#gridItemRoot"
            if await page.locator(selector).count() == 0:
                selector = ".zg-grid-general-faceout"
            if await page.locator(selector).count() == 0:
                selector = "div[data-asin]"
            previous_count = -1
            stable_rounds = 0
            for _ in range(80):
                cards = await page.locator(selector).count()
                if cards == previous_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    previous_count = cards
                await page.locator(selector).last.scroll_into_view_if_needed()
                await page.mouse.wheel(0, 1800)
                await page.wait_for_timeout(350)
                at_bottom = await page.evaluate("window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 8")
                if at_bottom and stable_rounds >= 3:
                    break
            else:
                raise ValueError(f"Amazon bestseller page did not reach a stable bottom: {url}")
            items = await page.evaluate(_EXTRACT_JS, rank_offset)
            next_selector = 'a[aria-label="Go to next page"], li.a-last:not(.a-disabled) a'
            next_href = await page.locator(next_selector).first.get_attribute("href") if await page.locator(next_selector).count() else None
            next_url = page.url.split("#")[0]
            if next_href:
                from urllib.parse import urljoin
                next_url = urljoin(page.url, next_href).split("#")[0]
            return items, next_url if next_href else None, True
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
    raise ValueError(f"Amazon bestseller page failed after 3 attempts: {url}: {last_error}")


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
                amazon_by_asin = {
                    extract_asin(row.source_url): row for row in case_rows
                    if row.source_site.lower() == "amazon" and extract_asin(row.source_url)
                }
                amazon_by_cpk = {
                    case_product_key(row.name, row.brand, row.model): row for row in case_rows
                    if row.source_site.lower() == "amazon"
                }
                for item in items:
                    item_cpk = case_product_key(item["title"])
                    matching_case = amazon_by_asin.get(item["asin"]) or amazon_by_cpk.get(item_cpk)
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
                        matching_case.source_url = item["url"]
                        matching_case.image_url = item.get("image_url") or matching_case.image_url
                        matching_case.updated_at = datetime.utcnow()
                        results["matched"] += 1
                    else:
                        created = Case(
                            name=item["title"],
                            price=float(item["price"] or 0),
                            price_new=float(item["price"] or 0),
                            source_site="Amazon",
                            source_url=item["url"],
                            image_url=item.get("image_url") or "",
                            rating=item.get("rating"),
                            review_count=item.get("review_count"),
                            sales_velocity=clean_sales_velocity(item.get("sales_velocity")),
                            rrp=item.get("rrp"),
                            bestseller_rank=int(item["rank"]),
                        )
                        db.add(created)
                        case_rows.append(created)
                        results["created"] += 1
                    amazon_by_asin[item["asin"]] = matching_case or created
                    amazon_by_cpk[item_cpk] = matching_case or created

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
    asin = (item.get("asin") or "").upper()
    if asin:
        # ASIN is the strongest available identity for Amazon marketplace
        # listings. If we have an exact listing, use it only when its CPK is
        # present and its resolved category agrees. Do not fall through to a
        # fuzzy title match when the exact row is unclassified or conflicted.
        exact_rows = [
            row for row in rows
            if extract_asin(row.get("url")) == asin
            or str(row.get("listing_id") or "").upper() == asin
        ]
        if exact_rows:
            exact_cpk_rows = [
                row for row in exact_rows
                if row.get("cpk") and (row.get("category") or "").lower() in accepted_categories
            ]
            distinct_cpks = {row["cpk"] for row in exact_cpk_rows}
            return exact_cpk_rows[0] if len(distinct_cpks) == 1 else None

    candidates = [
        row for row in rows
        if (row["category"] or "").lower() in accepted_categories
    ]
    # A full sweep contains tens of thousands of scored rows. Compare the
    # expensive sequence ratio only for plausible same-product candidates.
    generic = {"the", "for", "with", "and", "computer", "gaming", "case", "pc", "black", "white", "rgb", "argb"}
    item_tokens = set(re.findall(r"[a-z0-9]{3,}", (item.get("title") or "").lower())) - generic
    # Without an exact ASIN listing, keep title matching conservative rather
    # than attaching a rank to an ambiguous product variant.
    scored_by_cpk: dict[str, tuple[float, dict]] = {}
    for row in candidates:
        if not row.get("cpk"):
            continue
        row_tokens = set(re.findall(r"[a-z0-9]{3,}", (row["title"] or "").lower())) - generic
        if len(item_tokens & row_tokens) < 2:
            continue
        similarity = name_similarity(item.get("title") or "", row["title"] or "")
        previous = scored_by_cpk.get(row["cpk"])
        if previous is None or similarity > previous[0]:
            scored_by_cpk[row["cpk"]] = (similarity, row)
    scored = sorted(scored_by_cpk.values(), key=lambda value: value[0], reverse=True)
    if not scored or scored[0][0] <= 0.66:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.05:
        return None
    return scored[0][1]


def bestseller_item_matches_category(title: str, category: str) -> bool:
    """Reject Amazon redirects/incorrect browse-node lists before ranking them."""
    value = title.lower()
    if category == "cpu":
        return bool(re.search(r"\b(?:ryzen|threadripper|core\s+i[3579]|core\s+ultra|processor|cpu)\b", value)) and not bool(re.search(r"\b(?:motherboard|cooler|heatsink|laptop)\b", value))
    if category == "gpu":
        return bool(re.search(r"\b(?:graphics\s+card|geforce|radeon|rtx\s*\d|gtx\s*\d|rx\s*\d)\b", value)) and "laptop" not in value
    if category == "motherboard":
        return bool(re.search(r"\b(?:motherboard|mainboard)\b", value))
    if category == "storage":
        return bool(re.search(r"\b(?:ssd|solid\s+state)\b", value)) and not bool(re.search(r"\b(?:hdd|hard\s+drive|cartridge|tape)\b", value))
    if category == "case":
        return bool(re.search(r"\b(?:pc\s+case|computer\s+case|chassis|mid[- ]tower|full[- ]tower)\b", value))
    if category == "ram":
        return bool(re.search(r"\b(?:ram|memory|dimm|ddr[345])\b", value))
    if category == "psu":
        return bool(re.search(r"\b(?:power\s+supply|psu)\b", value))
    if category == "cooler":
        return bool(re.search(r"\b(?:cpu\s+cooler|aio|heatsink|liquid\s+cooler)\b", value))
    return False


async def scrape_amazon_component_bestsellers(categories: list[str] | None = None) -> dict:
    """Capture daily Amazon bestseller ranks for all supported PC components.

    Ranks are historical observations.  A current scored listing is matched
    to an Amazon item by ASIN where possible, then conservatively by title and
    category.  The CPK is stored on the observation, allowing every
    marketplace listing for that product to inherit the same rank in the
    catalogue.
    """
    selected_lists = {key: value for key, value in COMPONENT_BESTSELLER_LISTS.items()
                      if categories is None or key in categories}
    if not selected_lists or (categories is not None and len(selected_lists) != len(set(categories))):
        raise ValueError("Unknown or empty Amazon bestseller category selection")
    results = {"scraped": 0, "matched": 0, "categories": 0, "errors": 0, "category_results": {}}
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
                amazon_rows = (await db.execute(
                    select(
                        GemRadarScoredListing.listing_id,
                        GemRadarScoredListing.category,
                        GemRadarScoredListing.cpk,
                        GemRadarScoredListing.title,
                        GemRadarScoredListing.url,
                    ).where(GemRadarScoredListing.source == "amazon")
                )).mappings().all()
                amazon_by_asin: dict[str, list[dict]] = {}
                for row in amazon_rows:
                    amazon_row = dict(row)
                    asin = extract_asin(amazon_row.get("url")) or str(amazon_row.get("listing_id") or "").upper()
                    if asin:
                        amazon_by_asin.setdefault(asin, []).append(amazon_row)

                for category, (list_name, base_url) in selected_lists.items():
                    try:
                        match_categories = {"storage": {"ssd", "storage"}, "cooler": {"cooler", "cooling"}}.get(category, {category})
                        scored_for_category = [
                            row for row in scored
                            if (row.get("category") or "").lower() in match_categories
                        ]
                        items: list[dict] = []
                        page_urls: set[str] = set()
                        url: str | None = base_url
                        page_num = 1
                        while url:
                            normalized_url = url.split("#")[0]
                            if normalized_url in page_urls:
                                raise ValueError(f"Amazon bestseller pagination loop detected at {normalized_url}")
                            page_urls.add(normalized_url)
                            page_items, next_url, page_complete = await _load_bestseller_page(page, normalized_url, (page_num - 1) * 50)
                            if not page_complete:
                                raise ValueError(f"Amazon bestseller page {page_num} was not fully traversed")
                            page_title = (await page.title()).lower()
                            if list_name.lower() not in page_title:
                                raise ValueError(f"unexpected Amazon list page: {page_title[:100]}")
                            items.extend(page_items)
                            if next_url and next_url in page_urls:
                                raise ValueError(f"Amazon bestseller next-page link loops to {next_url}")
                            url = next_url
                            page_num += 1
                            if page_num > 100:
                                raise ValueError(f"Amazon bestseller pagination exceeded 100 pages for {category}")

                        if not page_urls:
                            raise ValueError(f"{category} bestseller list had no pages")

                        unique: dict[str, dict] = {}
                        for item in items:
                            asin = (item.get("asin") or "").upper()
                            if asin and (asin not in unique or item["rank"] < unique[asin]["rank"]):
                                item["asin"] = asin
                                unique[asin] = item

                        if not unique:
                            raise ValueError(f"{category} bestseller pages yielded no products")
                        valid_items = [item for item in unique.values() if bestseller_item_matches_category(item["title"], category)]
                        category_matched = 0
                        category_priced = sum(item.get("price") is not None for item in valid_items)
                        category_scraped = category_matched_total = 0
                        for item in sorted(unique.values(), key=lambda value: value["rank"]):
                            # Preserve every Amazon rank in the admin list, even when
                            # Amazon places an unrelated item in this source category.
                            exact_rows = amazon_by_asin.get(item["asin"], [])
                            match = (_best_scored_match(item, [*scored_for_category, *exact_rows], category)
                                     if bestseller_item_matches_category(item["title"], category) else None)
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
                                price=item.get("price"),
                                rrp=item.get("rrp"),
                                sales_velocity=clean_sales_velocity(item.get("sales_velocity")),
                            ))
                            category_scraped += 1
                            if match:
                                category_matched_total += 1
                                category_matched += 1
                        await db.commit()
                        results["scraped"] += category_scraped
                        results["matched"] += category_matched_total
                        results["categories"] += 1
                        results["category_results"][category] = {"status": "ok", "pages": len(page_urls), "parsed": len(unique), "valid": len(valid_items), "matched": category_matched, "priced": category_priced}
                    except Exception as exc:
                        await db.rollback()
                        log.warning("bestsellers.category_error", category=category, error=str(exc))
                        results["errors"] += 1
                        results["category_results"][category] = {"status": "failed", "error": str(exc)}
        finally:
            await page.close()
            await context.close()
            await browser.close()
    results["ok"] = results["errors"] == 0 and results["categories"] == len(selected_lists)
    if not results["ok"]:
        results["reason"] = f"pagination_failed: {results['categories']}/{len(selected_lists)} lists completed, {results['errors']} errors"
    log.info("bestsellers.components_complete", **results)
    return results


async def backfill_recent_bestseller_prices() -> dict[str, int]:
    """Refresh offer fields on already-captured ASINs without rematching CPKs."""
    updated: dict[str, int] = {}
    async with managed_playwright() as p:
        browser, context = await _make_pw_context(p)
        page = await context.new_page()
        try:
            async with AsyncSessionLocal() as db:
                for category, (_, base_url) in COMPONENT_BESTSELLER_LISTS.items():
                    count = 0
                    url: str | None = base_url
                    page_num = 1
                    seen_pages: set[str] = set()
                    items: list[dict] = []
                    while url:
                        if url in seen_pages:
                            raise ValueError(f"Amazon bestseller pagination loop detected at {url}")
                        seen_pages.add(url)
                        page_items, url, _ = await _load_bestseller_page(page, url, (page_num - 1) * 50)
                        items.extend(page_items)
                        page_num += 1
                    for item in items:
                        if item.get("price") is None:
                            continue
                        result = await db.execute(text("""
                            UPDATE amazon_bestseller_observations
                            SET price=:price, rrp=:rrp, sales_velocity=:sales_velocity
                            WHERE category=:category AND asin=:asin
                              AND captured_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                        """), {"price": item["price"], "rrp": item.get("rrp"),
                               "sales_velocity": clean_sales_velocity(item.get("sales_velocity")),
                               "category": category, "asin": item["asin"]})
                        count += result.rowcount or 0
                    if count == 0:
                        raise RuntimeError(f"No recent {category} bestseller prices could be backfilled")
                    updated[category] = count
                    await db.commit()
        finally:
            await page.close()
            await context.close()
            await browser.close()
    return updated
