"""
Scraper service — fetches listings from configured data sources.
Each platform has its own adapter. Falls back to HTML scraping when no API.
"""
import asyncio
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from app.config import get_settings
from app.services.spec_parser import parse_specs

settings = get_settings()
ua = UserAgent()

# ── Global title exclusions ──────────────────────────────────────────────────
# Mini PCs / NUCs are not worth flipping: they use laptop CPUs, soldered RAM,
# proprietary PSUs, and sell for £50-150 against a £30-40 upgrade ceiling.
# Exclude at parse time so they never enter the pipeline.
_MINI_PC_EXCLUDE: set[str] = {
    "mini pc",
    "mini-pc",
    "mini computer",
    "mini desktop",
    "intel nuc",
    " nuc ",
    "nuc pc",
    "stick pc",
    "pc stick",
    "beelink",
    "minisforum",
    "gmktec",
    "trigkey",
    "geekom",
    "mele quieter",
    "acemagic",
    "asus nuc",
    "compute stick",
    "hdmi stick",
    "tiny pc",
    "nano pc",
    "pico pc",
}


@dataclass
class RawListing:
    external_id: str
    title: str
    price: float
    url: str
    location: Optional[str]
    condition: Optional[str]
    description: str
    image_urls: list[str] = field(default_factory=list)
    source_name: str = ""
    # "auction" | "buy_it_now" | "classified"
    listing_type: str = "buy_it_now"
    # When the auction/listing expires (None for BIN / classified)
    listing_ends_at: Optional[datetime] = None
    # Seller intelligence
    seller_name: Optional[str] = None
    seller_feedback_count: Optional[int] = None
    seller_feedback_pct: Optional[float] = None   # 0–100 positive %
    seller_type: Optional[str] = None             # shop|refurb_shop|flipper|private
    seller_has_shop: bool = False
    # When the listing was originally posted by the seller
    listed_at: Optional[datetime] = None


# ── Seller classification heuristics ─────────────────────────────────────────

_SHOP_KW: set[str] = {
    "computer", "computers", "tech", "it", "systems", "solutions",
    "store", "shop", "supplies", "electronics", "digital", "hardware",
    "ltd", "limited", "trading", "direct", "sales", "uk",
    "outlet", "world", "zone", "hub", "depot",
}
_REFURB_KW: set[str] = {
    "refurb", "refurbished", "renewed", "reconditioned",
    "grade", "graded", "tested", "recon", "certified", "renewed",
}
_FLIPPER_KW: set[str] = {
    "clearance", "lot", "joblot", "bundle", "surplus", "bulk",
    "flip", "resell", "resale", "second-hand", "secondhand",
}


def classify_seller(
    seller_name: Optional[str],
    feedback_count: Optional[int],
    title: str,
    has_shop: bool = False,
) -> str:
    """
    Return one of: 'shop' | 'refurb_shop' | 'flipper' | 'private'
    Order of priority: refurb_shop > shop > flipper > private
    """
    name = (seller_name or "").lower()
    t = title.lower()
    fc = feedback_count or 0

    # Refurb signals in title or seller name dominate
    if any(kw in t for kw in _REFURB_KW) or any(kw in name for kw in _REFURB_KW):
        return "refurb_shop"

    # Official eBay store, very high feedback, or shop keywords in name
    if has_shop or fc >= 500 or any(kw in name for kw in _SHOP_KW):
        return "shop"

    # Active flipper range: moderate feedback or flipper language
    if (20 <= fc < 500) or any(kw in t for kw in _FLIPPER_KW):
        return "flipper"

    return "private"


