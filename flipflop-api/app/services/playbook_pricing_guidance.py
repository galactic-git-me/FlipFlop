"""Simple draft prices: whole-PC sales, component sales, then cost plus 10%.

Uses already captured data only. No provider calls, LLM, rights-review workflow,
minimum sample gate or physical workload acceptance is needed for a suggestion.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from statistics import median
from types import SimpleNamespace

from sqlalchemy import select, text
from app.models.commerce_evidence import PriceQuoteSnapshot


def amount(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def buying_postage(part, supplier):
    verified = (supplier.get('postage_verified') is True
                or supplier.get('postage_assumption') == 'captured'
                or (not supplier and part.get('supplier_postage_assumption') == 'captured'))
    value = supplier.get('delivery_gbp') if supplier else part.get('supplier_postage_gbp')
    return amount(value) if verified else Decimal('0.00'), verified


def money(value):
    return str(value.quantize(Decimal('.01'), rounding=ROUND_CEILING)) if value is not None else None


RATES = SimpleNamespace(vat_rate=Decimal('0'), payment_rate=Decimal('.0315'),
                        warranty_rate=Decimal('.05'), returns_rate=Decimal('.02'))


def economics(fixed, price):
    from app.services.playbook_commercial_quote import _economics
    return _economics(RATES, fixed, price)


def cost_plus_ten(fixed):
    """10% profit on total cost, including price-dependent fees/reserves."""
    factor = Decimal('1.10')
    rates = RATES.payment_rate + RATES.warranty_rate + RATES.returns_rate
    price = Decimal(money(fixed * factor / (1 - rates * factor)))
    while True:
        _, _, cost, profit = economics(fixed, price)
        if profit >= cost * Decimal('.10'):
            return price
        price += Decimal('.01')


def estimate(offer, definition, parent, settings):
    from app.services.playbook_service import required_parts, unmodelled_required_components
    parts = {part['role']: deepcopy(part) for part in (offer or {}).get('components', [])}
    gaps = [f'{role}: no selected component' for role in sorted(set(required_parts(definition)) - parts.keys())]
    gaps.extend(unmodelled_required_components(definition))
    known = Decimal(0)
    postage_defaults = []
    for role, part in parts.items():
        supplier = part.get('suggested_supplier_offer') or {}
        item = amount(supplier.get('item_gbp', part.get('listing_price_gbp')))
        postage, postage_verified = buying_postage(part, supplier)
        if supplier:
            quantity=part.get('quantity') or 1
            item=item*quantity if item is not None else None
            postage=postage*quantity if postage is not None else None
        if item is None:
            gaps.append(f'{role}: no recorded item price')
        if not postage_verified:
            postage_defaults.append(f'{role}: buying postage defaults to £0.00 (not recorded).')
        if part.get('draft_software_candidate'):
            postage_defaults.append(f'{role}: captured licence cost is provisional; source review is still required before publication.')
        known += (item or Decimal(0)) + (postage or Decimal(0))
    delivery = amount(getattr(settings, 'opportunity_delivery_fallback_gbp', None))
    allowances = {'build_labour': Decimal(0), 'packaging': Decimal(6),
                  'outbound_delivery': delivery if delivery is not None else Decimal(15),
                  'insurance': Decimal(15), 'payment_fixed': Decimal('.20'),
                  'allocated_overhead': (known * Decimal('.10')).quantize(Decimal('.01'), rounding=ROUND_CEILING)}
    fixed = known + sum(allowances.values())
    result = {'authority': 'admin_estimate_only', 'purchasable': False, 'status': 'partial',
              'estimated_price_gbp': None, 'estimated_profit_gbp': None,
              'known_parts_subtotal_gbp': money(known), 'gaps': gaps,
              'cost_allowances_gbp': {key: money(value) for key, value in allowances.items()},
              'price_basis': 'cost_plus_10_percent', 'cost_plus_10_floor_gbp': None,
              'fixed_cost_gbp': money(fixed),
              'assumptions': ['Fallback profit is 10% of total cost (markup), not a 10% sales margin.',
                              'Unknown buying postage defaults to £0.00; selling-build delivery defaults to £15.00.',
                              'Includes operating allowances and payment/warranty/returns rates; VAT assumes current non-registration.',
                              *postage_defaults],
              'market_advice': {'status': 'unavailable', 'summary': 'Checking stored sold-price evidence.'}}
    if not parts or gaps:
        result['market_advice']['summary'] = 'Some component identities or costs are missing.'
        return result
    price = cost_plus_ten(fixed)
    result['cost_plus_10_floor_gbp'] = money(price)
    return _set_price(result, price, 'cost_plus_10_percent')


def _set_price(result, price, basis):
    net, charges, cost, profit = economics(Decimal(result['fixed_cost_gbp']), price)
    result.update(status='estimated', estimated_price_gbp=money(price),
                  estimated_profit_gbp=money(profit), price_basis=basis)
    result['profit_check'] = {'status': 'estimate', 'passes_on_recorded_costs': profit >= cost * Decimal('.10'),
        'actual_costs_verified': False, 'minimum_margin_fraction': str(Decimal(1)/11),
        'margin_fraction': str(profit/net), 'profit_gbp': money(profit),
        'total_cost_gbp': money(cost), 'basis': 'Suggested price covers recorded full cost plus 10% profit on cost.',
        'markup_fraction': str(profit/cost) if cost else None,
        'charges_gbp': {key: money(value) for key, value in charges.items()}}
    return result


async def _sold_index(db):
    if 'simple_playbook_component_sales' not in db.info:
        rows = (await db.execute(text('''
            WITH dedup AS (
              SELECT DISTINCT ON (coalesce(nullif(canonical_item_id,''), nullif(source_url,''), 'row:'||id))
                     cpk, condition, price+coalesce(postage,0) AS total, observed_at, source_url
              FROM gem_radar_sold_observations
              WHERE cpk IS NOT NULL AND observed_at >= :since
                AND price > 0 AND price < 'Infinity'::float8
                AND (postage IS NULL OR (postage >= 0 AND postage < 'Infinity'::float8))
              ORDER BY coalesce(nullif(canonical_item_id,''), nullif(source_url,''), 'row:'||id), observed_at DESC,id DESC
            ) SELECT cpk, condition, percentile_cont(.5) WITHIN GROUP (ORDER BY total) AS median,
                     count(*) AS sample_count, max(observed_at) AS observed_at, min(source_url) AS source_url
              FROM dedup GROUP BY cpk,condition
        '''), {'since': datetime.utcnow()-timedelta(days=90)})).all()
        db.info['simple_playbook_component_sales'] = {(row.cpk, row.condition): dict(row._mapping) for row in rows}
    return db.info['simple_playbook_component_sales']


async def cached_advice(db, parent, definition, offer, guidance):
    """Use stored sold records immediately; pending approval does not hide a suggestion."""
    if not guidance.get('estimated_price_gbp'):
        return guidance
    from app.services.playbook_market import key, core_spec_blockers
    parts = {part['role']: part for part in (offer or {}).get('components', [])}
    batches = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key == key(parent.id, definition['id']),
        PriceQuoteSnapshot.status == 'market_candidates',
        PriceQuoteSnapshot.created_at >= datetime.utcnow()-timedelta(days=90)
    ).order_by(PriceQuoteSnapshot.id.desc()).limit(5))).scalars().all()
    whole = {}
    for batch in batches:
        for row in (batch.evidence_json or {}).get('candidates', []):
            price = amount(row.get('total_gbp'))
            blockers = ' '.join(str(value) for value in row.get('blockers', [])).casefold()
            if (row.get('kind') == 'sold' and row.get('condition') == 'new' and price and row.get('url')
                    and not any(word in blockers for word in ('accepted offer', 'unsold', 'defective', 'faulty'))
                    and not core_spec_blockers(row.get('title', ''), parts)):
                whole.setdefault(row.get('id') or row['url'], {**row, 'total_gbp': money(price)})
    comparisons = list(whole.values())
    context = []
    floor = Decimal(guidance['cost_plus_10_floor_gbp'])
    target = None
    basis = 'cost_plus_10_percent'
    if comparisons:
        target = Decimal(money(median(Decimal(row['total_gbp']) for row in comparisons)))
        basis = 'complete_pc_sold_median'
        summary = f'{len(comparisons)} recorded matching complete-PC sales; median £{money(target)}.'
    else:
        index = await _sold_index(db)
        for role, part in parts.items():
            if role.startswith('os'):
                continue
            cpk = part.get('cpk')
            sale = index.get((cpk, 'new')) or index.get((cpk, 'used'))
            if sale:
                context.append({'role': role, 'cpk': cpk, 'condition': sale['condition'],
                                'median_gbp': money(amount(sale['median'])*(part.get('quantity') or 1)),
                                'unit_median_gbp': money(amount(sale['median'])),
                                'quantity': part.get('quantity') or 1,
                                'sample_count': sale['sample_count'],
                                'source_url': sale.get('source_url'),
                                'observed_at': str(sale.get('observed_at') or '')})
        hardware_roles = [role for role in parts if not role.startswith('os')]
        if context:
            subtotal = sum(Decimal(row['median_gbp']) for row in context)
            covered = {row['role'] for row in context}
            for role, part in parts.items():
                if role.startswith('os') or role in covered:
                    continue
                supplier = part.get('suggested_supplier_offer') or {}
                subtotal += (amount(supplier.get('item_gbp', part.get('listing_price_gbp'))) or Decimal(0))
                postage, _ = buying_postage(part, supplier)
                subtotal += postage or Decimal(0)
            other = Decimal(guidance['fixed_cost_gbp']) - Decimal(guidance['known_parts_subtotal_gbp'])
            software = sum((amount(part.get('listing_price_gbp')) or Decimal(0)) for role, part in parts.items() if role.startswith('os'))
            target = cost_plus_ten(subtotal + other + software)
            basis = ('component_sold_prices_plus_10_percent' if len(context)==len(hardware_roles)
                     else 'component_sold_prices_with_cost_fallback')
            summary = (f'Component sold-price medians cover {len(context)}/{len(hardware_roles)} hardware roles. '
                       'Remaining roles use recorded supplier costs; software and operating costs added.')
        else:
            summary = f'Component sold prices cover {len(context)}/{len(hardware_roles)} hardware roles. Using recorded full cost plus 10% profit.'
    guidance['component_sold_context'] = context
    if target is not None and target < floor:
        summary += f' Market-based £{money(target)} is below the cost-plus-10 floor £{money(floor)}; suggesting the floor.'
        basis = 'cost_plus_10_percent_market_below_cost'
    price = max(target or floor, floor)
    _set_price(guidance, price, basis)
    guidance['market_advice'] = {'status': 'ready', 'summary': summary, 'position': basis,
                                'price_option_gbp': money(price), 'comparisons': comparisons}
    return guidance


async def refresh_market_advice(actor_id=0):
    """Legacy scheduler entry point; suggestions are now deterministic on read."""
    return {'status': 'stored_data_pricing', 'provider_requests': 0}
