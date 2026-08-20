from app.services.browser_pool import managed_playwright
"""
Scraper service — fetches listings from configured data sources.
Each platform has its own adapter. Falls back to HTML scraping when no API.
"""
import asyncio
import base64
import random
import re
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from app.config import get_settings
from app.services.search_telemetry import record_term_result
from app.services.delivery_filters import allow_temu_aliexpress_listing
from app.services.spec_parser import parse_specs
from app.services.proxy import apply_httpx_proxy, playwright_proxy_config
from app.services.playwright_scraper import chromium_available

settings = get_settings()
ua = UserAgent()
_EBAY_TOKEN: str | None = None
_EBAY_TOKEN_EXP_TS: float = 0.0
_EBAY_PLAYWRIGHT_SEM = asyncio.Semaphore(1)
_EBAY_VENDOR_BLOCK_UNTIL_TS: float = 0.0


def _ebay_state_path() -> Path:
    p = Path(settings.ebay_playwright_state_path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _shape_retry_term(term: str) -> str:
    t = str(term or "").strip()
    if not t:
        return t
    replacements = {
        "pc tower": "desktop tower pc",
        "desktop pcs lot": "desktop pc bundle",
        "gaming pc untested": "untested gaming desktop",
        "office pc tower": "office desktop computer",
        "motherboard cpu combo": "cpu motherboard bundle",
    }
    low = t.lower()
    for k, v in replacements.items():
        if k in low:
            return re.sub(re.escape(k), v, t, flags=re.IGNORECASE)
    return t


def _ebay_base_url() -> str:
    env = (settings.ebay_environment or "production").strip().lower()
    if env == "sandbox":
        return "https://api.sandbox.ebay.com"
    return "https://api.ebay.com"

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
    # Laptops — not flippable under our desktop model
    "laptop",
    "notebook",
    "chromebook",
    "macbook",
    "thinkpad",
    "ideapad",
    "elitebook",
    "probook",
    "latitude",
    "inspiron laptop",
    "pavilion laptop",
    "envy laptop",
    "spectre laptop",
    "omen laptop",
    "zenbook",
    "vivobook",
    "aspire laptop",
    "swift laptop",
    "surface laptop",
    "surface pro",
    "surface book",
    # Dell laptop model lines (no "laptop" in title)
    "xps 13",
    "xps 15",
    "xps 17",
    "precision 5570",
    "precision 5580",
    "precision 7570",
    "precision 7670",
    "precision 7770",
    "inspiron 13",
    "inspiron 14",
    "inspiron 15",
    "inspiron 16",
    "vostro 14",
    "vostro 15",
    # HP laptop model lines
    "omen 15",
    "omen 16",
    "omen 17",
    "pavilion 14",
    "pavilion 15",
    "pavilion 16",
    "spectre x360",
    "envy x360",
    "envy 13",
    "envy 14",
    "envy 15",
    "hp 15s",
    "hp 14s",
    # Lenovo laptop lines
    "yoga",          # Yoga = always a laptop/tablet
    "legion 5",
    "legion 7",
    "legion slim",
    "slim 5",
    "slim 7",
    "flex 5",
    "flex 7",
    # ASUS/Acer laptop lines
    "rog zephyrus",
    "rog strix g",
    "tuf gaming a",
    "predator helios",
    "predator triton",
    "nitro 5",
    "nitro an515",
    # All-in-one PCs — soldered components, no upgrade path
    "all-in-one",
    "all in one",
    "aio pc",
    "aio desktop",
    "imac",
    "optiplex aio",
    "eliteone",
    "inspiron aio",
    "pavilion aio",
    "veriton z",
    "esprimo x",
    # Standalone RAM sticks — not PCs
    "server ram",
    "server memory",
    "ecc registered",
    "ecc reg",
    "rdimm",
    "lrdimm",
    "pc4-2",    # JEDEC DDR4 spec prefix (pc4-2133, pc4-2400, etc.)
    "pc4-3",
    "mt/s",
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
    source_confidence: str = "browser_verified"
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
    # Search term that retrieved this listing (for demand score annotation)
    found_via_term: str = ""


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


def _normalise_ebay_condition(raw: str) -> str:
    """Map eBay condition labels (from HTML or API) to our internal strings."""
    t = raw.lower()
    if not t:
        return "used"
    if "new" in t and "not" not in t:
        return "new"
    if "refurb" in t or "renewed" in t or "restored" in t:
        return "refurbished"
    if "open" in t:          # "Open box"
        return "open_box"
    if "for parts" in t or "not working" in t:
        return "for_parts"
    return "used"


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
            continue
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

async def _get_ebay_access_token(client: httpx.AsyncClient) -> str | None:
    """Get/refresh eBay OAuth token for Browse API."""
    global _EBAY_TOKEN, _EBAY_TOKEN_EXP_TS
    now = asyncio.get_event_loop().time()
    if _EBAY_TOKEN and now < _EBAY_TOKEN_EXP_TS - 60:
        return _EBAY_TOKEN

    if not settings.ebay_app_id or not settings.ebay_client_secret:
        return None

    ebay_base = _ebay_base_url()
    scope_base = "https://api.ebay.com/oauth/api_scope"
    creds = f"{settings.ebay_app_id}:{settings.ebay_client_secret}".encode("utf-8")
    basic = base64.b64encode(creds).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    # Client Credentials flow only supports base scope for public data access
    # buy.browse scope requires Authorization Code Grant (user login)
    data = {"grant_type": "client_credentials", "scope": scope_base}
    resp = await client.post(f"{ebay_base}/identity/v1/oauth2/token", data=data, headers=headers)
    if resp.status_code != 200:
        return None
    payload = resp.json()
    token = payload.get("access_token")
    expires_in = int(payload.get("expires_in", 3600))
    if not token:
        return None
    _EBAY_TOKEN = token
    _EBAY_TOKEN_EXP_TS = now + expires_in
    return _EBAY_TOKEN


_EBAY_SPEC_KEYS = {
    # Maps eBay aspect name (lowercase) → our description key
    "processor": "Processor",
    "gpu": "GPU",
    "graphics processing unit": "GPU",
    "graphics card": "GPU",
    "ram size": "RAM",
    "memory ram": "RAM",
    "storage capacity": "Storage",
    "hard drive capacity": "Storage",
    "ssd capacity": "Storage",
    "operating system": "OS",
    "form factor": "FormFactor",
    "type": "Type",
    "model": "Model",
}


async def enrich_gem_with_specifics(ebay_external_id: str) -> dict[str, str]:
    """
    Fetch eBay Item Specifics for a single gem/amazing_gem listing.
    Called post-classification so we only spend API quota on worthwhile items.
    Returns a dict of spec key → value (empty dict on any failure).
    """
    item_id = ebay_external_id.removeprefix("ebay_")
    if not item_id or not item_id.isdigit():
        return {}
    client_kwargs = apply_httpx_proxy({"timeout": 15, "follow_redirects": True})
    async with httpx.AsyncClient(**client_kwargs) as client:
        token = await _get_ebay_access_token(client)
        if not token:
            return {}
        specifics = await _fetch_ebay_item_specifics(client, token, [item_id])
        return specifics.get(item_id, {})  # type: ignore[return-value]


async def _fetch_ebay_item_specifics(
    client: httpx.AsyncClient,
    token: str,
    item_ids: list[str],
) -> dict[str, str]:
    """
    Fetch Item Specifics (localizedAspects) for a batch of eBay item IDs.
    Returns {item_id: "Processor: i5-9400F\nGPU: RTX 3060\nRAM: 32GB\n..."}.
    Failures are silently ignored — title parsing is the fallback.
    """
    base = _ebay_base_url()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    results: dict[str, str] = {}

    # Limit concurrency to avoid bursting the Browse API rate limit.
    # 30 simultaneous getItem calls per search term was causing 429s.
    sem = asyncio.Semaphore(4)

    async def _fetch_one(iid: str) -> None:
        async with sem:
            try:
                resp = await client.get(
                    f"{base}/buy/browse/v1/item/v1|{iid}|0",
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 429:
                    await asyncio.sleep(2)
                    return
                if resp.status_code != 200:
                    return
                data = resp.json()
                aspects = data.get("localizedAspects") or []
                lines = []
                for aspect in aspects:
                    name_raw = (aspect.get("name") or "").lower().strip()
                    value = (aspect.get("value") or "").strip()
                    if not value:
                        continue
                    mapped = _EBAY_SPEC_KEYS.get(name_raw)
                    if mapped:
                        lines.append(f"{mapped}: {value}")
                if lines:
                    results[iid] = "\n".join(lines)
            except Exception:
                pass

    await asyncio.gather(*[_fetch_one(iid) for iid in item_ids])
    return results


def _parse_ebay_api_items(items: list[dict], term: str, source_name: str, specifics: dict[str, str] | None = None) -> list[RawListing]:
    out: list[RawListing] = []
    for it in items or []:
        title = str(it.get("title") or "").strip()
        if not title or _is_mini_pc(title):
            continue
        item_id = str(it.get("itemId") or "")
        item_web_url = str(it.get("itemWebUrl") or "")
        price_obj = (it.get("price") or {})
        price = _parse_price(str(price_obj.get("value") or "0"))
        if price <= 0:
            continue
        image = (it.get("image") or {}).get("imageUrl") or ""
        condition = _normalise_ebay_condition(it.get("condition") or "")
        loc = (it.get("itemLocation") or {}).get("country")
        buying = (it.get("buyingOptions") or [])
        listing_type = "auction" if "AUCTION" in buying else "buy_it_now"
        if item_id:
            external_id = f"ebay_{item_id}"
        else:
            external_id = f"ebay_{_extract_ebay_id(item_web_url)}"
        # Use eBay Item Specifics if available, otherwise fall back to title parsing
        spec_text = (specifics or {}).get(item_id, "")
        description = f"{spec_text}\nterm:{term}" if spec_text else f"term:{term}"
        out.append(
            RawListing(
                external_id=external_id,
                title=title,
                price=price,
                url=item_web_url,
                location=loc,
                condition=condition,
                description=description,
                image_urls=[image] if image else [],
                source_name=source_name,
                source_confidence="official_api",
                listing_type=listing_type,
                found_via_term=term,
            )
        )
    return out


async def _scrape_ebay_api_term(
    client: httpx.AsyncClient,
    token: str,
    term: str,
    min_price: float,
    max_price: float,
    auction_mode: bool,
    is_component_term: bool,
    condition_code: str | None = None,
    worldwide: bool = False,
) -> list[RawListing] | None:
    """
    Returns:
      list[RawListing]  — API call succeeded (may be empty list = genuine 0 results)
      None              — API call failed (non-200, auth error, network error)
                         Caller may choose to fall back to HTML scraping.
    """
    endpoint = f"{_ebay_base_url()}/buy/browse/v1/item_summary/search"
    buying = "AUCTION" if auction_mode else "FIXED_PRICE"
    hi = int(max_price) if max_price > 0 else 5000
    filters = [
        f"price:[{int(min_price)}..{hi}]",
        "priceCurrency:GBP",
        f"buyingOptions:{{{buying}}}",
    ]
    if not worldwide:
        filters.append("itemLocationCountry:GB")
    if condition_code:
        if condition_code == "3000":
            filters.append("conditions:{USED}")
        elif condition_code == "1000":
            filters.append("conditions:{NEW}")
    elif not is_component_term:
        filters.append("conditions:{USED}")
    params = {
        "q": term,
        "limit": "60",
        "sort": "endingSoonest" if auction_mode else "newlyListed",
        "filter": ",".join(filters),
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
    }
    resp = await client.get(endpoint, params=params, headers=headers)
    if resp.status_code != 200:
        # None signals the caller that the API call itself failed
        return None
    payload = resp.json()
    items = payload.get("itemSummaries") or []
    if not items:
        return []

    # Item specifics (getItem calls) are deferred until after classification —
    # only gem/amazing_gem listings will request them, keeping API usage minimal.
    return _parse_ebay_api_items(items, term, "eBay UK Auctions" if auction_mode else "eBay UK")


async def _scrape_ebay_playwright_term(
    term: str,
    min_price: float,
    max_price: float,
    auction_mode: bool = False,
) -> tuple[list[RawListing], bool]:
    """Browser fallback for eBay when HTTP path is blocked or returns empty."""
    if not chromium_available():
        return [], False

    term_q = term.replace(" ", "+")
    if auction_mode:
        urls = [
            (
                "https://www.ebay.co.uk/sch/i.html"
                f"?_nkw={term_q}"
                "&_sacat=179&LH_Auction=1&LH_ItemCondition=3000"
                f"&_udlo={int(min_price)}&_udhi={int(max_price)}"
                "&LH_PrefLoc=1&_sop=1&_ipg=60"
            ),
            (
                "https://www.ebay.co.uk/sch/i.html"
                f"?_nkw={term_q}"
                "&_sacat=0&LH_Auction=1"
                f"&_udlo={int(min_price)}&_udhi={max(int(max_price), 2000)}"
                "&_sop=1&_ipg=120"
            ),
        ]
    else:
        urls = [
            (
                "https://www.ebay.co.uk/sch/i.html"
                f"?_nkw={term_q}"
                "&_sacat=179&LH_BIN=1&LH_ItemCondition=3000"
                f"&_udlo={int(min_price)}&_udhi={int(max_price)}"
                "&LH_PrefLoc=1&_sop=10&_ipg=60"
            ),
            (
                "https://www.ebay.co.uk/sch/i.html"
                f"?_nkw={term_q}"
                "&_sacat=0&LH_BIN=1"
                f"&_udlo={int(min_price)}&_udhi={max(int(max_price), 2000)}"
                "&_sop=10&_ipg=120"
            ),
        ]

    stealth_js = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""
    html = ""
    title = ""
    blocked = False
    listings: list[RawListing] = []
    async with _EBAY_PLAYWRIGHT_SEM:
        async with managed_playwright() as p:
            cdp_url = str(getattr(settings, "browser_cdp_url", "") or "").strip()
            browser = None
            attached_cdp = False
            if cdp_url:
                try:
                    browser = await p.chromium.connect_over_cdp(cdp_url)
                    attached_cdp = True
                    print(f"[scraper] playwright.cdp_attached ebay cdp_url={cdp_url}")
                except Exception:
                    browser = None
            if browser is None:
                browser = await p.chromium.launch(
                    headless=os.getenv("EBAY_HEADLESS", "1").lower() not in {"0", "false", "no"},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-infobars",
                        "--window-size=1366,768",
                        "--lang=en-GB",
                    ],
                    proxy=playwright_proxy_config(),
                )
            state_path = _ebay_state_path()
            context_kwargs = {
                "user_agent": ua.random,
                "locale": "en-GB",
                "viewport": {"width": 1366, "height": 768},
            }
            if state_path.exists():
                context_kwargs["storage_state"] = str(state_path)
            if attached_cdp and browser.contexts:
                context = browser.contexts[0]
            else:
                context = await browser.new_context(**context_kwargs)
            await context.add_init_script(stealth_js)
            page = await context.new_page()
            try:
                for url in urls:
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(1500)
                        # Avoid page.evaluate crashes seen under heavy anti-bot pages.
                        await page.mouse.wheel(0, 900)
                        await page.wait_for_timeout(900)
                        html = await page.content()
                        title = (await page.title()) or ""
                    except Exception:
                        continue
                    blocked_markers = (
                        "access denied",
                        "errors.edgesuite.net",
                        "akamai",
                        "forbidden",
                        "error page | ebay",
                        "something went wrong on our end",
                        "robot",
                        "captcha",
                    )
                    blocked = any(m in (title + " " + html).lower() for m in blocked_markers)
                    if blocked:
                        print(f"[scraper] eBay playwright blocked term={term!r} title={title[:80]!r}")
                        continue
                    listings = _parse_ebay_html(html, term) if html else []
                    if not listings:
                        card_markers = html.count("s-card") + html.count("s-item")
                        print(
                            f"[scraper] eBay playwright empty term={term!r} "
                            f"title={title[:80]!r} html_len={len(html)} markers={card_markers}"
                        )
                    if listings:
                        break
            finally:
                if not attached_cdp:
                    try:
                        await context.storage_state(path=str(state_path))
                    except Exception as exc:
                        print(f"[scraper] unable to persist eBay playwright state: {exc}")
                    await context.close()
                    await browser.close()
                else:
                    await page.close()
    return listings, blocked


def _is_ebay_blocked(status_code: int, body: str) -> bool:
    if status_code in (401, 403, 429):
        return True
    probe = (body or "").lower()
    blocked_markers = (
        "access denied",
        "you don't have permission",
        "errors.edgesuite.net",
        "akamai",
        "bot",
        "forbidden",
        "error page | ebay",
        "something went wrong on our end",
        "reference-id",
    )
    return any(m in probe for m in blocked_markers)


# ---------------------------------------------------------------------------
# eBay adapter — uses Browse API when key available, else HTML scraping
# ---------------------------------------------------------------------------

async def scrape_ebay(
    search_terms: list[str],
    min_price: float,
    max_price: float,
    auction_mode: bool = False,
    condition_code: str | None = None,
    worldwide: bool = False,
) -> list[RawListing]:
    """
    Searches eBay UK with sequential term execution (per-vendor ordering).
    auction_mode=True → returns ending-soonest auctions (LH_Auction=1, _sop=1).
    auction_mode=False → returns Buy It Now listings (LH_BIN=1, _sop=10 newest).
    Deduplicates within run. Per-term jitter/delays are still applied.
    """
    results: list[RawListing] = []
    seen_ids: set[str] = set()
    source_label = "eBay UK Auctions" if auction_mode else "eBay UK"
    global _EBAY_VENDOR_BLOCK_UNTIL_TS
    component_markers = (
        "motherboard",
        "cpu",
        "bundle",
        "ram",
        "ssd",
        "psu",
        "graphics card",
        "gpu",
    )

    blocked_terms: list[str] = []
    client_kwargs = apply_httpx_proxy({"timeout": 30, "follow_redirects": True})

    async with httpx.AsyncClient(**client_kwargs) as client:
        if _EBAY_VENDOR_BLOCK_UNTIL_TS > time.monotonic():
            wait_s = int(_EBAY_VENDOR_BLOCK_UNTIL_TS - time.monotonic())
            for term in search_terms:
                record_term_result(term=term, found=0, new=0, error=f"ebay_retry_later_circuit_breaker_{wait_s}s", source_name=source_label)
            return []

        async def _fetch_term(term: str) -> tuple[str, list[RawListing], bool, int, str | None]:
            await asyncio.sleep(random.uniform(settings.ebay_delay_min_seconds, settings.ebay_delay_max_seconds))
            try:
                    is_component_term = any(m in term.lower() for m in component_markers)
                    sacat = "0" if is_component_term else "179"
                    prefer_api = bool(
                        settings.ebay_use_api
                        or (settings.ebay_app_id and settings.ebay_client_secret)
                    )
                    token = await _get_ebay_access_token(client) if prefer_api else None
                    if token:
                        api_listings = await _scrape_ebay_api_term(
                            client=client,
                            token=token,
                            term=term,
                            min_price=min_price,
                            max_price=max_price,
                            auction_mode=auction_mode,
                            is_component_term=is_component_term,
                            condition_code=condition_code,
                            worldwide=worldwide,
                        )
                        if api_listings is not None:
                            # API call succeeded — authoritative result, never fall back to HTML/Playwright
                            if auction_mode:
                                for l in api_listings:
                                    l.source_name = "eBay UK Auctions"
                                    l.listing_type = "auction"
                            return term, api_listings, False, 200, None
                        # api_listings is None → API call failed (non-200/auth error)
                        # Fall through to HTML scraping as last resort — no Playwright

                    # ── HTML scraping path (no API token, or API returned non-200) ──
                    # No Playwright fallback here: Playwright for eBay violates ToS and
                    # generates browser processes. API is the authoritative path.
                    params = {"_nkw": term, "_sacat": "0", "_ipg": "120"}
                    new_listings: list[RawListing] = []
                    blocked = False
                    last_status = 0

                    resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=_headers())
                    last_status = resp.status_code
                    blocked = _is_ebay_blocked(resp.status_code, resp.text)
                    new_listings = _parse_ebay_html(resp.text, term)

                    if auction_mode:
                        for l in new_listings:
                            if l.listing_type != "auction":
                                l.listing_type = "auction"
                            l.source_name = "eBay UK Auctions"
                    return term, new_listings, blocked, last_status, None
            except Exception as exc:
                msg = str(exc)
                low = msg.lower()
                # Intermittent browser/runtime transport faults should be treated like
                # temporary anti-bot blocks so they retry in the same pass instead of
                # surfacing as hard term errors.
                if isinstance(exc, OSError) or "invalid argument" in low or "unknown error -1" in low:
                    return term, [], True, 0, None
                return term, [], False, 0, msg

        consecutive_blocked_terms = 0
        for idx, term in enumerate(search_terms):
            term, new_listings, blocked, last_status, err = await _fetch_term(term)
            if err:
                record_term_result(term=term, error=err, source_name=source_label)
                print(f"[scraper] eBay error for {term!r}: {err}")
                continue

            before = len(results)
            for listing in new_listings:
                if listing.external_id not in seen_ids:
                    seen_ids.add(listing.external_id)
                    results.append(listing)
            added = len(results) - before

            if blocked and not new_listings:
                record_term_result(
                    term=term,
                    found=0,
                    new=0,
                    error=f"ebay_blocked(status={last_status})",
                    source_name=source_label,
                )
                blocked_terms.append(term)
                consecutive_blocked_terms += 1
                # Extra jitter when blocked to reduce repeated bot signatures.
                await asyncio.sleep(random.uniform(8.0, 25.0))
            else:
                record_term_result(term=term, found=len(new_listings), new=added, source_name=source_label)
                consecutive_blocked_terms = 0
            print(f"[scraper] eBay '{term}': {len(new_listings)} found, {added} new (total {len(results)})")

            if consecutive_blocked_terms >= max(2, int(settings.ebay_block_circuit_breaker_threshold)):
                cooldown_s = max(60, int(settings.ebay_block_circuit_breaker_cooldown_minutes) * 60)
                _EBAY_VENDOR_BLOCK_UNTIL_TS = time.monotonic() + cooldown_s
                # Mark remaining terms as retry-later for this pass.
                remaining = search_terms[idx + 1:]
                for rt in remaining:
                    record_term_result(term=rt, found=0, new=0, error=f"ebay_retry_later_circuit_breaker_{cooldown_s}s", source_name=source_label)
                break

        second_pass = False
        if blocked_terms and not second_pass:
            second_pass = True
            await asyncio.sleep(settings.ebay_block_cooldown_seconds)
            queue = list(dict.fromkeys(blocked_terms))
            blocked_terms.clear()
            while queue:
                term = queue.pop(0)
                retry_term = _shape_retry_term(term)
                await asyncio.sleep(random.uniform(settings.ebay_delay_min_seconds, settings.ebay_delay_max_seconds))
                try:
                    is_component_term = any(m in retry_term.lower() for m in component_markers)
                    # Retry via API first — same rule as primary pass
                    retry_token = await _get_ebay_access_token(client) if (settings.ebay_use_api or settings.ebay_app_id) else None
                    if retry_token:
                        new_listings = await _scrape_ebay_api_term(
                            client=client, token=retry_token, term=retry_term,
                            min_price=min_price, max_price=max_price,
                            auction_mode=auction_mode, is_component_term=is_component_term,
                        ) or []
                        blocked = False
                    else:
                        params = {"_nkw": retry_term, "_sacat": "0", "_ipg": "120"}
                        resp = await client.get("https://www.ebay.co.uk/sch/i.html", params=params, headers=_headers())
                        new_listings = _parse_ebay_html(resp.text, term)
                        blocked = _is_ebay_blocked(resp.status_code, resp.text)
                    before = len(results)
                    for listing in new_listings:
                        if listing.external_id not in seen_ids:
                            seen_ids.add(listing.external_id)
                            results.append(listing)
                    added = len(results) - before
                    if blocked and not new_listings:
                        record_term_result(term=term, found=0, new=0, error=f"ebay_blocked_retry(status={resp.status_code})", source_name=source_label)
                    else:
                        record_term_result(term=term, found=len(new_listings), new=added, source_name=source_label)
                    print(f"[scraper] eBay retry '{term}': {len(new_listings)} found, {added} new (total {len(results)})")
                except Exception as exc:
                    record_term_result(term=term, error=f"ebay_retry_error:{exc}", source_name=source_label)
                    print(f"[scraper] eBay retry error for {term!r}: {exc}")
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
            # Condition — eBay renders this in SECONDARY_INFO or the subtitle span
            cond_el = (
                item.select_one("span.SECONDARY_INFO")
                or item.select_one(".s-item__subtitle span")
                or item.select_one("[class*='s-item__condition']")
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
                # Skip non-content images
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
                        continue
                # Extract positive % e.g. "99.8% positive"
                pct_m = re.search(r"([\d.]+)%", raw_seller)
                if pct_m:
                    try:
                        seller_feedback_pct = float(pct_m.group(1))
                    except ValueError:
                        continue

            # eBay Shop indicator — seller URL contains /str/ or a shop icon exists
            shop_link = item.select_one("a[href*='/str/']") or item.select_one("[class*='store']")
            if shop_link:
                seller_has_shop = True

            seller_type = classify_seller(seller_name, seller_feedback_count, title, seller_has_shop)

            raw_cond = cond_el.get_text(strip=True) if cond_el else ""
            condition = _normalise_ebay_condition(raw_cond)

            listings.append(RawListing(
                external_id=f"ebay_{external_id}",
                title=title,
                price=price,
                url=url,
                location=location,
                condition=condition,
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
                found_via_term=term,
            ))
        except Exception:
            continue
    return listings


# Mobile CPU suffixes: Intel H/HK/HX/HQ, U, P, Y — AMD H/HS/HX, U
# These always indicate a laptop — desktop CPUs never carry these suffixes.
_MOBILE_CPU_RE = re.compile(
    r'\bi[3579]-\d{4,5}[HUPY][HKXQS]?\b'  # Intel: i7-12700H, i5-1135G7-style handled below
    r'|\bi[3579]-\d{4}G\d\b'               # Intel Iris Xe: i5-1135G7
    r'|\bcore\s+ultra\s+[579]\s+\d{3}[HU]\b'  # Core Ultra H/U
    r'|\bryzen\s+[3579]\s+\d{4}[HU]S?\b',  # AMD: Ryzen 7 6800H, 5600U, 6600HS
    re.IGNORECASE,
)

def _is_mini_pc(title: str) -> bool:
    """Return True if the listing is a mini PC, NUC, laptop, or AIO (skip it)."""
    t = title.lower()
    if any(kw in t for kw in _MINI_PC_EXCLUDE):
        return True
    # Detect laptops by mobile CPU model number in the title (e.g. i7-12700H)
    if _MOBILE_CPU_RE.search(title):
        return True
    return False


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    return float(m.group(0)) if m else 0.0


def _parse_marketplace_price(text: str) -> float:
    """Temu/AliExpress card text (title + price + promo copy all concatenated
    by BeautifulSoup's get_text join) is unsafe for _parse_price: titles are
    full of digits (model numbers, capacities — "RTX3060", "12G", "8GB") that
    get_text() joins BEFORE the real price, so a plain "first digit run"
    search grabs the spec number instead of the price. These sites also
    render each price character in its own DOM node, so the joined text has
    stray spaces inside the number itself (e.g. "87 . 39"). Anchoring the
    match to the currency symbol and stripping internal whitespace fixes
    both problems at once."""
    m = re.search(r"[£￡]\s*([\d,]+(?:\s*\.\s*\d+)?)", text)
    if not m:
        return 0.0
    digits = re.sub(r"\s+", "", m.group(1)).replace(",", "")
    try:
        return float(digits)
    except ValueError:
        return 0.0


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
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 30, "follow_redirects": True})) as client:
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
                results.extend(_parse_gumtree_html(resp.text, term))
            except Exception as exc:
                print(f"[scraper] Gumtree error for {term!r}: {exc}")
    return results


