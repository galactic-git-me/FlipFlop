"""Admin-only readiness reads and explicit review of collected supplier data."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.commerce_evidence import PriceQuoteSnapshot, SupplierOfferEvidence
from app.routes.admin_auth import get_current_admin
from app.services.commercial_readiness import readiness_detail, readiness_index

router = APIRouter()


@router.post('/reconciliation/run')
async def run_reconciliation(db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    import asyncio
    from app.services.commercial_reconciliation import reconcile_commercial
    return await asyncio.wait_for(reconcile_commercial(db, admin.id, 'admin'), timeout=120)


@router.get('/reconciliation/health')
async def reconciliation_health(db: AsyncSession = Depends(get_db)):
    from app.config import get_settings
    rows = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key == 'commercial:reconciliation',
    ).order_by(PriceQuoteSnapshot.id.desc()).limit(20))).scalars().all()
    success = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key == 'commercial:reconciliation',
        PriceQuoteSnapshot.status == 'reconcile_complete',
    ).order_by(PriceQuoteSnapshot.id.desc()).limit(1))).scalar_one_or_none()
    return {'scheduled_enabled':get_settings().commercial_reconciliation_enabled,
        'last_success_at':success.created_at.isoformat() if success else None,
        'runs':[{'id':row.id,'status':row.status,'created_at':row.created_at.isoformat(),
                 'result':row.decision_json} for row in rows]}


@router.get("/readiness")
async def get_readiness(db: AsyncSession = Depends(get_db)):
    return await readiness_index(db)


@router.get("/playbooks/{playbook_id}/cells/{cell_id}/readiness")
async def get_cell_readiness(playbook_id: int, cell_id: str, case_id: int | None = Query(default=None, gt=0),
                             reset_draft: bool = False,
                             db: AsyncSession = Depends(get_db)):
    return await readiness_detail(db, playbook_id, cell_id, case_id, reset_draft)


@router.put("/playbooks/{playbook_id}/cells/{cell_id}/commercial-draft")
async def save_commercial_draft(playbook_id: int, cell_id: str,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    raise HTTPException(409, "Per-cell prices and costs are calculated by the catalogue-owned Playbook service; manual policy entry is disabled.")


@router.post("/playbooks/{playbook_id}/cells/{cell_id}/import-evidence")
async def import_collected_evidence(playbook_id: int, cell_id: str,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    raise HTTPException(409, "Supplier facts must be reviewed from the generated Playbook source queue; manual fee, risk and confidence entry is disabled.")


async def store_reviewed_sources(db, pending, admin_id):
    from app.services.commercial_source_validation import delivery_estimate_source_label
    imported, reused = [], []
    # A shared source can appear in several cells; serialize it independently
    # of the parent row so concurrent imports remain idempotent.
    for original in sorted(pending, key=lambda item: (item["part_key"], item["evidence_ref"])):
        values = dict(original)
        # Multiple import paths write this shared table. Enforce the persisted
        # label limit here too, including scheduled reconciliation refreshes.
        values["delivery_estimate_source"] = delivery_estimate_source_label(
            values.get("delivery_estimate_source")
        )
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key), 61310)"),
                         {"key": values["part_key"] + "|" + values["evidence_ref"]})
        existing = (await db.execute(select(SupplierOfferEvidence).where(
            SupplierOfferEvidence.part_key == values["part_key"],
            SupplierOfferEvidence.evidence_ref == values["evidence_ref"],
            SupplierOfferEvidence.evidence_source == values["evidence_source"],
        ).order_by(SupplierOfferEvidence.id.desc()).limit(1))).scalar_one_or_none()
        if existing and all(getattr(existing, key) == value for key, value in values.items()):
            reused.append(existing.id)
            continue
        row = SupplierOfferEvidence(**values, captured_by_admin_id=admin_id)
        db.add(row)
        await db.flush()
        imported.append(row.id)
    return imported, reused


@router.post('/playbooks/{playbook_id}/cells/{cell_id}/approve-prices')
async def approve_catalogue_delivery_prices(playbook_id: int, cell_id: str,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    raise HTTPException(409, "Review the calculated Playbook proposal; manual price-policy payloads are disabled.")


