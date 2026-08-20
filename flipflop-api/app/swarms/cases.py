from app.services.browser_pool import managed_playwright
"""
PC Cases Swarm — runs daily.
Searches for PC cases (new and used) across eBay UK, Amazon UK, Temu, AliExpress, and Etsy.
eBay uses plain httpx. Amazon, Temu, AliExpress, and Etsy use a shared Playwright browser context
with stealth mode to bypass bot detection — same approach as the Gumtree/Facebook scrapers.
Cases are a key part of the flip — they transform a bare PC into a themed product.
"""
import re
import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from dataclasses import dataclass
from fake_useragent import UserAgent

from app.database import AsyncSessionLocal
from app.models.part import Part, PartCategory, PartCondition
from app.models.price_history import PriceHistory, PriceHistoryType
from app.models.source_search_term import SourceSearchTerm
from app.services.search_telemetry import record_term_result
from app.services.scraper import scrape_ebay, scrape_overclockers_cases
from app.services.proxy import playwright_proxy_config
from app.services.playwright_scraper import chromium_available
from app.services.delivery_filters import allow_temu_aliexpress_listing
import structlog
from sqlalchemy import select as sa_select

log = structlog.get_logger(__name__)
ua = UserAgent()

# Themes with practical search terms that actually appear on eBay/Amazon/AliExpress
CASE_THEMES = [
    {"theme": "Fish Tank", "terms": ["fish tank pc case"]},
    {"theme": "Airflow RGB", "terms": ["rgb airflow case"]},
    {"theme": "White", "terms": ["white gaming case"]},
    {"theme": "Micro ATX", "terms": ["micro atx case"]},
    {"theme": "O11 Style", "terms": ["Lian Li O11 style case"]},
]
CORE_CASE_TERMS = [
    "atx pc case",
    "mid tower case",
    "micro atx case",
    "airflow rgb case",
    "white gaming case",
]

SOURCES = [
    {"name": "Amazon",       "fn": "amazon"},       # Playwright — new cases with Prime shipping
    {"name": "Overclockers", "fn": "overclockers"}, # Playwright — UK retailer, fast delivery
]
_PLAYWRIGHT_CASE_SOURCES = {"amazon", "overclockers"}

_SOURCE_ALIASES: dict[str, str] = {
    "ebay uk": "eBay",
    "ebay uk auctions": "eBay",
    "amazon uk": "Amazon",
    "bargain hardware": "BargainHardware",
}


def _canonical_source_name(name: str) -> str:
    raw = str(name or "").strip()
    return _SOURCE_ALIASES.get(raw.lower(), raw)


@dataclass
class RawCase:
    name: str
    price: float
    source_site: str
    source_url: str
    image_url: str
    theme: str
    specs: str = "ATX Mid Tower · New"


async def _playbook_extra_themes() -> list[dict]:
    """
    Read active playbooks and return extra case themes derived from their
    component_catalogue.preferred_cases and target_use_case.
    Deduplicates against the global CASE_THEMES search terms.
    """
    from sqlalchemy import select as sa_select
    from app.models.playbook import Playbook

    _use_case_terms: dict[str, list[str]] = {
        "gaming":        ["gaming atx case rgb", "gaming pc case mid tower"],
        "office":        ["slim micro atx case office", "mini tower desktop case"],
        "workstation":   ["full tower workstation case atx", "fractal define case atx"],
        "htpc":          ["mini itx htpc case", "slim htpc case living room"],
        "budget":        ["cheap atx pc case", "budget gaming case atx"],
        "ai_workstation": ["full tower atx case workstation", "server tower case atx"],
    }

    extra: list[dict] = []
    existing_terms: set[str] = {t for td in CASE_THEMES for t in td["terms"]}

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(sa_select(Playbook).where(Playbook.status == "active"))
            for pb in result.scalars().all():
                cat = pb.component_catalogue or {}
                preferred = cat.get("preferred_cases", [])

                # Explicit preferred case names → direct Google Shopping searches
                for case_name in preferred:
                    term = f"{case_name} pc case"
                    if term not in existing_terms:
                        extra.append({"theme": f"{pb.name} Case", "terms": [term]})
                        existing_terms.add(term)

                # Fallback: map target_use_case to generic search terms
                use_case = (pb.target_use_case or "gaming").lower()
                for term in _use_case_terms.get(use_case, []):
                    if term not in existing_terms:
                        extra.append({"theme": f"{pb.name} Case", "terms": [term]})
                        existing_terms.add(term)
    except Exception as exc:
        log.warning("playbook_extra_themes.error", error=str(exc))

    return extra


