"""
Admin and bot API endpoints for unified approval workflows.

Bots submit items for approval; Michael reviews in the admin tool.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, func, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routes.admin_auth import get_current_admin
from app.models.admin_user import AdminUser
from app.models.bot_approval import (
    BotApprovalQueue, ApprovalType, ApprovalStatus,
    PlaybookProposalExtended, PricingProposal
)
from app.models.component_3d_asset import Component3DAsset, Component3DAssetStatus, AssetSubjectType


# Admin router (requires authentication)
router = APIRouter(
    prefix="/bot-approvals",
    tags=["bot-approvals"],
    dependencies=[Depends(get_current_admin)]
)

# Bot ingest router (internal/authenticated - extend as needed)
bot_router = APIRouter(prefix="/bot-ingest", tags=["bot-ingest"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PhotoPackSubmission(BaseModel):
    """MeshyBot submits 4 reference photos for 3D generation."""
    sku: str
    category: str  # case / component
    image_urls: List[str] = Field(..., min_length=4, max_length=4)
    argb_flags: Optional[dict] = None
    lighting_zones: Optional[dict] = None
    submitted_by: str = "MeshyBot"


class Model3DSubmission(BaseModel):
    """MeshyBot submits generated .glb for approval."""
    sku: str
    category: str
    glb_url: str
    preview_image_url: Optional[str] = None
    poly_count: Optional[int] = None
    file_size_kb: Optional[int] = None
    source_image_refs: Optional[List[str]] = None
    submitted_by: str = "MeshyBot"


class PlaybookComponent(BaseModel):
    """Component in a playbook BOM."""
    sku: str
    category: str
    vendor: Optional[str] = None
    title: Optional[str] = None
    cost_gbp: float
    lead_time_days: Optional[int] = None
    argb_flags: Optional[dict] = None


class PlaybookUpsell(BaseModel):
    """Upsell option in a playbook."""
    category: str
    from_sku: str
    to_sku: str
    delta_cost_gbp: float
    delta_sell_gbp: Optional[float] = None
    reason: Optional[str] = None


class PlaybookSubmission(BaseModel):
    """BuildBot submits a curated playbook proposal."""
    playbook_id: str
    customer_type: Optional[str] = None
    budget_tier: Optional[str] = None  # Value / Balanced / Performance
    core_components: List[PlaybookComponent]
    upsells: Optional[List[PlaybookUpsell]] = None
    allowed_cases: Optional[List[str]] = None
    sell_price_gbp: Optional[float] = None
    total_cost_gbp: Optional[float] = None
    est_margin_pct: Optional[float] = None
    submitted_by: str = "BuildBot"


class PrebuiltSubmission(BaseModel):
    """BuildBot submits a pre-built BOM (e.g. Prometheus)."""
    build_id: str
    build_name: str
    components: List[PlaybookComponent]
    total_cost_gbp: float
    sell_price_gbp: Optional[float] = None
    est_margin_pct: Optional[float] = None
    submitted_by: str = "BuildBot"


class PricingSubmission(BaseModel):
    """PricingBot submits a price proposal."""
    target_type: str  # playbook / prebuilt
    target_id: str
    sell_price_gbp: float
    total_cost_gbp: float
    est_margin_pct: float
    delivery_buffer_gbp: Optional[float] = None
    upsell_delta_sell_gbp: Optional[float] = None
    upsell_delta_cost_gbp: Optional[float] = None
    pricing_rationale: Optional[str] = None
    market_comparison: Optional[dict] = None
    submitted_by: str = "PricingBot"


class ApprovalDecision(BaseModel):
    """Admin approval/rejection decision."""
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class ApprovalItemOut(BaseModel):
    """Unified approval item response."""
    id: int
    approval_type: str
    status: str
    subject_sku: Optional[str]
    subject_category: Optional[str]
    playbook_id: Optional[str]
    payload: dict
    sell_price_gbp: Optional[float]
    total_cost_gbp: Optional[float]
    est_margin_pct: Optional[float]
    submitted_by: Optional[str]
    submitted_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ApprovalSummary(BaseModel):
    """Summary counts for admin dashboard."""
    total_pending: int
    pending_photo_packs: int
    pending_models_3d: int
    pending_playbooks: int
    pending_prebuilts: int
    pending_pricing: int


# ─── Admin Endpoints ──────────────────────────────────────────────────────────

@router.get("/summary", response_model=ApprovalSummary)
async def get_approval_summary(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Get summary counts of pending approvals."""
    result = await db.execute(
        select(
            BotApprovalQueue.approval_type,
            func.count(BotApprovalQueue.id).label("count")
        )
        .where(BotApprovalQueue.status == ApprovalStatus.PENDING)
        .group_by(BotApprovalQueue.approval_type)
    )
    
    counts = {row.approval_type.value: row.count for row in result}
    
    return ApprovalSummary(
        total_pending=sum(counts.values()),
        pending_photo_packs=counts.get("photo_pack", 0),
        pending_models_3d=counts.get("model_3d", 0),
        pending_playbooks=counts.get("playbook", 0),
        pending_prebuilts=counts.get("prebuilt", 0),
        pending_pricing=counts.get("pricing", 0),
    )


