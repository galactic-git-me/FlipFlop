"""Collected complete-PC comparisons, pinned to one cell's selected BOM.

Prices are provider facts. Reviewers select listings and attest to the complete
specification; they cannot enter replacement prices or an invented median.
"""
import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select
from app.models.commerce_evidence import PriceQuoteSnapshot
from app.models.playbook import PlaybookProposal
from app.services.commercial_readiness import cell_context, definition_hash

MIN_MARKET_CAP_SOLD_SAMPLE = 8


def bom_hash(definition, parts):
    values = {role: {'variant_id': part.get('variant_id'), 'case_catalogue_id': part.get('case_catalogue_id'), 'title': part.get('title')}
              for role, part in parts.items()}
    return hashlib.sha256(json.dumps([definition_hash(definition), values], sort_keys=True).encode()).hexdigest()


def approved_market(parent, definition, parts):
    saved = (((getattr(parent, 'pricing_model', None) or {}).get('cell_market_evidence') or {})
             .get(definition['id']))
    if not saved or saved.get('bom_sha256') != bom_hash(definition, parts):
        return None
    transactions=saved.get('sold_transactions') or []
    if len(transactions)<MIN_MARKET_CAP_SOLD_SAMPLE or any(sold_date_blocker(row.get('sold_at')) for row in transactions):
        return None
    observed = datetime.fromisoformat(saved['observed_at'])
    if not observed.tzinfo or not datetime.now(timezone.utc) - timedelta(days=30) <= observed <= datetime.now(timezone.utc):
        return None
    return saved


def listing_identity(url):
    parsed = urlsplit(url or '')
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        return None
    if not (parsed.hostname or '').endswith('.ebay.co.uk') and parsed.hostname != 'www.ebay.com':
        return None
    match = re.search(r'/itm/(?:[^/]+/)?(\d{9,15})(?:[/?]|$)', parsed.path + '/')
    return match.group(1) if match else None


def summarize(rows):
    result = {}
    for kind in ('sold', 'active'):
        prices = [Decimal(row['total_gbp']) for row in rows if row['kind'] == kind]
        result[f'{kind}_sample_size'] = len(prices)
        result[f'{kind}_median_gbp'] = str(Decimal(median(prices)).quantize(Decimal('.01'))) if prices else None
        if kind == 'sold':
            result['sold_p75_gbp'] = percentile_75(prices)
    return result


def percentile_75(prices):
    """Linear-interpolated 75th percentile, rounded to the nearest penny."""
    ordered = sorted(Decimal(str(price)) for price in prices)
    if len(ordered) < MIN_MARKET_CAP_SOLD_SAMPLE:
        return None
    position = Decimal('0.75') * (len(ordered) - 1)
    lower = int(position)
    fraction = position - lower
    value = ordered[lower] + fraction * (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower])
    return str(value.quantize(Decimal('.01')))


def sold_date_blocker(value, *, now=None):
    now=now or datetime.now(timezone.utc)
    text=' '.join(str(value or '').split())
    try:
        if text.lower().startswith('sold '):
            date=datetime.strptime(text[5:],'%d %b %Y').date()
        else:
            date=datetime.fromisoformat(text.replace('Z','+00:00')).date()
    except (ValueError,TypeError):
        return 'Sold transaction date is missing or unrecognised'
    age=(now.date()-date).days
    if age<0:return 'Sold transaction date is in the future'
    if age>30:return 'Sold transaction is outside the current 30-day window'
    return None


