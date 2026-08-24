"""
Build Wizard API — orchestrates the multi-agent build pipeline.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any

from app.database import get_db
from app.models.playbook import Playbook, PlaybookStatus
from app.models.listing import Listing, Classification, ListingStatus
from app.services.build_wizard import run_build_wizard, run_planner

router = APIRouter(prefix="/build-wizard", tags=["build-wizard"])


class GenerateRequest(BaseModel):
    playbook_id: int
    budget: float
    user_notes: str = ""
    priorities: list[str] = []
    constraints: list[str] = []


class PlanRequest(BaseModel):
    build: dict
    intent: dict


class GemMatrixRequest(BaseModel):
    budget: float
    user_notes: str = ""
    priorities: list[str] = []
    constraints: list[str] = []
    gem_limit: int = 4
    playbook_limit: int = 4
    listing_id: int | None = None


def _listing_lane(listing: Listing) -> str:
    title = (listing.title or "").lower()
    condition = (listing.condition or "").lower()
    if any(k in title for k in ["motherboard", "mainboard", "cpu", "processor", "gpu", "graphics card", "ram", "ddr4", "ddr5"]):
        return "individual_parts"
    if "workstation" in title:
        if "refurb" in title or "refurbished" in title or "manufacturer refurbished" in condition:
            return "refurb_workstation"
        return "preowned_workstation"
    if any(k in title for k in ["desktop", "tower", "gaming pc", "pc"]):
        if "refurb" in title or "refurbished" in title or "manufacturer refurbished" in condition:
            return "refurb_desktop"
        return "preowned_desktop"
    return "mixed_pc"


def _seller_label(listing: Listing) -> str:
    st = (listing.seller_type or "").lower()
    if st == "refurb_shop":
        return "refurb_business"
    if st in {"shop", "flipper"}:
        return "business_seller"
    if st == "private":
        return "private_seller"
    return "unknown_seller"


def _playbook_build_from_gem(playbook: Playbook, listing: Listing) -> dict[str, Any]:
    upgrades = []
    upgrade_cost = 0.0
    required = (playbook.upgrade_strategy or {}).get("required", []) or []
    optional = (playbook.upgrade_strategy or {}).get("optional", []) or []

    for item in required:
        cost = float(item.get("max_cost") or 0)
        upgrade_cost += cost
        upgrades.append({
            "role": str(item.get("component", "upgrade")),
            "item": str(item.get("target", "required upgrade")),
            "cost_estimate": cost,
            "source": "market_scrape",
            "required": True,
        })
    for item in optional[:2]:
        cost = float(item.get("max_cost") or 0)
        upgrades.append({
            "role": str(item.get("component", "upgrade")),
            "item": str(item.get("target", "optional upgrade")),
            "cost_estimate": cost,
            "source": "market_scrape",
            "required": False,
        })

    base_cost = float(listing.price or 0)
    total_cost = base_cost + upgrade_cost
    target_profit = float((playbook.profit_strategy or {}).get("target_profit_gbp") or 120)
    resale = float(listing.estimated_resale or (total_cost + target_profit))
    estimated_profit = float((listing.estimated_profit if listing.estimated_profit is not None else (resale - total_cost)))
    if estimated_profit < 0:
        estimated_profit = 0.0
    margin = (estimated_profit / total_cost * 100.0) if total_cost > 0 else 0.0

    feedback = float(listing.seller_feedback_pct or 0)
    if listing.seller_type in {"shop", "refurb_shop"} and feedback >= 95:
        risk = "low"
    elif listing.seller_type == "private":
        risk = "high"
    else:
        risk = "medium"

    demand = "good"
    use_case = playbook.target_use_case or ""
    title = (listing.title or "").lower()
    if use_case in {"gaming", "ai_workstation"} and any(k in title for k in ["rtx", "ryzen", "i7", "i9", "workstation"]):
        demand = "excellent"
    elif use_case == "budget" and base_cost <= 300:
        demand = "excellent"
    elif use_case == "office" and any(k in title for k in ["office", "desktop", "mini pc"]):
        demand = "good"
    elif use_case == "workstation" and "workstation" in title:
        demand = "excellent"
    else:
        demand = "moderate"

    req = playbook.requirements or {}
    missing = []
    if req.get("gpu_required") and not listing.gpu:
        missing.append("GPU")
    if req.get("ram_min_gb") and (listing.ram_gb or 0) < int(req.get("ram_min_gb")):
        missing.append(f"RAM >= {req.get('ram_min_gb')}GB")
    if req.get("storage_min_gb") and (listing.storage_gb or 0) < int(req.get("storage_min_gb")):
        missing.append(f"Storage >= {req.get('storage_min_gb')}GB")

    validation_score = max(20.0, min(98.0, 62.0 + (listing.gem_score or 0) * 0.25 - (len(missing) * 10)))
    decision = "BUY" if (estimated_profit >= target_profit * 0.7 and not missing) else ("WATCH" if estimated_profit > 40 else "SKIP")

    return {
        "id": f"gem-{listing.id}-pb-{playbook.id}",
        "name": f"{playbook.name} · {listing.title[:44]}",
        "base_spec": listing.title,
        "base_cost": base_cost,
        "upgrades": upgrades,
        "total_cost": total_cost,
        "estimated_resale": resale,
        "estimated_profit": estimated_profit,
        "profit_margin_pct": margin,
        "risk": risk,
        "demand_fit": demand,
        "why": f"{decision}: lane={_listing_lane(listing)} · seller={_seller_label(listing)} · missing={', '.join(missing) if missing else 'none'}",
        "sell_platform": str((playbook.profit_strategy or {}).get("sell_platform") or "eBay"),
        "sell_price_target": resale,
        "valid": decision != "SKIP",
        "validation_score": validation_score,
        "rejection_reason": "" if decision != "SKIP" else "Low projected edge for this playbook",
        "rank": 0,
        "gem_id": listing.id,
        "playbook_id": playbook.id,
        "playbook_name": playbook.name,
        "seller_type": listing.seller_type,
        "seller_label": _seller_label(listing),
        "sourcing_lane": _listing_lane(listing),
        "listing_url": listing.url,
    }


@router.post("/generate")
async def generate_builds(body: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """
    Run the full Wizard → Composer → Validator → Ranker pipeline.
    Returns up to 5 ranked, validated builds.
    """
    playbook = await db.get(Playbook, body.playbook_id)
    if not playbook:
        raise HTTPException(404, "Playbook not found")

    playbook_dict = {
        "id": playbook.id,
        "name": playbook.name,
        "emoji": playbook.emoji or "🔧",
        "target_use_case": playbook.target_use_case,
        "requirements": playbook.requirements or {},
        "search_strategy": playbook.search_strategy or {},
        "upgrade_strategy": playbook.upgrade_strategy or {},
        "profit_strategy": playbook.profit_strategy or {},
        "upsell_strategy": playbook.upsell_strategy or {},
    }

    result = await run_build_wizard(
        playbook=playbook_dict,
        budget=body.budget,
        user_notes=body.user_notes,
        priorities=body.priorities,
        constraints=body.constraints,
    )
    return result


@router.post("/generate-gem-matrix")
async def generate_gem_matrix(body: GemMatrixRequest, db: AsyncSession = Depends(get_db)):
    """
    Build wizard-first matrix: for each top gem, propose one build per active/candidate playbook.
    """
    pb_query = await db.execute(
        select(Playbook).where(Playbook.status == PlaybookStatus.ACTIVE).order_by(Playbook.id).limit(max(1, body.playbook_limit))
    )
    playbooks = pb_query.scalars().all()
    if not playbooks:
        raise HTTPException(404, "No active playbooks found")

    if body.listing_id is not None:
        listing = await db.get(Listing, body.listing_id)
        if not listing or listing.status != ListingStatus.active:
            raise HTTPException(404, f"Listing {body.listing_id} not found or not active.")
        gems = [listing]
    else:
        gem_query = await db.execute(
            select(Listing)
            .where(
                Listing.status == ListingStatus.active,
                Listing.classification.in_([Classification.gem, Classification.amazing_gem]),
            )
            .order_by(Listing.gem_score.desc(), Listing.last_seen_at.desc())
            .limit(max(1, body.gem_limit))
        )
        gems = gem_query.scalars().all()
        if not gems:
            raise HTTPException(404, "No gem listings found. Run a market scan first.")

    builds = []
    for gem in gems:
        for pb in playbooks:
            b = _playbook_build_from_gem(pb, gem)
            if b["total_cost"] <= body.budget * 1.25:
                builds.append(b)

    builds.sort(key=lambda x: (x["estimated_profit"], x["validation_score"]), reverse=True)
    for i, b in enumerate(builds, start=1):
        b["rank"] = i

    intent = {
        "playbook_name": "Gem Matrix",
        "playbook_emoji": "🧭",
        "budget_max": body.budget,
        "target_use_case": "multi",
        "priorities": body.priorities,
        "constraints": body.constraints,
        "user_notes": body.user_notes,
    }
    return {
        "intent": intent,
        "builds": builds[: max(1, body.gem_limit * body.playbook_limit)],
        "rejected_count": 0,
        "attempts": 1,
        "matrix_meta": {
            "gem_count": len(gems),
            "playbook_count": len(playbooks),
            "coverage": "one build per gem per playbook",
        },
    }


@router.post("/plan")
async def generate_plan(body: PlanRequest):
    """
    Run the Planner agent for the user's selected build.
    Returns a step-by-step purchase plan.
    """
    result = await run_planner(body.build, body.intent)
    return result


@router.get("/playbooks")
async def list_wizard_playbooks(db: AsyncSession = Depends(get_db)):
    """Return active playbooks for the wizard playbook-picker."""
    result = await db.execute(
        select(Playbook).where(Playbook.status == PlaybookStatus.ACTIVE)
        .order_by(Playbook.id)
    )
    playbooks = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "emoji": p.emoji or "🔧",
            "description": p.what_they_use_it_for or "",
            "target_use_case": p.target_use_case,
            "status": p.status.value if isinstance(p.status, PlaybookStatus) else str(p.status),
            "profit_strategy": p.profit_strategy or {},
        }
        for p in playbooks
    ]
