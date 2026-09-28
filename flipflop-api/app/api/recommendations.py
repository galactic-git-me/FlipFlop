"""Guided recommendation foundation; no purchasing or quote side effects."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.recommendation_session import RecommendationSession
from app.services.performance_envelope import CustomerRequirements, build_envelope
from app.services.recommendation_catalogue import (
    find_catalogue_bom_candidates,
    find_ready_to_ship_matches,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/envelope")
async def create_envelope(requirements: CustomerRequirements, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        envelope = build_envelope(requirements)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    requirements_snapshot = requirements.model_dump()
    requirements_snapshot["playbook_version"] = envelope["playbook_version"]
    catalogue_bom_candidates = await find_catalogue_bom_candidates(
        db, envelope, envelope["performance_options"], requirements.condition_policy
    )
    ready_to_ship_matches = await find_ready_to_ship_matches(db, envelope, requirements.condition_policy)
    decision_snapshot = {
        **envelope,
        "catalogue_bom_candidates": catalogue_bom_candidates,
        "ready_to_ship_matches": ready_to_ship_matches,
    }
    session = RecommendationSession(
        rules_version=envelope["envelope_version"],
        requirements_json=requirements_snapshot,
        envelope_json=decision_snapshot,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {**decision_snapshot, "recommendation_session_id": session.id}