def _parse_gumtree_html(html: str, term: str = "") -> list[RawListing]:
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
                    found_via_term=term,
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
                found_via_term=term,
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
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 30, "follow_redirects": True})) as client:
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

                listings = _parse_preloved_html(resp.text, term)
                added = 0
                for l in listings:
                    if l.external_id not in seen:
                        seen.add(l.external_id)
                        results.append(l)
                        added += 1
                record_term_result(term=term, found=len(listings), new=added, source_name="Preloved")
                print(f"[scraper] Preloved '{term}': {len(listings)} parsed, {added} new (total {len(results)})")
            except Exception as exc:
                record_term_result(term=term, error=str(exc), source_name="Preloved")
                print(f"[scraper] Preloved error for {term!r}: {exc}")

    return results


def _parse_preloved_html(html: str, term: str = "") -> list[RawListing]:
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
                    found_via_term=term,
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
                found_via_term=term,
            ))
        except Exception:
            continue

    return listings


# ---------------------------------------------------------------------------
# John Pye Auctions — UK's largest general auctioneers, large IT/PC lots
# ---------------------------------------------------------------------------

_JOHN_PYE_TERMS = [
    "desktop pc", "gaming pc", "computer tower", "pc build",
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

    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 30, "follow_redirects": True})) as client:
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
                before = len(results)
                for l in new:
                    if l.external_id not in seen:
                        seen.add(l.external_id)
                        results.append(l)
                record_term_result(term=term, found=len(new), new=len(results) - before, source_name="John Pye")
                print(f"[scraper] John Pye '{term}': {len(new)} parsed, total {len(results)}")
            except Exception as exc:
                record_term_result(term=term, error=str(exc), source_name="John Pye")
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
                price=price or min_price,  # use min_price when no current bid is visible
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
    "pc tower", "gaming pc", "desktop pc", "pc build",
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
    # component lanes (build-from-parts)
    "motherboard bundle", "motherboard lga1700", "motherboard am4",
    "cpu bundle", "intel i7 cpu", "ryzen 7 cpu",
    "motherboard cpu combo",
    "graphics card", "rtx 3060", "gtx 1660",
    "ddr4 ram", "ddr5 ram", "nvme ssd", "power supply psu",
    "pc case atx", "mid tower case",
    # AM5 sweet-spot bundles (high-priority 2026 targets)
    "7700x b650", "7700 motherboard bundle", "am5 bundle", "ryzen bundle",
    "ddr5 bundle", "b650 tomahawk", "proart am5", "7900 bundle",
    "ryzen 7700", "ryzen 7700x", "ryzen 9700x", "ryzen 7900",
    "asus tuf b650", "gigabyte aorus elite b650", "msi gaming plus b650",
]

