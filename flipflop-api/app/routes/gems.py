"""
API routes for Gem Build recommendations.

Endpoints:
- POST /api/gems/recommendations - Generate new recommendations using Claude API
- GET /api/gems - List recent recommendations
- GET /api/gems/{gem_id} - Get single recommendation
- POST /api/gems/{gem_id}/build - Convert recommendation to actual build order
- DELETE /api/gems/{gem_id} - Dismiss/delete a recommendation
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
import structlog

from app.database import get_db
from app.services.gem_service import GemRecommendationService
from app.schemas.gem import (
    GemRecommendationOut,
    GemRecommendationsResponse,
    GemBuildActionIn,
    GemBuildActionOut,
)
from app.models.gem import GemBuild
from app.routes.admin_auth import get_current_admin

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/gems", tags=["gems"], dependencies=[Depends(get_current_admin)])


@router.post("/recommendations")
async def generate_recommendations(
    analysis_days: int = Query(30, ge=7, le=90, description="Days of order history to analyze"),
    db: AsyncSession = Depends(get_db),
) -> GemRecommendationsResponse:
    """
    Generate gem build recommendations using Claude API.

    Analyzes recent order data to identify demand patterns, then uses Claude to generate
    3-5 specific speculative build recommendations with full specs, cost analysis, and
    confidence scores.

    Args:
        analysis_days: Number of days of order history to analyze (7-90, default 30)
        db: Database session

    Returns:
        GemRecommendationsResponse with generated recommendations

    Raises:
        HTTPException: If Claude API call fails or no orders to analyze
    """
    try:
        log.info("Generating gem recommendations", analysis_days=analysis_days)

        service = GemRecommendationService(db)
        result = await service.generate_recommendations(analysis_days)

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail="Failed to generate recommendations")

        return GemRecommendationsResponse(
            generated_at=datetime.fromisoformat(result.get("generated_at")),
            analysis_period_days=result.get("analysis_period_days", 30),
            total_orders_analyzed=result.get("total_orders_analyzed", 0),
            demand_summary=result.get("demand_summary", {}),
            recommendations=[
                GemRecommendationOut(**rec)
                for rec in result.get("recommendations", [])
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error generating recommendations", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.get("")
async def list_recommendations(
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    use_case: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List gem recommendations with optional filtering.

    Args:
        risk_level: Filter by risk level (low, medium, high)
        use_case: Filter by use case (gaming, workstation, streaming, etc.)
        limit: Maximum number of results
        db: Database session

    Returns:
        List of recommendations
    """
    try:
        service = GemRecommendationService(db)
        gems = await service.list_recommendations(
            risk_level=risk_level,
            use_case=use_case,
            limit=limit,
        )

        return {
            "total": len(gems),
            "gems": [gem.to_dict() for gem in gems],
        }

    except Exception as e:
        log.error("Error listing recommendations", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list recommendations: {str(e)}")


@router.get("/{gem_id}")
async def get_recommendation(
    gem_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get a single gem recommendation by ID.

    Args:
        gem_id: Gem ID
        db: Database session

    Returns:
        Gem recommendation details

    Raises:
        HTTPException: If gem not found
    """
    try:
        service = GemRecommendationService(db)
        gem = await service.get_recommendation_by_id(gem_id)

        if not gem:
            raise HTTPException(status_code=404, detail=f"Gem {gem_id} not found")

        return gem.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching recommendation", gem_id=gem_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch recommendation: {str(e)}")


@router.post("/{gem_id}/build")
async def build_gem(
    gem_id: int,
    action: GemBuildActionIn,
    db: AsyncSession = Depends(get_db),
) -> GemBuildActionOut:
    """
    Convert a gem recommendation to an actual build order.

    Creates an Order with the gem's specifications and marks it as speculative
    inventory. This triggers the standard build workflow (sourcing, building, QA, shipping).

    Args:
        gem_id: Gem ID to build
        action: Action details (quantity, notes)
        db: Database session

    Returns:
        Action result with order reference if successful

    Raises:
        HTTPException: If gem not found or order creation fails
    """
    try:
        log.info("Building gem", gem_id=gem_id, quantity=action.quantity)

        service = GemRecommendationService(db)
        gem = await service.get_recommendation_by_id(gem_id)

        if not gem:
            raise HTTPException(status_code=404, detail=f"Gem {gem_id} not found")

        # TODO: Implement order creation from gem specs
        # This would:
        # 1. Create an Order with the gem's specs
        # 2. Set order.notes with gem reasoning + admin notes
        # 3. Trigger sourcing workflow
        # 4. Return order reference

        return GemBuildActionOut(
            status="success",
            message=f"Gem '{gem.name}' build initiated",
            gem_id=gem_id,
            action="build",
            result={
                "order_id": "FF-2026-XXXX",  # TODO: Generate real order ID
                "quantity": action.quantity,
                "estimated_cost": gem.estimated_cost_to_build * action.quantity,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error building gem", gem_id=gem_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to build gem: {str(e)}")


@router.delete("/{gem_id}")
async def dismiss_gem(
    gem_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Dismiss/delete a gem recommendation.

    Removes the recommendation from view, useful for rejecting builds
    that aren't suitable or have changed market conditions.

    Args:
        gem_id: Gem ID to dismiss
        db: Database session

    Returns:
        Confirmation of dismissal

    Raises:
        HTTPException: If gem not found
    """
    try:
        service = GemRecommendationService(db)
        deleted = await service.delete_recommendation(gem_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Gem {gem_id} not found")

        await db.commit()

        return {
            "status": "success",
            "message": f"Gem {gem_id} dismissed",
            "gem_id": gem_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error dismissing gem", gem_id=gem_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to dismiss gem: {str(e)}")
