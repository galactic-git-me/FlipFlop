from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.part import Part, PartCategory, PartCondition
from app.schemas.part import PartOut, PartCreate
from app.services.part_gem_scorer import score_groups, GOOD_SOURCES
from app.services.part_gem_eval_queue import enqueue_part_for_claude

router = APIRouter(prefix="/parts", tags=["parts"])


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