_PRELOVED_TERMS = [
    "pc tower", "gaming pc", "desktop pc", "pc build",
    "HP EliteDesk", "Dell OptiPlex", "Lenovo ThinkCentre",
    "gaming pc no gpu", "pc no hard drive",
    "pc untested", "pc spares or repair",
    "i7 tower", "i7 desktop", "ryzen 7 desktop",
    "office pc tower", "ex office pc",
    # component lanes
    "motherboard", "cpu", "motherboard cpu combo", "graphics card", "ddr4 ram", "ddr5 ram",
    "nvme ssd", "psu", "pc case",
    # AM5 combo strategy
    "7700x b650", "am5 bundle", "ryzen bundle", "ddr5 bundle",
    "b650 tomahawk", "proart am5", "7900 bundle",
]

# Auction-focused terms — sorted by most likely to yield cheap deals.
# Results sort ending-soonest so this list turns over every few hours naturally.
# Terms for auction platforms (Wilsons, i-bidder, BidSpotter, Apex)
_AUCTION_TERMS = [
    "desktop pc",
    "gaming pc",
    "computer tower",
    "pc build",
    "HP EliteDesk",
    "Dell OptiPlex",
    "workstation",
    "Lenovo ThinkCentre",
    "gaming computer",
    "i7 desktop",
    "i5 desktop",
    "office pc",
    "refurbished pc",
    # components and enclosures
    "motherboard",
    "cpu bundle",
    "motherboard cpu combo",
    "graphics card",
    "ddr4 ram",
    "nvme ssd",
    "power supply",
    "pc case",
    # AM5 bundle watchlist
    "7700x b650",
    "am5 bundle",
    "ryzen bundle",
    "ddr5 bundle",
    "b650 tomahawk",
    "proart am5",
    "7900 bundle",
]

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
    "pc build",
    # ── CPU-named (uninformed seller = low reserve)
    "i7 tower",
    "i9 tower",
    "ryzen desktop",
    "xeon tower",
    "i7 desktop",
    # ── Individual components and cases ─────────────────────────────────────
    "motherboard bundle",
    "motherboard cpu combo",
    "lga1700 motherboard",
    "am4 motherboard",
    "intel i7 cpu",
    "ryzen 7 cpu",
    "rtx 3060",
    "gtx 1660",
    "ddr4 ram lot",
    "ddr5 ram lot",
    "nvme ssd",
    "pc power supply",
    "atx pc case",
    # ── AM5 combo and board targets ─────────────────────────────────────────
    "7700x b650",
    "7700 motherboard bundle",
    "am5 bundle",
    "ryzen bundle",
    "ddr5 bundle",
    "b650 tomahawk",
    "proart am5",
    "7900 bundle",
    "ryzen 7700",
    "ryzen 7700x",
    "ryzen 9700x",
    "ryzen 7900",
    "asus tuf b650",
    "gigabyte aorus elite b650",
    "msi gaming plus b650",
]

