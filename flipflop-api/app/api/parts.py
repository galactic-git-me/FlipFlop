from collections import defaultdict
from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.part import Part, PartCategory, PartCondition
from app.schemas.part import PartOut, PartCreate
from app.schemas.component import ComponentPriceData
from app.services.part_gem_scorer import score_groups, GOOD_SOURCES
from app.services.part_gem_eval_queue import enqueue_part_for_claude
from app.services.component_models import CANONICAL_MODELS

router = APIRouter(prefix="/parts", tags=["parts"])

# Valid component categories for live pricing
_VALID_CATEGORIES = list(CANONICAL_MODELS.keys())


@router.get("/", response_model=list[PartOut])
async def get_parts(
    category: PartCategory | None = Query(None),
    condition: PartCondition | None = Query(None),
    theme: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Part).where(Part.is_active == True)
    if category:
        q = q.where(Part.category == category)
    if condition:
        q = q.where(Part.condition == condition)
    if theme:
        q = q.where(Part.theme == theme)
    # Exclude cases from the general parts list unless explicitly requested
    if not category:
        q = q.where(Part.category != PartCategory.case)
    q = q.order_by(Part.category, Part.price)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/cases", response_model=list[PartOut])
async def get_cases(
    theme: str | None = Query(None),
    source_site: str | None = Query(None),
    max_price: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Part).where(Part.is_active == True, Part.category == PartCategory.case)
    if theme:
        q = q.where(Part.theme == theme)
    if source_site:
        q = q.where(Part.source_site == source_site)
    if max_price:
        q = q.where(Part.price <= max_price)
    q = q.order_by(Part.price)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/themes", response_model=list[str])
