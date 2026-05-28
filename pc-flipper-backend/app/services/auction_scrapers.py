from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import structlog

from app.config import get_settings
from app.services.proxy import apply_httpx_proxy

_ua = UserAgent()
log = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class AuctionLot:
    external_id: str
    title: str
    current_bid: float
    buy_now_price: Optional[float] = None
    url: str = ""
    location: Optional[str] = None
    condition: Optional[str] = None
    description: str = ""
    image_url: str = ""
    ends_at: Optional[datetime] = None
    lot_number: Optional[str] = None
    source_name: str = ""
    is_joblot: bool = False
    quantity: int = 1


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_price(text: str | None) -> float:
    if not text:
        return 0.0
    m = re.search(r"(\d[\d,]*\.?\d*)", text.replace("\xa0", " "))
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return 0.0


def _to_datetime(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    rel = re.search(r"(\d+)\s*(day|hour|minute|hr|min)", text, re.I)
    if rel:
        n = int(rel.group(1))
        u = rel.group(2).lower()
        if "day" in u:
            return _now_utc() + timedelta(days=n)
        if "hour" in u or "hr" in u:
            return _now_utc() + timedelta(hours=n)
        return _now_utc() + timedelta(minutes=n)
    return None


def _is_pc_relevant(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in (
        "pc", "desktop", "tower", "workstation", "computer",
        "i3", "i5", "i7", "i9", "ryzen", "xeon",
        "optiplex", "elitedesk", "thinkcentre", "z4", "z6",
        "gpu", "graphics", "nvidia", "radeon", "rtx", "gtx", "rx ",
        "ram", "ssd", "nvme", "motherboard", "bundle", "job lot",
    ))


def _lot_from_fields(
    source_name: str,
    external_id: str,
    title: str,
    price: float,
    url: str,
    location: str | None = None,
    image_url: str | None = None,
    ends_at: datetime | None = None,
    lot_number: str | None = None,
) -> AuctionLot:
    return AuctionLot(
        external_id=external_id,
        title=title,
        current_bid=price,
        url=url,
        location=location,
        image_url=image_url or "",
        ends_at=ends_at,
        lot_number=lot_number,
        source_name=source_name,
        is_joblot=any(k in title.lower() for k in ("lot", "bundle", "bulk", "pallet", "qty", "x ")),
    )


WILSONS_SEARCH_URL = "https://www.wilsonsauctions.com/api/lots/search"


async def scrape_wilsons(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {"User-Agent": _ua.random, "Accept": "application/json,text/plain,*/*"}
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:6]:
            for page_idx in range(0, 3):
                params = {
                    "q": term,
                    "minEstimate": max(0, int(min_price)),
                    "maxEstimate": int(max_price) if max_price > 0 else 999999,
                    "pageSize": 30,
                    "pageIndex": page_idx,
                }
                try:
                    r = await client.get(WILSONS_SEARCH_URL, params=params)
                    if r.status_code != 200:
                        break
                    payload = r.json()
                    candidates = []
                    if isinstance(payload, list):
                        candidates = payload
                    elif isinstance(payload, dict):
                        for key in ("items", "results", "lots", "data"):
                            if isinstance(payload.get(key), list):
                                candidates = payload[key]
                                break
                    if not candidates:
                        break

                    found = 0
                    for item in candidates:
                        title = str(item.get("title") or item.get("name") or "").strip()
                        if not title or not _is_pc_relevant(title):
                            continue
                        lot_id = str(item.get("id") or item.get("lotId") or item.get("slug") or "").strip()
                        lot_url = str(item.get("url") or item.get("detailUrl") or "").strip()
                        if lot_url and not lot_url.startswith("http"):
                            lot_url = urljoin("https://www.wilsonsauctions.com", lot_url)
                        if not lot_id and lot_url:
                            lot_id = lot_url.rstrip("/").split("/")[-1]
                        if not lot_id:
                            lot_id = re.sub(r"\W+", "_", title.lower())[:64]
                        external_id = f"wilsons_{lot_id}"
                        if external_id in seen:
                            continue
                        price_text = str(item.get("currentBid") or item.get("estimate") or item.get("price") or "")
                        price = _parse_price(price_text)
                        if price < min_price:
                            continue
                        if max_price > 0 and price > max_price:
                            continue
                        seen.add(external_id)
                        results.append(
                            _lot_from_fields(
                                "Wilsons Auctions",
                                external_id,
                                title,
                                price,
                                lot_url,
                                location=str(item.get("location") or "").strip() or None,
                                image_url=str(item.get("image") or item.get("imageUrl") or "") or None,
                                ends_at=_to_datetime(str(item.get("endTime") or item.get("endsAt") or "") or None),
                                lot_number=str(item.get("lotNumber") or "").strip() or None,
                            )
                        )
                        found += 1

                    if found < 3:
                        break
                    await asyncio.sleep(0.6)
                except Exception as exc:
                    log.warning("auction_scraper.wilsons.error", term=term, page=page_idx, error=str(exc))
                    break
    log.info("auction_scraper.wilsons.done", total=len(results))
    return results


IBIDDER_SEARCH_URL = "https://www.i-bidder.com/en-gb/search"


async def scrape_ibidder(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {"User-Agent": _ua.random, "Accept-Language": "en-GB,en;q=0.9"}
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:6]:
            for page in range(1, 3):
                try:
                    resp = await client.get(IBIDDER_SEARCH_URL, params={"q": term, "page": page})
                    if resp.status_code != 200 or len(resp.text) < 400:
                        break
                    soup = BeautifulSoup(resp.text, "lxml")
                    cards = soup.select("article, .lot-card, .search-result, .auction-card")
                    if not cards:
                        cards = soup.select("a[href*='lot'], a[href*='catalogue']")
                    found = 0
                    for card in cards:
                        link_el = card if card.name == "a" else card.select_one("a[href]")
                        if not link_el:
                            continue
                        href = (link_el.get("href") or "").strip()
                        if not href:
                            continue
                        if not href.startswith("http"):
                            href = urljoin("https://www.i-bidder.com", href)
                        title_el = card.select_one("h2, h3, .title") or link_el
                        title = title_el.get_text(" ", strip=True)
                        if not title or not _is_pc_relevant(title):
                            continue
                        lot_id = href.rstrip("/").split("/")[-1].split("?")[0]
                        external_id = f"ibidder_{lot_id}"
                        if external_id in seen:
                            continue
                        text_block = card.get_text(" ", strip=True)
                        price = _parse_price(text_block)
                        if price < min_price:
                            continue
                        if max_price > 0 and price > max_price:
                            continue
                        seen.add(external_id)
                        results.append(
                            _lot_from_fields(
                                "i-bidder",
                                external_id,
                                title,
                                price,
                                href,
                                ends_at=_to_datetime(text_block),
                            )
                        )
                        found += 1
                    if found < 3:
                        break
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    log.warning("auction_scraper.ibidder.error", term=term, page=page, error=str(exc))
                    break
    log.info("auction_scraper.ibidder.done", total=len(results))
    return results


BIDSPOTTER_API_URL = "https://www.bidspotter.co.uk/en-gb/search-results"


async def scrape_bidspotter(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {"User-Agent": _ua.random, "Accept-Language": "en-GB,en;q=0.9"}
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:6]:
            for page in range(1, 3):
                try:
                    resp = await client.get(BIDSPOTTER_API_URL, params={"keywords": term, "page": page})
                    if resp.status_code != 200 or len(resp.text) < 400:
                        break
                    soup = BeautifulSoup(resp.text, "lxml")
                    cards = soup.select("article, .search-item, .lot-card, .card")
                    if not cards:
                        cards = soup.select("a[href*='lot'], a[href*='auction']")
                    found = 0
                    for card in cards:
                        link_el = card if card.name == "a" else card.select_one("a[href]")
                        if not link_el:
                            continue
                        href = (link_el.get("href") or "").strip()
                        if not href:
                            continue
                        if not href.startswith("http"):
                            href = urljoin("https://www.bidspotter.co.uk", href)
                        title_el = card.select_one("h2, h3, .title") or link_el
                        title = title_el.get_text(" ", strip=True)
                        if not title or not _is_pc_relevant(title):
                            continue
                        lot_id = href.rstrip("/").split("/")[-1].split("?")[0]
                        external_id = f"bidspotter_{lot_id}"
                        if external_id in seen:
                            continue
                        block = card.get_text(" ", strip=True)
                        price = _parse_price(block)
                        if price < min_price:
                            continue
                        if max_price > 0 and price > max_price:
                            continue
                        seen.add(external_id)
                        results.append(_lot_from_fields("BidSpotter", external_id, title, price, href, ends_at=_to_datetime(block)))
                        found += 1
                    if found < 3:
                        break
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    log.warning("auction_scraper.bidspotter.error", term=term, page=page, error=str(exc))
                    break
    log.info("auction_scraper.bidspotter.done", total=len(results))
    return results


APEX_SEARCH_URL = "https://www.apexauctions.co.uk/search"


async def scrape_apex(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {
        "User-Agent": _ua.random,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.apexauctions.co.uk/",
    }

    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:8]:
            for page in range(1, 4):
                try:
                    resp = await client.get(APEX_SEARCH_URL, params={"q": term, "page": page, "sort": "date_asc"})
                    if resp.status_code != 200 or len(resp.text) < 500:
                        break

                    soup = BeautifulSoup(resp.text, "lxml")
                    cards = (
                        soup.select("div.lot-item")
                        or soup.select("div.lot-card")
                        or soup.select("[class*='lot-item']")
                        or soup.select("article.lot")
                        or soup.select(".auction-lot")
                    )
                    if not cards:
                        cards = soup.select("a[href*='/lot/'], a[href*='/lots/']")

                    if not cards:
                        break

                    found_on_page = 0
                    for card in cards:
                        try:
                            title_el = card.select_one("h3, h2, .lot-title, .lot-name, [class*='title']") or (
                                card if card.name == "a" else card.select_one("a")
                            )
                            title = (title_el.get_text(strip=True) if title_el else "").strip()
                            if not title or len(title) < 5 or not _is_pc_relevant(title):
                                continue

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

                            price_el = card.select_one(".lot-estimate, .estimate, .current-bid, .lot-price, [class*='price'], [class*='bid']")
                            price = _parse_price(price_el.get_text(strip=True) if price_el else "")
                            if price < min_price:
                                continue
                            if price > max_price and max_price > 0:
                                continue

                            img_el = card.select_one("img")
                            img_url = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""
                            if img_url and not img_url.startswith("http"):
                                img_url = "https://www.apexauctions.co.uk" + img_url

                            ends_el = card.select_one("[class*='ends'], [class*='closing'], time, [data-ends], [data-close]")
                            ends_at = _to_datetime((ends_el.get("datetime") if ends_el else None) or (ends_el.get_text(strip=True) if ends_el else None))

                            lot_num_el = card.select_one("[class*='lot-num'], [class*='lot-number']")
                            lot_number = lot_num_el.get_text(strip=True) if lot_num_el else None

                            results.append(
                                _lot_from_fields(
                                    "Apex Auctions",
                                    external_id,
                                    title,
                                    price,
                                    href,
                                    image_url=img_url,
                                    ends_at=ends_at,
                                    lot_number=lot_number,
                                )
                            )
                            found_on_page += 1

                        except Exception as exc:
                            log.debug("apex.card_error", error=str(exc))
                            continue

                    if found_on_page < 5:
                        break

                    await asyncio.sleep(0.8)

                except Exception as exc:
                    log.warning("apex.request_error", term=term, page=page, error=str(exc))
                    break

    log.info("auction_scraper.apex.done", total=len(results))
    return results


WHOLESALE_CLEARANCE_URL = "https://www.wholesaleclearance.co.uk"


async def scrape_wholesale_clearance(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {"User-Agent": _ua.random, "Accept-Language": "en-GB,en;q=0.9"}
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:5]:
            try:
                resp = await client.get(f"{WHOLESALE_CLEARANCE_URL}/", params={"s": term, "post_type": "product"})
                if resp.status_code != 200 or len(resp.text) < 300:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("li.product, .product, article.product")
                for card in cards:
                    link_el = card.select_one("a[href]")
                    if not link_el:
                        continue
                    href = link_el.get("href", "").strip()
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = urljoin(WHOLESALE_CLEARANCE_URL, href)
                    title = (card.select_one("h2, h3, .woocommerce-loop-product__title") or link_el).get_text(" ", strip=True)
                    if not title or not _is_pc_relevant(title):
                        continue
                    lot_id = href.rstrip("/").split("/")[-1]
                    external_id = f"wholesale_{lot_id}"
                    if external_id in seen:
                        continue
                    price = _parse_price((card.select_one(".price") or card).get_text(" ", strip=True))
                    if price and price < min_price:
                        continue
                    if price and max_price > 0 and price > max_price:
                        continue
                    seen.add(external_id)
                    results.append(_lot_from_fields("Wholesale Clearance UK", external_id, title, price, href))
            except Exception as exc:
                log.warning("auction_scraper.wholesale_clearance.error", term=term, error=str(exc))
    log.info("auction_scraper.wholesale_clearance.done", total=len(results))
    return results


MERKANDI_API_URL = "https://merkandi.co.uk/api/v1/offers"


async def scrape_merkandi(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    api_key = kwargs.get("api_key") or settings.merkandi_api_key
    if not api_key:
        log.info("auction_scraper.merkandi.skipped", reason="missing_api_key")
        return []

    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {"User-Agent": _ua.random, "Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:6]:
            try:
                r = await client.get(MERKANDI_API_URL, params={"q": term, "country": "GB", "category": "electronics"})
                if r.status_code != 200:
                    continue
                payload = r.json()
                offers = payload if isinstance(payload, list) else payload.get("offers", []) if isinstance(payload, dict) else []
                for offer in offers:
                    title = str(offer.get("title") or offer.get("name") or "").strip()
                    if not title or not _is_pc_relevant(title):
                        continue
                    offer_id = str(offer.get("id") or offer.get("slug") or "").strip() or re.sub(r"\W+", "_", title)[:48]
                    external_id = f"merkandi_{offer_id}"
                    if external_id in seen:
                        continue
                    price = _parse_price(str(offer.get("price") or ""))
                    if price and price < min_price:
                        continue
                    if price and max_price > 0 and price > max_price:
                        continue
                    url = str(offer.get("url") or "").strip()
                    if url and not url.startswith("http"):
                        url = urljoin("https://merkandi.co.uk", url)
                    seen.add(external_id)
                    results.append(_lot_from_fields("Merkandi", external_id, title, price, url))
            except Exception as exc:
                log.warning("auction_scraper.merkandi.error", term=term, error=str(exc))
    log.info("auction_scraper.merkandi.done", total=len(results))
    return results


JOHN_PYE_SEARCH_URL = "https://www.johnpye.co.uk/search"


async def scrape_john_pye(search_terms: list[str], min_price: float = 0, max_price: float = 500, **kwargs) -> list[AuctionLot]:
    results: list[AuctionLot] = []
    seen: set[str] = set()
    headers = {"User-Agent": _ua.random, "Accept-Language": "en-GB,en;q=0.9"}
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True, "headers": headers})) as client:
        for term in search_terms[:5]:
            try:
                resp = await client.get(JOHN_PYE_SEARCH_URL, params={"q": term})
                if resp.status_code != 200 or len(resp.text) < 250:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("article, .lot, .product, .search-result")
                if not cards:
                    cards = soup.select("a[href*='lot'], a[href*='auction']")
                for card in cards:
                    link_el = card if card.name == "a" else card.select_one("a[href]")
                    if not link_el:
                        continue
                    href = (link_el.get("href") or "").strip()
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = urljoin("https://www.johnpye.co.uk", href)
                    title = (card.select_one("h2, h3, .title") or link_el).get_text(" ", strip=True)
                    if not title or not _is_pc_relevant(title):
                        continue
                    lot_id = href.rstrip("/").split("/")[-1]
                    external_id = f"johnpye_{lot_id}"
                    if external_id in seen:
                        continue
                    price = _parse_price(card.get_text(" ", strip=True))
                    if price and price < min_price:
                        continue
                    if price and max_price > 0 and price > max_price:
                        continue
                    seen.add(external_id)
                    results.append(_lot_from_fields("John Pye", external_id, title, price, href))
            except Exception as exc:
                log.warning("auction_scraper.john_pye.error", term=term, error=str(exc))
    log.info("auction_scraper.john_pye.done", total=len(results))
    return results


AUCTION_SCRAPERS: dict[str, object] = {
    "Wilsons Auctions": scrape_wilsons,
    "i-bidder": scrape_ibidder,
    "BidSpotter": scrape_bidspotter,
    "Apex Auctions": scrape_apex,
    "Wholesale Clearance UK": scrape_wholesale_clearance,
    "Merkandi": scrape_merkandi,
    "John Pye": scrape_john_pye,
}

READY_AUCTION_SCRAPERS: list[str] = [
    "Apex Auctions",
    "Wilsons Auctions",
    "i-bidder",
    "BidSpotter",
    "Wholesale Clearance UK",
    "John Pye",
]

IMPLEMENTATION_PRIORITY = [
    "Apex Auctions",
    "Wilsons Auctions",
    "i-bidder",
    "BidSpotter",
    "Wholesale Clearance UK",
    "Merkandi",
    "John Pye",
]