async def run_cases_swarm(mode: str = "main") -> dict:
    log.info("cases_swarm.start")
    stats = {"found": 0, "upserted": 0, "errors": 0}

    max_terms = max(1, int(os.getenv("CASES_MAX_TERMS", "20")))

    # Build term → theme mapping and per-source term lists.
    # Matches the flip_opportunities pattern: each DB row distributes its term
    # to its configured sources (or all non-CherryTree sources if source_names
    # is empty).  No global source allowlist — that was silently excluding Amazon
    # and limiting terms to [:2] per group.
    term_to_theme: dict[str, str] = {}
    terms_by_vendor: dict[str, list[str]] = {}

    async with AsyncSessionLocal() as db:
        db_rows = (
            await db.execute(
                sa_select(SourceSearchTerm).where(
                    SourceSearchTerm.scope == "cases",
                    SourceSearchTerm.enabled == True,
                )
            )
        ).scalars().all()

    if db_rows:
        for row in db_rows:
            term = str(row.term or "").strip()
            if not term:
                continue
            theme = row.group_name or "Custom"
            term_to_theme.setdefault(term, theme)
            src_names = row.source_names or []
            if src_names:
                for s in src_names:
                    canonical = _canonical_source_name(str(s))
                    terms_by_vendor.setdefault(canonical, []).append(term)
            else:
                for source in SOURCES:
                    if source["fn"] != "cherrytree":
                        terms_by_vendor.setdefault(source["name"], []).append(term)
        # Always blend in playbook-derived themes too
        playbook_themes = await _playbook_extra_themes()
        for theme_def in playbook_themes:
            for t in theme_def["terms"]:
                if t not in term_to_theme:
                    term_to_theme[t] = theme_def["theme"]
                    for source in SOURCES:
                        if source["fn"] != "cherrytree":
                            terms_by_vendor.setdefault(source["name"], []).append(t)
    else:
        # Fallback: use hardcoded CASE_THEMES + CORE_CASE_TERMS + playbook themes
        playbook_themes = await _playbook_extra_themes()
        all_themes = CASE_THEMES + playbook_themes
        for theme_def in all_themes:
            for t in theme_def["terms"]:
                term_to_theme.setdefault(t, theme_def["theme"])
        fallback_terms = list(dict.fromkeys(
            CORE_CASE_TERMS + [t for td in all_themes for t in td["terms"]]
        ))
        for source in SOURCES:
            if source["fn"] != "cherrytree":
                terms_by_vendor[source["name"]] = fallback_terms

    # Dedup per source, apply cap, always give CherryTree its catalogue term
    terms_by_vendor = {k: list(dict.fromkeys(v))[:max_terms] for k, v in terms_by_vendor.items()}
    terms_by_vendor["CherryTree Inc"] = ["catalogue"]

    batch_terms = terms_by_vendor
    log.info(
        "cases.terms.capped",
        max_terms=max_terms,
        vendors=len(batch_terms),
        total_terms=sum(len(v) for v in batch_terms.values()),
    )

    async def _scrape_one(source: dict, theme: str, term: str):
        fn_key = source["fn"].replace("-", "_").replace(" ", "_")
        scrape_fn = globals().get(f"_scrape_{fn_key}")
        if not scrape_fn:
            log.warning("cases.no_scraper", source=source["name"])
            return {"source_name": source["name"], "term": term, "cases": [], "error": None}
        try:
            cases = await scrape_fn(term, theme)
            return {"source_name": source["name"], "term": term, "cases": cases, "error": None}
        except Exception as exc:
            return {"source_name": source["name"], "term": term, "cases": [], "error": str(exc)}

    has_chromium = chromium_available()
    enabled_sources = []
    for s in SOURCES:
        if s["name"] not in batch_terms:
            continue
        if s["fn"] in _PLAYWRIGHT_CASE_SOURCES and not has_chromium:
            continue
        enabled_sources.append(s)
    term_concurrency = max(1, int(os.getenv("CASES_TERM_CONCURRENCY", "10")))
    term_sem = asyncio.Semaphore(term_concurrency)

    async def _scrape_source_seq(source: dict) -> list[dict]:
        rows: list[dict] = []
        # CherryTree should ingest from its cases catalogue once, not per search term.
        if source["fn"] == "cherrytree":
            rows.append(await _scrape_one(source, "Catalogue", "catalogue"))
            return rows
        async def _one(term: str):
            async with term_sem:
                return await _scrape_one(source, term_to_theme.get(term, "Dynamic"), term)
        rows = await asyncio.gather(
            *[_one(term) for term in batch_terms.get(source["name"], [])],
            return_exceptions=False,
        )
        return rows

    scrape_results: list[dict] = []
    if not has_chromium:
        for source in SOURCES:
            if source["name"] not in batch_terms:
                continue
            if source["fn"] not in _PLAYWRIGHT_CASE_SOURCES:
                continue
            for term in batch_terms.get(source["name"], []):
                record_term_result(
                    source_name=f"Cases:{source['name']}",
                    term=term,
                    error="playwright.chromium_not_installed",
                )
    source_batches: list[list[dict]] = await asyncio.gather(
        *[_scrape_source_seq(source) for source in enabled_sources],
        return_exceptions=False,
    )
    for batch in source_batches:
        for r in batch:
            scrape_results.append(r)
            source_name = r.get("source_name") or "unknown"
            term = r.get("term") or ""
            err = r.get("error")
            if err:
                stats["errors"] += 1
                record_term_result(
                    source_name=f"Cases:{source_name}",
                    term=term,
                    error=err,
                )
                log.error("cases.scrape.error", source=source_name, term=term, error=err)
            else:
                cases = r.get("cases") or []
                raw_found = len(cases)
                saved_count = min(24, raw_found)
                record_term_result(
                    source_name=f"Cases:{source_name}",
                    term=term,
                    found=raw_found,
                    new=saved_count,
                )

    async with AsyncSessionLocal() as db:
        for r in scrape_results:
            source_name = r.get("source_name") or "unknown"
            term = r.get("term") or ""
            cases = r.get("cases") or []
            if r.get("error"):
                continue
            try:
                stats["found"] += len(cases)
                for case in cases[:8]:
                    await _upsert_case(db, case)
                    stats["upserted"] += 1
            except Exception as exc:
                stats["errors"] += 1
                record_term_result(
                    source_name=f"Cases:{source_name}",
                    term=term,
                    error=str(exc),
                )
                log.error("cases.upsert.error", source=source_name, term=term, error=str(exc))

        await db.commit()

    log.info("cases_swarm.done", **stats)
    return stats


async def _dynamic_case_themes_from_db() -> tuple[list[dict], set[str]]:
    try:
        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    sa_select(SourceSearchTerm).where(
                        SourceSearchTerm.scope == "cases",
                        SourceSearchTerm.enabled == True,
                    )
                )
            ).scalars().all()
        if not rows:
            return [], set()
        grouped: dict[str, list[str]] = {}
        source_allowlist: set[str] = set()
        for row in rows:
            grouped.setdefault(row.group_name or "Custom", []).append(row.term)
            for s in row.source_names or []:
                source_allowlist.add(_canonical_source_name(str(s)))
        themes = [{"theme": g, "terms": list(dict.fromkeys(ts))} for g, ts in grouped.items() if ts]
        return themes, source_allowlist
    except Exception as exc:
        log.warning("cases.dynamic_terms.error", error=str(exc))
        return [], set()


