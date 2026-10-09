"""
Curated Build Availability API.

Public endpoints:
- Get build availability status
- Get available builds by tier
- Get component BOM with availability

Admin endpoints:
- Check/refresh availability
- Manage SKUs (add backup, swap, deactivate)
- View swap history
- Force availability override
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

from app.database import get_db
from app.models.curated_component_sku import (
    CuratedComponentSKU,
    CuratedBuildAvailability,
    SKUSwapEvent,
    SKUAvailabilityStatus
)
from app.services.curated_availability_service import (
    CuratedAvailabilityService,
    check_all_builds_availability,
    get_oos_builds
)
from app.routes.admin_auth import get_current_admin
from structlog import get_logger

log = get_logger(__name__)

# Public router (no auth required)
public_router = APIRouter(
    prefix="/api/public/curated-availability",
    tags=["public", "curated-availability"]
)

# Admin router (auth required)
admin_router = APIRouter(
    prefix="/api/admin/curated-availability",
    tags=["admin", "curated-availability"],
    dependencies=[Depends(get_current_admin)]
)


# Schemas

class ComponentAvailability(BaseModel):
    slot: str
    title: str
    sku_source: str  # "primary" or "backup"
    is_backup: bool
    availability_status: str
    vendor: Optional[str]
    checked_at: Optional[str]


class BuildAvailabilityResponse(BaseModel):
    build_id: str
    is_available: bool
    using_backup_count: int
    components: Dict[str, ComponentAvailability]
    last_checked_at: Optional[datetime]
    hidden_reason: Optional[str]


class SKUResponse(BaseModel):
    id: int
    component_slot: str
    is_primary: bool
    priority: int
    component_title: str
    availability_status: str
    estimated_stock_level: Optional[int]
    preferred_vendor: Optional[str]
    vendor_sku: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


class AddBackupSKURequest(BaseModel):
    build_id: str
    component_slot: str
    component_title: str
    priority: int = Field(ge=1, description="1=first backup, 2=second backup, etc.")
    preferred_vendor: Optional[str] = None
    vendor_sku: Optional[str] = None
    vendor_url: Optional[str] = None
    target_cost_gbp: Optional[float] = None
    compatibility_notes: Optional[Dict] = None
    requires_approval_for_swap: bool = False
    requires_remesh: bool = False


class SwapSKURequest(BaseModel):
    build_id: str
    component_slot: str
    to_sku_id: int
    reason: str
    notes: Optional[str] = None


# Public Endpoints

@public_router.get("/build/{build_id}")
async def get_build_availability(
    build_id: str,
    check_live: bool = Query(False, description="Check live vendor availability"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get availability status and BOM for a curated build.
    
    Returns:
    - Overall availability (can we sell it?)
    - Per-component status
    - Which SKUs are active (primary or backup)
    - Backup usage count
    
    Shop behavior:
    - is_available=false → don't show "Add to Cart"
    - using_backup_count > 0 → show info banner about component substitution
    """
    service = CuratedAvailabilityService(db)
    
    bom = await service.get_build_bom_with_availability(build_id, check_live)
    
    return bom