_REQUIRED_CPU_TERMS = [
    "AMD Ryzen 7 7800X3D",
    "Ryzen 9 7900",
    "Ryzen 9 7900X",
]

_EBAY_PRIORITY_PATTERNS = [
    "motherboard cpu combo",
    "motherboard bundle",
    "cpu motherboard bundle",
    "pc build",
    "pc base unit",
    "desktop pc",
    "pc tower",
    "gaming pc",
]


def _prioritize_terms(base_terms: list[str], required_terms: list[str]) -> list[str]:
    """Place required terms first while preserving order and deduping case-insensitively."""
    seen: set[str] = set()
    merged: list[str] = []
    for term in required_terms + base_terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def _prioritize_ebay_flip_terms(terms: list[str]) -> list[str]:
    """Prioritize combo/base-build generic terms first for eBay runs."""
    cleaned = [t.strip() for t in terms if str(t).strip()]
    seen: set[str] = set()
    out: list[str] = []

    # 1) Explicit required CPU terms first.
    for t in _REQUIRED_CPU_TERMS:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)

    # 2) High-priority generic combo/base-build patterns.
    for p in _EBAY_PRIORITY_PATTERNS:
        for t in cleaned:
            k = t.lower()
            if k in seen:
                continue
            if p in k:
                seen.add(k)
                out.append(t)

    # 3) Everything else in original order.
    for t in cleaned:
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


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
        scrape_wilsons_playwright,
        scrape_ibidder_playwright,
        scrape_bidspotter_playwright,
        scrape_lots_co_uk_playwright,
        scrape_the_saleroom_playwright,
        RawListing as PlRawListing,
    )
    from app.services.auction_scrapers import (
        scrape_apex as scrape_apex_http,
        scrape_wholesale_clearance,
        scrape_merkandi,
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
            listing_type=getattr(pl, "listing_type", "classified"),
        )

    def _convert_auction_lot(lot) -> RawListing:
        imgs = [lot.image_url] if getattr(lot, "image_url", None) else []
        return RawListing(
            external_id=lot.external_id,
            title=lot.title,
            price=lot.current_bid,
            url=lot.url,
            location=lot.location,
            condition=lot.condition,
            description=lot.description or "",
            image_urls=imgs,
            source_name=lot.source_name or source_name,
            listing_type="auction",
            listing_ends_at=getattr(lot, "ends_at", None),
        )

    name = source_name.lower()
    input_terms = [t for t in (search_terms or []) if str(t).strip()]
    prioritized_input_terms = _prioritize_terms(input_terms, _REQUIRED_CPU_TERMS)
    prioritized_ebay_auction_terms = prioritized_input_terms or _prioritize_terms(_EBAY_AUCTION_TERMS, _REQUIRED_CPU_TERMS)
    prioritized_gumtree_fb_terms = prioritized_input_terms or _prioritize_terms(_GUMTREE_FB_TERMS, _REQUIRED_CPU_TERMS)
    prioritized_preloved_terms = prioritized_input_terms or _prioritize_terms(_PRELOVED_TERMS, _REQUIRED_CPU_TERMS)
    prioritized_auction_terms = prioritized_input_terms or _prioritize_terms(_AUCTION_TERMS, _REQUIRED_CPU_TERMS)

    if "ebay" in name and "auction" in name:
        return await scrape_ebay(_prioritize_ebay_flip_terms(prioritized_ebay_auction_terms), min_price, max_price, auction_mode=True)

    if "ebay" in name:
        return await scrape_ebay(_prioritize_ebay_flip_terms(search_terms), min_price, max_price)

    if "gumtree" in name:
        pl_results = await scrape_gumtree_playwright(prioritized_gumtree_fb_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "facebook" in name or "marketplace" in name:
        pl_results = await scrape_facebook_playwright(prioritized_gumtree_fb_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "preloved" in name:
        pl_results = await scrape_preloved_playwright(prioritized_preloved_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "john pye" in name or "johnpye" in name:
        return await scrape_john_pye(min_price, max_price)

    if "apex" in name:
        from app.services.playwright_scraper import scrape_apex_playwright
        pl_results = await scrape_apex_playwright(prioritized_ebay_auction_terms, min_price, max_price)
        if pl_results:
            return [_convert(r) for r in pl_results]
        # Fallback path: lightweight HTTP scraper when Playwright is unavailable/blocked.
        lots = await scrape_apex_http(prioritized_ebay_auction_terms, min_price=min_price, max_price=max_price)
        return [_convert_auction_lot(l) for l in lots]

    if "wilsons" in name:
        pl_results = await scrape_wilsons_playwright(prioritized_auction_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "i-bidder" in name or "ibidder" in name:
        pl_results = await scrape_ibidder_playwright(prioritized_auction_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "bidspotter" in name:
        pl_results = await scrape_bidspotter_playwright(prioritized_auction_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "lots.co.uk" in name or name == "lots":
        pl_results = await scrape_lots_co_uk_playwright(prioritized_auction_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "saleroom" in name:
        pl_results = await scrape_the_saleroom_playwright(prioritized_auction_terms, min_price, max_price)
        return [_convert(r) for r in pl_results]

    if "amazon" in name:
        return await _scrape_generic_marketplace_listings(
            source_name="Amazon",
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            build_url=lambda term: f"https://www.amazon.co.uk/s?k={term.replace(' ', '+')}&i=computers",
            item_selector='[data-component-type="s-search-result"]',
            link_selector='h2 a, a.a-link-normal[href*="/dp/"]',
            title_selector='h2 span, h2',
        )

    if "temu" in name:
        http_rows = await _scrape_temu_http(
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
        )
        if http_rows:
            return http_rows
        return await _scrape_generic_marketplace_listings(
            source_name="Temu",
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            build_url=lambda term: f"https://www.temu.com/search_result.html?search_key={term.replace(' ', '+')}&search_method=user",
            item_selector='a[href*="/goods"]',
            link_selector='a[href*="/goods"]',
            title_selector='h3, h4, p, span',
        )

    if "aliexpress" in name:
        http_rows = await _scrape_aliexpress_http(
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
        )
        if http_rows:
            return http_rows
        return await _scrape_generic_marketplace_listings(
            source_name="AliExpress",
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            build_url=lambda term: f"https://www.aliexpress.com/wholesale?SearchText={term.replace(' ', '+')}&g=y&SortType=price_asc",
            item_selector='a[href*="/item/"]',
            link_selector='a[href*="/item/"]',
            title_selector='h1, h2, h3, h4, p, span',
        )

    if "alibaba" in name:
        http_rows = await _scrape_alibaba_http(
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
        )
        if http_rows:
            return http_rows
        return await _scrape_generic_marketplace_listings(
            source_name="Alibaba",
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            build_url=lambda term: f"https://www.alibaba.com/trade/search?SearchText={term.replace(' ', '+')}",
            item_selector='a[href*="/product-detail/"], a[href*="/x/"]',
            link_selector='a[href*="/product-detail/"], a[href*="/x/"]',
            title_selector='h1, h2, h3, h4, p, span',
        )

    if "bargainhardware" in name or "bargain hardware" in name:
        from app.services.playwright_scraper import scrape_bargainhardware_playwright
        return await scrape_bargainhardware_playwright(
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
        )

    if "vinted" in name:
        from app.scrapers.vinted_scraper import fetch_vinted_listings
        raw_dicts = await fetch_vinted_listings(
            search_terms=search_terms or None,
            min_price=min_price,
            max_price=max_price,
        )
        rows = []
        # Track per-term counts for the sourcing telemetry table
        term_counts: dict[str, int] = {}
        for d in raw_dicts:
            rows.append(RawListing(
                external_id=d["external_id"],
                title=d["title"],
                price=d["price"],
                url=d["url"],
                location=d.get("location"),
                condition=d.get("condition"),
                description=d.get("description", ""),
                image_urls=d.get("image_urls", []),
                source_name="Vinted",
                listing_type=d.get("listing_type", "buy_it_now"),
                seller_name=d.get("seller_name"),
                found_via_term=d.get("found_via_term", ""),
            ))
            t = d.get("found_via_term") or "vinted"
            term_counts[t] = term_counts.get(t, 0) + 1
        for term, count in term_counts.items():
            record_term_result(term=term, found=count, new=count, source_name="Vinted")
        return rows

    if "cherrytree" in name:
        return await _scrape_generic_marketplace_listings(
            source_name="CherryTree",
            search_terms=search_terms[:20],
            min_price=min_price,
            max_price=max_price,
            build_url=lambda term: f"https://www.cherrytreeinc.com/search?q={term.replace(' ', '+')}",
            item_selector='a[href]',
            link_selector='a[href]',
            title_selector='h1, h2, h3, h4, p, span',
        )

    if any(k in name for k in ("merkandi", "wholesale clearance")):
        # Explicit adapter calls for observability — logs reasons and keeps pipeline healthy.
        if "merkandi" in name:
            await scrape_merkandi(prioritized_auction_terms, min_price=min_price, max_price=max_price)
        else:
            await scrape_wholesale_clearance(prioritized_auction_terms, min_price=min_price, max_price=max_price)
        return []

    print(f"[scraper] No adapter for source {source_name!r}, skipping")
    return []


async def _scrape_generic_marketplace_listings(
    *,
    source_name: str,
    search_terms: list[str],
    min_price: float,
    max_price: float,
    build_url,
    item_selector: str,
    link_selector: str,
    title_selector: str,
) -> list[RawListing]:

    results: list[RawListing] = []
    seen: set[str] = set()

    def _with_page(url: str, page_num: int) -> str:
        if page_num <= 1:
            return url
        joiner = "&" if "?" in url else "?"
        src = source_name.lower()
        if "amazon" in src:
            return f"{url}{joiner}page={page_num}"
        if "aliexpress" in src:
            return f"{url}{joiner}page={page_num}"
        if "alibaba" in src:
            return f"{url}{joiner}page={page_num}"
        if "bargainhardware" in src:
            # Magento pagination key.
            return f"{url}{joiner}p={page_num}"
        if "temu" in src:
            return f"{url}{joiner}page={page_num}"
        if "cherrytree" in src:
            return f"{url}{joiner}page={page_num}"
        return f"{url}{joiner}page={page_num}"

    max_pages = max(1, int(getattr(settings, "marketplace_max_pages_per_term", 2) or 2))

    async with managed_playwright() as p:
        cdp_url = str(getattr(settings, "browser_cdp_url", "") or "").strip()
        browser = None
        attached_cdp = False
        if cdp_url:
            try:
                browser = await p.chromium.connect_over_cdp(cdp_url)
                attached_cdp = True
                print(f"[scraper] playwright.cdp_attached generic source={source_name} cdp_url={cdp_url}")
            except Exception:
                browser = None
        if browser is None:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                proxy=playwright_proxy_config(),
            )
        if attached_cdp and browser.contexts:
            ctx = browser.contexts[0]
        else:
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-GB",
                timezone_id="Europe/London",
            )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

        page = await ctx.new_page()
        for term in search_terms:
            try:
                added = 0
                filtered_delivery = 0
                challenge_emitted = False
                for page_num in range(1, max_pages + 1):
                    url = _with_page(build_url(term), page_num)
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Explicit anti-bot/login detection so telemetry is truthful.
                    title_l = (await page.title() or "").lower()
                    body_l = (await page.content() or "").lower()[:120000]
                    if source_name.lower() == "temu" and (
                        "login" in title_l
                        or "/login" in (page.url or "").lower()
                        or "kwcdn.com/upload-static/assets/chl/js" in body_l
                        or "challenge" in body_l
                    ):
                        record_term_result(
                            term=term,
                            found=0,
                            new=0,
                            error="login_required",
                            source_name=source_name,
                        )
                        challenge_emitted = True
                        added = 0
                        break
                    if source_name.lower() in {"aliexpress", "alibaba"} and (
                        "captcha interception" in title_l
                        or "captcha" in body_l
                        or "_____tmd_____" in body_l
                        or "/punish" in body_l
                        or "awsc/captcha" in body_l
                    ):
                        record_term_result(
                            term=term,
                            found=0,
                            new=0,
                            error="captcha_required",
                            source_name=source_name,
                        )
                        challenge_emitted = True
                        added = 0
                        break
                    try:
                        await page.wait_for_selector(item_selector, timeout=10000)
                    except Exception:
                        continue
                    await asyncio.sleep(1.0)
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(0.8)

                    raw = await page.evaluate(
                        """({itemSelector, linkSelector, titleSelector}) => {
                        const out = [];
                        const seen = new Set();
                        const nodes = document.querySelectorAll(itemSelector);
                        const priceRe = /([£$€])\\s*([\\d,]+\\.?\\d*)/;
                        for (const node of nodes) {
                            try {
                                const linkEl = node.matches('a') ? node : node.querySelector(linkSelector);
                                if (!linkEl) continue;
                                let href = linkEl.href || linkEl.getAttribute('href') || '';
                                if (!href) continue;
                                if (href.startsWith('/')) href = location.origin + href;
                                const key = href.split('?')[0];
                                if (seen.has(key)) continue;
                                seen.add(key);

                                const titleEl = node.querySelector(titleSelector) || linkEl;
                                const title = (titleEl?.textContent || node.textContent || '').replace(/\\s+/g, ' ').trim();
                                if (!title || title.length < 6) continue;

                                let price = 0;
                                const scope = node.matches('a') ? (node.parentElement || node) : node;
                                for (const el of scope.querySelectorAll('*')) {
                                    const txt = (el.textContent || '').trim();
                                    const m = priceRe.exec(txt);
                                    if (m) {
                                        price = parseFloat((m[2] || '').replace(/,/g, ''));
                                        if (Number.isFinite(price) && price > 0) break;
                                    }
                                }
                                if (!price || !Number.isFinite(price)) continue;
                                const imgEl = node.querySelector('img');
                                const image = imgEl ? (imgEl.src || imgEl.getAttribute('src') || '') : '';
                                const contextText = (scope?.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 1200);
                                out.push({title, href, price, image, contextText});
                            } catch (_) {}
                        }
                        return out;
                    }""",
                        {"itemSelector": item_selector, "linkSelector": link_selector, "titleSelector": title_selector},
                    )

                    page_added = 0
                    for item in raw or []:
                        try:
                            price = float(item.get("price") or 0)
                        except Exception:
                            continue
                        if price < float(min_price) or price > float(max_price):
                            continue
                        if source_name.lower() in {"temu", "aliexpress"}:
                            if not allow_temu_aliexpress_listing(item.get("contextText") or ""):
                                filtered_delivery += 1
                                continue
                        href = str(item.get("href") or "")
                        external_id = f"{source_name.lower()}_{abs(hash(href))}"
                        if external_id in seen:
                            continue
                        seen.add(external_id)
                        results.append(
                            RawListing(
                                external_id=external_id,
                                title=str(item.get("title") or "")[:240],
                                price=price,
                                url=href,
                                location=None,
                                condition="unknown",
                                description="",
                                image_urls=[item.get("image")] if item.get("image") else [],
                                source_name=source_name,
                                listing_type="classified",
                            )
                        )
                        added += 1
                        page_added += 1
                    # Keep sequential pagination, but stop early when no new rows are parsed.
                    if page_added == 0:
                        break
                # Avoid duplicate telemetry row if this term already emitted a challenge-required status.
                if challenge_emitted:
                    pass
                elif added > 0:
                    record_term_result(term=term, found=added, new=added, source_name=source_name)
                else:
                    if filtered_delivery > 0 and source_name.lower() in {"temu", "aliexpress"}:
                        record_term_result(
                            term=term,
                            found=0,
                            new=0,
                            error="delivery_filtered_non_uk_or_gt5d",
                            source_name=source_name,
                        )
                    else:
                        record_term_result(term=term, found=0, new=0, source_name=source_name)
            except Exception as exc:
                record_term_result(term=term, error=str(exc), source_name=source_name)
        if attached_cdp:
            await page.close()
        else:
            await browser.close()
    return results


async def _scrape_bargainhardware_http(
    *,
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    results: list[RawListing] = []
    seen: set[str] = set()
    headers = _headers()
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True})) as client:
        for term in search_terms:
            added = 0
            try:
                url = f"https://www.bargainhardware.eu/de/catalogsearch/result/?q={term.replace(' ', '+')}"
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    record_term_result(term=term, found=0, new=0, error=f"http_status_{resp.status_code}", source_name="BargainHardware")
                    continue
                html = resp.text
                soup = BeautifulSoup(html, "lxml")
                anchors = soup.select("a[href]")
                for a in anchors:
                    href = str(a.get("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = "https://www.bargainhardware.eu" + href
                    if "/catalogsearch/" in href:
                        continue
                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 6:
                        continue
                    scope = a.find_parent(["li", "div", "article"]) or a
                    scope_text = scope.get_text(" ", strip=True)
                    if not allow_temu_aliexpress_listing(scope_text):
                        continue
                    price = _parse_price(scope_text)
                    if price <= 0:
                        continue
                    if price < float(min_price) or price > float(max_price):
                        continue
                    external_id = f"bargainhardware_{abs(hash(href))}"
                    if external_id in seen:
                        continue
                    seen.add(external_id)
                    results.append(
                        RawListing(
                            external_id=external_id,
                            title=title[:240],
                            price=price,
                            url=href,
                            location=None,
                            condition="unknown",
                            description="",
                            image_urls=[],
                            source_name="BargainHardware",
                            listing_type="classified",
                        )
                    )
                    added += 1
                record_term_result(term=term, found=added, new=added, source_name="BargainHardware")
            except Exception as exc:
                record_term_result(term=term, found=0, new=0, error=str(exc), source_name="BargainHardware")
    return results


async def _scrape_temu_http(
    *,
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    results: list[RawListing] = []
    seen: set[str] = set()
    headers = _headers()
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True})) as client:
        for term in search_terms:
            added = 0
            try:
                url = f"https://www.temu.com/search_result.html?search_key={term.replace(' ', '+')}&search_method=user"
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    record_term_result(term=term, found=0, new=0, error=f"http_status_{resp.status_code}", source_name="Temu")
                    continue
                body_l = resp.text.lower()
                if "kwcdn.com/upload-static/assets/chl/js" in body_l or "challenge" in body_l or "/login" in body_l:
                    record_term_result(term=term, found=0, new=0, error="login_required", source_name="Temu")
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                anchors = soup.select("a[href*='/goods'], a[href*='_goods']")
                for a in anchors:
                    href = str(a.get("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = "https://www.temu.com" + href
                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 6:
                        continue
                    scope = a.find_parent(["li", "div", "article"]) or a
                    scope_text = scope.get_text(" ", strip=True)
                    if not allow_temu_aliexpress_listing(scope_text):
                        continue
                    price = _parse_marketplace_price(scope.get_text(" ", strip=True))
                    if price <= 0 or price < float(min_price) or price > float(max_price):
                        continue
                    external_id = f"temu_{abs(hash(href))}"
                    if external_id in seen:
                        continue
                    seen.add(external_id)
                    results.append(RawListing(external_id=external_id, title=title[:240], price=price, url=href, location=None, condition="unknown", description="", image_urls=[], source_name="Temu", listing_type="classified"))
                    added += 1
                record_term_result(term=term, found=added, new=added, source_name="Temu")
            except Exception as exc:
                record_term_result(term=term, found=0, new=0, error=str(exc), source_name="Temu")
    return results


async def _scrape_aliexpress_http(
    *,
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    results: list[RawListing] = []
    seen: set[str] = set()
    headers = _headers()
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True})) as client:
        for term in search_terms:
            added = 0
            try:
                url = f"https://www.aliexpress.com/wholesale?SearchText={term.replace(' ', '+')}&g=y&SortType=price_asc"
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    record_term_result(term=term, found=0, new=0, error=f"http_status_{resp.status_code}", source_name="AliExpress")
                    continue
                body_l = resp.text.lower()
                if "captcha" in body_l or "_____tmd_____" in body_l or "/punish" in body_l:
                    record_term_result(term=term, found=0, new=0, error="captcha_required", source_name="AliExpress")
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                anchors = soup.select("a[href*='/item/'], a[href*='/i/']")
                for a in anchors:
                    href = str(a.get("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = "https://www.aliexpress.com" + href
                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 6:
                        continue
                    scope = a.find_parent(["li", "div", "article"]) or a
                    price = _parse_marketplace_price(scope.get_text(" ", strip=True))
                    if price <= 0 or price < float(min_price) or price > float(max_price):
                        continue
                    external_id = f"aliexpress_{abs(hash(href))}"
                    if external_id in seen:
                        continue
                    seen.add(external_id)
                    results.append(RawListing(external_id=external_id, title=title[:240], price=price, url=href, location=None, condition="unknown", description="", image_urls=[], source_name="AliExpress", listing_type="classified"))
                    added += 1
                record_term_result(term=term, found=added, new=added, source_name="AliExpress")
            except Exception as exc:
                record_term_result(term=term, found=0, new=0, error=str(exc), source_name="AliExpress")
    return results


async def _scrape_alibaba_http(
    *,
    search_terms: list[str],
    min_price: float,
    max_price: float,
) -> list[RawListing]:
    results: list[RawListing] = []
    seen: set[str] = set()
    headers = _headers()
    async with httpx.AsyncClient(**apply_httpx_proxy({"timeout": 25, "follow_redirects": True})) as client:
        for term in search_terms:
            added = 0
            try:
                url = f"https://www.alibaba.com/trade/search?SearchText={term.replace(' ', '+')}"
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    record_term_result(term=term, found=0, new=0, error=f"http_status_{resp.status_code}", source_name="Alibaba")
                    continue
                body_l = resp.text.lower()
                if "captcha" in body_l or "awsc/captcha" in body_l or "punish-component" in body_l:
                    record_term_result(term=term, found=0, new=0, error="captcha_required", source_name="Alibaba")
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                anchors = soup.select("a[href*='/product-detail/'], a[href*='/x/'], a[href*='offer']")
                for a in anchors:
                    href = str(a.get("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = "https://www.alibaba.com" + href
                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 6:
                        continue
                    scope = a.find_parent(["li", "div", "article"]) or a
                    price = _parse_marketplace_price(scope.get_text(" ", strip=True))
                    if price <= 0 or price < float(min_price) or price > float(max_price):
                        continue
                    external_id = f"alibaba_{abs(hash(href))}"
                    if external_id in seen:
                        continue
                    seen.add(external_id)
                    results.append(RawListing(external_id=external_id, title=title[:240], price=price, url=href, location=None, condition="unknown", description="", image_urls=[], source_name="Alibaba", listing_type="classified"))
                    added += 1
                record_term_result(term=term, found=added, new=added, source_name="Alibaba")
            except Exception as exc:
                record_term_result(term=term, found=0, new=0, error=str(exc), source_name="Alibaba")
    return results


# ---------------------------------------------------------------------------
# Overclockers UK — PC Cases (logged-in session via httpx)
# ---------------------------------------------------------------------------
# Overclockers blocks unauthorized requests heavily. This scraper mimics eBay:
# it uses httpx with headers, relies on your browser session cookies if
# authentication is needed, and parses HTML with BeautifulSoup.

async def scrape_overclockers_cases(min_price: float = 10.0, max_price: float = 500.0) -> list[RawListing]:
    """
    Overclockers UK — PC Cases by Brand category.
    Scrapes the entire cases section using httpx (like eBay).
    Falls back gracefully if blocked.
    """
    results: list[RawListing] = []
    seen: set[str] = set()
    url = "https://www.overclockers.co.uk/cases-and-modding/pc-cases/pc-cases-by-brand"

    client_kwargs = apply_httpx_proxy({"timeout": 30, "follow_redirects": True})

    async with httpx.AsyncClient(**client_kwargs) as client:
        try:
            await _delay()
            resp = await client.get(url, headers=_headers())

            if resp.status_code != 200:
                record_term_result(term="catalogue", found=0, new=0, error=f"http_{resp.status_code}", source_name="Overclockers")
                return []

            if len(resp.text) < 1000:
                record_term_result(term="catalogue", found=0, new=0, error="response_too_short", source_name="Overclockers")
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # Find all product links (Overclockers uses a-tags with /product/ URLs)
            product_links = soup.select('a[href*="/product/"]')

            for link in product_links:
                try:
                    # Extract URL
                    href = link.get("href", "").strip()
                    if not href.startswith("http"):
                        if href.startswith("/"):
                            href = "https://www.overclockers.co.uk" + href
                        else:
                            continue

                    # Deduplicate
                    key = href.split("?")[0]
                    if key in seen:
                        continue
                    seen.add(key)

                    # Find the product card container
                    card = link.find_parent("li") or link.find_parent("div", class_=re.compile("product", re.I)) or link

                    # Extract title
                    title = link.get_text(strip=True) or ""
                    if not title:
                        title_el = card.find("h2") or card.find("h3") or card.find("a", string=True)
                        title = title_el.get_text(strip=True) if title_el else ""

                    title = title.strip()[:250]
                    if not title or len(title) < 5:
                        continue

                    # Extract price (look for £ symbol)
                    price_text = card.get_text()
                    price_match = re.search(r"£\s*([\d,]+\.?\d*)", price_text)
                    if not price_match:
                        continue

                    try:
                        price = float(price_match.group(1).replace(",", ""))
                    except ValueError:
                        continue

                    if price < min_price or price > max_price:
                        continue

                    # Extract image if available
                    image_url = ""
                    img = card.find("img")
                    if img:
                        image_url = img.get("src") or img.get("data-src") or ""

                    # Create listing
                    external_id = f"overclockers_{abs(hash(key))}"
                    results.append(RawListing(
                        external_id=external_id,
                        title=title,
                        price=price,
                        url=href,
                        location="UK",
                        condition="new",
                        description="",
                        image_urls=[image_url] if image_url else [],
                        source_name="Overclockers",
                        listing_type="classified",
                    ))
                except Exception:
                    continue

            record_term_result(term="catalogue", found=len(results), new=len(results), source_name="Overclockers")

        except Exception as exc:
            record_term_result(term="catalogue", found=0, new=0, error=str(exc), source_name="Overclockers")

    return results