async def _scrape_ebay(search: str, theme: str) -> list[RawCase]:
    try:
        listings = await scrape_ebay(
            [search],
            min_price=1,
            max_price=350,
            auction_mode=False,
            condition_code="1000",
            worldwide=False,
        )
        # Fallback: if strict "new-only" pass returns nothing, retry without
        # condition filtering to capture mixed-condition listings.
        if not listings:
            listings = await scrape_ebay(
                [search],
                min_price=1,
                max_price=350,
                auction_mode=False,
                condition_code=None,
                worldwide=False,
            )
        return [
            RawCase(
                name=l.title[:200],
                price=l.price,
                source_site="eBay",
                source_url=l.url,
                image_url=l.image_urls[0] if l.image_urls else "",
                theme=theme,
            )
            for l in listings[:24]
        ]
    except Exception as exc:
        log.warning("ebay.cases.error", error=str(exc))
        return []


async def _scrape_gumtree(search: str, theme: str) -> list[RawCase]:
    try:
        from app.services.playwright_scraper import scrape_gumtree_playwright
    except Exception as exc:
        log.warning("gumtree.cases.import_error", error=str(exc))
        return []
    try:
        listings = await scrape_gumtree_playwright([search], min_price=1, max_price=350)
        out: list[RawCase] = []
        for l in listings[:24]:
            out.append(
                RawCase(
                    name=str(l.title or "")[:200],
                    price=float(l.price or 0),
                    source_site="Gumtree",
                    source_url=str(l.url or ""),
                    image_url=(l.image_urls[0] if getattr(l, "image_urls", None) else ""),
                    theme=theme,
                )
            )
        return out
    except Exception as exc:
        log.warning("gumtree.cases.error", term=search, error=str(exc))
        return []


async def _scrape_vinted(search: str, theme: str) -> list[RawCase]:
    try:
        from app.scrapers.vinted_scraper import fetch_vinted_listings
        rows = await fetch_vinted_listings(search_terms=[search], min_price=1, max_price=350)
        out: list[RawCase] = []
        for r in rows[:20]:
            title = str(r.get("title", "")).strip()
            price = float(r.get("price", 0) or 0)
            url = str(r.get("url", ""))
            if not title or price <= 0 or not url:
                continue
            imgs = r.get("image_urls") or []
            out.append(RawCase(
                name=title[:200],
                price=price,
                source_site="Vinted",
                source_url=url,
                image_url=imgs[0] if imgs else "",
                theme=theme,
            ))
        return out
    except Exception as exc:
        log.debug("vinted.cases.error", term=search, error=str(exc))
        return []


async def _scrape_facebook(search: str, theme: str) -> list[RawCase]:
    try:
        from app.services.playwright_scraper import scrape_facebook_playwright
    except Exception as exc:
        log.warning("facebook.cases.import_error", error=str(exc))
        return []
    try:
        listings = await scrape_facebook_playwright([search], min_price=1, max_price=350)
        out: list[RawCase] = []
        for l in listings[:24]:
            out.append(
                RawCase(
                    name=str(l.title or "")[:200],
                    price=float(l.price or 0),
                    source_site="Facebook Marketplace",
                    source_url=str(l.url or ""),
                    image_url=(l.image_urls[0] if getattr(l, "image_urls", None) else ""),
                    theme=theme,
                )
            )
        return out
    except Exception as exc:
        if "facebook_login_required" in str(exc):
            raise
        log.warning("facebook.cases.error", term=search, error=str(exc))
        return []


async def _scrape_ebay_worldwide(search: str, theme: str) -> list[RawCase]:
    """
    eBay UK with worldwide seller location — pulls in Chinese/HK sellers who list
    new ATX cases at 40-60% of UK retail with free shipping. Excellent for finding
    cheap themed cases to include in flips.
    """
    try:
        listings = await scrape_ebay(
            [search],
            min_price=1,
            max_price=200,
            auction_mode=False,
            condition_code="1000",
            worldwide=True,
        )
        if not listings:
            listings = await scrape_ebay(
                [search],
                min_price=1,
                max_price=200,
                auction_mode=False,
                condition_code=None,
                worldwide=True,
            )
        return [
            RawCase(
                name=l.title[:200],
                price=l.price,
                source_site="eBay (Worldwide)",
                source_url=l.url,
                image_url=l.image_urls[0] if l.image_urls else "",
                theme=theme,
            )
            for l in listings[:10]
        ]
    except Exception as exc:
        log.warning("ebay_worldwide.cases.error", error=str(exc))
        return []


# ── Google Shopping (UK) ──────────────────────────────────────────────────────

