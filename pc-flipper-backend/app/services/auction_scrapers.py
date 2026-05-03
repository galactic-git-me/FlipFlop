"""
Auction source adapters — stubs for UK liquidation and auction platforms.

Each adapter follows the same interface as the existing scraper adapters:
  async def scrape(search_terms, min_price, max_price, ...) -> list[RawListing]

Status of each source:
  ✅ READY     — scraper implemented and tested
  🔧 STUB      — framework in place, site-specific parsing not yet implemented
  ❌ BLOCKED   — site blocks scrapers (WAF/Cloudflare); requires authenticated session

All stubs return empty lists rather than raising so the pipeline degrades
gracefully. When a stub is promoted to READY, remove the NotImplemented
comment and implement the parsing logic.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

_ua = UserAgent()

log = structlog.get_logger(__name__)


@dataclass
class AuctionLot:
    """Minimal raw lot from an auction source — richer than RawListing for bids."""
    external_id: str
    title: str
    current_bid: float            # Live current bid or estimate price
    buy_now_price: Optional[float] = None
    url: str = ""
    location: Optional[str] = None
    condition: Optional[str] = None
    description: str = ""
    image_url: str = ""
    ends_at: Optional[datetime] = None   # Auction end datetime (UTC)
    lot_number: Optional[str] = None
    source_name: str = ""
    # Signals for evaluator
    is_joblot: bool = False
    quantity: int = 1


# ── Wilsons Auctions ──────────────────────────────────────────────────────────
# UK's largest independent auction house. Lots include IT clearance and
# liquidation stock. Site uses a React SPA with a JSON search API.
# Status: 🔧 STUB — API endpoint discovered but pagination not finalised.

WILSONS_SEARCH_URL = "https://www.wilsonsauctions.com/api/lots/search"

async def scrape_wilsons(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    Wilsons Auctions scraper stub.

    Wilsons uses a JSON search endpoint at /api/lots/search with parameters:
      q, categoryId, minEstimate, maxEstimate, pageSize, pageIndex

    The endpoint works without auth in testing but may add bot detection.
    TODO: Implement pagination + lot detail parsing.
    """
    log.info("auction_scraper.wilsons.stub", terms=len(search_terms))
    # STUB: return empty until implemented
    return []


# ── i-bidder ─────────────────────────────────────────────────────────────────
# Multi-vendor platform aggregating lots from 1000s of auctioneers.
# Status: 🔧 STUB — HTML parsing skeleton present, captcha blocks volume.

IBIDDER_SEARCH_URL = "https://www.i-bidder.com/en-gb/auction-catalogues/all"

