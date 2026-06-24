"""
Live price fetcher for the catalogue tab.

Scrapes eBay BIN used listings fresh (not from DB cache) and gets
new retail prices from Scan/Overclockers, with LLM as fallback for RRP.
Results are cached in-process for CACHE_TTL seconds per category.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import time

import httpx
from bs4 import BeautifulSoup

from app.services.component_models import CANONICAL_MODELS
from app.services.proxy import apply_httpx_proxy
from app.swarms.upgrade_parts import _EBAY_HEADERS, _parse_price, _fetch_scan, _fetch_overclockers

import structlog

log = structlog.get_logger(__name__)

CACHE_TTL = 1800  # 30 minutes
_LIVE_CACHE: dict[str, tuple[float, list]] = {}  # category -> (timestamp, rows)


async def _fetch_ebay_cheapest_listing(client: httpx.AsyncClient, search: str) -> dict | None:
    """Return {price, url, title} for the cheapest BIN used listing on eBay UK."""
    params = {
        "_nkw": search,
        "_sacat": "0",
        "LH_BIN": "1",
        "LH_ItemCondition": "3000",  # Used
        "_sop": "15",               # Sort by price ascending
        "_ipg": "60",
    }
    for attempt in range(2):
        try:
            r = await client.get(
                "https://www.ebay.co.uk/sch/i.html",
                params=params,
                headers=_EBAY_HEADERS,
                timeout=20,
            )
            if r.status_code == 403:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "lxml")
            for item in soup.select(".s-item"):
                title_el = item.select_one(".s-item__title")
                link_el  = item.select_one(".s-item__link")
                price_el = item.select_one(".s-item__price")
                if not title_el or not link_el or not price_el:
                    continue
                title = title_el.get_text(strip=True)
                if "shop on ebay" in title.lower():
                    continue
                href = link_el.get("href", "")
                if not href or "/itm/" not in href:
                    continue
                clean_url = href.split("?")[0]
                price = _parse_price(price_el.get_text(strip=True))
                if 5 < price < 5000:
                    return {"price": round(price, 2), "url": clean_url, "title": title}
            return None
        except Exception as exc:
            log.debug("live_prices.ebay.error", search=search, attempt=attempt, error=str(exc))
            await asyncio.sleep(1.0)
    return None


async def _batch_llm_rrp(model_names: list[str]) -> dict[str, float]:
    """Single LLM call returning estimated UK new retail prices for a list of models."""
    from app.config import get_settings
    s = get_settings()

    names_block = "\n".join(f"- {n}" for n in model_names)
    prompt = (
        "You are a UK PC hardware pricing expert. For each component listed below, "
        "provide the current UK new retail price in GBP from major retailers "
        "(Amazon UK, Scan, Overclockers, Box) as of early 2026.\n\n"
        "Return ONLY a valid JSON object — no markdown, no explanation:\n"
        '{"ModelName": 295, ...}\n\n'
        f"Components:\n{names_block}"
    )

    raw: str | None = None

    if s.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text if resp.content else None
        except Exception as exc:
            log.warning("live_prices.llm.anthropic_error", error=str(exc))

    if not raw and s.openrouter_api_key:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {s.openrouter_api_key}",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "PC Flipper Live Prices",
                    },
                    json={
                        "model": s.openrouter_primary_model or "anthropic/claude-haiku-4-5",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1024,
                    },
                )
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log.warning("live_prices.llm.openrouter_error", error=str(exc))

    if not raw:
        return {}

    try:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            data = json.loads(m.group())
            return {k: float(v) for k, v in data.items() if isinstance(v, (int, float)) and v > 0}
    except Exception:
        pass
    return {}


async def get_live_prices_for_category(category: str, force_refresh: bool = False) -> list[dict]:
    """
    For each canonical model in the category, scrape eBay live for the cheapest
    used BIN listing (with URL) and get new retail RRP from Scan/Overclockers
    (LLM estimate as fallback). Results are cached 30 minutes per category.
    """
    now = time.time()
    if not force_refresh:
        cached = _LIVE_CACHE.get(category)
        if cached and (now - cached[0]) < CACHE_TTL:
            return cached[1]

    models = CANONICAL_MODELS.get(category, [])
    if not models:
        return []

    n = len(models)
    ebay_results: list[dict | None] = [None] * n
    scan_results: list[float | None] = [None] * n
    oc_results:   list[float | None] = [None] * n

    # Bounded concurrency — be polite to eBay especially
    ebay_sem = asyncio.Semaphore(5)
    retail_sem = asyncio.Semaphore(8)

    async def _one_ebay(i: int, search: str) -> None:
        async with ebay_sem:
            await asyncio.sleep(random.uniform(0.15, 0.5))
            async with httpx.AsyncClient(
                **apply_httpx_proxy({"follow_redirects": True, "timeout": 25})
            ) as client:
                ebay_results[i] = await _fetch_ebay_cheapest_listing(client, search)

    async def _one_scan(i: int, search: str) -> None:
        async with retail_sem:
            scan_results[i] = await _fetch_scan(search)

    async def _one_oc(i: int, search: str) -> None:
        async with retail_sem:
            oc_results[i] = await _fetch_overclockers(search)

    model_names = [m["name"] for m in models]
    llm_task = asyncio.create_task(_batch_llm_rrp(model_names))

    await asyncio.gather(
        *[_one_ebay(i, m["name"]) for i, m in enumerate(models)],
        *[_one_scan(i, m["name"]) for i, m in enumerate(models)],
        *[_one_oc(i, m["name"])  for i, m in enumerate(models)],
        llm_task,
        return_exceptions=True,
    )

    llm_rrp: dict[str, float] = {}
    try:
        result = llm_task.result()
        if isinstance(result, dict):
            llm_rrp = result
    except Exception:
        pass

    rows: list[dict] = []
    for i, m in enumerate(models):
        ebay = ebay_results[i]
        scan_p = scan_results[i]
        oc_p   = oc_results[i]

        # Best new retail price
        retail_opts: dict[str, float] = {}
        if scan_p:
            retail_opts["Scan"] = scan_p
        if oc_p:
            retail_opts["Overclockers"] = oc_p

        if retail_opts:
            rrp_source = min(retail_opts, key=lambda k: retail_opts[k])
            rrp = retail_opts[rrp_source]
        else:
            rrp = llm_rrp.get(m["name"])
            rrp_source = "Est." if rrp else None

        ebay_price = ebay["price"] if ebay else None
        ebay_url   = ebay["url"]   if ebay else None
        ebay_title = ebay["title"] if ebay else None

        # Lowest price across all sources
        candidates = [
            (v, src, url, title)
            for v, src, url, title in [
                (ebay_price, "eBay UK",   ebay_url,  ebay_title),
                (rrp,        rrp_source,  None,       None),
            ]
            if v
        ]
        if candidates:
            lowest_price, lowest_source, lowest_url, lowest_title = min(
                candidates, key=lambda x: x[0]
            )
        else:
            lowest_price = lowest_source = lowest_url = lowest_title = None

        rows.append({
            "model":         m["name"],
            "tier":          m["tier"],
            "rrp":           round(rrp, 2) if rrp else None,
            "rrp_source":    rrp_source,
            "ebay_used":     ebay_price,
            "ebay_url":      ebay_url,
            "ebay_title":    ebay_title,
            "lowest_price":  round(lowest_price, 2) if lowest_price else None,
            "lowest_url":    lowest_url,
            "lowest_title":  lowest_title,
            "lowest_source": lowest_source,
        })

    _LIVE_CACHE[category] = (now, rows)
    log.info("live_prices.fetched", category=category, count=len(rows))
    return rows
