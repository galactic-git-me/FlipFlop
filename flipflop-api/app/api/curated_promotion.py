"""
Admin API for curated set promotion (dev → production).

Provides endpoints for:
- Exporting approved curated playbooks, pricing, photo packs, 3D assets
- Importing promotion manifests (with dry-run support)
- Viewing promotion history
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.curated_promotion import CuratedPromotion
from app.services.curated_promotion_service import CuratedPromotionService
from app.routes.admin_auth import get_current_admin
from structlog import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/api/admin/curated-promotion",
    tags=["admin", "curated-promotion"],
    dependencies=[Depends(get_current_admin)]
)


# Schemas

class ExportRequest(BaseModel):
    include_playbooks: bool = True
    include_pricing: bool = True
    include_photo_packs: bool = True
    include_3d_assets: bool = True
    notes: Optional[str] = None


class ImportRequest(BaseModel):
    manifest_path: Optional[str] = None  # If provided, load from file
    manifest: Optional[dict] = None  # Or provide manifest directly
    dry_run: bool = True
    verify_environment: bool = True
    notes: Optional[str] = None


class PromotionResponse(BaseModel):
    id: int
    promoted_at: datetime
    promoted_by: str
    source_environment: str
    target_environment: str
    playbooks_count: int
    pricing_count: int
    photo_packs_count: int
    assets_3d_count: int
    status: str
    notes: Optional[str]
    
    class Config:
        from_attributes = True


# Endpoints

@router.post("/export")
async def export_curated_set(
    request: ExportRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Export approved curated set from current environment.
    
    Creates a promotion manifest with all approved playbooks, pricing,
    photo packs, and 3D assets ready for import to production.
    
    **Dev sign-off only**: Michael's current Approve clicks are dev sign-off.
    After promote, only new/changed SKUs go through /approvals again.
    """
    try:
        service = CuratedPromotionService(source_environment="dev", target_environment="production")
        
        manifest = service.export_curated_set(
            include_playbooks=request.include_playbooks,
            include_pricing=request.include_pricing,
            include_photo_packs=request.include_photo_packs,
            include_3d_assets=request.include_3d_assets,
            promoted_by=admin_email
        )
        
        # Record the export in database
        promotion = CuratedPromotion(
            promoted_by=admin_email,
            source_environment="dev",
            target_environment="production",
            promotion_manifest=manifest,
            playbooks_count=manifest.get("playbooks_count", 0),
            pricing_count=manifest.get("pricing_count", 0),
            photo_packs_count=manifest.get("photo_packs_count", 0),
            assets_3d_count=manifest.get("assets_3d_count", 0),
            status="exported",
            notes=request.notes
        )
        
        db.add(promotion)
        await db.commit()
        await db.refresh(promotion)
        
        log.info(
            "curated_promotion.exported",
            promotion_id=promotion.id,
            promoted_by=admin_email,
            playbooks=manifest.get("playbooks_count"),
            pricing=manifest.get("pricing_count")
        )
        
        return {
            "success": True,
            "promotion_id": promotion.id,
            "manifest": manifest,
            "message": "Curated set exported successfully. Use /import with dry_run=true to preview, then dry_run=false to apply."
        }
        
    except Exception as e:
        log.error("curated_promotion.export_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/import")
