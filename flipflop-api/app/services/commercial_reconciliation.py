"""Refresh previously reviewed exact listings; never publish commercial rules."""
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, text
from app.database import AsyncSessionLocal
from app.models.commerce_evidence import PriceQuoteSnapshot, SupplierOfferEvidence
from app.models.listing import Listing
from app.services.commercial_quote_evidence import latest_listing_observations
from app.services.commercial_readiness import source_preview, readiness_index
from app.services.commercial_source_validation import ImportEntry, source_values


def refresh_values(previous, source):
    """Re-use reviewed allowances, not a previous operator's stock approval."""
    if not source or (not source.get('commercial_capture_verified') and source.get('active_listing')):
        return None
    positive = bool(source['fresh'] and source['active_listing']
                    and source.get('stock_status') == 'available' and source.get('stock_evidence'))
    entry = ImportEntry(part_key=previous.part_key, observation_id=source['observation_id'],
        source_fingerprint=source['fingerprint'], fees_gbp=previous.fees_gbp,
        risk_gbp=previous.risk_gbp, supplier_confidence=previous.supplier_confidence,
        stock_confirmed=positive)
    values = source_values(source, entry)
    # Changed condition requires a fresh identity/condition review.
    if values['condition'] != previous.condition:
        values['condition'] = previous.condition
        values['stock_confirmed'] = False
    values['evidence_source'] = f"commercial_refresh:{source['observation_id']}:{source['fingerprint'][:16]}"
    return values


async def reconcile_commercial(db, actor_id=0, trigger='scheduled'):
    audit = PriceQuoteSnapshot(product_key='commercial:reconciliation', status='reconcile_running',
        created_by_admin_id=actor_id, evidence_json={'trigger':trigger}, decision_json={})
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    audit_id = audit.id
    try:
        locked = await db.scalar(text('SELECT pg_try_advisory_xact_lock(61310, 2)'))
        if not locked:
            audit.status='reconcile_skipped'
            audit.decision_json={'reason':'Another reconciliation is running'}
            await db.commit()
            return {'audit_id':audit_id,'status':'skipped'}
        overview = await readiness_index(db)
        candidates = (await db.execute(select(SupplierOfferEvidence).where(
            (SupplierOfferEvidence.evidence_source.like('catalogue_import:%')) |
            (SupplierOfferEvidence.evidence_source.like('commercial_refresh:%')),
        ))).scalars().all()
        imported, reused, blocked = 0, 0, []
        for previous in latest_listing_observations(candidates):
            # Exact persisted URL only; ambiguous duplicate links require review.
            listings = (await db.execute(select(Listing).where(Listing.url == previous.evidence_ref).limit(2))).scalars().all()
            if len(listings) != 1:
                blocked.append({'part_key':previous.part_key,'reason':'Exact catalogue link missing or ambiguous'})
                continue
            source = await source_preview(db, listings[0])
            try:
                values = refresh_values(previous, source)
            except Exception as error:
                from fastapi import HTTPException
                if not isinstance(error, (HTTPException, ValueError)):
                    raise
                values = None
            if values is None:
                blocked.append({'part_key':previous.part_key,'reason':'Original commercial capture requires review'})
                continue
            await db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:key), 61310)'),
                             {'key':previous.part_key+'|'+previous.evidence_ref})
            # Compare with all writers, including more recent operator reviews.
            latest = (await db.execute(select(SupplierOfferEvidence).where(
                SupplierOfferEvidence.part_key == previous.part_key,
                SupplierOfferEvidence.evidence_ref == previous.evidence_ref,
            ).order_by(SupplierOfferEvidence.observed_at.desc(), SupplierOfferEvidence.id.desc()).limit(1))).scalar_one()
            if values['observed_at'] < latest.observed_at:
                reused += 1
                continue
            if values['observed_at'] == latest.observed_at and (
                (values['stock_confirmed'] and not latest.stock_confirmed)
                or (source.get('stock_status') == 'unknown' and source['active_listing']
                    and latest.evidence_source.startswith('catalogue_import:'))
            ):
                # An unchanged scan cannot undo an explicit operator review.
                reused += 1
                continue
            if all(getattr(latest, key) == value for key,value in values.items() if key != 'evidence_source'):
                reused += 1
                continue
            db.add(SupplierOfferEvidence(**values,captured_by_admin_id=actor_id))
            await db.flush()
            imported += 1
        audit.status='reconcile_complete'
        overview = await readiness_index(db)
        audit.decision_json={'imported':imported,'reused':reused,'blocked':blocked,
            'cells':overview['items'],'finished_at':datetime.now(timezone.utc).isoformat(),
            'checkout_changed':False,'prices_published':False}
        await db.commit()
        if imported and trigger=='scheduled':
            from app.services.playbook_service import enqueue_scheduled_playbook_rebuild
            rebuild=await enqueue_scheduled_playbook_rebuild(
                f'{imported} reviewed supplier price or availability fact(s) changed')
            audit.decision_json={**audit.decision_json,'playbook_rebuild':{
                'job_id':rebuild['job_id'],'status':rebuild['status'],
                'coalesced':rebuild.get('coalesced',False)}}
            await db.commit()
        return {'audit_id':audit_id,'status':'complete',**audit.decision_json}
    except BaseException as error:
        await db.rollback()
        audit = await db.get(PriceQuoteSnapshot,audit_id)
        audit.status='reconcile_failed'
        audit.decision_json={'error_type':type(error).__name__,'finished_at':datetime.now(timezone.utc).isoformat()}
        await db.commit()
        raise


async def run_commercial_reconciliation():
    async with AsyncSessionLocal() as db:
        return await asyncio.wait_for(reconcile_commercial(db),timeout=120)