def candidate(raw, kind, condition, index):
    url = raw.get('url')
    identity = listing_identity(url)
    price, postage = raw.get('price'), raw.get('postage')
    blockers = []
    if not identity:
        blockers.append('Exact eBay listing URL missing')
    if not raw.get('title'):
        blockers.append('Listing title missing')
    actual_condition = str(raw.get('condition') or '').lower()
    if actual_condition != condition:
        blockers.append('Condition is unknown or does not match')
    try:
        total = Decimal(str(price)) + Decimal(str(postage))
        if not total.is_finite() or total <= 0 or Decimal(str(postage)) < 0 or Decimal(str(price)) <= 0:
            raise ValueError()
        total = str(total.quantize(Decimal('.01')))
    except Exception:
        total = None
        blockers.append('Item price or postage missing')
    if kind=='sold' and (reason:=sold_date_blocker(raw.get('sold_at'))):
        blockers.append(reason)
    title = str(raw.get('title') or '')
    if re.search(r'\b(faulty|broken|spares|repair|barebone|bundle|parts only|no gpu)\b', title, re.I):
        blockers.append('Incomplete or defective build')
    return {'id': f'{kind}:{identity or index}', 'kind': kind, 'title': title,
            'url': url if identity else None, 'condition': actual_condition,
            'total_gbp': total, 'sold_at': raw.get('sold_at'), 'blockers': blockers}


CPU_MODEL = r'\b(?:i[3579]-)?\d{3,5}(?:X3D|XT|X|KF|K|F|G|GT)?\b'
GPU_MODEL = r'\b(?:RTX|GTX|RX|Arc)\s*[AB]?\d{3,4}(?:\s*(?:Ti|SUPER|XT|XTX))?\b'
CAPACITY = r'\b(\d+(?:\.\d+)?)\s*(GB|TB)\b'


def search_query(parts):
    terms = ['desktop pc']
    for role, pattern in (('cpu', CPU_MODEL), ('gpu', GPU_MODEL), ('ram', CAPACITY), ('storage', CAPACITY)):
        match = re.search(pattern, str((parts.get(role) or {}).get('title') or ''), re.I)
        if match:
            terms.append(match.group())
    return ' '.join(terms)


def core_spec_blockers(title, parts):
    """Title anchors plus human review of the remaining complete specification."""
    blockers = []
    for role in ('cpu', 'gpu'):
        spec = str((parts.get(role) or {}).get('title') or '')
        pattern = GPU_MODEL if role == 'gpu' else CPU_MODEL
        model = re.search(pattern, spec, re.I)
        if not model:
            if role in parts:
                blockers.append(f'{role.upper()} model could not be resolved for comparison')
            continue
        wanted = r'[\s-]*'.join(re.escape(token) for token in re.findall(r'[a-z]+|\d+', model.group().lower()))
        if not re.search(r'(?<![a-z0-9])' + wanted + r'(?![a-z0-9]|\s*(?:xtx|xt|ti|super)\b)', title, re.I):
            blockers.append(f'Exact {role.upper()} model not evidenced in listing title')
    for role in ('ram', 'storage'):
        spec = str((parts.get(role) or {}).get('title') or '')
        capacity = re.search(CAPACITY, spec, re.I)
        if not capacity or not re.search(r'(?<![\d.])' + re.escape(capacity.group(1)) + r'\s*' + capacity.group(2) + r'\b', title, re.I):
            blockers.append(f'Exact {role} capacity not evidenced in listing title')
    if not re.search(r'\b(pc|desktop|computer|workstation)\b', title, re.I):
        blockers.append('Complete desktop PC not evidenced in listing title')
    return blockers


async def context(db, parent_id, cell_id, lock=False):
    parent, definition = await cell_context(db, parent_id, cell_id, lock=lock)
    if lock:
        await db.refresh(parent)
    proposal = (await db.execute(select(PlaybookProposal).where(
        PlaybookProposal.playbook_id == parent_id, PlaybookProposal.status == 'pending',
        PlaybookProposal.action == 'UPDATE').order_by(PlaybookProposal.id.desc()).execution_options(populate_existing=True))).scalars().all()
    offer = next((row.proposed_data for row in proposal
                  if (row.proposed_data or {}).get('cell_id') == cell_id), None)
    offer = offer or ((parent.pricing_model or {}).get('managed_offers') or {}).get(cell_id)
    parts = {row['role']: row for row in (offer or {}).get('components', [])}
    from app.services.playbook_service import required_parts
    if not set(required_parts(definition)).issubset(parts):
        raise HTTPException(409, 'Generate a complete selected build before collecting its market comparisons')
    return parent, definition, parts


def key(parent_id, cell_id):
    return f'playbook:{parent_id}:cell:{cell_id}'