async def _scrape_google_shopping(search: str, theme: str) -> list[RawCase]:
    """
    Google Shopping UK — Playwright stealth browser.
    Pre-sets the SOCS=CAI cookie to bypass Google's GDPR consent page.
    Uses JS evaluation against the live DOM for resilience against
    Google's frequently-rotating CSS class names.
    """
    cases = []
    filtered_delivery = 0
    query = search.replace(" ", "+")
    url = f"https://www.google.co.uk/search?q={query}&tbm=shop&hl=en-GB&gl=gb&num=20"

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("google_shopping.cases.browser_error", error=str(exc))
            return []

        # Pre-set Google's consent cookie — bypasses the EU/UK consent gate entirely
        await context.add_cookies([
            {"name": "SOCS", "value": "CAI", "domain": ".google.co.uk", "path": "/"},
            {"name": "SOCS", "value": "CAI", "domain": ".google.com",   "path": "/"},
        ])

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Belt-and-braces consent click in case cookie wasn't sufficient
            for selector in [
                "#L2AGLb", "button:has-text('Accept all')", "[aria-label='Accept all']",
            ]:
                try:
                    await page.click(selector, timeout=1500)
                    await asyncio.sleep(0.5)
                    break
                except Exception as exc:
                    log.debug("google_shopping.consent.click_failed", selector=selector, error=str(exc))

            await asyncio.sleep(random.uniform(2.0, 3.0))
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1.0)

            # Extract products using JS against the live DOM — far more resilient
            # than HTML parsing because it sees the rendered element tree.
            raw = await page.evaluate("""() => {
                const seen = new Set();
                const out  = [];
                const priceRe = /[£$]\\s*([\\d,]+\\.?\\d*)/;

                function getCleanTitle(el) {
                    // Clone node and remove price/retailer child elements
                    const clone = el.cloneNode(true);
                    clone.querySelectorAll(".VbBaOe,.a8Pemb,.T14wmb,.CsnLnf,.UsGWMe," +
                                          "[class*='price'],[class*='Price'],[class*='store'],[class*='Store']")
                         .forEach(n => n.remove());
                    let t = clone.textContent.trim();
                    // Strip trailing price/retailer text: "£49 SomeSite + £3.99 delivery"
                    t = t.replace(/£[\\s\\S]*/g, "").trim();
                    // Strip trailing store suffixes left as raw text
                    t = t.replace(/[-–|·•]?\\s*[A-Z][a-z]+[\\s.]+(?:co\\.uk|UK|de|com)[\\s\\S]*/i, "").trim();
                    // Remove leftover trailing punctuation
                    t = t.replace(/[+\\-\\u2013\\u00B7\\u2022|,\\s]+$/, "").trim();
                    return t;
                }

                function addItem(title, price, href, img) {
                    if (!title || !href || price <= 0) return;
                    // Deduplicate on normalised title (Google repeats the same item in multiple containers)
                    const key = title.toLowerCase().replace(/\\s+/g, " ").slice(0, 80);
                    if (seen.has(key)) return;
                    seen.add(key);
                    out.push({title, price, href, img});
                }

                // Strategy 1: use explicit product containers
                const containers = document.querySelectorAll(
                    ".pla-unit-container, .sh-dgr__grid-result, [data-sh-sr], .g.sh-np"
                );

                containers.forEach(el => {
                    // .orXoSd is Google Shopping's clean product-title div (no price/retailer)
                    const titleEl = el.querySelector("h3, h4, .ropLT, .orXoSd, .rwVHAc");
                    const priceEl = el.querySelector(".VbBaOe, .a8Pemb, .T14wmb");
                    const linkEl  = el.querySelector("a.plantl, a[href*='aclk'], a[href*='/shopping/product/'], a[href]");
                    const imgEl   = el.querySelector("img");

                    const title = titleEl ? getCleanTitle(titleEl) : "";
                    const priceText = priceEl?.textContent?.trim() || "";
                    const pm = priceRe.exec(priceText);
                    const price = pm ? parseFloat(pm[1].replace(",","")) : 0;
                    addItem(title, price, linkEl?.href || "", imgEl?.src || "");
                });

                // Strategy 2: work backwards from price spans if strategy 1 found nothing
                if (out.length === 0) {
                    document.querySelectorAll(".VbBaOe, .a8Pemb").forEach(priceEl => {
                        const pm = priceRe.exec(priceEl.textContent.trim());
                        if (!pm) return;
                        const price = parseFloat(pm[1].replace(",",""));
                        let node = priceEl.parentElement;
                        for (let i = 0; i < 8 && node; i++, node = node.parentElement) {
                            const titleEl = node.querySelector("h3, h4, .ropLT, .orXoSd, .rwVHAc");
                            const linkEl  = node.querySelector("a.plantl, a[href*='aclk'], a[href*='/shopping/product/'], a[href]");
                            if (titleEl && linkEl) {
                                addItem(getCleanTitle(titleEl), price,
                                        linkEl.href, node.querySelector("img")?.src || "");
                                break;
                            }
                        }
                    });
                }

                return out.slice(0, 20);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 350:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    img_src = str(item.get("img", ""))
                    # Skip tiny data URIs from lazy-load markup
                    if img_src.startswith("data:") and len(img_src) < 300:
                        img_src = ""

                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Google Shopping",
                        source_url=href,
                        image_url=img_src,
                        theme=theme,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log.warning("google_shopping.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("google_shopping.cases.done", search=search, found=len(cases))
    return cases


# ── Shared Playwright browser factory for bot-protected sites ────────────────
# Amazon, Temu and AliExpress are JS-rendered SPAs that block plain httpx.
# We reuse a single browser context per swarm run to save on launch overhead.

_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-infobars",
    "--window-size=1366,768",
    "--lang=en-GB",
]
_STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
"""


def _interactive_scraper_mode() -> bool:
    enabled = os.getenv("SHOW_SCRAPER_BROWSER", "0").lower() in {"1", "true", "yes"}
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    return enabled and has_display


async def _make_pw_context(playwright):
    """Launch a stealthy Chromium context. Returns (browser, context)."""
    headless = not _interactive_scraper_mode()
    try:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=_STEALTH_ARGS,
            proxy=playwright_proxy_config(),
        )
    except Exception as exc:
        if headless:
            raise
        log.warning("cases.playwright.headed_launch_failed_fallback_headless", error=str(exc))
        browser = await playwright.chromium.launch(
            headless=True,
            args=_STEALTH_ARGS,
            proxy=playwright_proxy_config(),
        )
    context = await browser.new_context(
        user_agent=_STEALTH_UA,
        viewport={"width": 1366, "height": 768},
        locale="en-GB",
        timezone_id="Europe/London",
        java_script_enabled=True,
    )
    await context.add_init_script(_STEALTH_JS)
    return browser, context


async def _pw_get_page_html(page, url: str, wait_selector: str, timeout: int = 15000) -> str:
    """Navigate to URL and return page HTML once wait_selector appears (or timeout)."""
    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
    try:
        await page.wait_for_selector(wait_selector, timeout=timeout)
    except Exception as exc:
        log.debug("playwright.wait_selector_timeout", selector=wait_selector, error=str(exc))
    await asyncio.sleep(random.uniform(0.8, 1.5))
    return await page.content()


import random


# ── Amazon UK ─────────────────────────────────────────────────────────────────

