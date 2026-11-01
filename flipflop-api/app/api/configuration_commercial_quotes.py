"""Authenticated review and approval for exact custom and upgraded PC pricing."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.commerce_evidence import PriceQuoteSnapshot
from app.models.playbook import Playbook
from app.routes.admin_auth import get_current_admin
from app.schemas.commercial_quote import CellCommercialPolicy, StrictModel
from app.services.configuration_readiness import request_context, configuration_detail, assess_configuration
from app.services.commercial_configuration import validate_configuration_policy
from app.services.commercial_quote_evidence import definition_hash

router = APIRouter()


class ConfigurationPriceApproval(StrictModel):
    review_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class ConfigurationEvidenceSelection(StrictModel):
    part_key: str
    observation_id: int
    source_fingerprint: str


class ConfigurationEvidenceReview(StrictModel):
    definition_sha256: str
    case_id: int | None
    entries: list[ConfigurationEvidenceSelection]


@router.get('/configurations')
async def list_configuration_reviews(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.status == 'configuration_review',
    ).order_by(PriceQuoteSnapshot.id.desc()).limit(100))).scalars().all()
    parents = {row.id: row for row in (await db.execute(select(Playbook).where(
        Playbook.id.in_({row.evidence_json['build_config']['playbook_id'] for row in rows}),
    ))).scalars().all()} if rows else {}
    items = []
    for row in rows:
        definition = row.evidence_json['definition']
        parent = parents.get(definition['playbook_id'])
        raw = (((parent.pricing_model or {}).get('commercial_configurations') or {}).get(definition_hash(definition))) if parent else None
        items.append({'request_id': row.id, 'playbook_name': parent.name if parent else 'Unavailable Playbook',
            'curated_build_id': definition['curated_build_id'], 'budget_tier': definition['budget_tier'],
            'component_count': len(definition['slot_selections']),
            'checkout_enabled': bool(raw and raw.get('checkout_enabled')),
            'created_at': row.created_at.isoformat()})
    return {'items': items}


@router.get('/configurations/{request_id}')
async def get_configuration_review(request_id: int, db: AsyncSession = Depends(get_db)):
    return await configuration_detail(db, request_id)


@router.put('/configurations/{request_id}/draft')
async def save_configuration_draft(request_id: int,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    raise HTTPException(409, 'Exact-configuration prices and delivery rules are generated from current catalogue facts and approved Playbook rules; manual policy entry is disabled.')


@router.post('/configurations/{request_id}/import-evidence')
async def import_configuration_evidence(request_id: int, body: ConfigurationEvidenceReview,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    request, _, _, definition = await request_context(db, request_id, lock=True)
    if definition_hash(definition) != body.definition_sha256 or body.case_id != definition['case_id']:
        raise HTTPException(409, 'Configuration changed; refresh the evidence preview')
    preview = await configuration_detail(db, request_id)
    if not body.entries:
        raise HTTPException(422, 'Review at least one current supplier listing before recording source facts')
    sources = {part['part_key']: {'role':part['role'],'part_key':part['part_key'],'source':part['source']}
        for part in preview['parts'] if part.get('part_key')}
    if len({entry.part_key for entry in body.entries}) != len(body.entries):
        raise HTTPException(422, 'Select each product only once')
    for entry in body.entries:
        part = sources.get(entry.part_key)
        source = part.get('source') if part else None
        if not source or source['fingerprint'] != entry.source_fingerprint:
            raise HTTPException(409, 'Collector evidence changed; refresh before importing')
        postage_fallback=(source.get('postage_assumption')=='owner-approved-zero-fallback'
            and str(source.get('delivery_gbp')) in {'0','0.0','0.00'})
        if (not source.get('fresh') or not source.get('commercial_capture_verified')
                or source.get('condition') != 'new' or source.get('item_gbp') is None
                or source.get('delivery_gbp') is None
                or (source.get('postage_verified') is not True and not postage_fallback)):
            raise HTTPException(409, 'Only fresh exact new-product captures with a verified item price can be recorded; unknown supplier postage is costed at £0.00')
    from app.services.catalogue_price_import import import_current_catalogue_prices
    result = await import_current_catalogue_prices(db,
        [sources[entry.part_key] for entry in body.entries], admin.id)
    db.add(PriceQuoteSnapshot(product_key=request.product_key, status='evidence_import',
        created_by_admin_id=admin.id, evidence_json={'request': body.model_dump(mode='json'),
            'reviewed_sources':[sources[entry.part_key]['source'] for entry in body.entries]},
        decision_json={'imported':result['imported'],'reused':result['reused'],
            'blocked':result['blocked'],'checkout_changed':False}))
    await db.commit()
    return {**result,'checkout_changed':False}


@router.put('/configurations/{request_id}/policy')
async def approve_configuration_policy(request_id: int, body: ConfigurationPriceApproval,
    db: AsyncSession = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    request, parent, config, definition = await request_context(db, request_id, lock=True)
    detail=await configuration_detail(db,request_id)
    if detail['checkout_enabled']:
        raise HTTPException(409,'This exact configuration is already approved for checkout')
    if not detail.get('draft') or detail.get('policy_blockers'):
        raise HTTPException(409,{'message':'The service must finish exact source pricing before approval',
            'service_work_remaining':detail.get('policy_blockers') or detail.get('draft_errors')})
    policy=CellCommercialPolicy.model_validate(detail['draft'])
    validate_configuration_policy(policy, definition)
    from app.services.strict_configuration_fit import require_configuration_fit
    await require_configuration_fit(db, config)
    pricing = dict(parent.pricing_model or {})
    policies = dict(pricing.get('commercial_configurations') or {})
    key = definition_hash(definition)
    old = policies.get(key)
    if policy.version != (old['version'] + 1 if old else 1):
        raise HTTPException(409, 'Policy version must increment by exactly one; reload this review')
    assessment=detail['assessment'] or await assess_configuration(db, parent, definition, policy)
    from app.services.commercial_readiness import price_review_hash
    if body.review_sha256 != price_review_hash(assessment):
        raise HTTPException(409, 'Listing prices or delivery options changed; review refreshed totals before approving')
    if not all(mode['offerable'] for mode in assessment['modes'].values()):
        raise HTTPException(409, 'All three modes need current supplier, compatibility, delivery and profit evidence before approval')
    policy=policy.model_copy(update={'checkout_enabled':True})
    policies[key] = policy.model_dump(mode='json')
    parent.pricing_model = {**pricing, 'commercial_configurations': policies}
    snapshot = PriceQuoteSnapshot(product_key=request.product_key, status='configuration_policy',
        created_by_admin_id=admin.id, evidence_json={'previous_policy': old,
            'policy': policies[key], 'definition': definition}, decision_json=assessment)
    db.add(snapshot)
    await db.commit()
    return {'checkout_enabled': policy.checkout_enabled, 'policy_version': policy.version, 'assessment': assessment}