async def import_curated_set(
    request: ImportRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Import a promotion manifest into current environment.
    
    **SAFETY**: Always run with dry_run=true first to preview changes!
    
    **Production check**: Verifies target environment is production before applying.
    Set verify_environment=false to bypass (not recommended).
    
    After successful import:
    - Curated builds are available on storefront immediately
    - BuildBot/PricingBot/MeshyBot daily updates write to prod admin
    - Only new/changed SKUs require re-approval
    """
    try:
        # Load manifest from promotion_id if provided
        if request.manifest_path:
            from pathlib import Path
            manifest_path = Path(request.manifest_path)
            if not manifest_path.exists():
                raise HTTPException(status_code=404, detail=f"Manifest file not found: {request.manifest_path}")
            import json
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        elif request.manifest:
            manifest = request.manifest
        else:
            raise HTTPException(status_code=400, detail="Either manifest_path or manifest must be provided")
        
        service = CuratedPromotionService(target_environment="production")
        
        success, result = service.import_curated_set(
            manifest,
            dry_run=request.dry_run,
            verify_environment=request.verify_environment
        )
        
        # Record import attempt
        if not request.dry_run:
            promotion = CuratedPromotion(
                promoted_by=admin_email,
                source_environment=manifest.get("source_environment", "dev"),
                target_environment="production",
                promotion_manifest=manifest,
                playbooks_count=manifest.get("playbooks_count", 0),
                pricing_count=manifest.get("pricing_count", 0),
                photo_packs_count=manifest.get("photo_packs_count", 0),
                assets_3d_count=manifest.get("assets_3d_count", 0),
                status="completed" if success else "failed",
                verification_checks=result.get("checks"),
                import_result=result.get("applied"),
                import_error="\n".join(result.get("errors", [])) if not success else None,
                notes=request.notes
            )
            
            db.add(promotion)
            await db.commit()
            await db.refresh(promotion)
            
            log.info(
                "curated_promotion.imported",
                promotion_id=promotion.id,
                success=success,
                dry_run=request.dry_run,
                promoted_by=admin_email
            )
        
        return {
            "success": success,
            "dry_run": request.dry_run,
            "result": result,
            "message": "DRY RUN: No changes applied" if request.dry_run else (
                "Import completed successfully" if success else "Import failed"
            )
        }
        
    except Exception as e:
        log.error("curated_promotion.import_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/history", response_model=List[PromotionResponse])
async def get_promotion_history(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get promotion history (most recent first)."""
    stmt = (
        select(CuratedPromotion)
        .order_by(desc(CuratedPromotion.promoted_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    promotions = result.scalars().all()
    
    return promotions


@router.get("/{promotion_id}")
async def get_promotion(
    promotion_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get details of a specific promotion."""
    stmt = select(CuratedPromotion).where(CuratedPromotion.id == promotion_id)
    result = await db.execute(stmt)
    promotion = result.scalar_one_or_none()
    
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    return {
        "id": promotion.id,
        "promoted_at": promotion.promoted_at,
        "promoted_by": promotion.promoted_by,
        "source_environment": promotion.source_environment,
        "target_environment": promotion.target_environment,
        "status": promotion.status,
        "playbooks_count": promotion.playbooks_count,
        "pricing_count": promotion.pricing_count,
        "photo_packs_count": promotion.photo_packs_count,
        "assets_3d_count": promotion.assets_3d_count,
        "manifest": promotion.promotion_manifest,
        "verification_checks": promotion.verification_checks,
        "import_result": promotion.import_result,
        "import_error": promotion.import_error,
        "notes": promotion.notes,
        "created_at": promotion.created_at,
        "updated_at": promotion.updated_at
    }


@router.post("/{promotion_id}/rollback")
async def rollback_promotion(
    promotion_id: int,
    reason: str,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a promotion as rolled back.
    
    Note: This does NOT automatically revert changes - it only marks the record.
    Manual reversion or re-import of previous state is required.
    """
    stmt = select(CuratedPromotion).where(CuratedPromotion.id == promotion_id)
    result = await db.execute(stmt)
    promotion = result.scalar_one_or_none()
    
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    promotion.status = "rolled_back"
    promotion.rolled_back_at = datetime.utcnow()
    promotion.rolled_back_by = admin_email
    promotion.rollback_reason = reason
    
    await db.commit()
    
    log.info(
        "curated_promotion.rolled_back",
        promotion_id=promotion_id,
        rolled_back_by=admin_email,
        reason=reason
    )
    
    return {
        "success": True,
        "message": "Promotion marked as rolled back. Manual reversion required."
    }