async def _scrape_amazon(search: str, theme: str) -> list[RawCase]:
    """
    Amazon UK — Playwright stealth browser with JS evaluation.
    BeautifulSoup on page.content() misses h2 links because Amazon renders
    them client-side. JS evaluation against the live DOM works reliably.
    """
    cases = []
    url = f"https://www.amazon.co.uk/s?k={search.replace(' ', '+')}&i=computers"

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("amazon.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('[data-component-type="s-search-result"]', timeout=12000)
            except Exception as exc:
                log.debug("amazon.wait_selector_timeout", selector='[data-component-type=\"s-search-result\"]', error=str(exc))
            await asyncio.sleep(random.uniform(1.5, 2.5))

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
                        if (price <= 0 || price > 350) return;

                        out.push({title, price, href, img: imgEl ? imgEl.src : ''});
                    } catch (e) {}
                });
                return out.slice(0, 10);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 350:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Amazon",
                        source_url=href,
                        image_url=str(item.get("img", "")),
                        theme=theme,
                    ))
                except Exception:
                    continue
        except Exception as exc:
            log.warning("amazon.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("amazon.cases.done", search=search, found=len(cases))
    return cases


# ── Overclockers ──────────────────────────────────────────────────────────────

async def _scrape_overclockers(search: str, theme: str) -> list[RawCase]:
    """
    Overclockers UK — Full browser (non-headless) to bypass Cloudflare.

    Scrapes PC Cases by Brand using custom-element ck-product-box.
    Uses full browser to handle Cloudflare challenge.
    """
    cases = []
    url = "https://www.overclockers.co.uk/cases-and-modding/pc-cases/pc-cases-by-brand"

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2)

                # Dismiss cookie banner if present
                for selector in ["button:has-text('Accept')", "[data-cookielaw='accept']", ".cookie-accept"]:
                    try:
                        await page.click(selector, timeout=2000)
                        await asyncio.sleep(1)
                    except:
                        pass

                all_products = []
                page_num = 1
                max_pages = 5  # Limit to 5 pages (~120 cases max)

                # Paginate through all results on same tab
                while page_num <= max_pages and len(all_products) < 200:
                    # Extract products from ck-product-box elements
                    products = await page.evaluate("""() => {
                        const items = [];
                        const seen = new Set();

                        document.querySelectorAll('ck-product-box').forEach(box => {
                            try {
                                const analyticsStr = box.getAttribute('data-analytics') || '{}';
                                let analytics = JSON.parse(analyticsStr);
                                const productsArray = analytics.products || [];
                                if (productsArray.length === 0) return;

                                const product = productsArray[0];
                                if (!product.name || !product.price) return;

                                const link = box.querySelector('a');
                                const href = link ? link.href : '';
                                if (!href) return;

                                const key = href.split('?')[0];
                                if (seen.has(key)) return;
                                seen.add(key);

                                const price = parseFloat(product.price);
                                if (price < 10 || price > 500) return;

                                const img = box.querySelector('img');
                                const imgSrc = img ? (img.src || img.dataset.src || '') : '';

                                items.push({
                                    title: product.name.slice(0, 250),
                                    price,
                                    href,
                                    img: imgSrc
                                });
                            } catch (e) {}
                        });

                        return items;
                    }""")

                    all_products.extend(products)
                    log.debug("overclockers.cases.page", page=page_num, found=len(products), total=len(all_products))

                    # Look for next page button on current tab
                    next_button = None
                    next_selectors = [
                        'a[rel="next"]',
                        'a:has-text("Next")',
                        '[class*="next"] a',
                        'a[aria-label*="next"]',
                    ]

                    for selector in next_selectors:
                        try:
                            next_button = await page.query_selector(selector)
                            if next_button and await next_button.is_enabled():
                                break
                        except:
                            pass

                    if not next_button:
                        log.debug("overclockers.cases.no_more_pages", page=page_num)
                        break

                    try:
                        # Click next on same tab
                        await next_button.click()
                        await page.wait_for_load_state("networkidle", timeout=30000)
                        await asyncio.sleep(1)
                        page_num += 1
                    except Exception as e:
                        log.debug("overclockers.cases.pagination_error", error=str(e))
                        break

                # Deduplicate by URL and add to cases list
                seen_urls = set()
                for product in all_products[:200]:
                    key = product["href"].split("?")[0]
                    if key not in seen_urls:
                        seen_urls.add(key)
                        cases.append(RawCase(
                            name=product["title"],
                            price=product["price"],
                            source_site="Overclockers",
                            source_url=product["href"],
                            image_url=product["img"] or "",
                            theme=theme,
                        ))

                log.info("overclockers.cases.done", found=len(cases), total_collected=len(all_products))

            finally:
                await browser.close()

    except Exception as exc:
        log.warning("overclockers.cases.error", error=str(exc))

    return cases


# ── AliExpress ────────────────────────────────────────────────────────────────

