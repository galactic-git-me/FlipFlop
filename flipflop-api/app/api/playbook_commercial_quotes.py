"""Admin review of Playbook-owned core-build economics; never a payment quote."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.commerce_evidence import PriceQuoteSnapshot
from app.models.playbook import Playbook
from app.routes.admin_auth import get_current_admin
from app.schemas.commercial_quote import CellCommercialPolicy, Mode, StrictModel
from app.services.curated_build_policy import definitions
from app.services.commercial_quote_evidence import assess_stored_cell, definition_hash, latest_listing_observations

router = APIRouter()


class CoreQuoteRequest(StrictModel):
    playbook_id: int = Field(gt=0)
    curated_build_id: str = Field(min_length=1, max_length=120)
    capacity_evidence_ids: dict[Mode, int] = Field(default_factory=dict)
    nonnew_consent: bool = False


@router.put("/playbooks/{playbook_id}/cells/{cell_id}/commercial-policy")
async def save_cell_commercial_policy(
    playbook_id: int, cell_id: str, body: CellCommercialPolicy,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    raise HTTPException(409, "Commercial prices and policies are generated from current catalogue facts; manual policy entry is disabled. Review a generated Playbook proposal instead.")


@router.get("/playbooks/{playbook_id}/cells/{cell_id}/commercial-policy")
async def get_cell_commercial_policy(
    playbook_id: int, cell_id: str, db: AsyncSession = Depends(get_db),
) -> dict:
    playbook = await db.get(Playbook, playbook_id)
    definition = next((item for item in definitions()["builds"] if item["id"] == cell_id), None)
    if (playbook is None or definition is None or definition["segment"] != playbook.name
            or getattr(playbook.status, "value", playbook.status) != "active"):
        raise HTTPException(404, "Active Playbook cell not found")
    return {"playbook_id": playbook_id, "curated_build_id": cell_id,
            "definition": definition, "definition_sha256": definition_hash(definition),
            "policy": ((playbook.pricing_model or {}).get("commercial_cells") or {}).get(cell_id),
            "purchasable": False}


@router.post("/playbook-quotes", status_code=201)
async def create_playbook_commercial_quote(
    body: CoreQuoteRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    # Lock the authored policy while calculating/snapshotting it. Existing
    # Playbook updates serialize on this row through ordinary database writes.
    playbook = (await db.execute(select(Playbook).where(
        Playbook.id == body.playbook_id, Playbook.status == "active",
    ).with_for_update())).scalar_one_or_none()
    definition = next((item for item in definitions()["builds"]
                       if item["id"] == body.curated_build_id), None)
    if playbook is None or definition is None or definition["segment"] != playbook.name:
        raise HTTPException(404, "Active Playbook cell not found")
    raw = ((playbook.pricing_model or {}).get("commercial_cells") or {}).get(body.curated_build_id)
    if raw is None:
        raise HTTPException(409, "This Playbook cell has no reviewed commercial policy")
    try:
        policy = CellCommercialPolicy.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(409, "This Playbook cell's commercial policy is invalid or incomplete") from exc
    if policy.definition_sha256 != definition_hash(definition):
        raise HTTPException(409, "The build definition changed; review the commercial policy before quoting")
    result, evidence = await assess_stored_cell(db, playbook, definition, policy, body)
    snapshot = PriceQuoteSnapshot(
        product_key=f"playbook:{playbook.id}:cell:{body.curated_build_id}",
        status="assessment_only", created_by_admin_id=admin.id,
        evidence_json=evidence, decision_json=result,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return {"status": "assessment_only", "quote_snapshot_id": snapshot.id, **result}
