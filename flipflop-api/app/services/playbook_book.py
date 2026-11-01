"""Read-only, exact-cell operational projection and append-only change records."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from sqlalchemy import select
from app.models.playbook import Playbook, PlaybookProposal
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.commerce_evidence import PriceQuoteSnapshot
from app.models.catalogue import CatalogueVariant
from app.models.listing import Listing
from app.services.curated_build_policy import definitions
from app.services.commercial_quote_evidence import definition_hash
from app.services.playbook_book_evidence import distribution_evidence, build_market_evidence


def cell_state(segment):
    return {key: getattr(segment, key, None) for key in (
        'components', 'selling_price', 'proposed_selling_price', 'is_live',
        'availability_status', 'budget_min', 'budget_max', 'software_profile',
        'approved_upgrades', 'bestseller_components', 'allow_flip_component_sources')}


def record_cell_event(db, cell_id, event, reason, before, after, actor_id=0):
    if before == after:
        return
    db.add(PriceQuoteSnapshot(
        product_key=f'playbook-cell:{cell_id}', status='playbook_event',
        evidence_json={'cell_id': cell_id, 'event': event, 'reason': reason,
                       'before': deepcopy(before), 'after': deepcopy(after)},
        decision_json={'actor': 'automation' if actor_id == 0 else 'admin'},
        created_by_admin_id=actor_id,
    ))


def definition_for_segment(segment):
    return next((row for row in definitions()['builds']
                 if row['segment'] == segment.customer_type and row['tier'] == segment.budget_level), None)


def record_segment_event(db, segment, event, reason, before, actor_id=0):
    definition = definition_for_segment(segment)
    cell_id = definition['id'] if definition else f'segment:{segment.id}'
    record_cell_event(db, cell_id, event, reason, before, cell_state(segment), actor_id)


def enum_value(value):
    return getattr(value, 'value', value)


def assignment_availability(segment, states):
    ids = list((segment.components or {}).values()) if segment else []
    if not ids:
        return 'not_configured'
    return 'in_stock' if all(str(value).isdigit() and states.get(int(value)) == ('active', 'active')
                             for value in ids) else 'out_of_stock'


def project_cell(definition, segment, parent, proposals, snapshots, channels, distribution_records=()):
    cell_id = definition['id']
    history = [row for row in proposals if (row.proposed_data or {}).get('cell_id') == cell_id]
    pending = next((row for row in history if row.status == 'pending'), None)
    pricing = (parent.pricing_model or {}) if parent else {}
    approved = (pricing.get('managed_offers') or {}).get(cell_id)
    policy = (pricing.get('commercial_cells') or {}).get(cell_id) or {}
    offer = {'proposal_id': pending.id, **pending.proposed_data} if pending else approved
    # Segment-wide market fields cannot establish a price for a budget cell.
    market = policy.get('market') if policy.get('definition_sha256')==definition_hash(definition) else None
    from app.services.playbook_market import approved_market, bom_hash
    reviewed_market = approved_market(parent, definition,
        {part['role']:part for part in (offer or {}).get('components',[])}) if parent else None
    from app.services.playbook_mvp import mvp_enabled, publication_limit_reason
    automation_reason = publication_limit_reason(parent, definition, offer) if parent and offer and mvp_enabled(parent) else None
    standard = ((offer or {}).get('delivery_products') or {}).get('standard') or {}
    approved_standard = ((approved or {}).get('delivery_products') or {}).get('standard') or {}
    approved_mappings={part['role']:part['variant_id'] for part in (approved or {}).get('components',[])}
    approved_matches=bool(approved and segment and segment.components==approved_mappings
        and approved.get('revision_sha256') and approved.get('approved_revision_sha256')==approved.get('revision_sha256')
        and approved.get('approved_policy_version') is not None
        and approved.get('approved_policy_version')==policy.get('version')
        and policy.get('definition_sha256')==definition_hash(definition))
    market = reviewed_market or (market if approved_matches else None)
    walk_away=approved_standard.get('profit_floor_gbp') if approved_matches else None
    events = []
    keys = {f'playbook-cell:{cell_id}'}
    if parent:
        keys.add(f'playbook:{parent.id}:cell:{cell_id}')
    for row in snapshots:
        if row.product_key not in keys:
            continue
        evidence = row.evidence_json or {}
        events.append({'id': f'snapshot:{row.id}', 'at': row.created_at,
            'event': evidence.get('event', row.status), 'reason': evidence.get('reason'),
            'actor': (row.decision_json or {}).get('actor', 'automation' if row.created_by_admin_id == 0 else 'admin'),
            'before': evidence.get('before'), 'after': evidence.get('after')})
    market_batch = next((row for row in snapshots if row.product_key in keys and row.status == 'market_candidates'), None)
    market_decision = next((row for row in snapshots if row.product_key in keys
        and row.status in ('market_approved','market_rejected')
        and (row.evidence_json or {}).get('batch_id') == (market_batch.id if market_batch else None)), None)
    market_review_status = market_decision.status.removeprefix('market_') if market_decision else 'pending' if market_batch else 'not_collected'
    if market_batch:
        evidence = market_batch.evidence_json
        if (evidence['bom_sha256'] != bom_hash(definition, {part['role']:part for part in (offer or {}).get('components',[])})
                or datetime.fromisoformat(evidence['observed_at']) < datetime.now(timezone.utc)-timedelta(days=30)):
            market_review_status = 'stale'
    for row in history:
        events.append({'id': f'proposal:{row.id}', 'at': row.resolved_at or row.proposed_at,
            'event': f'proposal_{row.status}', 'reason': row.rejection_reason or row.reason,
            'actor': row.resolved_by or 'automation', 'before': None, 'after': None})
    events.sort(key=lambda row: row['at'].replace(tzinfo=timezone.utc) if row['at'] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    distribution = [{'channel': 'storefront', 'status': 'published' if segment and segment.is_live else 'offline',
                     'source': 'Curated cell publication record', 'external_id': cell_id, 'offer_kind': 'curated'}]
    for product, listing in channels:
        identity = (product.item_specifics or {}).get('curated_build_id')
        if identity != cell_id:
            continue
        distribution.append({'channel': enum_value(listing.channel), 'status': enum_value(listing.status),
            'source': f'Product {product.id} channel record', 'external_id': listing.external_listing_id,
            'updated_at': listing.updated_at})
    distribution.extend({key:value for key,value in record.items() if key!='cell_id'}
                        for record in distribution_records if record['cell_id']==cell_id)
    return {'cell_id': cell_id, 'playbook_id': parent.id if parent else None, 'segment_id': segment.id if segment else None,
        'customer_type': definition['segment'], 'budget_tier': definition['tier'],
        'name': definition['name'], 'definition': definition,
        'offer': offer, 'approved_offer': approved,
        'automation_reason':automation_reason,
        'mvp_autonomy':bool(((parent.pricing_model or {}).get('mvp_autonomy') or {}).get('enabled')) if parent else False,
        'offer_basis': 'pending_proposal' if pending else 'approved_offer' if approved else 'no_offer',
        'proposal_status': pending.status if pending else None,
        'proposal_observed_at': pending.updated_at if pending else (approved or {}).get('approved_at'),
        'approved_price_gbp': segment.selling_price if segment else None,
        'market': market, 'market_review_status': market_review_status,
        'active_build_market_gbp': (reviewed_market or {}).get('active_median_gbp'), 'walk_away_price_gbp': walk_away,
        'proposed_walk_away_price_gbp':standard.get('profit_floor_gbp') if pending else None,
        'walk_away_observed_at':(approved or {}).get('approved_at') if walk_away is not None else None,
        'pricing_gaps': ([] if (reviewed_market or {}).get('active_median_gbp') else ['Exact-build active-market comparison is not recorded'])+
            (['An approved cell minimum selling price matching the current build and policy is not recorded'] if walk_away is None else []),
        'is_live': bool(segment and segment.is_live),
        'checkout_enabled': bool(policy.get('checkout_enabled')),
        'availability_status': segment.availability_status if segment else 'not_configured',
        'software_profile': segment.software_profile if segment else None,
        'policy_version': policy.get('version'), 'history': events[:100],
        'history_coverage': 'Recorded proposal, review and operational events; earlier overwritten drafts cannot be reconstructed',
        'distribution': distribution,
        'distribution_coverage': 'Exact curated_build_id links only; no channel presence inferred from customer type'}


async def operational_book(db):
    parents = (await db.execute(select(Playbook))).scalars().all()
    segments = (await db.execute(select(CuratedBuildSegment))).scalars().all()
    proposals = (await db.execute(select(PlaybookProposal).where(
        PlaybookProposal.action == 'UPDATE').order_by(PlaybookProposal.id.desc()))).scalars().all()
    # Fetch only exact-cell audit keys; quote and customer details are never exposed.
    cells = list(definitions()['builds'])
    pairs = {(row.customer_type, row.budget_level): row for row in segments}
    parent_by_name = {row.name: row for row in parents}
    for segment in segments:
        if not any(row['segment'] == segment.customer_type and row['tier'] == segment.budget_level for row in cells):
            cells.append({'id': f'segment:{segment.id}', 'segment': segment.customer_type,
                          'tier': segment.budget_level, 'name': f'{segment.customer_type} {segment.budget_level}', 'components': {}})
    keys = [key for row in cells for key in (f"playbook-cell:{row['id']}",
            f"playbook:{parent_by_name[row['segment']].id}:cell:{row['id']}" if row['segment'] in parent_by_name else '') if key]
    snapshots = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key.in_(keys)).order_by(PriceQuoteSnapshot.id.desc()))).scalars().all()
    distribution_records, unassigned = await distribution_evidence(db, cells, parents)
    market_references = await build_market_evidence(db)
    assigned_ids = {int(value) for segment in segments for value in (segment.components or {}).values()
                    if str(value).isdigit()}
    states = {variant_id: (enum_value(variant_status), enum_value(listing_status))
        for variant_id, variant_status, listing_status in (await db.execute(select(
            CatalogueVariant.id, CatalogueVariant.status, Listing.status).join(
                Listing, Listing.id == CatalogueVariant.listing_id).where(
                    CatalogueVariant.id.in_(assigned_ids)))).all()}
    from app.models.app_settings import AppSettings
    from app.services.playbook_pricing_guidance import estimate, cached_advice
    pricing_settings = await db.get(AppSettings, 1)
    projected = []
    for row in cells:
        segment = pairs.get((row['segment'], row['tier']))
        cell = project_cell(row, segment, parent_by_name.get(row['segment']), proposals, snapshots, [], distribution_records)
        cell['availability_status'] = assignment_availability(segment, states)
        parent = parent_by_name.get(row['segment'])
        if parent:
            guidance = estimate(cell.get('offer'), row, parent, pricing_settings)
            cell['pricing_guidance'] = await cached_advice(db, parent, row, cell.get('offer'), guidance)

        projected.append(cell)
    # Approval tasks come from current product state, not an old quote snapshot.
    media_ids={part['variant_id'] for cell in projected for key in ('offer','approved_offer')
        for part in (cell.get(key) or {}).get('components',[]) if part.get('variant_id')}
    variants=(await db.execute(select(CatalogueVariant).where(CatalogueVariant.id.in_(media_ids)))).scalars().all() if media_ids else []
    from app.services.shared_variant_assets import final_assets_by_variant, approved_model_photos
    ready=await final_assets_by_variant(db,variants)
    by_id={variant.id:variant for variant in variants}
    for cell in projected:
        for key in ('offer','approved_offer'):
            if not cell.get(key):
                continue
            cell[key]=deepcopy(cell[key])
            for part in cell[key].get('components',[]):
                variant=by_id.get(part.get('variant_id'))
                if variant is None:
                    part.update(photo_ready=False,media_ready=False,model_generation_status=None)
                    continue
                part.update(photo_ready=bool(approved_model_photos(variant)),media_ready=variant.id in ready,
                    model_generation_status=((variant.asset_media_review or {}).get('generation') or {}).get('status'))
    return {'observed_at': datetime.now(timezone.utc), 'cells': projected,
        'unassigned_channel_records': len(unassigned),
        'unassigned_distribution': unassigned, 'build_market_references': market_references}