async def latest(db, parent_id, cell_id):
    return (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key == key(parent_id, cell_id),
        PriceQuoteSnapshot.status == 'market_candidates').order_by(
            PriceQuoteSnapshot.id.desc()).limit(1))).scalar_one_or_none()


async def review_view(db, parent_id, cell_id):
    parent, definition, parts = await context(db, parent_id, cell_id)
    batch = await latest(db, parent_id, cell_id)
    data = batch.evidence_json if batch else None
    decisions = []
    if batch:
        decisions = (await db.execute(select(PriceQuoteSnapshot).where(
            PriceQuoteSnapshot.product_key == key(parent_id, cell_id),
            PriceQuoteSnapshot.status.in_(['market_approved', 'market_rejected']))
            .order_by(PriceQuoteSnapshot.id.desc()).limit(20))).scalars().all()
    decision = next((row for row in decisions if row.evidence_json.get('batch_id') == (batch.id if batch else None)), None)
    return {'batch_id': batch.id if batch else None, 'batch': data,
            'current_bom_sha256': bom_hash(definition, parts),
            'stale': bool(data and (data['bom_sha256'] != bom_hash(definition, parts)
                or datetime.fromisoformat(data['observed_at']) < datetime.now(timezone.utc)-timedelta(days=30))),
            'decision': decision.status if decision else None,
            'approved': approved_market(parent, definition, parts),
            'components': {role: part['title'] for role, part in parts.items()}}


async def collect(db, parent_id, cell_id, actor_id, *, sold_timeout_seconds=150):
    from dataclasses import asdict
    from app.gem_radar.adapters.sold_comps import LiveSoldCompsAdapter, PlaywrightSoldCompsAdapter
    from app.services.ebay_browse import search_active_listings
    _, definition, parts = await context(db, parent_id, cell_id)
    fingerprint = bom_hash(definition, parts)
    query = search_query(parts)
    sold_adapter = LiveSoldCompsAdapter()
    sold_adapter._MAX_PRICE = 10000  # Include the Playbook's premium complete PCs.
    async def sold_with_browser_fallback():
        result = await sold_adapter.fetch(query, 'new')
        if result.available:
            return result
        browser_adapter = PlaywrightSoldCompsAdapter()
        browser_adapter._MAX_PRICE = 10000
        browser_result = await browser_adapter.fetch(query, 'new')
        if not browser_result.available and browser_result.unavailable_reason:
            browser_result.unavailable_reason = f"{result.unavailable_reason}; {browser_result.unavailable_reason}"
        return browser_result

    # New-build comparisons only; used PCs cannot establish a new-build market.
    sold, active = await asyncio.gather(
        asyncio.wait_for(sold_with_browser_fallback(), sold_timeout_seconds),
        asyncio.wait_for(search_active_listings(query, condition_filter='NEW', limit=30, category_id='179'), 65),
        return_exceptions=True)
    rows, errors = [], []
    if isinstance(sold, BaseException):
        errors.append('Sold-listing provider unavailable or timed out')
    else:
        errors.extend([] if sold.available else [sold.unavailable_reason or 'No sold observations'])
        rows.extend(candidate({**asdict(row),
            'postage': row.postage if row.delivery_cost_known else None,
            'sold_at': row.sold_date_text}, 'sold', 'new', i) for i, row in enumerate(sold.comps[:60]))
    if isinstance(active, BaseException):
        errors.append('Current-listing provider unavailable or timed out')
    else:
        # Browse prices already include delivery. Unknown delivery remains blocked.
        rows.extend(candidate({**row, 'postage': 0 if row.get('delivery_cost_known') else None},
                              'active', 'new', i) for i, row in enumerate(active[:30]))
        if not active:
            errors.append('No current listings returned; check provider availability')
    dedup = {}
    for row in rows:
        row['blockers'].extend(core_spec_blockers(row['title'], parts))
        dedup.setdefault(row['id'], row)
    # Never attach a slow provider result to a selection that changed meanwhile.
    _, current_definition, current_parts = await context(db, parent_id, cell_id, lock=True)
    if bom_hash(current_definition, current_parts) != fingerprint:
        raise HTTPException(409, 'The selected build changed during collection; collect again')
    batch = PriceQuoteSnapshot(product_key=key(parent_id, cell_id), status='market_candidates',
        created_by_admin_id=actor_id, evidence_json={'bom_sha256': fingerprint,
            'observed_at': datetime.now(timezone.utc).isoformat(), 'condition': 'new', 'query': query,
            'components': {role: part['title'] for role, part in parts.items()},
            'candidates': list(dedup.values()), 'errors': errors}, decision_json={'purchasable': False})
    db.add(batch)
    await db.commit()
    return await review_view(db, parent_id, cell_id)