def _parse_ebay_time_left(text: str) -> Optional[datetime]:
    """
    Parse eBay relative-time strings like '2d 5h left', '3h 45m', '59m 30s'.
    Returns the estimated end datetime (UTC).
    """
    from datetime import timedelta
    total_secs = 0
    m = re.search(r"(\d+)\s*d", text, re.I)
    if m: total_secs += int(m.group(1)) * 86400
    m = re.search(r"(\d+)\s*h", text, re.I)
    if m: total_secs += int(m.group(1)) * 3600
    m = re.search(r"(\d+)\s*m", text, re.I)
    if m: total_secs += int(m.group(1)) * 60
    if total_secs > 0:
        return datetime.utcnow() + timedelta(seconds=total_secs)
    return None


def _parse_ebay_listing_date(text: str) -> Optional[datetime]:
    """
    Parse eBay listing-date strings like 'Listed: Mar 12, 2025' or 'Listed today'.
    Returns UTC datetime or None.
    """
    from datetime import timedelta
    t = text.lower().strip()
    if "today" in t:
        return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if "yesterday" in t:
        return (datetime.utcnow() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # "X days ago"
    m = re.search(r"(\d+)\s*days?\s*ago", t)
    if m:
        return datetime.utcnow() - timedelta(days=int(m.group(1)))
    # "Mon DD, YYYY" or "DD Mon YYYY"
    for fmt in ("%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y"):
        try:
            # Strip "listed:" prefix
            clean = re.sub(r"^[^a-z]*listed\s*:?\s*", "", t, flags=re.I).strip()
            return datetime.strptime(clean, fmt)
        except ValueError:
            pass
    return None


async def _delay():
    await asyncio.sleep(
        random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
    )


def _headers() -> dict:
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }


# ---------------------------------------------------------------------------
# eBay adapter — uses Browse API when key available, else HTML scraping
# ---------------------------------------------------------------------------

async def scrape_ebay(
    search_terms: list[str],
    min_price: float,
    max_price: float,
    auction_mode: bool = False,
) -> list[RawListing]:
    """
    Searches eBay UK for each term in sequence.
    auction_mode=True → returns ending-soonest auctions (LH_Auction=1, _sop=1).
    auction_mode=False → returns Buy It Now listings (LH_BIN=1, _sop=10 newest).
    Deduplicates within run. Delay 0.8–1.8 s.
    """
    results: list[RawListing] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in search_terms:
            await asyncio.sleep(random.uniform(0.8, 1.8))
            try:
                if auction_mode:
                    params = {
                        "_nkw": term,
                        "_sacat": "179",
                        "LH_Auction": "1",   # Auctions only
                        "LH_ItemCondition": "3000",
                        "_udlo": str(int(min_price)),
                        "_udhi": str(int(max_price)),
                        "LH_PrefLoc": "1",
                        "_sop": "1",         # Sort: ending soonest (live deals)
                        "_ipg": "60",
                    }
                else:
                    params = {
                        "_nkw": term,
                        "_sacat": "179",   # PCs / Desktops category
                        "LH_BIN": "1",     # Buy It Now
                        "LH_ItemCondition": "3000",  # Used
                        "_udlo": str(int(min_price)),
                        "_udhi": str(int(max_price)),
                        "LH_PrefLoc": "1", # UK only
                        "_sop": "10",      # Sort: newly listed
                        "_ipg": "60",      # 60 results per page
                    }
                resp = await client.get(
                    "https://www.ebay.co.uk/sch/i.html",
                    params=params,
                    headers=_headers(),
                )
                new_listings = _parse_ebay_html(resp.text, term)
                # In auction mode every result is an auction — enforce it regardless
                # of whether the bid-count element was parsed (it's sometimes absent
                # in search snippets but always present on the item page).
                if auction_mode:
                    for l in new_listings:
                        if l.listing_type != "auction":
                            l.listing_type = "auction"
                        l.source_name = "eBay UK Auctions"
                before = len(results)
                for listing in new_listings:
                    if listing.external_id not in seen_ids:
                        seen_ids.add(listing.external_id)
                        results.append(listing)
                added = len(results) - before
                print(f"[scraper] eBay '{term}': {len(new_listings)} found, {added} new (total {len(results)})")
            except Exception as exc:
                print(f"[scraper] eBay error for {term!r}: {exc}")
    return results