async def scrape_ibidder(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    i-bidder scraper stub.

    i-bidder renders server-side HTML with standard pagination (?q=&page=).
    Lot cards have class .lot-card with .lot-card__title, .lot-card__estimate.
    Site serves CloudFlare challenge on high-frequency requests.
    TODO: Implement with Playwright + stealth mode for CF bypass.
    """
    log.info("auction_scraper.ibidder.stub", terms=len(search_terms))
    return []


# ── BidSpotter ────────────────────────────────────────────────────────────────
# US-origin platform with a substantial UK catalogue (IT/electronics lots).
# Status: 🔧 STUB — JSON API documented but rate-limited.

BIDSPOTTER_API_URL = "https://www.bidspotter.co.uk/en-us/api/search"

async def scrape_bidspotter(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    BidSpotter scraper stub.

    BidSpotter exposes a REST search API (JSON) — key params:
      q, categoryId, country=GB, auctionStatus=active

    Rate limit is ~10 req/min unauthenticated. Authenticated users get 60/min.
    TODO: Implement basic search + lot parsing.
    """
    log.info("auction_scraper.bidspotter.stub", terms=len(search_terms))
    return []


# ── Apex Auctions ─────────────────────────────────────────────────────────────
# UK specialist in IT, telecoms, and electronics liquidation.
# Regular IT clearance lots — exactly what we want.
# Status: 🔧 STUB — HTML-based, no bot protection observed in manual testing.

APEX_SEARCH_URL = "https://www.apexauctions.co.uk/search"

async def scrape_apex(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    Apex Auctions scraper — UK IT/electronics liquidation specialist.
    No bot detection observed. Paginated HTML, httpx + BeautifulSoup.
    Status: ✅ READY
    """
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {
        "User-Agent": _ua.random,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.apexauctions.co.uk/",
    }

    async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
        for term in search_terms[:8]:
            for page in range(1, 4):  # up to 3 pages per term
                try:
                    resp = await client.get(
                        APEX_SEARCH_URL,
                        params={
                            "q": term,
                            "page": page,
                            "sort": "date_asc",  # ending soonest first
                        },
                    )
                    if resp.status_code != 200 or len(resp.text) < 500:
                        break

                    soup = BeautifulSoup(resp.text, "lxml")

                    # Apex lot cards — try common selectors, fall back broadly
                    cards = (
                        soup.select("div.lot-item") or
                        soup.select("div.lot-card") or
                        soup.select("[class*='lot-item']") or
                        soup.select("article.lot") or
                        soup.select(".auction-lot")
                    )
                    if not cards:
                        # Try to extract any lot-style links as a last resort
                        cards = soup.select("a[href*='/lot/'], a[href*='/lots/']")

                    if not cards:
                        log.debug("apex.no_cards", term=term, page=page, url=str(resp.url))
                        break  # No more results on this term

                    found_on_page = 0
                    for card in cards:
                        try:
                            # Title
                            title_el = (
                                card.select_one("h3, h2, .lot-title, .lot-name, [class*='title']") or
                                (card if card.name == "a" else card.select_one("a"))
                            )
                            title = (title_el.get_text(strip=True) if title_el else "").strip()
                            if not title or len(title) < 5:
                                continue

                            # Skip non-PC results
                            t = title.lower()
                            if not any(kw in t for kw in (
                                "pc", "desktop", "tower", "computer", "workstation",
                                "i3", "i5", "i7", "i9", "ryzen", "xeon",
                                "optiplex", "elitedesk", "thinkcentre", "graphics", "gpu",
                                "nvidia", "radeon", "rtx", "gtx", "rx ",
                                "laptop", "monitor", "server", "ram", "ssd", "cpu",
                            )):
                                continue

                            # URL
                            link_el = card.select_one("a[href]") if card.name != "a" else card
                            href = (link_el.get("href") or "") if link_el else ""
                            if href and not href.startswith("http"):
                                href = "https://www.apexauctions.co.uk" + href
                            if not href:
                                continue

                            lot_id = href.rstrip("/").split("/")[-1].split("?")[0] or re.sub(r"\W+", "_", title[:30])
                            external_id = f"apex_{lot_id}"
                            if external_id in seen:
                                continue
                            seen.add(external_id)

                            # Price / estimate
                            price_el = card.select_one(
                                ".lot-estimate, .estimate, .current-bid, "
                                ".lot-price, [class*='price'], [class*='bid']"
                            )
                            price_text = price_el.get_text(strip=True) if price_el else ""
                            price = _parse_apex_price(price_text)
                            if price > max_price and max_price > 0:
                                continue

                            # Image
                            img_el = card.select_one("img")
                            img_url = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""
                            if img_url and not img_url.startswith("http"):
                                img_url = "https://www.apexauctions.co.uk" + img_url

                            # Auction end time
                            ends_el = card.select_one(
                                "[class*='ends'], [class*='closing'], time, [data-ends], [data-close]"
                            )
                            ends_at = _parse_apex_date(ends_el) if ends_el else None

                            # Lot number
                            lot_num_el = card.select_one("[class*='lot-num'], [class*='lot-number']")
                            lot_number = lot_num_el.get_text(strip=True) if lot_num_el else None

                            results.append(AuctionLot(
                                external_id=external_id,
                                title=title,
                                current_bid=price,
                                url=href,
                                image_url=img_url,
                                ends_at=ends_at,
                                lot_number=lot_number,
                                source_name="Apex Auctions",
                                is_joblot=any(kw in t for kw in ("lot", "job lot", "bundle", "bulk", "pallet", "qty", "x ")),
                            ))
                            found_on_page += 1

                        except Exception as exc:
                            log.debug("apex.card_error", error=str(exc))
                            continue

                    log.info("apex.page_done", term=term, page=page, found=found_on_page, total=len(results))

                    # If fewer results than expected, no more pages
                    if found_on_page < 5:
                        break

                    await asyncio.sleep(0.8)  # polite delay

                except Exception as exc:
                    log.warning("apex.request_error", term=term, page=page, error=str(exc))
                    break

    log.info("auction_scraper.apex.done", total=len(results))
    return results


def _parse_apex_price(text: str) -> float:
    """Parse price/estimate strings like '£120', 'Est: £50 - £150', 'Current bid: £75'."""
    # Take the first number found (lower estimate or current bid)
    m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    return float(m.group(0)) if m else 0.0


def _parse_apex_date(el) -> Optional[datetime]:
    """Try to parse a closing date from a BeautifulSoup element."""
    from datetime import timedelta
    # Try datetime attribute first
    dt_str = el.get("datetime") or el.get("data-ends") or el.get("data-close") or el.get_text(strip=True)
    if not dt_str:
        return None
    try:
        # ISO format
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    # Relative: "2 days", "3 hours"
    m = re.search(r"(\d+)\s*(day|hour|minute|hr|min)", dt_str, re.I)
    if m:
        val = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(days=val) if "day" in unit else timedelta(hours=val) if "hour" in unit or "hr" in unit else timedelta(minutes=val)
        return datetime.utcnow() + delta
    return None


# ── Wholesale Clearance UK ────────────────────────────────────────────────────
# B2B wholesale lots — pallets and job lots of tech goods.
# Status: ❌ BLOCKED — requires business account registration for prices.

WHOLESALE_CLEARANCE_URL = "https://www.wholesaleclearance.co.uk"

async def scrape_wholesale_clearance(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    Wholesale Clearance UK stub.

    This site requires a free business account for prices and full listings.
    The registration flow is short and a session cookie is retained for ~7 days.
    TODO: Add Playwright auth flow with stored session cookie.
    Status: BLOCKED until auth flow is implemented.
    """
    log.info("auction_scraper.wholesale_clearance.blocked", reason="requires_auth")
    return []


# ── Merkandi ─────────────────────────────────────────────────────────────────
# European wholesale surplus marketplace with UK section.
# Status: 🔧 STUB — registration required but API documented.

MERKANDI_API_URL = "https://merkandi.co.uk/api/v1/offers"

async def scrape_merkandi(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    Merkandi scraper stub.

    Merkandi provides a REST API with an API key (free tier: 100 req/day).
    Key endpoint: GET /api/v1/offers?q=&category=electronics&country=GB
    TODO: Add API key configuration and implement offer parsing.
    """
    log.info("auction_scraper.merkandi.stub", reason="api_key_required")
    return []


# ── John Pye ──────────────────────────────────────────────────────────────────
# UK's largest online auction and asset recovery platform. High IT lot volume.
# Status: ❌ BLOCKED — Cloudflare Enterprise WAF returns 403 on all bot traffic.

JOHN_PYE_SEARCH_URL = "https://www.johnpye.co.uk/search"

async def scrape_john_pye(
    search_terms: list[str],
    min_price: float = 0,
    max_price: float = 500,
    **kwargs,
) -> list[AuctionLot]:
    """
    John Pye scraper stub.

    John Pye uses Cloudflare Enterprise WAF. All automated HTTP requests
    (including headless browsers without stealth patches) receive a 403 or
    JS challenge response. A residential proxy + Playwright-stealth combination
    might work but adds significant complexity and running cost.
    Status: BLOCKED. Consider manual monitoring or official API partnership.
    """
    log.info("auction_scraper.john_pye.blocked", reason="cloudflare_enterprise_waf")
    return []


# ── Registry — all available auction scrapers ─────────────────────────────────

AUCTION_SCRAPERS: dict[str, object] = {
    "Wilsons Auctions":      scrape_wilsons,
    "i-bidder":              scrape_ibidder,
    "BidSpotter":            scrape_bidspotter,
    "Apex Auctions":         scrape_apex,
    "Wholesale Clearance UK":scrape_wholesale_clearance,
    "Merkandi":              scrape_merkandi,
    "John Pye":              scrape_john_pye,
}

# Scrapers that are ready to use (not blocked, not stub-only)
READY_AUCTION_SCRAPERS: list[str] = ["Apex Auctions"]

# Priority order for implementation
IMPLEMENTATION_PRIORITY = [
    "Apex Auctions",         # No bot detection, IT focus — highest ROI for dev effort
    "BidSpotter",            # JSON API, UK catalogue, rate-limited but workable
    "Wilsons Auctions",      # Largest UK auctioneer, JSON API discovered
    "i-bidder",              # Multi-vendor aggregator, CF challenge manageable
    "Merkandi",              # API key needed — easy once registered
    "Wholesale Clearance UK",# Auth flow needed — moderate effort
    "John Pye",              # Cloudflare Enterprise — highest effort, highest volume
]