async def decide(db, parent_id, cell_id, body, actor_id):
    parent, definition, parts = await context(db, parent_id, cell_id, lock=True)
    batch = await latest(db, parent_id, cell_id)
    if not batch or batch.id != body.batch_id or batch.evidence_json['bom_sha256'] != bom_hash(definition, parts):
        raise HTTPException(409, 'Market evidence or selected build changed; reload the review')
    data = batch.evidence_json
    if datetime.fromisoformat(data['observed_at']) < datetime.now(timezone.utc)-timedelta(days=30):
        raise HTTPException(409, 'Market observations expired; collect fresh evidence')
    view = await review_view(db, parent_id, cell_id)
    if view['decision']:
        raise HTTPException(409, 'This collection has already been reviewed; collect again for a new decision')
    selected = [row for row in data['candidates'] if row['id'] in body.candidate_ids]
    if body.decision == 'approve':
        if not body.exact_build_confirmed or not selected or len(selected) != len(set(body.candidate_ids)):
            raise HTTPException(422, 'Select captured comparisons and confirm their complete build specifications')
        if any(row['kind']=='sold' and sold_date_blocker(row.get('sold_at')) for row in selected):
            raise HTTPException(422, 'Sold transactions need recognised dates within the current 30-day window')
        if any(row['blockers'] for row in selected):
            raise HTTPException(422, 'Blocked observations cannot be approved')
        # A relisted item cannot count both as a completed sale and a current offer.
        identities = [listing_identity(row['url']) or row['id'] for row in selected]
        if len(identities) != len(set(identities)):
            raise HTTPException(422, 'The same listing cannot count twice')
        summary = summarize(selected)
        if summary['sold_sample_size'] < MIN_MARKET_CAP_SOLD_SAMPLE:
            raise HTTPException(422, f'At least {MIN_MARKET_CAP_SOLD_SAMPLE} distinct confirmed sold complete PCs are required for a High-end cap')
        if summary['sold_p75_gbp'] is None:
            raise HTTPException(422, 'The selected comparisons do not yield a valid P75 cap')
        approved = {**summary, 'condition': data['condition'], 'observed_at': data['observed_at'],
            'bom_sha256': data['bom_sha256'], 'batch_id': batch.id, 'candidate_ids': body.candidate_ids,
            'approved_at': datetime.now(timezone.utc).isoformat(), 'approved_by': actor_id,
            'evidence_source': 'reviewed_ebay_complete_pc', 'evidence_ref': f'market-batch:{batch.id}',
            'cap_method': 'sold_p75_linear_interpolation',
            'minimum_sold_sample_size': MIN_MARKET_CAP_SOLD_SAMPLE,
            'sold_transactions':[{'url':row['url'],'sold_at':row['sold_at']} for row in selected if row['kind']=='sold']}
        pricing = dict(parent.pricing_model or {})
        parent.pricing_model = {**pricing, 'cell_market_evidence': {
            **(pricing.get('cell_market_evidence') or {}), cell_id: approved}}
    db.add(PriceQuoteSnapshot(product_key=key(parent_id, cell_id), status=f'market_{"approved" if body.decision == "approve" else "rejected"}',
        created_by_admin_id=actor_id, evidence_json={'batch_id': batch.id, 'request': body.model_dump(mode='json')},
        decision_json={'checkout_changed': False, 'published': False}))
    await db.commit()
    return await review_view(db, parent_id, cell_id)
