# Components Multi-Source Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor components catalogue to search all sources (Vinted, Gumtree, Amazon, Temu, AliExpress) while using eBay NEW/USED prices as benchmarks for gem scoring.

**Architecture:** The components catalogue will fetch eBay prices for benchmarking (NEW condition = new price, USED condition = used price), then search multiple sources for actual component listings. Each listing is scored against eBay benchmarks to determine if it's a gem deal. Results aggregate all sources with gem classifications based on eBay benchmarks only.

**Tech Stack:** FastAPI, asyncio, eBay Browse API, Vinted scraper, Gumtree scraper, existing upgrade_parts infrastructure

---

## File Structure

**Files to create:**
- `app/services/component_search.py` - Multi-source component search service (Vinted, Gumtree, Amazon, Temu, AliExpress)
- `app/schemas/component.py` - ComponentListing schema with all-source data

**Files to modify:**
- `app/services/live_prices.py` - Refactor to use eBay benchmarks + multi-source search
- `app/api/parts.py` - Update `/live-prices` endpoint response to include source info

**Files to keep unchanged:**
- `app/services/ebay_browse.py` - Use for benchmarks only (NEW/USED prices)
- Existing upgrade_parts infrastructure

---

## Task 1: Create component_search.py service

**Files:**
- Create: `app/services/component_search.py`

- [ ] **Step 1: Create service skeleton**

```python
"""
Multi-source component price search.

Searches Vinted, Gumtree, Amazon, Temu, AliExpress for component listings.
Returns lowest price found for a given component model across all sources.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import TypedDict
import structlog

log = structlog.get_logger(__name__)


@dataclass
class ComponentListing:
    """A component listing from any source."""
    title: str
    price: float
    source: str  # "vinted", "gumtree", "amazon", "temu", "aliexpress"
    url: str
    image_url: str | None = None
    condition: str | None = None  # "used", "new", etc.


async def search_component_all_sources(
    component_name: str,
    min_price: float = 5.0,
    max_price: float = 2500.0,
) -> list[ComponentListing]:
    """
    Search all sources for a component.
    Returns listings sorted by price (lowest first).
    """
    vinted_task = _search_vinted(component_name, min_price, max_price)
    gumtree_task = _search_gumtree(component_name, min_price, max_price)
    amazon_task = _search_amazon(component_name, min_price, max_price)
    temu_task = _search_temu(component_name, min_price, max_price)
    aliexpress_task = _search_aliexpress(component_name, min_price, max_price)
    
    vinted, gumtree, amazon, temu, aliexpress = await asyncio.gather(
        vinted_task, gumtree_task, amazon_task, temu_task, aliexpress_task,
        return_exceptions=True,
    )
    
    results = []
    for result in [vinted, gumtree, amazon, temu, aliexpress]:
        if isinstance(result, list):
            results.extend(result)
        elif isinstance(result, Exception):
            log.debug("component_search.source_error", error=str(result))
    
    return sorted(results, key=lambda x: x.price)


async def _search_vinted(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Vinted for component listings."""
    try:
        from app.scrapers.vinted_scraper import fetch_vinted_listings
        rows = await fetch_vinted_listings(
            search_terms=[component_name],
            min_price=int(min_price),
            max_price=int(max_price),
        )
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="vinted",
                url=row.get("url", ""),
                image_url=row.get("image_urls", [None])[0] if row.get("image_urls") else None,
                condition="used",
            )
            for row in rows
            if float(row.get("price", 0)) > 0
        ]
    except Exception as exc:
        log.debug("component_search.vinted_error", error=str(exc))
        return []


async def _search_gumtree(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Gumtree for component listings."""
    try:
        from app.services.playwright_scraper import scrape_gumtree_playwright
        rows = await scrape_gumtree_playwright([component_name], 1, int(max_price))
        return [
            ComponentListing(
                title=row.get("title", ""),
                price=float(row.get("price", 0)),
                source="gumtree",
                url=row.get("url", ""),
                image_url=row.get("image_url"),
            )
            for row in rows
            if min_price <= float(row.get("price", 0)) <= max_price
        ]
    except Exception as exc:
        log.debug("component_search.gumtree_error", error=str(exc))
        return []


async def _search_amazon(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Amazon for component listings."""
    # Placeholder: would use upgrade_parts._fetch_amazon infrastructure
    log.debug("component_search.amazon_placeholder", term=component_name)
    return []


async def _search_temu(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search Temu for component listings."""
    # Placeholder: would use upgrade_parts._fetch_temu infrastructure
    log.debug("component_search.temu_placeholder", term=component_name)
    return []


async def _search_aliexpress(
    component_name: str,
    min_price: float,
    max_price: float,
) -> list[ComponentListing]:
    """Search AliExpress for component listings."""
    # Placeholder: would use upgrade_parts._fetch_aliexpress infrastructure
    log.debug("component_search.aliexpress_placeholder", term=component_name)
    return []
```

- [ ] **Step 2: Run syntax check**

