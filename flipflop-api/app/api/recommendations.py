"""Guided recommendation foundation; no purchasing or quote side effects."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.recommendation_session import RecommendationSession
from app.services.performance_envelope import CustomerRequirements, build_envelope

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/envelope")
async def create_envelope(requirements: CustomerRequirements, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        envelope = build_envelope(requirements)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session = RecommendationSession(
        rules_version=envelope["envelope_version"],
        requirements_json=requirements.model_dump(),
        envelope_json=envelope,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {**envelope, "recommendation_session_id": session.id}