@router.get("/pending", response_model=List[ApprovalItemOut])
async def get_pending_approvals(
    approval_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Get pending approval items, optionally filtered by type."""
    query = select(BotApprovalQueue).where(
        BotApprovalQueue.status == ApprovalStatus.PENDING
    )
    
    if approval_type:
        try:
            query = query.where(BotApprovalQueue.approval_type == ApprovalType(approval_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid approval_type: {approval_type}")
    
    query = query.order_by(BotApprovalQueue.submitted_at).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return [
        ApprovalItemOut(
            id=item.id,
            approval_type=item.approval_type.value,
            status=item.status.value,
            subject_sku=item.subject_sku,
            subject_category=item.subject_category,
            playbook_id=item.playbook_id,
            payload=item.payload,
            sell_price_gbp=item.sell_price_gbp,
            total_cost_gbp=item.total_cost_gbp,
            est_margin_pct=item.est_margin_pct,
            submitted_by=item.submitted_by,
            submitted_at=item.submitted_at,
            reviewed_by=item.reviewed_by,
            reviewed_at=item.reviewed_at,
            rejection_reason=item.rejection_reason,
            notes=item.notes,
        )
        for item in items
    ]


@router.get("/history", response_model=List[ApprovalItemOut])
async def get_approval_history(
    status: Optional[str] = Query(None),
    approval_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Get historical approvals/rejections."""
    query = select(BotApprovalQueue).where(
        or_(
            BotApprovalQueue.status == ApprovalStatus.APPROVED,
            BotApprovalQueue.status == ApprovalStatus.REJECTED
        )
    )
    
    if status:
        try:
            query = query.where(BotApprovalQueue.status == ApprovalStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    if approval_type:
        try:
            query = query.where(BotApprovalQueue.approval_type == ApprovalType(approval_type))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid approval_type: {approval_type}")
    
    query = query.order_by(BotApprovalQueue.reviewed_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return [
        ApprovalItemOut(
            id=item.id,
            approval_type=item.approval_type.value,
            status=item.status.value,
            subject_sku=item.subject_sku,
            subject_category=item.subject_category,
            playbook_id=item.playbook_id,
            payload=item.payload,
            sell_price_gbp=item.sell_price_gbp,
            total_cost_gbp=item.total_cost_gbp,
            est_margin_pct=item.est_margin_pct,
            submitted_by=item.submitted_by,
            submitted_at=item.submitted_at,
            reviewed_by=item.reviewed_by,
            reviewed_at=item.reviewed_at,
            rejection_reason=item.rejection_reason,
            notes=item.notes,
        )
        for item in items
    ]


@router.post("/{item_id}/decision")
async def make_approval_decision(
    item_id: int,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Approve or reject a pending item."""
    result = await db.execute(
        select(BotApprovalQueue).where(BotApprovalQueue.id == item_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Approval item not found")
    
    if item.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Item already {item.status.value}"
        )
    
    # Update approval item
    new_status = ApprovalStatus.APPROVED if decision.action == "approve" else ApprovalStatus.REJECTED
    item.status = new_status
    item.reviewed_by = admin.email
    item.reviewed_at = datetime.utcnow()
    item.rejection_reason = decision.rejection_reason
    item.notes = decision.notes
    
    # For approved items, create/update the actual resource
    if decision.action == "approve":
        await _handle_approval_action(db, item)
    
    await db.commit()
    
    return {
        "status": "success",
        "item_id": item_id,
        "action": decision.action,
        "new_status": new_status.value
    }


async def _handle_approval_action(db: AsyncSession, item: BotApprovalQueue):
    """Handle side effects when an item is approved."""
    if item.approval_type == ApprovalType.MODEL_3D:
        # Approved 3D model: create Component3DAsset or update existing to VALIDATED
        payload = item.payload
        
        # Check if asset already exists
        existing = await db.execute(
            select(Component3DAsset).where(
                and_(
                    Component3DAsset.subject_type == AssetSubjectType.CASE,
                    Component3DAsset.glb_ref == payload.get("glb_url")
                )
            )
        )
        asset = existing.scalar_one_or_none()
        
        if asset:
            # Update existing to VALIDATED
            asset.status = Component3DAssetStatus.VALIDATED
            asset.is_active = True
        else:
            # Create new Component3DAsset
            # Note: This is simplified; real implementation would need subject_id lookup
            pass
    
    elif item.approval_type == ApprovalType.PLAYBOOK:
        # Approved playbook: could update Playbook table status to ACTIVE
        pass
    
    elif item.approval_type == ApprovalType.PRICING:
        # Approved pricing: update playbook/prebuilt sell price
        pass


# ─── Bot Ingest Endpoints ─────────────────────────────────────────────────────

@bot_router.post("/photo-pack")
async def submit_photo_pack(
    submission: PhotoPackSubmission,
    db: AsyncSession = Depends(get_db),
):
    """MeshyBot submits a photo pack for approval."""
    item = BotApprovalQueue(
        approval_type=ApprovalType.PHOTO_PACK,
        status=ApprovalStatus.PENDING,
        subject_sku=submission.sku,
        subject_category=submission.category,
        payload={
            "sku": submission.sku,
            "category": submission.category,
            "image_urls": submission.image_urls,
            "argb_flags": submission.argb_flags,
            "lighting_zones": submission.lighting_zones,
        },
        submitted_by=submission.submitted_by,
        submitted_at=datetime.utcnow(),
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return {"status": "success", "id": item.id, "message": "Photo pack submitted for approval"}


@bot_router.post("/model-3d")
async def submit_3d_model(
    submission: Model3DSubmission,
    db: AsyncSession = Depends(get_db),
):
    """MeshyBot submits a 3D model for approval."""
    item = BotApprovalQueue(
        approval_type=ApprovalType.MODEL_3D,
        status=ApprovalStatus.PENDING,
        subject_sku=submission.sku,
        subject_category=submission.category,
        payload={
            "sku": submission.sku,
            "category": submission.category,
            "glb_url": submission.glb_url,
            "preview_image_url": submission.preview_image_url,
            "poly_count": submission.poly_count,
            "file_size_kb": submission.file_size_kb,
            "source_image_refs": submission.source_image_refs or [],
        },
        submitted_by=submission.submitted_by,
        submitted_at=datetime.utcnow(),
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return {"status": "success", "id": item.id, "message": "3D model submitted for approval"}


@bot_router.post("/playbook")
async def submit_playbook(
    submission: PlaybookSubmission,
    db: AsyncSession = Depends(get_db),
):
    """BuildBot submits a playbook proposal."""
    item = BotApprovalQueue(
        approval_type=ApprovalType.PLAYBOOK,
        status=ApprovalStatus.PENDING,
        playbook_id=submission.playbook_id,
        payload={
            "playbook_id": submission.playbook_id,
            "customer_type": submission.customer_type,
            "budget_tier": submission.budget_tier,
            "core_components": [c.model_dump() for c in submission.core_components],
            "upsells": [u.model_dump() for u in (submission.upsells or [])],
            "allowed_cases": submission.allowed_cases or [],
        },
        sell_price_gbp=submission.sell_price_gbp,
        total_cost_gbp=submission.total_cost_gbp,
        est_margin_pct=submission.est_margin_pct,
        submitted_by=submission.submitted_by,
        submitted_at=datetime.utcnow(),
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return {"status": "success", "id": item.id, "message": "Playbook submitted for approval"}


@bot_router.post("/prebuilt")
async def submit_prebuilt(
    submission: PrebuiltSubmission,
    db: AsyncSession = Depends(get_db),
):
    """BuildBot submits a pre-built BOM."""
    item = BotApprovalQueue(
        approval_type=ApprovalType.PREBUILT,
        status=ApprovalStatus.PENDING,
        playbook_id=submission.build_id,
        payload={
            "build_id": submission.build_id,
            "build_name": submission.build_name,
            "components": [c.model_dump() for c in submission.components],
        },
        sell_price_gbp=submission.sell_price_gbp,
        total_cost_gbp=submission.total_cost_gbp,
        est_margin_pct=submission.est_margin_pct,
        submitted_by=submission.submitted_by,
        submitted_at=datetime.utcnow(),
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return {"status": "success", "id": item.id, "message": "Pre-built submitted for approval"}


@bot_router.post("/pricing")
async def submit_pricing_proposal(
    submission: PricingSubmission,
    db: AsyncSession = Depends(get_db),
):
    """PricingBot submits a pricing proposal."""
    item = BotApprovalQueue(
        approval_type=ApprovalType.PRICING,
        status=ApprovalStatus.PENDING,
        playbook_id=submission.target_id,
        payload={
            "target_type": submission.target_type,
            "target_id": submission.target_id,
            "pricing_rationale": submission.pricing_rationale,
            "market_comparison": submission.market_comparison or {},
            "delivery_buffer_gbp": submission.delivery_buffer_gbp,
            "upsell_delta_sell_gbp": submission.upsell_delta_sell_gbp,
            "upsell_delta_cost_gbp": submission.upsell_delta_cost_gbp,
        },
        sell_price_gbp=submission.sell_price_gbp,
        total_cost_gbp=submission.total_cost_gbp,
        est_margin_pct=submission.est_margin_pct,
        submitted_by=submission.submitted_by,
        submitted_at=datetime.utcnow(),
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return {"status": "success", "id": item.id, "message": "Pricing proposal submitted for approval"}
