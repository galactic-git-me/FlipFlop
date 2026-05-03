"""
Playbook CRUD + proposal/approval workflow.

All status transitions (candidate→active, active→deprecated) go through
PlaybookProposal.  A proposal must be explicitly approved before any change
lands on the Playbook row.  This keeps humans in the loop for every strategy
mutation while the AI can freely propose changes.

Routes:
  GET    /playbooks              → list all playbooks
  POST   /playbooks              → create a new candidate playbook directly
  GET    /playbooks/{id}         → get single playbook
  PUT    /playbooks/{id}         → update playbook fields directly
  DELETE /playbooks/{id}         → hard delete (dev only; use RETIRE in prod)

  GET    /playbooks/proposals    → list all pending proposals
  POST   /playbooks/proposals    → create a proposal (system or user)
  POST   /playbooks/proposals/{id}/approve  → approve & apply
  POST   /playbooks/proposals/{id}/reject   → reject with reason

  GET    /playbooks/active-keywords  → flat list of search keywords from all
                                        active playbooks (used by scraper)
"""
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.playbook import Playbook, PlaybookProposal
from app.schemas.playbook import (
    PlaybookCreate, PlaybookUpdate, PlaybookOut,
    ProposalCreate, ProposalResolve, ProposalOut,
)

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/playbooks", tags=["playbooks"])


# ─── Playbook CRUD ────────────────────────────────────────────────────────────

@router.get("", response_model=list[PlaybookOut])
async def list_playbooks(
    status: Optional[str] = Query(None, description="Filter by status: candidate|active|deprecated"),
    db: AsyncSession = Depends(get_db),
):
    q = select(Playbook).order_by(Playbook.created_at.desc())
    if status:
        q = q.where(Playbook.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=PlaybookOut, status_code=201)
async def create_playbook(body: PlaybookCreate, db: AsyncSession = Depends(get_db)):
    pb = Playbook(**body.model_dump())
    db.add(pb)
    await db.flush()
    await db.refresh(pb)
    log.info("playbook.created", id=pb.id, name=pb.name)
    return pb


@router.get("/active-keywords", response_model=list[str])
async def get_active_keywords(db: AsyncSession = Depends(get_db)):
    """Return a flat, deduplicated list of search keywords from all active playbooks."""
    result = await db.execute(
        select(Playbook).where(Playbook.status == "active")
    )
    playbooks = result.scalars().all()
    keywords: set[str] = set()
    for pb in playbooks:
        strat = pb.search_strategy or {}
        for kw in strat.get("keywords", []):
            if kw:
                keywords.add(kw.strip())
    return sorted(keywords)


@router.get("/proposals", response_model=list[ProposalOut])
async def list_proposals(
    status: Optional[str] = Query(None, description="pending|approved|rejected"),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(PlaybookProposal)
        .options(selectinload(PlaybookProposal.playbook))
        .order_by(PlaybookProposal.proposed_at.desc())
    )
    if status:
        q = q.where(PlaybookProposal.status == status)
    result = await db.execute(q)
    proposals = result.scalars().all()

    # Enrich with playbook name for UI
    out = []
    for p in proposals:
        d = ProposalOut.model_validate(p)
        if p.playbook:
            d.playbook_name = p.playbook.name
        elif p.action == "CREATE":
            d.playbook_name = (p.proposed_data or {}).get("name")
        out.append(d)
    return out


@router.get("/{playbook_id}", response_model=PlaybookOut)
async def get_playbook(playbook_id: int, db: AsyncSession = Depends(get_db)):
    pb = await _get_or_404(playbook_id, db)
    return pb


@router.put("/{playbook_id}", response_model=PlaybookOut)
async def update_playbook(
    playbook_id: int, body: PlaybookUpdate, db: AsyncSession = Depends(get_db)
):
    pb = await _get_or_404(playbook_id, db)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(pb, k, v)
    await db.flush()
    await db.refresh(pb)
    log.info("playbook.updated", id=pb.id, name=pb.name)
    return pb