@public_router.get("/available-builds")
async def get_available_builds(
    segment: Optional[str] = None,
    tier: Optional[str] = None,
    check_live: bool = Query(False, description="Check live availability"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of currently available builds, optionally filtered by segment/tier.
    
    Only returns builds where is_available=true.
    """
    # Get all build availabilities
    stmt = select(CuratedBuildAvailability).where(
        CuratedBuildAvailability.is_available == True
    )
    
    result = await db.execute(stmt)
    availabilities = result.scalars().all()
    
    # If check_live, refresh each build's availability
    if check_live:
        service = CuratedAvailabilityService(db)
        for avail in availabilities:
            await service.update_build_availability(avail.curated_build_id, check_live=True)
    
    # Filter by segment/tier if provided (would need to join with build definitions)
    # For now, return all available builds
    
    return {
        "available_builds": [a.curated_build_id for a in availabilities],
        "count": len(availabilities),
        "checked_live": check_live
    }


@public_router.get("/out-of-stock")
async def get_out_of_stock_builds(db: AsyncSession = Depends(get_db)):
    """Get list of builds currently out of stock."""
    oos_builds = await get_oos_builds(db)
    
    return {
        "out_of_stock_builds": oos_builds,
        "count": len(oos_builds)
    }


# Admin Endpoints

@admin_router.post("/refresh-all")
async def refresh_all_availability(
    check_live: bool = Query(True, description="Check live vendor availability"),
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh availability for all curated builds.
    
    Use this to:
    - Force a fresh check of all vendor availability
    - Update after bulk SKU changes
    - Recover from stale availability data
    """
    log.info("curated_availability.refresh_all_start", admin=admin_email, check_live=check_live)
    
    availability_map = await check_all_builds_availability(db, check_live)
    
    available_count = sum(1 for available in availability_map.values() if available)
    oos_count = len(availability_map) - available_count
    
    log.info(
        "curated_availability.refresh_all_complete",
        total=len(availability_map),
        available=available_count,
        oos=oos_count
    )
    
    return {
        "success": True,
        "total_builds": len(availability_map),
        "available": available_count,
        "out_of_stock": oos_count,
        "availability_map": availability_map
    }


@admin_router.get("/build/{build_id}/skus", response_model=List[SKUResponse])
async def get_build_skus(
    build_id: str,
    component_slot: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all SKUs (primary + backups) for a build, optionally filtered by slot.
    """
    stmt = select(CuratedComponentSKU).where(
        CuratedComponentSKU.curated_build_id == build_id
    )
    
    if component_slot:
        stmt = stmt.where(CuratedComponentSKU.component_slot == component_slot)
    
    stmt = stmt.order_by(
        CuratedComponentSKU.component_slot.asc(),
        CuratedComponentSKU.priority.asc()
    )
    
    result = await db.execute(stmt)
    skus = result.scalars().all()
    
    return skus


@admin_router.post("/build/{build_id}/add-backup-sku")
async def add_backup_sku(
    build_id: str,
    request: AddBackupSKURequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a backup SKU for a component slot.
    
    BuildBot typically provides these via approval queue.
    Manual additions require Michael approval in /approvals for permanent replacements.
    """
    # Validate build_id matches request
    if build_id != request.build_id:
        raise HTTPException(status_code=400, detail="build_id mismatch")
    
    # Check if SKU with this priority already exists
    stmt = select(CuratedComponentSKU).where(
        and_(
            CuratedComponentSKU.curated_build_id == build_id,
            CuratedComponentSKU.component_slot == request.component_slot,
            CuratedComponentSKU.priority == request.priority
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"SKU with priority {request.priority} already exists for {request.component_slot}"
        )
    
    # Create new backup SKU
    sku = CuratedComponentSKU(
        curated_build_id=build_id,
        component_slot=request.component_slot,
        is_primary=False,  # Backups are never primary
        priority=request.priority,
        component_title=request.component_title,
        preferred_vendor=request.preferred_vendor,
        vendor_sku=request.vendor_sku,
        vendor_url=request.vendor_url,
        target_cost_gbp=request.target_cost_gbp,
        compatibility_notes=request.compatibility_notes,
        requires_approval_for_swap=request.requires_approval_for_swap,
        requires_remesh=request.requires_remesh,
        approved_by=admin_email,
        approved_at=datetime.utcnow()
    )
    
    db.add(sku)
    await db.commit()
    await db.refresh(sku)
    
    log.info(
        "curated_availability.backup_sku_added",
        build_id=build_id,
        slot=request.component_slot,
        priority=request.priority,
        title=request.component_title,
        admin=admin_email
    )
    
    return {
        "success": True,
        "sku_id": sku.id,
        "message": "Backup SKU added successfully"
    }


@admin_router.post("/build/{build_id}/swap-sku")
async def swap_sku(
    build_id: str,
    request: SwapSKURequest,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually swap a component SKU.
    
    Use this to:
    - Force swap to backup when primary OOS
    - Swap back to primary when stock returns
    - Test backup configurations
    
    Permanent replacements require Michael approval in /approvals.
    """
    if build_id != request.build_id:
        raise HTTPException(status_code=400, detail="build_id mismatch")
    
    service = CuratedAvailabilityService(db)
    
    # Get current active SKU for this slot
    current_sku = await service.get_available_sku_for_slot(
        build_id,
        request.component_slot,
        check_live=False
    )
    
    # Perform swap
    swap_event = await service.swap_sku(
        build_id=build_id,
        slot=request.component_slot,
        from_sku_id=current_sku.id if current_sku else None,
        to_sku_id=request.to_sku_id,
        reason=request.reason,
        approved_by=admin_email
    )
    
    # Update build availability
    await service.update_build_availability(build_id, check_live=False)
    
    return {
        "success": True,
        "swap_event_id": swap_event.id,
        "message": "SKU swapped successfully"
    }


@admin_router.get("/build/{build_id}/swap-history")
async def get_swap_history(
    build_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get SKU swap history for a build."""
    stmt = (
        select(SKUSwapEvent)
        .where(SKUSwapEvent.curated_build_id == build_id)
        .order_by(desc(SKUSwapEvent.swapped_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    swaps = result.scalars().all()
    
    return {
        "build_id": build_id,
        "swaps": [
            {
                "id": swap.id,
                "component_slot": swap.component_slot,
                "swap_reason": swap.swap_reason,
                "swap_source": swap.swap_source,
                "approved_by": swap.approved_by,
                "swapped_at": swap.swapped_at
            }
            for swap in swaps
        ],
        "count": len(swaps)
    }


@admin_router.post("/sku/{sku_id}/deactivate")
async def deactivate_sku(
    sku_id: int,
    reason: str,
    admin_email: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate a SKU (mark as no longer usable).
    
    Use when:
    - Component is discontinued
    - Compatibility issue discovered
    - Permanent replacement approved
    """
    sku = await db.get(CuratedComponentSKU, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    
    sku.is_active = False
    sku.deactivated_at = datetime.utcnow()
    sku.deactivation_reason = reason
    
    await db.commit()
    
    log.info(
        "curated_availability.sku_deactivated",
        sku_id=sku_id,
        build_id=sku.curated_build_id,
        slot=sku.component_slot,
        reason=reason,
        admin=admin_email
    )
    
    # Update build availability after deactivation
    service = CuratedAvailabilityService(db)
    await service.update_build_availability(sku.curated_build_id, check_live=False)
    
    return {
        "success": True,
        "message": "SKU deactivated successfully"
    }


@admin_router.post("/sku/{sku_id}/check-availability")
async def check_sku_availability(
    sku_id: int,
    force_refresh: bool = Query(True, description="Force fresh check"),
    db: AsyncSession = Depends(get_db)
):
    """Check availability for a specific SKU."""
    sku = await db.get(CuratedComponentSKU, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    
    service = CuratedAvailabilityService(db)
    status, stock_level = await service.check_sku_availability(sku, force_refresh)
    
    return {
        "sku_id": sku_id,
        "component_title": sku.component_title,
        "availability_status": status.value,
        "estimated_stock_level": stock_level,
        "checked_at": sku.availability_checked_at.isoformat() if sku.availability_checked_at else None
    }
