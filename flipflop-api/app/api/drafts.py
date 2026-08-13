"""Saved draft builds — customers can save an unfinished playbook
configuration and resume it later. Always re-priced live from the real
catalogue on read, never trusting a stored total."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.customer import Customer
from app.models.draft_build import DraftBuild
from app.routes.auth import get_current_user
from app.schemas.draft import DraftBuildIn, DraftBuildOut, DraftBuildSlotOut
from app.services.playbook_pricing import InvalidBuildError, price_playbook_build

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


async def _price_draft(db: AsyncSession, draft: DraftBuild) -> DraftBuildOut:
    config = draft.config_json or {}
    priced = await price_playbook_build(
        db,
        playbook_id=draft.playbook_id,
        slot_selections={int(k): v for k, v in config.get("slot_selections", {}).items()},
        case_id=config.get("case_id"),
    )
    return DraftBuildOut(
        id=draft.id,
        playbook_id=draft.playbook_id,
        playbook_name=priced.playbook_name or "Unknown playbook",
        name=draft.name,
        slots=[
            DraftBuildSlotOut(
                slot_id=s.slot_id, slot_type=s.slot_type, variant_id=s.variant_id,
                title=s.title, price=s.price,
            )
            for s in priced.slots
        ],
        case_id=priced.case_id,
        case_name=priced.case_name,
        case_price=priced.case_price,
        chosen_week=config.get("chosen_week"),
        priced_total=priced.total,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.post("", response_model=DraftBuildOut, status_code=201)
async def create_draft(
    request: DraftBuildIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        # Validate against the real catalogue before saving anything.
        await price_playbook_build(
            db,
            playbook_id=request.playbook_id,
            slot_selections=request.slot_selections,
            case_id=request.case_id,
        )
    except InvalidBuildError as e:
        raise HTTPException(status_code=400, detail=str(e))

    draft = DraftBuild(
        customer_id=customer.id,
        playbook_id=request.playbook_id,
        name=request.name,
        config_json={
            "slot_selections": request.slot_selections,
            "case_id": request.case_id,
            "chosen_week": request.chosen_week,
        },
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return await _price_draft(db, draft)


@router.get("/me", response_model=list[DraftBuildOut])
async def list_my_drafts(
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DraftBuild)
        .where(DraftBuild.customer_id == customer.id)
        .order_by(DraftBuild.updated_at.desc())
    )
    drafts = result.scalars().all()

    out: list[DraftBuildOut] = []
    for draft in drafts:
        try:
            out.append(await _price_draft(db, draft))
        except InvalidBuildError as e:
            # A previously-valid selection can go stale if the catalogue
            # changes (a variant delisted, etc) — skip rather than 500 the
            # whole list; the draft itself is untouched and still owned.
            log.warning("draft.stale_selection", draft_id=draft.id, error=str(e))
    return out


@router.get("/{draft_id}", response_model=DraftBuildOut)
async def get_draft(
    draft_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DraftBuild).where(DraftBuild.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Draft not found")
    try:
        return await _price_draft(db, draft)
    except InvalidBuildError as e:
        raise HTTPException(status_code=409, detail=f"Draft selection is no longer valid: {e}")


@router.patch("/{draft_id}", response_model=DraftBuildOut)
async def update_draft(
    draft_id: int,
    request: DraftBuildIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DraftBuild).where(DraftBuild.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Draft not found")

    try:
        await price_playbook_build(
            db,
            playbook_id=request.playbook_id,
            slot_selections=request.slot_selections,
            case_id=request.case_id,
        )
    except InvalidBuildError as e:
        raise HTTPException(status_code=400, detail=str(e))

    draft.playbook_id = request.playbook_id
    draft.name = request.name
    draft.config_json = {
        "slot_selections": request.slot_selections,
        "case_id": request.case_id,
        "chosen_week": request.chosen_week,
    }
    await db.commit()
    await db.refresh(draft)
    return await _price_draft(db, draft)


@router.delete("/{draft_id}", status_code=204)
async def delete_draft(
    draft_id: int,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DraftBuild).where(DraftBuild.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Draft not found")
    await db.delete(draft)
    await db.commit()
