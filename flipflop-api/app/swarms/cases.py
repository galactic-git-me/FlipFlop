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
    "overclockers uk": "Overclockers",
    "overclockers": "Overclockers",
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
    form_factors: list[str] = None  # ["ATX", "MATX", "EATX", "ITX", "MINI_ITX"]
    keywords: list[str] = None  # ["gaming", "RGB", "tempered-glass", etc.]
    rating: float = None  # 0-5 stars (from Amazon/reviews)
    review_count: int = None  # number of customer reviews
    sales_velocity: str = None  # "50+ bought in past month" - real demand signal
    rrp: float = None  # Recommended Retail Price (shows discount %)
    brand: str = None
    model: str = None

    def __post_init__(self):
        # Auto-extract form factors and keywords from name if not provided
        if self.form_factors is None:
            self.form_factors = _extract_form_factors(self.name)
        if self.keywords is None:
            self.keywords = _extract_keywords(self.name)


def _extract_form_factors(text: str) -> list[str]:
    """Extract motherboard form factors from case name/specs."""
    text_upper = text.upper()
    factors = []

    # Check for form factors (order matters — check longer forms first)
    if "MINI ITX" in text_upper or "MINI-ITX" in text_upper or "MINI_ITX" in text_upper:
        factors.append("MINI_ITX")
    elif "ITX" in text_upper:
        factors.append("ITX")

    if "EATX" in text_upper or "E-ATX" in text_upper:
        factors.append("EATX")

    if "MATX" in text_upper or "M-ATX" in text_upper or "MICRO ATX" in text_upper or "MICROATX" in text_upper:
        factors.append("MATX")

    if "ATX" in text_upper and "MATX" not in text_upper and "EATX" not in text_upper and "MINI" not in text_upper:
        factors.append("ATX")

    # Default to ATX if nothing found (most common form factor)
    if not factors:
        factors.append("ATX")

    return list(dict.fromkeys(factors))  # Deduplicate while preserving order