async def get_case_themes(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import distinct
    result = await db.execute(
        select(distinct(Part.theme)).where(
            Part.category == PartCategory.case,
            Part.theme != None,
            Part.is_active == True,
        )
    )
    return [r for r in result.scalars().all() if r]


@router.get("/grouped", response_model=list[dict])
async def get_parts_grouped(
    category: PartCategory | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Return parts grouped by name, with cheapest price and all sources listed.
    Each group has: name, category, cheapest_price, cheapest_source, cheapest_url,
    all_prices (list of {source, price, url, condition}).
    """
    q = select(Part).where(Part.is_active == True)
    if category:
        q = q.where(Part.category == category)
    else:
        q = q.where(Part.category != PartCategory.case)
    q = q.order_by(Part.category, Part.name, Part.price)
    result = await db.execute(q)
    all_parts = result.scalars().all()

    # Group by normalized name (lowercase, strip trailing spaces/model variants)
    groups: dict[str, list] = defaultdict(list)
    for p in all_parts:
        # Normalize key: category + lowercase name
        key = f"{p.category}::{p.name.lower().strip()}"
        groups[key].append(p)

    output = []
    for key, parts in groups.items():
        # Find cheapest overall price across all sources
        priced = [p for p in parts if p.price is not None]
        if not priced:
            continue
        cheapest = min(priced, key=lambda p: p.price)
        good_priced = [p for p in priced if p.source_site in GOOD_SOURCES]
        cheapest_good = min(good_priced, key=lambda p: p.price) if good_priced else None
        # Merge stored AI verdict from any judged part in the group
        claude_verdict   = next((p.claude_verdict   for p in parts if p.claude_verdict   is not None), None)
        claude_reasoning = next((p.claude_reasoning for p in parts if p.claude_reasoning is not None), None)
        claude_judged    = any(p.claude_judged_at is not None for p in parts)
        output.append({
            "name": parts[0].name,
            "category": parts[0].category.value,
            "image_url": next((p.image_url for p in parts if p.image_url), None),
            "cheapest_price": cheapest.price,
            "cheapest_source": cheapest.source_site,
            "cheapest_url": cheapest.source_url,
            "cheapest_good_price": cheapest_good.price if cheapest_good else None,
            "cheapest_good_source": cheapest_good.source_site if cheapest_good else None,
            "cheapest_good_url": cheapest_good.source_url if cheapest_good else None,
            "price_used": next((p.price_used for p in parts if p.price_used), None),
            "price_refurb": next((p.price_refurb for p in parts if p.price_refurb), None),
            "price_new": next((p.price_new for p in parts if p.price_new), None),
            "last_price_update": max(
                (p.last_price_update for p in parts if p.last_price_update),
                default=None,
            ),
            "all_sources": [
                {
                    "source": p.source_site,
                    "price": p.price,
                    "url": p.source_url,
                    "condition": p.condition,
                }
                for p in sorted(priced, key=lambda p: p.price or 999)
            ],
            # Gem fields — populated by scorer below; AI fields from stored verdicts
            "gem_classification": None,
            "gem_score": None,
            "claude_verdict":   claude_verdict,
            "claude_reasoning": claude_reasoning,
            "_claude_judged":   claude_judged,   # internal flag for enqueue logic
        })

    # Apply per-category tier-aware gem scoring
    scores = score_groups(output)
    for g in output:
        key = f"{g['category']}::{g['name']}"
        if key in scores:
            g["gem_classification"] = scores[key]["gem_classification"]
            g["gem_score"] = scores[key]["gem_score"]

    # Enqueue rule-based gem candidates that haven't been AI-evaluated yet
    for g in output:
        if g["gem_classification"] is not None and not g["_claude_judged"]:
            enqueue_part_for_claude(g["name"], str(g["category"]))

    # Strip internal flag before serialising
    for g in output:
        g.pop("_claude_judged", None)

    output.sort(key=lambda g: (g["category"], g["cheapest_price"] or 999))
    return output


@router.get("/catalogue")
async def get_parts_catalogue(db: AsyncSession = Depends(get_db)):
    """
    Return the canonical component model price matrix.

    Response shape:
    {
      "gpu": [
        {
          "model": "RTX 3060 12GB",
          "tier": "budget",
          "ebay_used": 82.0,
          "bargain_hardware": 99.0,
          "new_retail": 230.0,
          "best_price": 82.0,
          "best_source": "eBay UK",
          "claude_verdict": "GEM",
          "claude_reasoning": "..."
        },
        ...
      ],
      "cpu": [...],
      ...
    }
    """
    from app.services.component_models import CANONICAL_MODELS, model_tier

    all_model_names = [m["name"] for models in CANONICAL_MODELS.values() for m in models]

    result = await db.execute(
        select(Part).where(
            Part.name.in_(all_model_names),
            Part.is_active == True,
        )
    )
    parts_by_name: dict[str, Part] = {p.name: p for p in result.scalars().all()}

    catalogue: dict[str, list[dict]] = {}
    for cat, models in CANONICAL_MODELS.items():
        entries = []
        for m in models:
            p = parts_by_name.get(m["name"])
            ebay_used      = p.price_used    if p else None
            bh_refurb      = p.price_refurb  if p else None
            new_retail     = p.price_new     if p else None
            claude_verdict  = p.claude_verdict   if p else None
            claude_reasoning = p.claude_reasoning if p else None

            candidates = [x for x in [ebay_used, bh_refurb, new_retail] if x]
            best_price = min(candidates) if candidates else None
            if best_price == ebay_used:
                best_source = "eBay UK"
            elif best_price == bh_refurb:
                best_source = "BargainHardware"
            elif best_price == new_retail:
                best_source = "New Retail"
            else:
                best_source = None

            entries.append({
                "model":            m["name"],
                "tier":             m["tier"],
                "ebay_used":        ebay_used,
                "bargain_hardware": bh_refurb,
                "new_retail":       new_retail,
                "best_price":       best_price,
                "best_source":      best_source,
                "claude_verdict":   claude_verdict,
                "claude_reasoning": claude_reasoning,
                "has_data":         p is not None,
            })
        catalogue[cat] = entries
    return catalogue


@router.post("/paste-scan")
async def paste_scan(body: dict, db: AsyncSession = Depends(get_db)):
    """
    Parse raw text pasted from an eBay or other marketplace search results page.
    The LLM extracts component listings, evaluates each one, and saves any gems
    to the parts catalogue.

    Body: { "text": "...", "source": "eBay UK" }
    Response: { "parsed": N, "gems": N, "super_gems": N, "items": [...] }
    """
    from datetime import datetime
    import json, re, asyncio
    from app.config import get_settings

    raw_text = str(body.get("text", "")).strip()
    source = str(body.get("source", "eBay UK")).strip() or "eBay UK"

    if not raw_text:
        return {"parsed": 0, "gems": 0, "super_gems": 0, "items": [], "error": "No text provided"}
    if len(raw_text) > 50_000:
        raw_text = raw_text[:50_000]

    SYSTEM = """You are an expert UK PC component market analyst.

You will receive raw text scraped or copied from a marketplace search page (eBay, Gumtree, etc.).

STEP 1 — Extract every individual PC component listing you can find in the text. Parse the name, price in GBP, and condition from each listing.

ONLY extract genuine desktop PC components: GPU, CPU, RAM, NVMe/SATA SSD, ATX/SFX PSU, desktop motherboard, CPU cooler.

IGNORE completely: game discs, USB drives, USB hubs, laptop/notebook parts, peripherals (mice/keyboards/monitors), gaming controllers, want ads, shipping cost strings, brand names without prices, accessories.

STEP 2 — For each extracted component, evaluate it against current UK eBay market prices:

GPU: RTX 3060 12GB £130-160, RTX 3060 Ti £155-190, RTX 3070 £160-200, RTX 3070 Ti £195-235, RTX 3080 10GB £200-260, RTX 4060 £220-260, RTX 4060 Ti £280-330, RTX 4070 £330-390, RX 6600 £110-140, RX 6600 XT £125-155, RX 6700 XT £155-195, RTX 2070 Super £100-135, RTX 2080 Ti £165-220
CPU: i3-12100 £65-85, i5-10400 £50-75, i5-12400 £85-110, i5-12600K £100-135, i5-13600K £130-165, i7-12700K £150-195, i9-12900K £190-240, Ryzen 5 5600 £65-90, Ryzen 5 5600X £75-100, Ryzen 7 5700X £95-120, Ryzen 7 7700X £175-215, Ryzen 9 5900X £145-190, Ryzen 9 7950X £400-500
RAM: 16GB DDR4 kit £12-22, 32GB DDR4 kit £22-40, 64GB DDR4 kit £50-80, 16GB DDR5 kit £25-45, 32GB DDR5 kit £50-90
SSD: 500GB NVMe £25-45, 1TB NVMe £45-75, 2TB NVMe £80-130, 500GB SATA £15-30, 1TB SATA £25-45
PSU: 650W 80+ Bronze £30-55, 650W 80+ Gold £50-85, 750W 80+ Gold £65-100, 850W 80+ Gold £75-120
Motherboard: B550 ATX AM4 £50-80, X570 ATX AM4 £75-120, B660 ATX LGA1700 £70-110, Z690 ATX LGA1700 £100-160, Z790 ATX LGA1700 £130-200
Cooler: Hyper 212 £12-22, Noctua NH-U12S £30-50, Noctua NH-D15 £55-85, 240mm AIO £40-80

VERDICT:
- GEM: Price is 30%+ below current UK eBay used market value
- GOOD: Price is 15-29% below market
- REJECT: Within 15% of market, above market, not a PC component, or cannot be confidently identified

Respond with ONLY a valid JSON array — no markdown, no explanation outside the JSON:
[
  {
    "name": "RTX 3060 12GB",
    "category": "gpu",
    "price": 89.99,
    "condition": "used",
    "verdict": "GEM",
    "market_price_estimate": 145,
    "confidence": 0.85,
    "reasoning": "RTX 3060 12GB typically £130-160 on eBay UK. At £90 this is 38% below midpoint — clear gem."
  }
]

If no PC components are found in the text, return an empty array: []"""

    user_msg = f"MARKETPLACE TEXT TO PARSE:\n\n{raw_text}"
    raw_response: str | None = None
    model_used = "none"
    _s = get_settings()

    if _s.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=_s.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw_response = resp.content[0].text if resp.content else None
            model_used = "claude-haiku-4-5"
        except Exception:
            pass

    if not raw_response and _s.openrouter_api_key:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {_s.openrouter_api_key}",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "PC Flipper Paste Scanner",
                    },
                    json={
                        "model": _s.openrouter_primary_model or "anthropic/claude-haiku-4-5",
                        "messages": [
                            {"role": "system", "content": SYSTEM},
                            {"role": "user",   "content": user_msg},
                        ],
                        "max_tokens": 4096,
                    },
                )
                resp.raise_for_status()
                raw_response = resp.json()["choices"][0]["message"]["content"]
                model_used = "openrouter"
        except Exception:
            pass

    if not raw_response and _s.ollama_base_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{_s.ollama_base_url}/api/chat",
                    json={
                        "model": _s.ollama_model,
                        "messages": [
                            {"role": "system", "content": SYSTEM},
                            {"role": "user",   "content": user_msg},
                        ],
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                raw_response = resp.json().get("message", {}).get("content")
                model_used = f"ollama/{_s.ollama_model}"
        except Exception:
            pass

    if not raw_response:
        return {"parsed": 0, "gems": 0, "super_gems": 0, "items": [], "error": "AI backend unavailable"}

    # Parse LLM response
    match = re.search(r'\[[\s\S]*\]', raw_response)
    if not match:
        return {"parsed": 0, "gems": 0, "super_gems": 0, "items": [], "error": "Could not parse AI response"}

    try:
        items = json.loads(match.group())
    except json.JSONDecodeError:
        return {"parsed": 0, "gems": 0, "super_gems": 0, "items": [], "error": "Invalid JSON from AI"}

    if not isinstance(items, list):
        items = []

    # Category name → PartCategory enum
    _CAT_MAP = {
        "gpu": PartCategory.gpu, "cpu": PartCategory.cpu,
        "ram": PartCategory.ram, "ssd": PartCategory.ssd,
        "psu": PartCategory.psu, "motherboard": PartCategory.motherboard,
        "cooler": PartCategory.cooler,
    }

    _VALID_VERDICTS = {"GEM", "GOOD", "REJECT"}
    saved_gems, saved_super_gems = 0, 0
    output_items = []

    now = datetime.utcnow()

    for raw in items:
        if not isinstance(raw, dict):
            continue
        name      = str(raw.get("name") or "").strip()
        cat_str   = str(raw.get("category") or "").strip().lower()
        verdict   = str(raw.get("verdict") or "REJECT").upper().strip()
        price     = float(raw.get("price") or 0)
        market    = float(raw.get("market_price_estimate") or 0)
        confidence = float(raw.get("confidence") or 0.5)
        reasoning  = str(raw.get("reasoning") or "")
        condition_raw = str(raw.get("condition") or "used").lower()

        if not name or verdict not in _VALID_VERDICTS or price <= 0:
            continue

        cat_enum = _CAT_MAP.get(cat_str)
        if not cat_enum:
            continue

        if condition_raw == "new":
            condition = PartCondition.new
        elif condition_raw in ("refurb", "refurbished"):
            condition = PartCondition.refurb
        else:
            condition = PartCondition.used

        # Classify as super_gem if 35%+ below market, gem if 15%+
        gem_classification = None
        if market > 0:
            discount = (market - price) / market * 100
            if discount >= 35 and verdict in ("GEM",):
                gem_classification = "super_gem"
            elif discount >= 15 and verdict in ("GEM", "GOOD"):
                gem_classification = "gem"

        item_out = {
            "name": name,
            "category": cat_str,
            "price": price,
            "condition": condition_raw,
            "verdict": verdict,
            "market_price_estimate": market,
            "confidence": confidence,
            "reasoning": reasoning,
            "gem_classification": gem_classification,
            "source": source,
        }
        output_items.append(item_out)

        # Save GEM/GOOD items to the parts catalogue
        if verdict in ("GEM", "GOOD"):
            existing = (await db.execute(
                select(Part).where(
                    Part.name == name,
                    Part.source_site == source,
                    Part.category == cat_enum,
                )
            )).scalar_one_or_none()

            if existing:
                existing.price         = price
                existing.price_used    = price if condition == PartCondition.used else existing.price_used
                existing.claude_verdict    = verdict
                existing.claude_reasoning  = reasoning
                existing.claude_confidence = confidence
                existing.claude_judged_at  = now
                existing.last_price_update = now
            else:
                db.add(Part(
                    name=name,
                    category=cat_enum,
                    condition=condition,
                    source_site=source,
                    price=price,
                    price_used=(price if condition == PartCondition.used else None),
                    resale_value_add=0.0,
                    claude_verdict=verdict,
                    claude_reasoning=reasoning,
                    claude_confidence=confidence,
                    claude_judged_at=now,
                    last_price_update=now,
                ))
                if verdict == "GEM":
                    saved_gems += 1
                    if gem_classification == "super_gem":
                        saved_super_gems += 1

    await db.commit()

    non_rejected = [i for i in output_items if i["verdict"] != "REJECT"]
    gems = [i for i in output_items if i["verdict"] == "GEM"]
    super_gems = [i for i in output_items if i.get("gem_classification") == "super_gem"]

    return {
        "parsed":      len(output_items),
        "kept":        len(non_rejected),
        "gems":        len(gems),
        "super_gems":  len(super_gems),
        "model_used":  model_used,
        "items":       output_items,
    }


@router.get("/live-prices", response_model=list[ComponentPriceData])
async def get_live_prices(
    category: Literal["gpu", "cpu", "ram", "ssd", "psu", "motherboard", "cooler"] = Query(..., description="Component category"),
    refresh: bool = Query(False),
    include_all_sources: bool = Query(True),
):
    """Get live component prices with all-source listings.

    Returns eBay benchmark prices and listings from all sources (Vinted, Gumtree, Amazon, Temu, AliExpress).
    Gem classification is based on eBay NEW/USED prices only.

    - **category**: Component category (gpu, cpu, ram, ssd, psu, motherboard, cooler)
    - **include_all_sources**: Include listings from all sources; if False, only return eBay benchmarks

    Returns list of ComponentPriceData with fields:
    - model, tier, new_price, new_count, used_median, used_count
    - used_cheapest_price/url/title/image (eBay cheapest used listing)
    - discount_pct, gem_classification (based on eBay benchmarks only)
    - all_sources: list of listings from all sources
    """
    from app.services.live_prices import get_live_prices_for_category
    return await get_live_prices_for_category(category, force_refresh=refresh, include_all_sources=include_all_sources)


@router.get("/{part_id}", response_model=PartOut)
async def get_part(part_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    part = await db.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    return part


@router.post("/", response_model=PartOut, status_code=201)
async def create_part(body: PartCreate, db: AsyncSession = Depends(get_db)):
    part = Part(**body.model_dump())
    db.add(part)
    await db.flush()
    await db.refresh(part)
    return part
