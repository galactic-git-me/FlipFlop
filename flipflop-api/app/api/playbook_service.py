"""Generated Playbook reviews. Operators never supply component or price values."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import get_settings
from app.models.admin_user import AdminUser
from app.models.playbook_refresh_run import PlaybookRefreshRun
from app.models.playbook import PlaybookProposal
from app.routes.admin_auth import get_current_admin
from app.config import get_settings
from app.schemas.commercial_quote import StrictModel
from app.services.playbook_service import (current_proposals, reject_proposal,
    approve_proposal, approve_current_supplier_sources, approve_all_current_supplier_sources,
    list_motherboard_engineering_suggestions, research_playbook_motherboard_specs,
    approve_playbook_motherboard_spec, list_playbook_product_engineering_suggestions,
    approve_playbook_product_engineering, royalcdkeys_licence_candidates,
    approve_royalcdkeys_licence_source, start_playbook_refresh_job,
    playbook_refresh_job_status, run_playbook_refresh_job)

router=APIRouter(prefix='/playbook-service',dependencies=[Depends(get_current_admin)])


class MarketDecision(StrictModel):
    batch_id: int = Field(gt=0)
    decision: str = Field(pattern='^(approve|reject)$')
    candidate_ids: list[str] = Field(default_factory=list, max_length=90)
    exact_build_confirmed: bool = False


@router.get('/market/{playbook_id}/{cell_id}')
async def market_review(playbook_id:int, cell_id:str, db:AsyncSession=Depends(get_db)):
    from app.services.playbook_market import review_view
    return await review_view(db, playbook_id, cell_id)


@router.post('/market/{playbook_id}/{cell_id}/collect')
async def collect_market(playbook_id:int, cell_id:str, db:AsyncSession=Depends(get_db), admin:AdminUser=Depends(get_current_admin)):
    from app.services.playbook_market import collect
    return await collect(db, playbook_id, cell_id, admin.id)


@router.post('/market/{playbook_id}/{cell_id}/review')
async def decide_market(playbook_id:int, cell_id:str, body:MarketDecision, db:AsyncSession=Depends(get_db), admin:AdminUser=Depends(get_current_admin)):
    from app.services.playbook_market import decide
    return await decide(db, playbook_id, cell_id, body, admin.id)


@router.get('/book')
async def book(db:AsyncSession=Depends(get_db)):
    from app.services.playbook_book import operational_book
    return await operational_book(db)


@router.post('/pricing-guidance/refresh')
async def refresh_pricing_guidance(background_tasks: BackgroundTasks, admin: AdminUser = Depends(get_current_admin)):
    from app.services.playbook_pricing_guidance import refresh_market_advice
    background_tasks.add_task(refresh_market_advice, admin.id)
    return {'queued': True, 'checkout_changed': False, 'published': False}


class SupplierEvidenceFingerprint(StrictModel):
    role:str=Field(min_length=1,max_length=64)
    listing_id:int=Field(gt=0)
    fingerprint:str=Field(pattern=r'^[0-9a-f]{64}$')


class ReviewRevision(StrictModel):
    revision_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    source_evidence:list[SupplierEvidenceFingerprint]=Field(default_factory=list,max_length=32)


class ProposalRevision(ReviewRevision):
    proposal_id:int=Field(gt=0)


class ReviewAllSupplierSources(StrictModel):
    proposals:list[ProposalRevision]=Field(min_length=1,max_length=64)


class LicenceSourceApproval(StrictModel):
    licence_review_fingerprint:str=Field(pattern=r'^[0-9a-f]{64}$')


class EngineeringSourceApproval(StrictModel):
    fingerprint:str=Field(pattern=r'^[0-9a-f]{64}$')
    replace_reviewed_values:bool=False


@router.get('/proposals')
async def proposals(db:AsyncSession=Depends(get_db)):
    return {'items':await current_proposals(db)}


@router.get('/automation')
async def automation_status(db:AsyncSession=Depends(get_db)):
    """Report scheduled refresh registration and durable latest run evidence."""
    from app.workers.scheduler import get_scheduler
    scheduler=get_scheduler()
    scheduled_job=scheduler.get_job('playbook_catalogue_refresh')
    scheduled=(await db.execute(select(PlaybookRefreshRun).where(
        PlaybookRefreshRun.actor_id==0,PlaybookRefreshRun.mode=='refresh'
    ).order_by(PlaybookRefreshRun.started_at.desc()).limit(1))).scalar_one_or_none()
    scheduled_rebuild=(await db.execute(select(PlaybookRefreshRun).where(
        PlaybookRefreshRun.actor_id==0,PlaybookRefreshRun.mode=='rebuild'
    ).order_by(PlaybookRefreshRun.started_at.desc()).limit(1))).scalar_one_or_none()
    manual=(await db.execute(select(PlaybookRefreshRun).where(
        PlaybookRefreshRun.actor_id!=0,PlaybookRefreshRun.mode=='refresh'
    ).order_by(PlaybookRefreshRun.started_at.desc()).limit(1))).scalar_one_or_none()
    scheduled_run=await playbook_refresh_job_status(db,scheduled.job_id) if scheduled else None
    scheduled_rebuild_run=await playbook_refresh_job_status(db,scheduled_rebuild.job_id) if scheduled_rebuild else None
    manual_run=await playbook_refresh_job_status(db,manual.job_id) if manual else None
    setting_enabled=get_settings().commercial_reconciliation_enabled
    return {'setting_enabled':setting_enabled,'registered':scheduled_job is not None,
        'enabled':bool(scheduled_job and scheduled_job.next_run_time is not None),
        'next_run_at':scheduled_job.next_run_time.isoformat() if scheduled_job and scheduled_job.next_run_time else None,
        'scheduled_latest':scheduled_run,'scheduled_rebuild_latest':scheduled_rebuild_run,
        'manual_latest':manual_run}


@router.get('/engineering-suggestions')
async def engineering_suggestions(db:AsyncSession=Depends(get_db)):
    return {'items':await list_motherboard_engineering_suggestions(db)}


@router.get('/product-engineering-suggestions')
async def product_engineering_suggestions(db:AsyncSession=Depends(get_db)):
    return {'items':await list_playbook_product_engineering_suggestions(db)}


@router.post('/product-engineering-suggestions/{listing_id}/approve')
async def approve_product_engineering_suggestion(listing_id:int,body:EngineeringSourceApproval,
        db:AsyncSession=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    result=await approve_playbook_product_engineering(db,listing_id,body.fingerprint,admin,
        replace_reviewed_values=body.replace_reviewed_values)
    await db.commit()
    return result


@router.get('/supplier-licences')
async def supplier_licences(db:AsyncSession=Depends(get_db)):
    return {'items':await royalcdkeys_licence_candidates(db)}


@router.post('/supplier-licences/{listing_id}/approve')
async def approve_supplier_licence(listing_id:int,body:LicenceSourceApproval,
        db:AsyncSession=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    result=await approve_royalcdkeys_licence_source(db,listing_id,body.licence_review_fingerprint,admin.id)
    await db.commit()
    return result


@router.post('/engineering-suggestions/research')
async def research_engineering_suggestions(db:AsyncSession=Depends(get_db)):
    result=await research_playbook_motherboard_specs(db)
    await db.commit()
    return result


@router.post('/engineering-suggestions/{spec_id}/approve')
async def approve_engineering_suggestion(spec_id:int,db:AsyncSession=Depends(get_db),
                                         admin:AdminUser=Depends(get_current_admin)):
    result=await approve_playbook_motherboard_spec(db,spec_id,admin)
    await db.commit()
    return result


@router.post('/refresh')
async def refresh(background_tasks:BackgroundTasks,db:AsyncSession=Depends(get_db),
                  admin:AdminUser=Depends(get_current_admin)):
    # Retailer scraping and product captures can take several minutes. Return a
    # job handle immediately so the admin UI can show progress and avoid a
    # browser/proxy timeout that leaves the result ambiguous.
    job=await start_playbook_refresh_job(db,admin.id)
    if job['started']:
        background_tasks.add_task(run_playbook_refresh_job,job['job_id'],admin.id)
    return {key:value for key,value in job.items() if key!='actor_id'}


@router.post('/rebuild')
async def rebuild_from_captured_catalogue(background_tasks:BackgroundTasks,
                                          db:AsyncSession=Depends(get_db),
                                          admin:AdminUser=Depends(get_current_admin)):
    """Recalculate pending cells from stored catalogue facts without scraping or publishing."""
    job=await start_playbook_refresh_job(db,admin.id,mode='rebuild')
    if job['started']:
        background_tasks.add_task(run_playbook_refresh_job,job['job_id'],admin.id)
    return {key:value for key,value in job.items() if key!='actor_id'}


@router.get('/refresh/{job_id}')
async def refresh_status(job_id:str,db:AsyncSession=Depends(get_db),
                         admin:AdminUser=Depends(get_current_admin)):
    return await playbook_refresh_job_status(db,job_id)


@router.post('/proposals/{proposal_id}/reject')
async def reject(proposal_id:int,body:ReviewRevision,db:AsyncSession=Depends(get_db),
                 admin:AdminUser=Depends(get_current_admin)):
    return await reject_proposal(db,proposal_id,body.revision_sha256,admin.id)


@router.post('/proposals/{proposal_id}/compatibility-second-opinion')
async def compatibility_second_opinion(proposal_id:int,body:ReviewRevision,
        db:AsyncSession=Depends(get_db)):
    proposal=(await db.execute(select(PlaybookProposal).where(
        PlaybookProposal.id==proposal_id))).scalar_one_or_none()
    if (proposal is None or proposal.status!='pending'
            or (proposal.demand_signals or {}).get('source')!='catalogue_playbook_service_v1'):
        raise HTTPException(404,'Pending Playbook proposal not found')
    offer=proposal.proposed_data or {}
    if offer.get('revision_sha256')!=body.revision_sha256:
        raise HTTPException(409,'The proposal changed; reload before reviewing')
    from app.services.compatibility_llm_review import review_compatibility_evidence
    try:
        return await review_compatibility_evidence(offer)
    except Exception as error:
        raise HTTPException(503,'The advisory compatibility review is unavailable') from error


@router.post('/proposals/{proposal_id}/approve')
async def approve(proposal_id:int,body:ReviewRevision,db:AsyncSession=Depends(get_db),
                  admin:AdminUser=Depends(get_current_admin)):
    return await approve_proposal(db,proposal_id,body.revision_sha256,admin.id)


@router.post('/proposals/{proposal_id}/approve-supplier-sources')
async def approve_supplier_sources(proposal_id:int,body:ReviewRevision,db:AsyncSession=Depends(get_db),
                                   admin:AdminUser=Depends(get_current_admin)):
    result=await approve_current_supplier_sources(db,proposal_id,body.revision_sha256,admin.id,
        [item.model_dump() for item in body.source_evidence])
    await db.commit()
    return result


@router.post('/supplier-sources/approve-all')
async def approve_all_supplier_sources(body:ReviewAllSupplierSources,db:AsyncSession=Depends(get_db),
                                       admin:AdminUser=Depends(get_current_admin)):
    result=await approve_all_current_supplier_sources(db,[item.model_dump() for item in body.proposals],admin.id)
    await db.commit()
    return result


class MvpRules(StrictModel):
    enabled: bool
    budget_ceilings: dict[str, float] = Field(default_factory=dict)
    max_price_change_fraction: float = Field(default=0.10, gt=0, le=0.25)


@router.get('/mvp-rules')
async def mvp_rules(db:AsyncSession=Depends(get_db)):
    from app.models.playbook import Playbook
    from app.models.curated_build_segment import CuratedBuildSegment
    from app.services.curated_build_policy import definitions
    from app.services.playbook_mvp import DEFAULT_SUPPLIERS
    parents=(await db.execute(select(Playbook).where(Playbook.status=='active'))).scalars().all()
    segments=(await db.execute(select(CuratedBuildSegment))).scalars().all()
    by_pair={(row.customer_type,row.budget_level):row for row in segments}
    parent_by_name={row.name:row for row in parents}
    cells=[]
    for definition in definitions()['builds']:
        parent=parent_by_name.get(definition['segment'])
        rules=((parent.pricing_model or {}).get('mvp_autonomy') or {}) if parent else {}
        segment=by_pair.get((definition['segment'],definition['tier']))
        cells.append({'cell_id':definition['id'],'name':definition['name'],
            'enabled':rules.get('enabled',False),
            'budget_ceiling':(rules.get('budget_ceilings') or {}).get(definition['id']) or (segment.budget_max if segment else None)})
    return {'cells':cells,'approved_suppliers':DEFAULT_SUPPLIERS,'mode':'standard',
        'max_price_change_fraction':next((((row.pricing_model or {}).get('mvp_autonomy') or {}).get('max_price_change_fraction',0.10) for row in parents),0.10)}


@router.put('/mvp-rules')
async def save_mvp_rules(body:MvpRules, background_tasks:BackgroundTasks, db:AsyncSession=Depends(get_db),
        admin:AdminUser=Depends(get_current_admin)):
    from math import isfinite
    from datetime import datetime, timezone
    from app.models.playbook import Playbook
    from app.services.curated_build_policy import definitions
    from app.services.playbook_mvp import DEFAULT_SUPPLIERS
    from app.models.commerce_evidence import PriceQuoteSnapshot
    definitions_by_id={row['id']:row for row in definitions()['builds']}
    if any(key not in definitions_by_id or not isfinite(value) or value<=0 for key,value in body.budget_ceilings.items()):
        raise HTTPException(422,'Budget ceilings must be positive finite amounts for existing Playbook cells')
    await db.execute(text('SELECT pg_advisory_xact_lock(61311, 1)'))
    parents=(await db.execute(select(Playbook).where(Playbook.status=='active').with_for_update())).scalars().all()
    for parent in parents:
        pricing=dict(parent.pricing_model or {})
        previous=pricing.get('mvp_autonomy') or {}
        ceilings={**(previous.get('budget_ceilings') or {}), **{key:value for key,value in body.budget_ceilings.items()
            if definitions_by_id[key]['segment']==parent.name}}
        anchors={key:offer.get('delivery_products',{}).get('standard',{}).get('recommended_price_gbp')
            for key,offer in (pricing.get('managed_offers') or {}).items()}
        rules={'profile':'matrix_mvp','enabled':body.enabled,'budget_ceilings':ceilings,'price_anchors':anchors,
            'max_price_change_fraction':body.max_price_change_fraction,'approved_suppliers':list(DEFAULT_SUPPLIERS),
            'approved_by':admin.id,'approved_at':datetime.now(timezone.utc).isoformat(),'version':int(previous.get('version',0))+1}
        parent.pricing_model={**pricing,'mvp_autonomy':rules}
        db.add(PriceQuoteSnapshot(product_key=f'playbook:{parent.id}:mvp-rules',status='mvp_rules_saved',
            evidence_json={'before':previous,'after':rules},decision_json={'actor':'admin'},created_by_admin_id=admin.id))
    await db.commit()
    job=None
    if body.enabled:
        job=await start_playbook_refresh_job(db,admin.id,mode='rebuild')
        background_tasks.add_task(run_playbook_refresh_job,job['job_id'],admin.id)
    return {'enabled':body.enabled,'job':job}
