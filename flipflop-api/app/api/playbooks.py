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
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.playbook import Playbook, PlaybookProposal
from app.services.alerts import emit_alert
from app.models.flip_intelligence import FlipIntelligence
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


@router.post("/seed", status_code=201)
async def seed_initial_playbooks(db: AsyncSession = Depends(get_db)):
    """Migrate to 11 canonical playbooks and refresh live pricing from benchmarks."""
    from app.services.playbook_seeder import seed_playbooks
    created = await seed_playbooks(db)
    return {"ok": True, "created": created}


@router.get("/ranked", response_model=list[PlaybookOut])
async def list_playbooks_ranked(db: AsyncSession = Depends(get_db)):
    """Return active playbooks sorted by composite_rank_score descending."""
    result = await db.execute(
        select(Playbook)
        .where(Playbook.status == "active")
        .order_by(Playbook.composite_rank_score.desc())
    )
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


@router.get("/experiments/summary")
async def experiment_summary(db: AsyncSession = Depends(get_db)):
    """
    A/B experiment snapshot from proposal metadata.
    Reports variant counts and approval rates for playbook evolution proposals.
    """
    result = await db.execute(
        select(PlaybookProposal).where(
            PlaybookProposal.action == "UPDATE"
        ).order_by(PlaybookProposal.proposed_at.desc())
    )
    rows = result.scalars().all()

    by_variant: dict[str, dict[str, int]] = {}
    for p in rows:
        ds = p.demand_signals or {}
        if ds.get("source") != "playbook_evolution_v1":
            continue
        variant = str(ds.get("ab_variant") or "unknown")
        d = by_variant.setdefault(variant, {"total": 0, "pending": 0, "approved": 0, "rejected": 0})
        d["total"] += 1
        if p.status in d:
            d[p.status] += 1

    summary = {}
    for variant, stats in by_variant.items():
        total = stats["total"]
        approved = stats["approved"]
        summary[variant] = {
            **stats,
            "approval_rate": round((approved / total) * 100, 1) if total else 0.0,
        }

    return {"variants": summary}


@router.get("/experiments/attribution")
async def experiment_attribution(window_days: int = Query(14, ge=7, le=60), db: AsyncSession = Depends(get_db)):
    """
    Attribute sold-outcome performance to approved A/B evolution proposals.
    Method:
      - For each approved UPDATE proposal from playbook_evolution_v1,
        collect sold outcomes in FlipIntelligence for `window_days` after approval.
      - Aggregate avg profit/ROI by variant.
    """
    result = await db.execute(
        select(PlaybookProposal)
        .where(
            PlaybookProposal.action == "UPDATE",
            PlaybookProposal.status == "approved",
        )
        .order_by(PlaybookProposal.resolved_at.desc().nullslast())
    )
    proposals = result.scalars().all()

    by_variant: dict[str, dict[str, float]] = {}
    by_variant_counts: dict[str, int] = {}

    for p in proposals:
        ds = p.demand_signals or {}
        if ds.get("source") != "playbook_evolution_v1":
            continue
        variant = str(ds.get("ab_variant") or "unknown")
        if not p.resolved_at:
            continue

        from_dt = p.resolved_at
        to_dt = p.resolved_at + timedelta(days=window_days)
        flips_result = await db.execute(
            select(FlipIntelligence).where(
                FlipIntelligence.created_at >= from_dt,
                FlipIntelligence.created_at < to_dt,
            )
        )
        flips = list(flips_result.scalars().all())
        if not flips:
            continue

        total_profit = sum(float(f.profit or 0.0) for f in flips)
        total_roi = sum(float(f.roi_pct or 0.0) for f in flips)

        d = by_variant.setdefault(variant, {"profit_sum": 0.0, "roi_sum": 0.0, "flip_count": 0.0, "proposal_count": 0.0})
        d["profit_sum"] += total_profit
        d["roi_sum"] += total_roi
        d["flip_count"] += float(len(flips))
        d["proposal_count"] += 1.0
        by_variant_counts[variant] = by_variant_counts.get(variant, 0) + 1

    summary = {}
    for variant, d in by_variant.items():
        flips = max(1.0, d["flip_count"])
        flip_count = int(d["flip_count"])
        proposal_windows = int(d["proposal_count"])
        if flip_count >= 30 and proposal_windows >= 5:
            quality = "high"
        elif flip_count >= 10 and proposal_windows >= 2:
            quality = "medium"
        else:
            quality = "low"
        summary[variant] = {
            "proposal_windows": proposal_windows,
            "attributed_flips": flip_count,
            "avg_profit": round(d["profit_sum"] / flips, 2),
            "avg_roi_pct": round(d["roi_sum"] / flips, 2),
            "sample_quality": quality,
        }

    return {"window_days": window_days, "variants": summary}


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
        # Capture a rollback snapshot before applying update.
        rollback_snapshot = {
            "name": pb.name,
            "description": pb.description,
            "emoji": pb.emoji,
            "status": pb.status,
            "target_use_case": pb.target_use_case,
            "requirements": pb.requirements,
            "component_catalogue": pb.component_catalogue,
            "search_strategy": pb.search_strategy,
            "upgrade_strategy": pb.upgrade_strategy,
            "profit_strategy": pb.profit_strategy,
            "upsell_strategy": pb.upsell_strategy,
        }
        ds = dict(proposal.demand_signals or {})
        ds["rollback_snapshot"] = rollback_snapshot
        proposal.demand_signals = ds
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

    ds = dict(proposal.demand_signals or {})
    demand_source = str(ds.get("source") or "").strip()
    if demand_source:
        try:
            await emit_alert(
                code="playbook_demand_change_applied",
                source="playbooks",
                severity="info",
                message=(
                    f"Playbook '{pb.name}' {proposal.action.lower()} applied "
                    f"(proposal #{proposal.id}) from demand signal source '{demand_source}'."
                ),
            )
        except Exception as exc:
            log.warning("playbooks.alert_emit_error", proposal_id=proposal.id, error=str(exc))

    log.info("proposal.approved", id=proposal_id, action=proposal.action, playbook_id=pb.id)
    return pb


@router.post("/{playbook_id}/rollback-last-update", response_model=ProposalOut, status_code=201)
async def rollback_last_update(playbook_id: int, db: AsyncSession = Depends(get_db)):
    """
    Create a pending UPDATE proposal that restores the most recent approved
    rollback snapshot for this playbook. Human approval is still required.
    """
    await _get_or_404(playbook_id, db)

    result = await db.execute(
        select(PlaybookProposal)
        .where(
            PlaybookProposal.playbook_id == playbook_id,
            PlaybookProposal.action == "UPDATE",
            PlaybookProposal.status == "approved",
        )
        .order_by(PlaybookProposal.resolved_at.desc().nullslast(), PlaybookProposal.id.desc())
    )
    proposals = result.scalars().all()
    snapshot = None
    for p in proposals:
        ds = p.demand_signals or {}
        snap = ds.get("rollback_snapshot")
        if isinstance(snap, dict) and snap:
            snapshot = snap
            break

    if snapshot is None:
        raise HTTPException(404, detail="No rollback snapshot found for this playbook")

    proposal = PlaybookProposal(
        action="UPDATE",
        playbook_id=playbook_id,
        proposed_data=snapshot,
        reason="Rollback to last approved playbook snapshot",
        demand_signals={"source": "manual_rollback"},
        status="pending",
    )
    db.add(proposal)
    await db.flush()
    await db.refresh(proposal)

    out = ProposalOut.model_validate(proposal)
    pb = await _get_or_404(playbook_id, db)
    out.playbook_name = pb.name
    return out


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