def _extract_keywords(text: str) -> list[str]:
    """Extract relevant case keywords from name/specs."""
    text_lower = text.lower()
    keywords = []

    # Visual/material keywords
    keyword_map = {
        "gaming": ["gaming", "gamer", "esports"],
        "RGB": ["rgb", "argb", "aura", "addressable"],
        "tempered-glass": ["tempered glass", "tg", "glass panel", "glass window"],
        "white": ["white", "pearl", "snow"],
        "black": ["black", "dark"],
        "wood": ["bamboo", "wood", "walnut"],
        "curved": ["curved", "edge", "curve"],
        "dual-chamber": ["dual chamber", "divided", "split"],
        "airflow": ["airflow", "air flow", "ventilation"],
        "showcase": ["showcase", "display", "panoramic"],
        "fishtank": ["fish tank", "aquarium", "panoramic"],
        "compact": ["compact", "small", "mini", "micro"],
        "tower": ["tower", "mid tower", "full tower"],
        "mesh": ["mesh", "front mesh"],
        "window": ["window", "side window"],
        "silent": ["silent", "quiet", "noise"],
        "modular": ["modular"],
        "budget": ["budget", "budget-friendly", "affordable"],
        "premium": ["premium", "high-end", "luxury"],
        "retro": ["retro", "vintage", "classic"],
        "modern": ["modern", "contemporary", "sleek"],
    }

    for keyword, patterns in keyword_map.items():
        for pattern in patterns:
            if pattern in text_lower:
                keywords.append(keyword)
                break  # Only add keyword once

    return list(dict.fromkeys(keywords))  # Deduplicate while preserving order


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

    # Dedup per source, apply cap. Catalogue vendors are scraped once, not per term.
    terms_by_vendor = {k: list(dict.fromkeys(v))[:max_terms] for k, v in terms_by_vendor.items()}
    terms_by_vendor["CherryTree Inc"] = ["catalogue"]
    if os.getenv("CASES_AMAZON_ONLY", "0").lower() not in {"1", "true", "yes"}:
        terms_by_vendor["Overclockers"] = ["catalogue"]

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
    amazon_only = os.getenv("CASES_AMAZON_ONLY", "0").lower() in {"1", "true", "yes"}
    enabled_sources = []
    for s in SOURCES:
        if amazon_only and s["fn"] != "amazon":
            continue
        if s["name"] not in batch_terms:
            continue
        if s["fn"] in _PLAYWRIGHT_CASE_SOURCES and not has_chromium:
            continue
        enabled_sources.append(s)
    term_concurrency = max(1, int(os.getenv("CASES_TERM_CONCURRENCY", "10")))
    term_sem = asyncio.Semaphore(term_concurrency)

    async def _scrape_source_seq(source: dict) -> list[dict]:
        rows: list[dict] = []
        # CherryTree / Overclockers ingest a catalogue once, not per search term.
        if source["fn"] in {"cherrytree", "overclockers"}:
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
                save_limit = len(cases) if source_name == "Overclockers" else 16
                for case in cases[:save_limit]:
                    await _upsert_case(db, case)
                    await _upsert_case_new(db, case)
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

    try:
        from app.services.amazon_bestsellers import scrape_amazon_bestsellers

        bestseller_stats = await scrape_amazon_bestsellers()
        stats["bestsellers"] = bestseller_stats
        log.info("cases_swarm.bestsellers", **bestseller_stats)
    except Exception as exc:
        stats["errors"] += 1
        log.error("cases_swarm.bestsellers_error", error=str(exc))

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
                const parseMoney = (text) => {
                    if (!text) return 0;
                    const n = String(text).replace(/[^0-9.]/g, '');
                    const v = parseFloat(n);
                    return Number.isFinite(v) ? v : 0;
                };
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

                        const ratingAlt = item.querySelector('.a-icon-alt')?.textContent || '';
                        const ratingMatch = ratingAlt.match(/([0-9.]+)\\s+out of/);
                        const reviewEl = item.querySelector('a[href*="#customerReviews"] span, span.s-underline-text');
                        const reviewDigits = (reviewEl?.textContent || '').replace(/[^0-9]/g, '');
                        const bought = Array.from(item.querySelectorAll('span'))
                            .map((el) => (el.textContent || '').trim())
                            .find((t) => t.length < 60 && /bought in (the )?past month/i.test(t));
                        const strikeEl = item.querySelector('.a-price[data-a-strike="true"] .a-offscreen, span.a-price.a-text-price .a-offscreen');

                        out.push({
                            title,
                            price,
                            href,
                            img: imgEl ? imgEl.src : '',
                            rating: ratingMatch ? parseFloat(ratingMatch[1]) : null,
                            reviewCount: reviewDigits ? parseInt(reviewDigits, 10) : null,
                            salesVelocity: bought ? bought.slice(0, 80) : null,
                            rrp: parseMoney(strikeEl?.textContent) || null,
                        });
                    } catch (e) {}
                });
                return out.slice(0, 16);
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
                    rrp_raw = item.get("rrp")
                    cases.append(RawCase(
                        name=title,
                        price=price,
                        source_site="Amazon",
                        source_url=href,
                        image_url=str(item.get("img", "")),
                        theme=theme,
                        rating=float(item["rating"]) if item.get("rating") else None,
                        review_count=int(item["reviewCount"]) if item.get("reviewCount") else None,
                        sales_velocity=str(item["salesVelocity"]) if item.get("salesVelocity") else None,
                        rrp=float(rrp_raw) if rrp_raw else None,
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
    Overclockers UK PC Cases by Brand catalogue.
    One catalogue pass per swarm, not per search term.
    """
    cases = await _scrape_overclockers_once(headless=True)
    if not cases:
        log.info("overclockers.retry_headed")
        cases = await _scrape_overclockers_once(headless=False)
    log.info("overclockers.cases.done", search=search, found=len(cases))
    return cases


async def _scrape_overclockers_once(headless: bool) -> list[RawCase]:
    cases: list[RawCase] = []
    base_url = "https://www.overclockers.co.uk/cases-and-modding/pc-cases/pc-cases-by-brand"

    async with managed_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=False,  # MUST be False for Overclockers - headless blocks product rendering
                args=_STEALTH_ARGS + [
                    "--disable-extensions",
                    "--disable-plugins",
                    "--disable-images",
                ],
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
        except Exception as exc:
            log.warning("overclockers.cases.browser_error", error=str(exc), headless=headless)
            return []

        page = await context.new_page()

        # Set viewport to make window visible
        await page.set_viewport_size({"width": 1366, "height": 768})

        try:
            # Load first page
            await page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            for selector in ["button:has-text('Accept')", "[data-cookielaw='accept']", ".cookie-accept"]:
                try:
                    await page.click(selector, timeout=2000)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

            try:
                await page.wait_for_selector("ck-product-box", timeout=15000)
            except Exception as exc:
                log.debug("overclockers.wait_selector_timeout", error=str(exc))

            all_products = []
            seen_urls = set()

            # Use query string pagination - pages work fine when navigated to directly
            # CRITICAL: Keep browser session open throughout pagination to maintain auth/CAPTCHA session
            for page_num in range(1, 12):  # Overclockers has maxpage=11
                page_url = f"{base_url}?page={page_num}"
                log.info("overclockers.cases.loading_page", page=page_num, url=page_url, total_so_far=len(all_products))

                await page.goto(page_url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2)  # Wait for page to stabilize

                # CRITICAL: Wait for products to fully render before extraction
                try:
                    await page.wait_for_selector("ck-product-box", timeout=20000)
                    await asyncio.sleep(2)  # Extra wait for all products to render
                except Exception as e:
                    log.warning("overclockers.wait_product_timeout", page=page_num, error=str(e))
                    # Don't break - CAPTCHA page might need manual intervention on first page
                    # but session persists, so keep trying
                    if page_num == 1:
                        log.warning("overclockers.first_page_no_products", likely_captcha=True)
                    continue

                # Extract products from this page
                products = await page.evaluate(f"""() => {{
                    const items = [];
                    const seenUrls = {str(seen_urls).replace("'", '"')};
                    document.querySelectorAll('ck-product-box').forEach(box => {{
                        try {{
                            const analytics = JSON.parse(box.getAttribute('data-analytics') || '{{}}');
                            const product = (analytics.products || [])[0];
                            if (!product || !product.name || !product.price) return;
                            const link = box.querySelector('a');
                            const href = link ? link.href : '';
                            if (!href) return;
                            const key = href.split('?')[0];
                            if (seenUrls.has(key)) return;
                            const price = parseFloat(product.price);
                            if (price < 10 || price > 500) return;
                            const img = box.querySelector('img');
                            const rrp = parseFloat(product.wasPrice || product.rrp || product.listPrice || 0);
                            items.push({{
                                title: String(product.name).slice(0, 250),
                                price,
                                href,
                                img: img ? (img.src || img.dataset.src || '') : '',
                                rrp: Number.isFinite(rrp) && rrp > price ? rrp : null,
                                rating: product.rating || product.averageRating || null,
                                reviewCount: product.reviewCount || product.reviews || null,
                            }});
                        }} catch (e) {{}}
                    }});
                    return items;
                }}""")

                # Track newly found products
                for product in products:
                    url_key = product["href"].split("?")[0]
                    if url_key not in seen_urls:
                        seen_urls.add(url_key)
                        all_products.append(product)

                log.info("overclockers.cases.page_results", page=page_num, found=len(products), total=len(all_products), headless=headless)

                if not products:
                    log.info("overclockers.cases.no_products_on_page", page=page_num)
                    break

                if len(all_products) >= 400:
                    break

            seen_urls = set()
            for product in all_products[:240]:
                key = product["href"].split("?")[0]
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                rating = product.get("rating")
                review_count = product.get("reviewCount")
                rrp = product.get("rrp")
                cases.append(RawCase(
                    name=product["title"],
                    price=product["price"],
                    source_site="Overclockers",
                    source_url=product["href"],
                    image_url=product.get("img") or "",
                    theme="Catalogue",
                    rating=float(rating) if rating else None,
                    review_count=int(review_count) if review_count else None,
                    rrp=float(rrp) if rrp else None,
                ))
        except Exception as exc:
            log.warning("overclockers.cases.error", error=str(exc), headless=headless)
        finally:
            await browser.close()

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

    # First: check for exact match (same name + source)
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
        # Update price if cheaper
        if case.price < part.price:
            part.price = case.price
            part.price_new = case.price
            part.source_url = case.source_url
            part.source_site = case.source_site  # Switch to cheaper source
            part.image_url = case.image_url
            part.form_factors = case.form_factors
            part.keywords = case.keywords
            part.last_price_update = now

        # Capture RRP from whichever source has it
        if case.rrp:
            part.rrp = case.rrp

        # Always prefer Amazon ratings & demand (more reliable) regardless of price source
        if case.source_site == "Amazon":
            # Always take Amazon ratings, reviews, and sales velocity (demand signal)
            if case.rating:
                part.rating = case.rating
            if case.review_count:
                part.review_count = case.review_count
            if case.sales_velocity:
                part.sales_velocity = case.sales_velocity  # "50+ sold this month"
        elif not part.rating and case.rating:
            # Only use Overclockers ratings if we have no Amazon ratings yet
            part.rating = case.rating
            part.review_count = case.review_count
            if case.sales_velocity:
                part.sales_velocity = case.sales_velocity
    else:
        # Check for cross-source duplicates (same case name, different source)
        # If found, only keep if this source is cheaper
        result = await db.execute(
            select(Part).where(
                Part.name == case.name,
                Part.category == PartCategory.case,
                Part.source_site.in_(["Amazon", "Overclockers"]),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Case exists from another fast source
            if case.price < existing.price:
                # This source is cheaper, update it
                existing.price = case.price
                existing.price_new = case.price
                existing.source_url = case.source_url
                existing.source_site = case.source_site
                existing.image_url = case.image_url
                existing.form_factors = case.form_factors
                existing.keywords = case.keywords
                existing.last_price_update = now
                part = existing
            else:
                # Existing source is cheaper or equal, don't create duplicate
                part = existing

            # Capture RRP from whichever source has it
            if case.rrp:
                existing.rrp = case.rrp

            # Always prefer Amazon ratings regardless of which source has the best price
            if case.source_site == "Amazon":
                if case.rating:
                    existing.rating = case.rating
                if case.review_count:
                    existing.review_count = case.review_count
                if case.sales_velocity:
                    existing.sales_velocity = case.sales_velocity
            elif not existing.rating and case.rating:
                # Only use Overclockers ratings if we have no Amazon ratings yet
                existing.rating = case.rating
                existing.review_count = case.review_count
                if case.sales_velocity:
                    existing.sales_velocity = case.sales_velocity
        else:
            # No existing entry, create new
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
                form_factors=case.form_factors,
                keywords=case.keywords,
                rating=case.rating,
                review_count=case.review_count,
                sales_velocity=case.sales_velocity,
                rrp=case.rrp,
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


async def _upsert_case_new(db, case: RawCase):
    """Upsert into new Case table (clean, isolated from Parts inventory)."""
    from sqlalchemy import select
    from app.models.case import Case

    # Check for exact match (same name + source)
    result = await db.execute(
        select(Case).where(
            Case.name == case.name,
            Case.source_site == case.source_site,
        )
    )
    case_row = result.scalar_one_or_none()
    now = datetime.utcnow()

    if case_row:
        # Keep the latest Amazon price, not only a cheaper one — the extra
        # rating/demand fields live on the same card and must refresh too.
        if case.source_site == "Amazon" and case.price:
            case_row.price = case.price
            case_row.price_new = case.price
            case_row.source_url = case.source_url
            case_row.image_url = case.image_url or case_row.image_url
        elif case.price < (case_row.price or 999999):
            case_row.price = case.price
            case_row.price_new = case.price
            case_row.source_url = case.source_url
            case_row.source_site = case.source_site
            case_row.image_url = case.image_url
            case_row.form_factors = case.form_factors
            case_row.keywords = case.keywords

        # Capture RRP from whichever source has it
        if case.rrp:
            case_row.rrp = case.rrp

        # Always prefer Amazon ratings & demand (more reliable)
        if case.source_site == "Amazon":
            if case.rating:
                case_row.rating = case.rating
            if case.review_count:
                case_row.review_count = case.review_count
            if case.sales_velocity:
                case_row.sales_velocity = case.sales_velocity
        elif not case_row.rating and case.rating:
            # Only use Overclockers ratings if we have no Amazon ratings yet
            case_row.rating = case.rating
            case_row.review_count = case.review_count
            if case.sales_velocity:
                case_row.sales_velocity = case.sales_velocity
    else:
        # Check for cross-source duplicates
        result = await db.execute(
            select(Case).where(
                Case.name == case.name,
                Case.source_site.in_(["Amazon", "Overclockers"]),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Case exists from another source
            if case.price < (existing.price or 999999):
                # This source is cheaper, update it
                existing.price = case.price
                existing.price_new = case.price
                existing.source_url = case.source_url
                existing.source_site = case.source_site
                existing.image_url = case.image_url
                existing.form_factors = case.form_factors
                existing.keywords = case.keywords
                case_row = existing
            else:
                case_row = existing

            # Capture RRP from whichever source has it
            if case.rrp:
                existing.rrp = case.rrp

            # Always prefer Amazon ratings
            if case.source_site == "Amazon":
                if case.rating:
                    existing.rating = case.rating
                if case.review_count:
                    existing.review_count = case.review_count
                if case.sales_velocity:
                    existing.sales_velocity = case.sales_velocity
            elif not existing.rating and case.rating:
                existing.rating = case.rating
                existing.review_count = case.review_count
                if case.sales_velocity:
                    existing.sales_velocity = case.sales_velocity
        else:
            # No existing entry, create new
            case_row = Case(
                name=case.name,
                brand=case.brand,
                model=case.model,
                source_site=case.source_site,
                source_url=case.source_url,
                image_url=case.image_url,
                price=case.price or None,
                price_new=case.price or None,
                rrp=case.rrp,
                form_factors=case.form_factors,
                keywords=case.keywords,
                rating=case.rating,
                review_count=case.review_count,
                sales_velocity=case.sales_velocity,
                status="pending",
            )
            db.add(case_row)
            await db.flush()

    return case_row


def _parse_price(text: str) -> float:
    m = re.search(r"[\d,]+\.?\d*", str(text).replace(",", ""))
    return float(m.group(0)) if m else 0.0
