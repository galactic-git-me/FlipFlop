"""
Build Wizard API — orchestrates the multi-agent build pipeline.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.playbook import Playbook
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
        select(Playbook).where(Playbook.status.in_(["active", "candidate"]))
        .order_by(Playbook.id)
    )
    playbooks = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "emoji": p.emoji or "🔧",
            "description": p.description or "",
            "target_use_case": p.target_use_case,
            "status": p.status,
            "profit_strategy": p.profit_strategy or {},
        }
        for p in playbooks
    ]