async def _scrape_aliexpress(search: str, theme: str) -> list[RawCase]:
    """
    AliExpress — Playwright stealth browser.
    AliExpress is fully JS-rendered. Playwright renders the SPA and extracts
    product cards from the DOM after the search results load.
    """
    cases = []
    filtered_delivery = 0
    url = f"https://www.aliexpress.com/wholesale?SearchText={search.replace(' ', '+')}&g=y&SortType=price_asc"

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("aliexpress.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            # AliExpress may show a region/language popup — dismiss it
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            for selector in ["button:has-text('Ship to')", ".close-btn", "[class*='close']", "button:has-text('OK')"]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    log.debug("aliexpress.modal.dismiss_failed", selector=selector, error=str(exc))

            # Wait for product listing cards
            try:
                await page.wait_for_selector(
                    "a[href*='/item/'], [class*='product-snippet'], [class*='search-item-card']",
                    timeout=12000,
                )
            except Exception as exc:
                log.debug("aliexpress.wait_selector_timeout", error=str(exc))

            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Scroll to load lazy images
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(0.8)

            # Use JS evaluation — AliExpress hashes its class names so selectors break
            raw = await page.evaluate("""() => {
                const out = [];
                const priceRe = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                const seen = new Set();

                document.querySelectorAll("a[href*='/item/']").forEach(link => {
                    try {
                        let href = link.href || "";
                        if (!href.startsWith("http")) return;
                        // Deduplicate by URL
                        const key = href.split("?")[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        // Title: prefer aria-label, then h1/h3/p inside card
                        let title = link.getAttribute("aria-label") || "";
                        if (!title) {
                            const h = link.querySelector("h1, h3, h4, p");
                            title = h ? h.textContent.trim() : link.textContent.trim();
                        }
                        title = title.replace(/\\s+/g, " ").trim().slice(0, 200);
                        if (!title || title.length < 5) return;

                        // Price: walk up to find a price element
                        let price = 0;
                        let node = link.parentElement;
                        for (let i = 0; i < 6 && node && price === 0; i++, node = node.parentElement) {
                            node.querySelectorAll("*").forEach(el => {
                                if (price > 0) return;
                                const txt = el.textContent.trim();
                                if ((txt.includes("$") || txt.includes("£") || txt.includes("€")) && txt.length < 30) {
                                    const m = priceRe.exec(txt);
                                    if (m) price = parseFloat(m[1].replace(",", ""));
                                }
                            });
                        }
                        if (price <= 0 || price > 200) return;

                        const img = link.querySelector("img");
                        const imgSrc = img ? (img.src || img.getAttribute("data-src") || "") : "";

                        const contextText = (node?.textContent || '').replace(/\\s+/g, " ").trim().slice(0, 1200);
                        out.push({title, price, href, img: imgSrc, contextText});
                    } catch (e) {}
                });
                return out.slice(0, 12);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 200:
                        continue
                    if not allow_temu_aliexpress_listing(str(item.get("contextText", ""))):
                        filtered_delivery += 1
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="AliExpress",
                        source_url=href,
                        image_url=str(item.get("img", "")),
                        theme=theme,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log.warning("aliexpress.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()
    if filtered_delivery > 0:
        log.info("aliexpress.cases.delivery_filtered", search=search, filtered=filtered_delivery)

    log.info("aliexpress.cases.done", search=search, found=len(cases))
    return cases


# ── Temu ──────────────────────────────────────────────────────────────────────

async def _scrape_temu(search: str, theme: str) -> list[RawCase]:
    """
    Temu — Playwright stealth browser.
    Temu is a fully client-side React SPA with aggressive bot detection.
    Playwright with stealth patches gets past the initial JS challenge.
    """
    cases = []
    filtered_delivery = 0
    url = f"https://www.temu.com/search_result.html?search_key={search.replace(' ', '+')}&search_method=user"

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("temu.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if "bgn_verification" in (page.url or ""):
                if _interactive_scraper_mode():
                    log.warning("temu.challenge.manual_required", search=search, url=page.url, wait_seconds=120)
                    await asyncio.sleep(120)
                if "bgn_verification" in (page.url or ""):
                    raise RuntimeError("temu_verification_challenge")

            # Dismiss cookie/region modals
            for selector in [
                "button:has-text('Accept')", "button:has-text('OK')",
                "[class*='modal'] button", "[class*='close']",
            ]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    log.debug("temu.modal.dismiss_failed", selector=selector, error=str(exc))

            # Wait for product grid
            try:
                await page.wait_for_selector(
                    "[class*='search-result'], [data-type='goods'], [class*='goods-item'], "
                    "[class*='product-item'], [class*='SearchResult']",
                    timeout=15000,
                )
            except Exception as exc:
                log.debug("temu.wait_selector_timeout", error=str(exc))

            # Scroll to trigger lazy loading
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.8)
            if "bgn_verification" in (page.url or ""):
                if _interactive_scraper_mode():
                    log.warning("temu.challenge.manual_required", search=search, url=page.url, wait_seconds=120)
                    await asyncio.sleep(120)
                if "bgn_verification" in (page.url or ""):
                    raise RuntimeError("temu_verification_challenge")

            # Use JS evaluation — Temu rotates hashed class names so selectors break
            raw = await page.evaluate("""() => {
                const out = [];
                const priceRe = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                const seen = new Set();

                document.querySelectorAll("a[href*='/goods']").forEach(link => {
                    try {
                        let href = link.href || "";
                        if (!href.startsWith("http")) {
                            href = "https://www.temu.com" + (href.startsWith("/") ? href : "/" + href);
                        }
                        const key = href.split("?")[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        // Title: aria-label first, then text children
                        let title = link.getAttribute("aria-label") || "";
                        if (!title) {
                            const h = link.querySelector("h3, h4, p, span");
                            title = h ? h.textContent.trim() : link.textContent.trim();
                        }
                        title = title.replace(/\\s+/g, " ").trim().slice(0, 200);
                        if (!title || title.length < 5) return;

                        // Price: walk up the tree to find price text
                        let price = 0;
                        let node = link.parentElement;
                        for (let i = 0; i < 6 && node && price === 0; i++, node = node.parentElement) {
                            node.querySelectorAll("*").forEach(el => {
                                if (price > 0) return;
                                const txt = el.textContent.trim();
                                if ((txt.includes("$") || txt.includes("£") || txt.includes("€")) && txt.length < 30) {
                                    const m = priceRe.exec(txt);
                                    if (m) price = parseFloat(m[1].replace(",", ""));
                                }
                            });
                        }
                        if (price <= 0 || price > 150) return;

                        const img = link.querySelector("img");
                        const imgSrc = img ? (img.src || img.getAttribute("data-src") || "") : "";

                        const contextText = (node?.textContent || '').replace(/\\s+/g, " ").trim().slice(0, 1200);
                        out.push({title, price, href, img: imgSrc, contextText});
                    } catch (e) {}
                });
                return out.slice(0, 12);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 150:
                        continue
                    if not allow_temu_aliexpress_listing(str(item.get("contextText", ""))):
                        filtered_delivery += 1
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Temu",
                        source_url=href,
                        image_url=str(item.get("img", "")),
                        theme=theme,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log.warning("temu.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()
    if filtered_delivery > 0:
        log.info("temu.cases.delivery_filtered", search=search, filtered=filtered_delivery)

    log.info("temu.cases.done", search=search, found=len(cases))
    return cases


async def _scrape_etsy(search: str, theme: str) -> list[RawCase]:
    """
    Etsy UK — Playwright stealth browser (JS-rendered).
    Etsy is a fully client-side SPA; Playwright renders the search results.
    Price cap £200 (handmade cases tend to be pricier).
    """
    cases = []
    url = f"https://www.etsy.com/uk/search?q={search.replace(' ', '+')}&explicit=1"

    async with managed_playwright() as p:
        try:
            browser, context = await _make_pw_context(p)
        except Exception as exc:
            log.warning("etsy.cases.browser_error", error=str(exc))
            return []

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Dismiss cookie/consent dialogs
            for selector in ["button:has-text('Accept')", "[data-gdpr-single-choice-accept]", "button:has-text('OK')"]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    log.debug("etsy.modal.dismiss_failed", selector=selector, error=str(exc))

            # Wait longer for Etsy's JS-rendered listing grid (5-6s)
            await asyncio.sleep(random.uniform(5.0, 6.0))
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(1.0)

            # Use JS evaluation — Etsy's DOM selectors frequently change;
            # a[href*='/listing/'] links are always present regardless of class names.
            raw = await page.evaluate("""() => {
                const out = [];
                const priceRe = /[£$€]\\s*([\\d,]+\\.?\\d*)/;
                const seen = new Set();

                document.querySelectorAll("a[href*='/listing/']").forEach(link => {
                    try {
                        let href = link.href || "";
                        if (href.startsWith("//")) href = "https:" + href;
                        if (!href.startsWith("http")) return;
                        const key = href.split("?")[0];
                        if (seen.has(key)) return;
                        seen.add(key);

                        // Title: aria-label first, then nearest h3/p inside the card
                        let title = link.getAttribute("aria-label") || "";
                        if (!title) {
                            const h = link.querySelector("h3, h2, p");
                            title = h ? h.textContent.trim() : link.textContent.trim();
                        }
                        // If still empty, walk up to find a heading near this link
                        if (!title || title.length < 5) {
                            let node = link.parentElement;
                            for (let i = 0; i < 4 && node; i++, node = node.parentElement) {
                                const h = node.querySelector("h3, h2, p");
                                if (h) { title = h.textContent.trim(); break; }
                            }
                        }
                        title = title.replace(/\\s+/g, " ").trim().slice(0, 200);
                        if (!title || title.length < 5) return;

                        // Price: .currency-value spans are Etsy's standard price element
                        let price = 0;
                        let node = link.parentElement;
                        for (let i = 0; i < 6 && node && price === 0; i++, node = node.parentElement) {
                            const priceEl = node.querySelector(
                                ".currency-value, [class*='currency-value'], [class*='price']"
                            );
                            if (priceEl) {
                                const m = priceRe.exec(priceEl.textContent.trim());
                                if (m) price = parseFloat(m[1].replace(",", ""));
                            }
                            // Fallback: look for any text matching price pattern
                            if (price === 0) {
                                node.querySelectorAll("span, p").forEach(el => {
                                    if (price > 0) return;
                                    const txt = el.textContent.trim();
                                    if (txt.length < 20 && (txt.includes("£") || txt.includes("$"))) {
                                        const m = priceRe.exec(txt);
                                        if (m) price = parseFloat(m[1].replace(",", ""));
                                    }
                                });
                            }
                        }
                        if (price <= 0 || price > 200) return;

                        const img = link.querySelector("img");
                        const imgSrc = img ? (img.src || img.getAttribute("data-src") || "") : "";

                        out.push({title, price, href, img: imgSrc});
                    } catch (e) {}
                });
                return out.slice(0, 10);
            }""")

            for item in raw:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    if not title or len(title) < 5:
                        continue
                    price = float(item.get("price", 0) or 0)
                    if price <= 0 or price > 200:
                        continue
                    href = str(item.get("href", ""))
                    if not href.startswith("http"):
                        continue
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Etsy",
                        source_url=href,
                        image_url=str(item.get("img", "")),
                        theme=theme,
                    ))
                except Exception:
                    continue
        except Exception as exc:
            log.warning("etsy.cases.scrape_error", error=str(exc))
        finally:
            await browser.close()

    log.info("etsy.cases.done", search=search, found=len(cases))
    return cases


async def _scrape_bargainhardware(search: str, theme: str) -> list[RawCase]:
    return await _scrape_generic_case_market(
        search=search,
        theme=theme,
        source_site="BargainHardware",
        url=f"https://www.bargainhardware.eu/de/catalogsearch/result/?q={search.replace(' ', '+')}",
    )


async def _scrape_cherrytree(search: str, theme: str) -> list[RawCase]:
    # Explicit request: do not search CherryTree by term; ingest from cases section.
    seeds = [
        "https://www.cherrytreeinc.com/collections/pc-cases",
        "https://www.cherrytreeinc.com/collections/cases",
        "https://www.cherrytreeinc.com/cases",
    ]
    all_cases: list[RawCase] = []
    seen_urls: set[str] = set()
    for url in seeds:
        scraped = await _scrape_generic_case_market(
            search="catalogue",
            theme=theme or "Catalogue",
            source_site="CherryTree Inc",
            url=url,
        )
        for c in scraped:
            key = (c.source_url or "").split("?")[0]
            if not key or key in seen_urls:
                continue
            seen_urls.add(key)
            all_cases.append(c)
    return all_cases


async def _scrape_alibaba(search: str, theme: str) -> list[RawCase]:
    return await _scrape_generic_case_market(
        search=search,
        theme=theme,
        source_site="Alibaba",
        url=f"https://www.alibaba.com/trade/search?SearchText={search.replace(' ', '+')}",
    )


async def _scrape_generic_case_market(search: str, theme: str, source_site: str, url: str) -> list[RawCase]:
    cases: list[RawCase] = []
    async with managed_playwright() as p:
        headless = not _interactive_scraper_mode()
        try:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
                proxy=playwright_proxy_config(),
            )
        except Exception as exc:
            if headless:
                raise
            log.warning("cases.generic_market.headed_launch_failed_fallback_headless", source=source_site, error=str(exc))
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
                proxy=playwright_proxy_config(),
            )
        ctx = await browser.new_context(user_agent=ua.random, locale="en-GB", timezone_id="Europe/London")
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.0)
            await page.evaluate("window.scrollBy(0, 700)")
            await asyncio.sleep(0.7)
            await page.evaluate("window.scrollBy(0, 1200)")
            await asyncio.sleep(0.8)
            raw = await page.evaluate(
                """() => {
                    const out = [];
                    const re = /(?:US\\$|[£$€])\\s*([\\d,]+\\.?\\d*)/i;
                    const anchors = Array.from(document.querySelectorAll('a[href]')).slice(0, 700);
                    const seen = new Set();
                    for (const a of anchors) {
                        let href = a.href || a.getAttribute('href') || '';
                        if (!href) continue;
                        if (href.startsWith('/')) href = location.origin + href;
                        const key = href.split('?')[0];
                        if (seen.has(key)) continue;
                        const node = a.closest('article,li,div') || a;
                        const title = ((a.textContent || node.textContent || '').replace(/\\s+/g, ' ').trim());
                        if (!title || title.length < 8) continue;
                        const m = re.exec(node.textContent || '');
                        if (!m) continue;
                        const price = parseFloat((m[1] || '').replace(/,/g, ''));
                        if (!Number.isFinite(price)) continue;
                        const img = (node.querySelector('img')?.src || '');
                        seen.add(key);
                        out.push({title, href, price, img});
                        if (out.length >= 14) break;
                    }
                    // Source-specific fallbacks for sites with structured cards.
                    const host = location.hostname;
                    if (out.length === 0 && host.includes('bargainhardware')) {
                        const cards = document.querySelectorAll('[data-price-amount], .product-item, li.product-item');
                        cards.forEach(card => {
                            if (out.length >= 20) return;
                            const priceAttr = card.getAttribute('data-price-amount') || card.querySelector('[data-price-amount]')?.getAttribute('data-price-amount') || '';
                            let price = parseFloat((priceAttr || '').replace(/,/g, ''));
                            if (!Number.isFinite(price) || price <= 0) {
                                const m = re.exec(card.textContent || '');
                                price = m ? parseFloat((m[1] || '').replace(/,/g, '')) : 0;
                            }
                            const linkEl = card.querySelector('a[href]') || null;
                            let href = linkEl ? (linkEl.href || linkEl.getAttribute('href') || '') : '';
                            if (href.startsWith('/')) href = location.origin + href;
                            const titleEl = card.querySelector('.product-item-link, h2, h3');
                            const linkWithTitle = card.querySelector('a[title]');
                            const title = (titleEl?.textContent || linkWithTitle?.getAttribute('title') || '').replace(/\\s+/g, ' ').trim();
                            if (!href || !title || !Number.isFinite(price) || price <= 0) return;
                            out.push({title, href, price, img: (card.querySelector('img')?.src || '')});
                        });
                    }
                    if (out.length === 0 && host.includes('alibaba')) {
                        const cards = document.querySelectorAll("a[href*='/product-detail/'], a[href*='/x/'], a[href*='offer/']");
                        const seenAli = new Set();
                        cards.forEach(a => {
                            if (out.length >= 20) return;
                            let href = a.href || a.getAttribute('href') || '';
                            if (!href) return;
                            if (href.startsWith('/')) href = location.origin + href;
                            const key = href.split('?')[0];
                            if (seenAli.has(key)) return;
                            seenAli.add(key);
                            const node = a.closest('article,li,div') || a;
                            const title = ((a.textContent || node.textContent || '').replace(/\\s+/g, ' ').trim());
                            const m = re.exec(node.textContent || '');
                            const price = m ? parseFloat((m[1] || '').replace(/,/g, '')) : 0;
                            if (!title || title.length < 6 || !Number.isFinite(price) || price <= 0) return;
                            out.push({title, href, price, img: (node.querySelector('img')?.src || '')});
                        });
                    }
                    return out;
                }"""
            )
            for item in raw or []:
                try:
                    title = str(item.get("title", "")).strip()[:200]
                    price = float(item.get("price", 0) or 0)
                    href = str(item.get("href", ""))
                    max_price = 2000 if source_site in {"Alibaba", "BargainHardware", "CherryTree Inc"} else 350
                    if not title or len(title) < 5 or price <= 0 or price > max_price or not href.startswith("http"):
                        continue
                    cases.append(
                        RawCase(
                            name=title,
                            price=price,
                            source_site=source_site,
                            source_url=href,
                            image_url=str(item.get("img", "")),
                            theme=theme,
                        )
                    )
                except Exception:
                    continue
            page_title = ""
            body_text = ""
            try:
                page_title = await page.title()
            except Exception:
                page_title = ""
            try:
                body_text = (await page.content()).lower()
            except Exception:
                body_text = ""
            title_l = page_title.lower()
            if "captcha interception" in title_l or "captcha interception" in body_text:
                raise RuntimeError(f"{source_site.lower()}_captcha_interception")
            if "429 too many requests" in title_l or "too many requests" in body_text:
                raise RuntimeError(f"{source_site.lower()}_rate_limited_429")
            if not cases:
                log.info(
                    "cases.generic_market.empty",
                    source=source_site,
                    search=search,
                    url=page.url,
                    title=page_title,
                )
        except Exception as exc:
            msg = str(exc)
            if "ERR_NAME_NOT_RESOLVED" in msg and source_site == "CherryTree Inc":
                # CherryTree DNS intermittently fails; treat as soft no-data for this cycle.
                log.info("cases.generic_market.no_data_dns", source=source_site, search=search)
            else:
                log.warning("cases.generic_market.error", source=source_site, search=search, error=msg)
        finally:
            await browser.close()
    log.info("cases.generic_market.done", source=source_site, search=search, found=len(cases))
    return cases


async def _upsert_case(db, case: RawCase):
    from sqlalchemy import select
    result = await db.execute(
        select(Part).where(
            Part.name == case.name,
            Part.source_site == case.source_site,
            Part.category == PartCategory.case,
        )
    )
    part = result.scalar_one_or_none()
    now = datetime.utcnow()
    if part:
        part.price = case.price
        part.price_new = case.price
        part.source_url = case.source_url
        part.image_url = case.image_url
        part.last_price_update = now
    else:
        part = Part(
            name=case.name,
            category=PartCategory.case,
            condition=PartCondition.new,
            source_site=case.source_site,
            source_url=case.source_url,
            price=case.price,
            price_new=case.price,
            image_url=case.image_url,
            theme=case.theme,
            specs=case.specs,
            resale_value_add=0.0,
            last_price_update=now,
        )
        db.add(part)
        await db.flush()

    db.add(PriceHistory(
        entity_type=PriceHistoryType.part,
        entity_id=part.id,
        price=case.price,
        condition="new",
        source=case.source_site,
    ))


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