@router.delete("/{playbook_id}", status_code=204)
async def delete_playbook(playbook_id: int, db: AsyncSession = Depends(get_db)):
    pb = await _get_or_404(playbook_id, db)
    await db.delete(pb)
    log.info("playbook.deleted", id=playbook_id)


# ─── Proposal workflow ────────────────────────────────────────────────────────

@router.post("/proposals", response_model=ProposalOut, status_code=201)
async def create_proposal(body: ProposalCreate, db: AsyncSession = Depends(get_db)):
    # Validate playbook_id exists when action is UPDATE or RETIRE
    if body.action in ("UPDATE", "RETIRE") and not body.playbook_id:
        raise HTTPException(422, detail="playbook_id required for UPDATE/RETIRE proposals")

    if body.playbook_id:
        await _get_or_404(body.playbook_id, db)

    proposal = PlaybookProposal(**body.model_dump())
    db.add(proposal)
    await db.flush()
    await db.refresh(proposal)
    log.info("proposal.created", id=proposal.id, action=proposal.action)

    out = ProposalOut.model_validate(proposal)
    if body.action == "CREATE":
        out.playbook_name = (body.proposed_data or {}).get("name")
    return out


@router.post("/proposals/{proposal_id}/approve", response_model=PlaybookOut)
async def approve_proposal(
    proposal_id: int,
    body: ProposalResolve,
    db: AsyncSession = Depends(get_db),
):
    if not body.approved:
        raise HTTPException(400, detail="Use /reject endpoint to reject a proposal")

    proposal = await _get_proposal_or_404(proposal_id, db)
    if proposal.status != "pending":
        raise HTTPException(409, detail=f"Proposal is already {proposal.status}")

    now = datetime.utcnow()

    if proposal.action == "CREATE":
        # Materialise a new active playbook from proposed_data
        data = proposal.proposed_data or {}
        data["status"] = "active"
        data.setdefault("activated_at", now)
        pb = Playbook(**data)
        db.add(pb)
        await db.flush()
        proposal.playbook_id = pb.id

    elif proposal.action == "UPDATE":
        pb = await _get_or_404(proposal.playbook_id, db)
        for k, v in (proposal.proposed_data or {}).items():
            setattr(pb, k, v)
        await db.flush()
        await db.refresh(pb)

    elif proposal.action == "RETIRE":
        pb = await _get_or_404(proposal.playbook_id, db)
        pb.status = "deprecated"
        pb.deprecated_at = now
        await db.flush()

    else:
        raise HTTPException(422, detail=f"Unknown action: {proposal.action}")

    proposal.status = "approved"
    proposal.resolved_at = now
    proposal.resolved_by = body.resolved_by or "user"
    await db.flush()
    await db.refresh(pb)

    log.info("proposal.approved", id=proposal_id, action=proposal.action, playbook_id=pb.id)
    return pb


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalOut)
async def reject_proposal(
    proposal_id: int,
    body: ProposalResolve,
    db: AsyncSession = Depends(get_db),
):
    proposal = await _get_proposal_or_404(proposal_id, db)
    if proposal.status != "pending":
        raise HTTPException(409, detail=f"Proposal is already {proposal.status}")

    proposal.status = "rejected"
    proposal.rejection_reason = body.rejection_reason
    proposal.resolved_at = datetime.utcnow()
    proposal.resolved_by = body.resolved_by or "user"
    await db.flush()
    await db.refresh(proposal)

    log.info("proposal.rejected", id=proposal_id)
    out = ProposalOut.model_validate(proposal)
    if proposal.playbook:
        out.playbook_name = proposal.playbook.name
    return out


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _get_or_404(playbook_id: int, db: AsyncSession) -> Playbook:
    result = await db.execute(select(Playbook).where(Playbook.id == playbook_id))
    pb = result.scalar_one_or_none()
    if not pb:
        raise HTTPException(404, detail=f"Playbook {playbook_id} not found")
    return pb


async def _get_proposal_or_404(proposal_id: int, db: AsyncSession) -> PlaybookProposal:
    result = await db.execute(
        select(PlaybookProposal)
        .options(selectinload(PlaybookProposal.playbook))
        .where(PlaybookProposal.id == proposal_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, detail=f"Proposal {proposal_id} not found")
    return p
