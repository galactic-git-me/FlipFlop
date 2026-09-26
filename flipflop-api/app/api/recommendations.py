"""Guided recommendation foundation; no purchasing or quote side effects."""
from fastapi import APIRouter, HTTPException

from app.services.performance_envelope import CustomerRequirements, build_envelope

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/envelope")
def create_envelope(requirements: CustomerRequirements) -> dict:
    try:
        return build_envelope(requirements)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