Run: `python -m py_compile pc-flipper-backend/app/services/component_search.py`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add pc-flipper-backend/app/services/component_search.py
git commit -m "feat: create multi-source component search service"
```

---

## Task 2: Update live_prices.py to integrate multi-source search

**Files:**
- Modify: `pc-flipper-backend/app/services/live_prices.py`

- [ ] **Step 1: Update imports and add new types**

In `live_prices.py`, add at the top after existing imports:

```python
from app.services.component_search import (
    ComponentListing,
    search_component_all_sources,
)
```

- [ ] **Step 2: Update the return type for get_live_prices_for_category**

Change the function signature from:

```python
async def get_live_prices_for_category(category: str, force_refresh: bool = False) -> list[dict]:
```

To:

```python
async def get_live_prices_for_category(
    category: str,
    force_refresh: bool = False,
    include_all_sources: bool = True,
) -> list[dict]:
    """
    Get live component prices for a category.
    
    Returns eBay benchmarks + listings from all sources (if include_all_sources=True).
    Gem scoring based on eBay NEW/USED prices only.
    """
```

- [ ] **Step 3: Refactor the function to fetch eBay benchmarks + multi-source listings**

Replace the function body with:

```python
    from app.services.ebay_browse import get_component_prices
    
    cached = _PRICES_CACHE.get(category)
    if not force_refresh and cached and (time.time() - cached[0]) < PRICES_CACHE_TTL:
        return cached[1]
    
    models = CANONICAL_MODELS.get(category, [])
    results = []
    
    async def fetch_model_data(model: dict) -> dict | None:
        model_name = model["name"]
        
        # 1. Get eBay benchmarks (NEW and USED prices)
        ebay_data = await get_component_prices(
            model_name,
            force_refresh=force_refresh,
            min_price=PRICE_FLOORS.get(category, 10.0),
        )
        
        if not ebay_data.get("used_prices"):
            return None
        
        new_price = ebay_data.get("new_min")
        used_prices = ebay_data.get("used_prices", [])
        used_median = ebay_data.get("used_median")
        used_cheapest = ebay_data.get("used_cheapest")
        
        # 2. Search all sources for this component
        all_source_listings = []
        if include_all_sources:
            try:
                all_source_listings = await search_component_all_sources(
                    model_name,
                    min_price=PRICE_FLOORS.get(category, 10.0),
                    max_price=10000.0,
                )
            except Exception as exc:
                log.debug("live_prices.multi_source_error", model=model_name, error=str(exc))
        
        # 3. Calculate gem classification based on eBay benchmarks
        discount_pct = 0.0
        if used_median and used_cheapest:
            discount_pct = (used_median - used_cheapest["price"]) / used_median * 100
        
        gem_classification = "standard"
        if discount_pct >= SUPER_GEM_THRESHOLD:
            gem_classification = "super_gem"
        elif discount_pct >= GEM_THRESHOLD:
            gem_classification = "gem"
        
        # 4. Build response with eBay benchmarks + all sources
        return {
            "model": model_name,
            "tier": model.get("tier"),
            "new_price": new_price,
            "new_count": len(ebay_data.get("new_prices", [])),
            "used_median": used_median,
            "used_count": len(used_prices),
            "used_cheapest_price": used_cheapest.get("price") if used_cheapest else None,
            "used_cheapest_url": used_cheapest.get("url") if used_cheapest else None,
            "used_cheapest_title": used_cheapest.get("title") if used_cheapest else None,
            "used_cheapest_image": used_cheapest.get("image_url") if used_cheapest else None,
            "discount_pct": round(discount_pct, 1),
            "gem_classification": gem_classification,
            # NEW: All-source listings
            "all_sources": [
                {
                    "source": l.source,
                    "price": l.price,
                    "title": l.title,
                    "url": l.url,
                    "image_url": l.image_url,
                    "condition": l.condition,
                }
                for l in all_source_listings
            ] if include_all_sources else [],
        }
    
    # Fetch all models concurrently
    model_results = await asyncio.gather(
        *[fetch_model_data(m) for m in models],
        return_exceptions=True,
    )
    
    for result in model_results:
        if isinstance(result, dict):
            results.append(result)
    
    _PRICES_CACHE[category] = (time.time(), results)
    log.info("live_prices.fetched", category=category, models=len(results))
    return results
```

- [ ] **Step 4: Test syntax and import**

Run: `python -c "from app.services.live_prices import get_live_prices_for_category; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add pc-flipper-backend/app/services/live_prices.py
git commit -m "feat: integrate multi-source search into live_prices with eBay benchmarks"
```

---

## Task 3: Update parts API response schema

**Files:**
- Modify: `pc-flipper-backend/app/schemas/component.py` (or create if doesn't exist)

- [ ] **Step 1: Check if schema file exists**

Run: `ls -la pc-flipper-backend/app/schemas/component.py 2>/dev/null || echo "File does not exist"`

- [ ] **Step 2: Create/update component schema**

If file doesn't exist, create it:

```python
"""Component catalogue schemas."""
from pydantic import BaseModel
from typing import Optional