def _parse_ebay_html(html: str, term: str) -> list[RawListing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    # eBay updated to .s-card in 2024/25 — fall back to legacy .s-item if needed
    cards = soup.select(".s-card[data-listingid]") or soup.select(".s-item:not(.s-item--placeholder)")

    for item in cards:
        try:
            # Title — try multiple selectors
            title_el = (
                item.select_one(".s-card__title span")
                or item.select_one("[class*='s-card__title']")
                or item.select_one(".s-item__title")
            )
            # Price
            price_el = (
                item.select_one("[class*='s-card__price']")
                or item.select_one(".s-item__price")
            )
            # Link — prefer href containing /itm/
            url_el = (
                item.select_one("a[href*='/itm/']")
                or item.select_one("a.s-card__link")
                or item.select_one("a.s-item__link")
            )
            # Image
            img_el = (
                item.select_one("img.s-card__image")
                or item.select_one("img[class*='s-card']")
                or item.select_one("img.s-item__image-img")
            )
            # Location
            loc_el = (
                item.select_one("[class*='location']")
                or item.select_one(".s-item__location")
            )

            if not title_el or not url_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or title.lower() in ("shop on ebay", ""):
                continue
            if _is_mini_pc(title):
                continue

            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _parse_price(price_text)
            if price <= 0:
                continue

            url = url_el.get("href", "")
            if not url:
                continue

            # Use data-listingid if available, else extract from URL
            external_id = item.get("data-listingid") or _extract_ebay_id(url)

            # Image src may be in data-defer-load for lazy-loaded images.
            # Upgrade to highest available resolution: s-l225/s-l300/s-l500 → s-l1600.
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-defer-load") or img_el.get("data-src") or ""
                # Skip placeholder images
                if "ebaystatic.com" in image_url or image_url.endswith(".png"):
                    image_url = ""
                elif image_url:
                    # eBay CDN: replace thumbnail size token with full-res 1600px
                    image_url = re.sub(r"s-l\d+", "s-l1600", image_url)

            location = loc_el.get_text(strip=True).replace("From ", "") if loc_el else None

            # ── Listing type and auction end time ────────────────────────────
            bid_el = (
                item.select_one(".s-item__bids")
                or item.select_one(".x-bid-count")
                or item.select_one("[class*='bidCount']")
                or item.select_one("[class*='bid--']")
            )
            is_auction = bool(
                bid_el and re.search(r"\d+\s*bid", bid_el.get_text(), re.I)
            )
            listing_type = "auction" if is_auction else "buy_it_now"

            listing_ends_at: Optional[datetime] = None
            if is_auction:
                time_el = (
                    item.select_one(".s-item__time-end")
                    or item.select_one("[class*='time-end']")
                    or item.select_one(".s-item__time-left")
                    or item.select_one("[class*='time-left']")
                )
                if time_el:
                    listing_ends_at = _parse_ebay_time_left(time_el.get_text(strip=True))

            # ── When originally listed ───────────────────────────────────────
            listed_at: Optional[datetime] = None
            listdate_el = (
                item.select_one(".s-item__listingdate")
                or item.select_one("[class*='listingdate']")
                or item.select_one("[class*='listing-date']")
            )
            if listdate_el:
                listed_at = _parse_ebay_listing_date(listdate_el.get_text(strip=True))

            # ── Seller intelligence ──────────────────────────────────────────
            seller_name: Optional[str] = None
            seller_feedback_count: Optional[int] = None
            seller_feedback_pct: Optional[float] = None
            seller_has_shop = False

            # Seller info block: "username (1234) 99.8% positive"
            seller_el = (
                item.select_one(".s-item__seller-info-text")
                or item.select_one("[class*='s-item__seller-info']")
                or item.select_one("[class*='seller-info']")
            )
            if seller_el:
                raw_seller = seller_el.get_text(strip=True)
                # Extract name (before the parenthesised number)
                name_m = re.match(r"^([^\(]+)", raw_seller)
                if name_m:
                    seller_name = name_m.group(1).strip()
                # Extract feedback count e.g. "(12,345)"
                fc_m = re.search(r"\(([0-9,]+)\)", raw_seller)
                if fc_m:
                    try:
                        seller_feedback_count = int(fc_m.group(1).replace(",", ""))
                    except ValueError:
                        pass
                # Extract positive % e.g. "99.8% positive"
                pct_m = re.search(r"([\d.]+)%", raw_seller)
                if pct_m:
                    try:
                        seller_feedback_pct = float(pct_m.group(1))
                    except ValueError:
                        pass

            # eBay Shop indicator — seller URL contains /str/ or a shop icon exists
            shop_link = item.select_one("a[href*='/str/']") or item.select_one("[class*='store']")
            if shop_link:
                seller_has_shop = True

            seller_type = classify_seller(seller_name, seller_feedback_count, title, seller_has_shop)

            listings.append(RawListing(
                external_id=f"ebay_{external_id}",
                title=title,
                price=price,
                url=url,
                location=location,
                condition="used",
                description="",
                image_urls=[image_url] if image_url else [],
                source_name="eBay UK",
                listing_type=listing_type,
                listing_ends_at=listing_ends_at,
                seller_name=seller_name,
                seller_feedback_count=seller_feedback_count,
                seller_feedback_pct=seller_feedback_pct,
                seller_type=seller_type,
                seller_has_shop=seller_has_shop,
                listed_at=listed_at,
            ))
        except Exception:
            continue
    return listings


def _is_mini_pc(title: str) -> bool:
    """Return True if the listing title looks like a mini PC / NUC (skip it)."""
    t = title.lower()
    return any(kw in t for kw in _MINI_PC_EXCLUDE)


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    return float(m.group(0)) if m else 0.0


def _extract_ebay_id(url: str) -> str:
    m = re.search(r"/itm/(\d+)", url)
    return m.group(1) if m else url[-16:]


# ---------------------------------------------------------------------------
# Gumtree adapter — HTML scraping
# ---------------------------------------------------------------------------

async def scrape_gumtree(search_terms: list[str], max_price: float) -> list[RawListing]:
    """
    NOTE: Gumtree is a fully JavaScript-rendered SPA and blocks automated HTTP requests
    (returns HTTP 247 with empty body). This adapter will return 0 results until a
    headless browser (Playwright) integration is added.
    """
    results: list[RawListing] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in search_terms:
            await _delay()
            try:
                resp = await client.get(
                    "https://www.gumtree.com/search",
                    params={
                        "search_category": "computers-desktop-computers",
                        "q": term,
                        "max_price": str(int(max_price)),
                        "sort": "date",
                    },
                    headers=_headers(),
                )
                # Gumtree returns a nearly-empty body when bot-detecting (often HTTP 247)
                if len(resp.text) < 2000 or resp.status_code not in (200, 301, 302):
                    print(f"[scraper] Gumtree: bot-detected for {term!r} "
                          f"(status={resp.status_code}, body_len={len(resp.text)}). "
                          "Skipping — Gumtree requires a headless browser.")
                    continue
                results.extend(_parse_gumtree_html(resp.text))
            except Exception as exc:
                print(f"[scraper] Gumtree error for {term!r}: {exc}")
    return results


def _parse_gumtree_html(html: str) -> list[RawListing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    # Gumtree has changed its HTML structure multiple times.
    # Try modern selectors first, then fall back to legacy ones.
    cards = (
        soup.select("article.listing-maxi")
        or soup.select("article.listing-thumbnail")
        or soup.select("[data-q='search-result']")
        or soup.select(".listing-link")
        or soup.select(".natural")
        or soup.select(".listing-maxi, .listing-thumbnail")
    )

    if not cards:
        # Last-ditch: any anchor with /ad/ in the href is a listing link
        anchors = soup.select("a[href*='/ad/']")
        print(f"[scraper] Gumtree: no cards found via standard selectors, found {len(anchors)} /ad/ links")
        for a in anchors[:30]:
            try:
                url = a.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.gumtree.com" + url
                title_el = a.select_one("h2, h3, [class*='title']") or a
                title = title_el.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                price_el = a.select_one("[class*='price']")
                price_text = price_el.get_text(strip=True) if price_el else "0"
                price = _parse_price(price_text)
                external_id = url.split("/")[-1].split("?")[0]
                img_el = a.select_one("img")
                image_url = img_el.get("src", "") if img_el else ""
                listings.append(RawListing(
                    external_id=f"gumtree_{external_id}",
                    title=title,
                    price=price,
                    url=url,
                    location=None,
                    condition="used",
                    description="",
                    image_urls=[image_url] if image_url else [],
                    source_name="Gumtree",
                ))
            except Exception:
                continue
        return listings

    print(f"[scraper] Gumtree: found {len(cards)} cards")
    for item in cards:
        try:
            title_el = (
                item.select_one("[data-q='listing-title']")
                or item.select_one(".listing-title")
                or item.select_one("h2")
                or item.select_one("h3")
            )
            price_el = (
                item.select_one("[data-q='listing-price']")
                or item.select_one(".listing-price strong")
                or item.select_one("[class*='price']")
                or item.select_one(".price")
            )
            url_el = (
                item.select_one("a[href*='/ad/']")
                or item.select_one("a[href*='/p/']")
                or item.select_one("a[href]")
            )
            img_el = item.select_one("img")
            loc_el = (
                item.select_one("[data-q='listing-location']")
                or item.select_one(".listing-location")
                or item.select_one("[class*='location']")
            )

            if not title_el or not url_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or len(title) < 5 or _is_mini_pc(title):
                continue

            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = _parse_price(price_text)

            url = url_el.get("href", "")
            if not url.startswith("http"):
                url = "https://www.gumtree.com" + url

            external_id = url.split("/")[-1].split("?")[0]
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            location = loc_el.get_text(strip=True) if loc_el else None

            listings.append(RawListing(
                external_id=f"gumtree_{external_id}",
                title=title,
                price=price,
                url=url,
                location=location,
                condition="used",
                description="",
                image_urls=[image_url] if image_url else [],
                source_name="Gumtree",
            ))
        except Exception:
            continue
    return listings


# ---------------------------------------------------------------------------
# Preloved.co.uk adapter — UK classifieds, server-rendered PHP HTML
# ---------------------------------------------------------------------------

async def scrape_preloved(search_terms: list[str], min_price: float, max_price: float) -> list[RawListing]:
    """
    Preloved.co.uk — UK second-hand classifieds, server-rendered PHP HTML (no JS required).
    Tries the computers category first, falls back to site-wide search if the page looks empty.
    """
    results: list[RawListing] = []
    seen: set[str] = set()

    # Preloved uses keyword search — try up to 10 terms
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in search_terms[:10]:
            await _delay()
            try:
                # Try the computers category URL first, then the broader all-categories search
                urls_to_try = [
                    "https://www.preloved.co.uk/classifieds/computers/all/uk",
                    "https://www.preloved.co.uk/classifieds/all/all/uk",
                ]
                resp = None
                for base_url in urls_to_try:
                    r = await client.get(
                        base_url,
                        params={
                            "keywords": term,
                            "price_max": str(int(max_price)),
                            "price_min": str(int(min_price)),
                            "sort": "date_desc",
                        },
                        headers=_headers(),
                    )
                    if r.status_code == 200 and len(r.text) > 3000:
                        resp = r
                        break
                    print(f"[scraper] Preloved: {base_url} → {r.status_code}, body_len={len(r.text)}")

                if resp is None:
                    print(f"[scraper] Preloved: no usable response for {term!r}, skipping")
                    continue

                listings = _parse_preloved_html(resp.text)
                added = 0
                for l in listings:
                    if l.external_id not in seen:
                        seen.add(l.external_id)
                        results.append(l)
                        added += 1
                print(f"[scraper] Preloved '{term}': {len(listings)} parsed, {added} new (total {len(results)})")
            except Exception as exc:
                print(f"[scraper] Preloved error for {term!r}: {exc}")

    return results


def _parse_preloved_html(html: str) -> list[RawListing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    # Preloved has used several HTML structures over the years — try them all
    cards = (
        soup.select("article.classifieds-item")
        or soup.select(".classifieds-item")
        or soup.select("li.advert")
        or soup.select("[class*='advert-item']")
        or soup.select(".advert")
        or soup.select("li[data-id]")
        or soup.select("[class*='listing-item']")
    )

    if not cards:
        # Last-ditch: find any link to an /adverts/ page
        anchors = [a for a in soup.select("a[href*='/adverts/']") if a.get_text(strip=True)]
        for a in anchors[:40]:
            try:
                url = a.get("href", "")
                if not url.startswith("http"):
                    url = "https://www.preloved.co.uk" + url
                title = a.get_text(strip=True)
                if not title or len(title) < 5 or _is_mini_pc(title):
                    continue
                external_id = "preloved_" + url.rstrip("/").split("/")[-1].split("?")[0]
                # Look for nearby price text
                parent = a.parent
                price_text = ""
                if parent:
                    price_text = parent.get_text(" ", strip=True)
                price = _parse_price(price_text)
                if price <= 0:
                    continue
                listings.append(RawListing(
                    external_id=external_id,
                    title=title,
                    price=price,
                    url=url,
                    location=None,
                    condition="used",
                    description="",
                    image_urls=[],
                    source_name="Preloved",
                ))
            except Exception:
                continue
        return listings

    for item in cards:
        try:
            title_el = (
                item.select_one("h2 a")
                or item.select_one("h3 a")
                or item.select_one(".advert-title a")
                or item.select_one("[class*='title'] a")
                or item.select_one("a[href*='/adverts/']")
                or item.select_one("a[href]")
            )
            price_el = (
                item.select_one(".advert-price")
                or item.select_one("[class*='price']")
                or item.select_one(".price")
                or item.select_one("strong")
            )
            img_el = item.select_one("img")
            loc_el = (
                item.select_one(".advert-location")
                or item.select_one("[class*='location']")
            )

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or len(title) < 5 or _is_mini_pc(title):
                continue

            url = title_el.get("href", "")
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://www.preloved.co.uk" + url

            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = _parse_price(price_text)
            if price <= 0:
                continue

            external_id = "preloved_" + url.rstrip("/").split("/")[-1].split("?")[0]

            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            location = loc_el.get_text(strip=True) if loc_el else None

            listings.append(RawListing(
                external_id=external_id,
                title=title,
                price=price,
                url=url,
                location=location,
                condition="used",
                description="",
                image_urls=[image_url] if image_url else [],
                source_name="Preloved",
            ))
        except Exception:
            continue

    return listings


# ---------------------------------------------------------------------------
# John Pye Auctions — UK's largest general auctioneers, large IT/PC lots
# ---------------------------------------------------------------------------

_JOHN_PYE_TERMS = [
    "desktop pc", "gaming pc", "computer tower",
    "HP EliteDesk", "Dell OptiPlex", "workstation",
    "i7 desktop", "i5 desktop", "gaming computer",
]

async def scrape_john_pye(min_price: float, max_price: float) -> list[RawListing]:
    """
    John Pye Auctions (johnpye.co.uk) — major UK IT liquidation auctioneer.
    Lots are publicly browsable HTML. No login required.
    """
    results: list[RawListing] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in _JOHN_PYE_TERMS[:6]:
            await _delay()
            try:
                resp = await client.get(
                    "https://www.johnpye.co.uk/auctions/",
                    params={"s": term},
                    headers=_headers(),
                )
                if resp.status_code != 200 or len(resp.text) < 1000:
                    print(f"[scraper] John Pye: unexpected {resp.status_code} for {term!r}")
                    continue
                new = _parse_john_pye_html(resp.text, min_price, max_price)
                for l in new:
                    if l.external_id not in seen:
                        seen.add(l.external_id)
                        results.append(l)
                print(f"[scraper] John Pye '{term}': {len(new)} parsed, total {len(results)}")
            except Exception as exc:
                print(f"[scraper] John Pye error for {term!r}: {exc}")

    return results


def _parse_john_pye_html(html: str, min_price: float, max_price: float) -> list[RawListing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    # John Pye lot cards — try multiple known selectors
    cards = (
        soup.select("article.lot-card")
        or soup.select(".lot-card")
        or soup.select("[class*='lot-item']")
        or soup.select(".auction-lot")
        or soup.select("li[class*='lot']")
        or soup.select("article")
    )

    if not cards:
        # Fallback: any link to a /lot/ or /auction/ page
        cards = soup.select("a[href*='/lot/'], a[href*='/auction/']")

    for item in cards:
        try:
            is_link = item.name == "a"

            if is_link:
                url = item.get("href", "")
                title = item.get_text(strip=True)
                price_text = ""
            else:
                link_el = (
                    item.select_one("a[href*='/lot/']")
                    or item.select_one("a[href*='/auction/']")
                    or item.select_one("a[href]")
                )
                title_el = (
                    item.select_one("h2")
                    or item.select_one("h3")
                    or item.select_one("[class*='title']")
                    or link_el
                )
                price_el = (
                    item.select_one("[class*='price']")
                    or item.select_one("[class*='bid']")
                    or item.select_one("strong")
                )

                if not link_el:
                    continue

                url = link_el.get("href", "")
                title = title_el.get_text(strip=True) if title_el else ""
                price_text = price_el.get_text(strip=True) if price_el else ""

            if not url or not title or len(title) < 5:
                continue
            if _is_mini_pc(title):
                continue
            if not url.startswith("http"):
                url = "https://www.johnpye.co.uk" + url

            price = _parse_price(price_text) if price_text else 0.0
            # For auctions, 0 price means bidding hasn't started — include it
            if price > 0 and (price < min_price or price > max_price):
                continue

            external_id = "johnpye_" + url.rstrip("/").split("/")[-1].split("?")[0]

            img_el = item.select_one("img") if not is_link else None
            image_url = ""
            if img_el:
                image_url = img_el.get("src") or img_el.get("data-src") or ""

            listings.append(RawListing(
                external_id=external_id,
                title=title,
                price=price or min_price,  # use min_price as placeholder if no current bid
                url=url,
                location=None,
                condition="used",
                description="",
                image_urls=[image_url] if image_url else [],
                source_name="John Pye",
            ))
        except Exception:
            continue

    return listings


# ---------------------------------------------------------------------------
# Dispatcher — routes to correct adapter based on source config
# ---------------------------------------------------------------------------

# ── Per-platform term budgets ─────────────────────────────────────────────────
# eBay gets every term (robust to volume, fast throttle).
# Bot-sensitive platforms (Gumtree, Facebook, Preloved) get a focused subset:
#   - most effective distress + workstation + broad terms
#   - kept short to reduce block risk and scan time
_GUMTREE_FB_TERMS = [
    # broad sweeps
    "pc tower", "gaming pc", "desktop pc",
    # workstation clearance
    "HP EliteDesk", "Dell OptiPlex", "Lenovo ThinkCentre",
    "HP workstation", "Dell workstation",
    # missing parts
    "gaming pc no gpu", "pc tower no graphics", "pc no hard drive",
    # distress signals
    "pc untested", "pc spares or repair", "pc quick sale",
    "pc need gone", "old pc clearing out",
    # CPU-named
    "i7 tower", "i7 desktop", "ryzen 7 desktop",
    # liquid cooled (often underpriced)
    "pc liquid cooler",
]

_PRELOVED_TERMS = [
    "pc tower", "gaming pc", "desktop pc",
    "HP EliteDesk", "Dell OptiPlex", "Lenovo ThinkCentre",
    "gaming pc no gpu", "pc no hard drive",
    "pc untested", "pc spares or repair",
    "i7 tower", "i7 desktop", "ryzen 7 desktop",
    "office pc tower", "ex office pc",
]

# Auction-focused terms — sorted by most likely to yield cheap deals.
# Results sort ending-soonest so this list turns over every few hours naturally.
_EBAY_AUCTION_TERMS = [
    # ── Job lots & clearance (best value — sellers pricing per-unit to move volume)
    "pc job lot",
    "desktop pcs lot",
    "office computers clearance",
    "it clearance desktop",
    "office pc lot",
    "bulk desktops",
    "ex office pc lot",
    "workstation joblot",
    # ── Untested / fault / incomplete (auction is where these land — BIN sellers avoid them)
    "pc untested",
    "pc spares or repair",
    "gaming pc untested",
    "pc no display",
    "gaming pc faulty",
    "desktop untested",
    # ── Workstations (IT dept auctions)
    "HP EliteDesk",
    "Dell OptiPlex",
    "HP workstation",
    "Lenovo ThinkCentre",
    "Dell Precision tower",
    "HP Z440",
    "HP Z640",
    # ── Broad sweeps
    "gaming pc",
    "desktop pc",
    "pc tower",
    # ── CPU-named (uninformed seller = low reserve)
    "i7 tower",
    "i9 tower",
    "ryzen desktop",
    "xeon tower",
    "i7 desktop",
]


async def fetch_listings(
    source_name: str,
    source_url: str,
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    from app.services.playwright_scraper import (
        scrape_gumtree_playwright,
        scrape_facebook_playwright,
        scrape_preloved_playwright,
        RawListing as PlRawListing,
    )

    def _convert(pl: PlRawListing) -> RawListing:
        return RawListing(
            external_id=pl.external_id,
            title=pl.title,
            price=pl.price,
            url=pl.url,
            location=pl.location,
            condition=pl.condition,
            description=pl.description,
            image_urls=pl.image_urls,
            source_name=pl.source_name,
        )

    name = source_name.lower()

    if "ebay" in name and "auction" in name:
        # eBay auctions — ending soonest, liquidation/clearance focus
        return await scrape_ebay(_EBAY_AUCTION_TERMS, min_price, max_price, auction_mode=True)

    if "ebay" in name:
        # eBay BIN — full 80+ term list, newest listed
        return await scrape_ebay(search_terms, min_price, max_price)

    if "gumtree" in name:
        pl_results = await scrape_gumtree_playwright(_GUMTREE_FB_TERMS, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "facebook" in name or "marketplace" in name:
        pl_results = await scrape_facebook_playwright(_GUMTREE_FB_TERMS, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "preloved" in name:
        pl_results = await scrape_preloved_playwright(_PRELOVED_TERMS, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "john pye" in name or "johnpye" in name:
        return await scrape_john_pye(min_price, max_price)

    if "apex" in name:
        from app.services.playwright_scraper import scrape_apex_playwright, RawListing as PlRawListing
        pl_results = await scrape_apex_playwright(_EBAY_AUCTION_TERMS, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if any(k in name for k in ("bidspotter", "wilsons", "i-bidder", "ibidder", "merkandi")):
        # These auction scrapers are stubs — return empty gracefully
        return []

    print(f"[scraper] No adapter for source {source_name!r}, skipping")
    return []
