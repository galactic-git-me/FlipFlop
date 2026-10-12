"""
Meshy Asset Download API.

Admin endpoints for downloading .glb files from Meshy CDN and storing locally.

Usage:
- POST /api/admin/meshy-assets/download - Download single asset
- POST /api/admin/meshy-assets/batch-download - Download multiple assets
- POST /api/admin/meshy-assets/download-from-approval - Download from approval queue
- GET /api/admin/meshy-assets/{id}/status - Check if asset needs download
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
from pathlib import Path

from app.database import get_db
from app.models.component_3d_asset import Component3DAsset, Component3DAssetStatus
from app.services.meshy_asset_downloader import MeshyAssetDownloader
from app.routes.admin_auth import get_current_admin
from structlog import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/api/admin/meshy-assets",
    tags=["admin", "meshy-assets"],
    dependencies=[Depends(get_current_admin)]
)


# Schemas

class DownloadAssetRequest(BaseModel):
    asset_id: int
    meshy_glb_url: str
    meshy_preview_url: Optional[str] = None
    force_redownload: bool = False
    update_status: bool = True
    new_status: str = "meshy_draft"  # After download


class BatchDownloadRequest(BaseModel):
    assets: List[dict] = Field(
        description="List of {asset_id, meshy_glb_url, meshy_preview_url}"
    )
    force_redownload: bool = False


class ApprovalDownloadRequest(BaseModel):
    asset_id: int
    approval_payload: dict = Field(
        description="Approval queue payload with meshy_glb_url and meshy_preview_url"
    )


class AssetStatusResponse(BaseModel):
    asset_id: int
    needs_download: bool
    current_glb_ref: Optional[str]
    is_meshy_url: bool
    status: str
    reason: Optional[str]


# Endpoints

@router.post("/download")
async def download_asset(
    request: DownloadAssetRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Download single .glb asset from Meshy CDN and store locally.
    
    Use this when:
    - Asset is approved and needs permanent storage
    - Meshy URL is about to expire
    - Promoting asset to production
    """
    try:
        # Get base upload directory
        base_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
        
        downloader = MeshyAssetDownloader(db, base_dir)
        
        # Download and store
        glb_url, preview_url = await downloader.download_and_store_asset(
            request.asset_id,
            request.meshy_glb_url,
            request.meshy_preview_url,
            request.force_redownload
        )
        
        # Update status if requested
        if request.update_status:
            try:
                status_enum = Component3DAssetStatus[request.new_status.upper()]
                await downloader.update_asset_status_after_download(
                    request.asset_id,
                    status_enum
                )
            except KeyError:
                log.warning(
                    "meshy_asset.invalid_status",
                    status=request.new_status,
                    asset_id=request.asset_id
                )
        
        log.info(
            "meshy_asset.download_api_success",
            asset_id=request.asset_id,
            admin=admin_email
        )
        
        return {
            "success": True,
            "asset_id": request.asset_id,
            "glb_url": glb_url,
            "preview_url": preview_url,
            "message": "Asset downloaded and stored successfully"
        }
        
    except Exception as e:
        log.error(
            "meshy_asset.download_api_failed",
            asset_id=request.asset_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.post("/batch-download")
async def batch_download_assets(
    request: BatchDownloadRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Download multiple assets in batch.
    
    Use this when:
    - Promoting multiple assets to production
    - Bulk download after approval queue processing
    """
    try:
        base_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
        downloader = MeshyAssetDownloader(db, base_dir)
        
        # Convert request to meshy_url_map
        meshy_url_map = {
            asset["asset_id"]: (
                asset["meshy_glb_url"],
                asset.get("meshy_preview_url")
            )
            for asset in request.assets
        }
        
        # Batch download
        results = await downloader.batch_download_assets(
            meshy_url_map,
            request.force_redownload
        )
        
        # Count successes/failures
        successful = [
            {"asset_id": k, "glb_url": v[0], "preview_url": v[1]}
            for k, v in results.items()
            if v[0] is not None
        ]
        
        failed = [
            {"asset_id": k, "reason": "Download failed"}
            for k, v in results.items()
            if v[0] is None
        ]
        
        log.info(
            "meshy_asset.batch_download_api_complete",
            total=len(request.assets),
            successful=len(successful),
            failed=len(failed),
            admin=admin_email
        )
        
        return {
            "success": True,
            "total": len(request.assets),
            "successful": successful,
            "failed": failed
        }
        
    except Exception as e:
        log.error("meshy_asset.batch_download_api_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch download failed: {str(e)}")


@router.post("/download-from-approval")
async def download_from_approval(
    request: ApprovalDownloadRequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Download asset from approval queue payload.
    
    Use this as part of approval flow:
    1. Michael approves 3D asset in admin
    2. This endpoint downloads from Meshy and stores locally
    3. Asset record updated with stable local URL
    """
    try:
        base_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
        downloader = MeshyAssetDownloader(db, base_dir)
        
        glb_url, preview_url = await downloader.download_from_approval_queue(
            request.asset_id,
            request.approval_payload
        )
        
        # Update status to MESHY_DRAFT after download
        await downloader.update_asset_status_after_download(
            request.asset_id,
            Component3DAssetStatus.MESHY_DRAFT
        )
        
        log.info(
            "meshy_asset.approval_download_success",
            asset_id=request.asset_id,
            admin=admin_email
        )
        
        return {
            "success": True,
            "asset_id": request.asset_id,
            "glb_url": glb_url,
            "preview_url": preview_url,
            "message": "Asset downloaded from approval queue"
        }
        
    except Exception as e:
        log.error(
            "meshy_asset.approval_download_failed",
            asset_id=request.asset_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Approval download failed: {str(e)}")


@router.get("/{asset_id}/status", response_model=AssetStatusResponse)
async def get_asset_download_status(
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Check if asset needs to be downloaded from Meshy.
    
    Returns:
    - needs_download: True if glb_ref is Meshy URL or missing
    - is_meshy_url: True if current glb_ref points to Meshy CDN
    - current_glb_ref: Current glb_ref value
    """
    stmt = select(Component3DAsset).where(Component3DAsset.id == asset_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    base_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
    downloader = MeshyAssetDownloader(db, base_dir)
    
    glb_ref = asset.glb_ref
    is_meshy = downloader.is_meshy_url(glb_ref) if glb_ref else False
    needs_download = not glb_ref or is_meshy
    
    reason = None
    if not glb_ref:
        reason = "No glb_ref set"
    elif is_meshy:
        reason = "glb_ref is Meshy CDN URL (will expire)"
    
    return AssetStatusResponse(
        asset_id=asset_id,
        needs_download=needs_download,
        current_glb_ref=glb_ref,
        is_meshy_url=is_meshy,
        status=asset.status.value if asset.status else "unknown",
        reason=reason
    )


@router.get("/check-all-meshy-urls")
async def check_all_meshy_urls(
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Find all assets still pointing to Meshy CDN URLs.
    
    Use this to identify assets that need to be downloaded and stored locally.
    """
    stmt = (
        select(Component3DAsset)
        .where(Component3DAsset.glb_ref.isnot(None))
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    assets = result.scalars().all()
    
    base_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
    downloader = MeshyAssetDownloader(db, base_dir)
    
    meshy_assets = []
    local_assets = []
    
    for asset in assets:
        if downloader.is_meshy_url(asset.glb_ref):
            meshy_assets.append({
                "asset_id": asset.id,
                "subject_type": asset.subject_type.value if asset.subject_type else None,
                "subject_id": asset.subject_id,
                "category": asset.category,
                "glb_ref": asset.glb_ref,
                "status": asset.status.value if asset.status else None
            })
        else:
            local_assets.append({
                "asset_id": asset.id,
                "glb_ref": asset.glb_ref
            })
    
    return {
        "total_checked": len(assets),
        "meshy_urls": len(meshy_assets),
        "local_urls": len(local_assets),
        "needs_download": meshy_assets
    }