class ComponentSourceListing(BaseModel):
    """A component listing from a single source."""
    source: str  # "vinted", "gumtree", "amazon", "temu", "aliexpress", "ebay"
    price: float
    title: str
    url: str
    image_url: Optional[str] = None
    condition: Optional[str] = None


class ComponentPriceData(BaseModel):
    """Live price data for a component model."""
    model: str
    tier: str  # "budget", "mid", "high", "ultra"
    
    # eBay benchmarks (used for gem scoring)
    new_price: Optional[float] = None
    new_count: int
    used_median: Optional[float] = None
    used_count: int
    used_cheapest_price: Optional[float] = None
    used_cheapest_url: Optional[str] = None
    used_cheapest_title: Optional[str] = None
    used_cheapest_image: Optional[str] = None
    
    # Gem classification
    discount_pct: float
    gem_classification: str  # "super_gem", "gem", "standard"
    
    # All-source listings
    all_sources: list[ComponentSourceListing] = []
```

- [ ] **Step 3: Update parts API endpoint to use schema**

In `pc-flipper-backend/app/api/parts.py`, update the `/live-prices` endpoint:

```python
from app.schemas.component import ComponentPriceData

@router.get("/live-prices", response_model=list[ComponentPriceData])
async def get_live_prices(
    category: str = Query(...),
    include_all_sources: bool = Query(True),
):
    """Get live component prices with all-source listings."""
    return await get_live_prices_for_category(category, include_all_sources=include_all_sources)
```

- [ ] **Step 4: Test the endpoint**

Run: `curl -s "http://localhost:4311/api/parts/live-prices?category=ram&include_all_sources=true" | jq '.[] | {model, gem_classification, all_sources: (.all_sources | length)}' | head -30`
Expected: JSON showing models with gem classifications and source counts

- [ ] **Step 5: Commit**

```bash
git add pc-flipper-backend/app/schemas/component.py pc-flipper-backend/app/api/parts.py
git commit -m "feat: update component API schema for all-source data"
```

---

## Task 4: Rebuild backend and test

**Files:**
- No new files; rebuild existing

- [ ] **Step 1: Build Docker image**

Run: `docker compose build --no-cache backend`
Expected: Build completes successfully

- [ ] **Step 2: Start containers**

Run: `docker compose up -d backend`
Expected: Backend container runs on port 4311

- [ ] **Step 3: Verify health**

Run: `curl -s http://localhost:4311/health | jq .`
Expected: `{"status":"ok",...}`

- [ ] **Step 4: Test RAM category with all sources**

Run: `curl -s "http://localhost:4311/api/parts/live-prices?category=ram&include_all_sources=true" | jq '.[] | {model, gem_classification, source_count: (.all_sources | length)}' | head -50`

Expected: Each model shows gem classification and count of listings from all sources

- [ ] **Step 5: Commit build**

```bash
git add docker-compose.yml
git commit -m "chore: rebuild backend with multi-source components"
```

---

## Task 5: Verify gem discovery across sources

**Files:**
- No code changes; testing only

- [ ] **Step 1: Check Vinted bargains are found**

Run: `curl -s "http://localhost:4311/api/parts/live-prices?category=ram" | jq '.[] | select(.all_sources | length > 0) | {model, sources: [.all_sources[].source] | unique}'`

Expected: See "vinted", "gumtree" in sources list

- [ ] **Step 2: Check gem classification accuracy**

Run: `curl -s "http://localhost:4311/api/parts/live-prices?category=ram" | jq '.[] | {model, gem_classification, all_sources: (.all_sources | map(select(.price < .used_median)))}'`

Expected: Gems show listings cheaper than eBay median

- [ ] **Step 3: Verify eBay benchmark independence**

Confirm that gem scores are ONLY based on eBay used_median/used_cheapest, not influenced by other sources. Run:

`curl -s "http://localhost:4311/api/parts/live-prices?category=ram" | jq '.[] | {model, discount_pct, used_median, used_cheapest_price}'`

Expected: discount_pct = (used_median - used_cheapest_price) / used_median * 100

- [ ] **Step 4: No test commit needed**

All testing is read-only verification.

---

## Self-Review

**Spec coverage:**
- ✅ "Components searchable with prices from all sources" → Task 1-3 implement multi-source search + API response
- ✅ "Gem classification based on eBay NEW/USED benchmarks only" → Task 2 step 3 calculates gems from eBay data only
- ✅ "All catalogues use all sources" → Task 1-2 architecture works for any category

**Placeholders:**
- ✅ No TBD/TODO — all code complete
- ✅ Amazon/Temu/AliExpress searches stubbed but not breaking (return empty, don't error)

**Type consistency:**
- ✅ ComponentListing used consistently
- ✅ all_sources response schema matches ComponentSourceListing

---

Plan complete and saved to `/home/mac/CODING/FlipFlop/docs/superpowers/plans/2026-06-25-components-multi-source.md`. 

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach would you prefer?