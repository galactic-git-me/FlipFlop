"""New focused deterministic checks; no provider calls or DB writes."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch
from app.services.playbook_pricing_guidance import estimate, local_market_advice, amount
from app.services.curated_build_policy import definitions
from app.services.playbook_service import required_parts

def checks():
    definition=definitions()['builds'][0]
    parts=[dict(role=role,title=role,slot_id=i+1,variant_id=i+1,listing_price_gbp='100',supplier_postage_gbp='5',landed_gbp='105',source_observation={}) for i,role in enumerate(required_parts(definition))]
    offer=dict(components=parts,purchasable=False,blockers=['Source checks incomplete'])
    parent=Obj(profit_strategy={},pricing_model={})
    settings=Obj(opportunity_delivery_fallback_gbp=15,speedy_curated_custom_days=7,standard_curated_custom_days=14,flexible_curated_custom_days=21,speedy_delivery_price_gbp=0)
    original=deepcopy(offer)
    full=estimate(offer,definition,parent,settings)
    assert full['estimated_price_gbp'] and not full['purchasable']
    assert offer==original
    parts[0]['supplier_postage_gbp']=None
    partial=estimate(offer,definition,parent,settings)
    assert partial['estimated_price_gbp'] and any('postage excluded' in g for g in partial['gaps'])
    assert float(partial['estimated_price_gbp']) < float(full['estimated_price_gbp'])
    parts.pop()
    partial=estimate(offer,definition,parent,settings)
    assert partial['estimated_price_gbp'] is None and partial['status']=='partial'
    assert partial['known_parts_subtotal_gbp']
    for bad in ('NaN','Infinity','-1'): assert amount(bad) is None
    assert amount('0')==0

async def advice_checks():
    from app.services.model_selection_service import model_selection_service
    data=dict(price_options_gbp=['1000.00'],above_observed_market=False,comparisons=[dict(id='sold:1',total_gbp='1200.00')],observed_at='2026-10-22T00:00:00+00:00')
    data.update(provisional_minimum_gbp='1000.00', profit_check=dict(passes_on_recorded_costs=True,fixed_cost_gbp='700.00',minimum_margin_fraction='0.10'),pricing_rates=dict(vat_rate='0',payment_rate='.03',warranty_rate='.05',returns_rate='.02'),minimum_contribution_gbp='60.00')
    good='{"summary":"Within observations","position":"value","price_option_gbp":"1000.00","comparison_ids":["sold:1"]}'
    response=Obj(text=good,provider='ollama',model='local-test')
    with patch.object(model_selection_service,'complete',new=AsyncMock(return_value=response)) as call:
        result=await local_market_advice(data)
        assert result['authority']=='advisory_only'
        assert call.call_args.kwargs['local_only'] and call.call_args.kwargs['free_only']
        for bad in (good.replace('1000.00','999999'),good.replace('1000.00','NaN'),good.replace('sold:1','fabricated')):
            response.text=bad
            try: await local_market_advice(data)
            except ValueError: pass
            else: raise AssertionError('Unsupported advice accepted')
        response.text=good
        data['above_observed_market']=True
        assert (await local_market_advice(data))['position']=='overpriced'
        data['profit_check']['fixed_cost_gbp']='950.00'
        try: await local_market_advice(data)
        except ValueError: pass
        else: raise AssertionError('LLM price below actual-cost margin floor accepted')


async def evidence_checks():
    from datetime import datetime, timedelta, timezone
    from app.services.playbook_market import bom_hash, key
    from app.services.playbook_pricing_guidance import market_input, cached_advice, input_hash
    definition=definitions()['builds'][0]
    parts={'cpu':dict(role='cpu',title='Example CPU',variant_id=1)}
    offer={'components':list(parts.values())}
    now=datetime.now(timezone.utc)
    market=dict(bom_sha256=bom_hash(definition,parts),batch_id=5,candidate_ids=['sold:1'],observed_at=now.isoformat(),
        sold_transactions=[dict(url=f'https://www.ebay.co.uk/itm/{123456789012+i}',sold_at=now.isoformat()) for i in range(8)])
    parent=Obj(id=1,pricing_model={'cell_market_evidence':{definition['id']:market}})
    batch=Obj(status='market_candidates',product_key=key(1,definition['id']),evidence_json={
        'bom_sha256':market['bom_sha256'],'observed_at':market['observed_at'],'candidates':[
            dict(id='sold:1',title='Complete PC',url='https://www.ebay.co.uk/itm/123456789012',kind='sold',condition='new',total_gbp='1200.00',blockers=[]),
            dict(id='sold:2',title='Unreviewed PC',url='https://www.ebay.co.uk/itm/123456789013',kind='sold',condition='new',total_gbp='1.00',blockers=[])]})
    db=Obj(get=AsyncMock(return_value=batch))
    guidance=dict(estimated_price_gbp='1000.00',gaps=[],market_advice={'status':'evidence_needed'})
    data=await market_input(db,parent,definition,offer,guidance)
    assert len(data['comparisons'])==1 and data['price_options_gbp']==['1200.00']
    cache=Obj(created_at=now,evidence_json={'input_hash':input_hash(data)},decision_json={'status':'ready','summary':'Cached'})
    db.execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda:cache))
    assert (await cached_advice(db,parent,definition,offer,deepcopy(guidance)))['market_advice']['summary']=='Cached'
    changed={**guidance,'estimated_price_gbp':'1300.00'}
    assert (await cached_advice(db,parent,definition,offer,changed))['market_advice']['status']=='pending'
    market['observed_at']=(now-timedelta(days=31)).isoformat()
    assert await market_input(db,parent,definition,offer,guidance) is None
    market['observed_at']=now.isoformat()
    offer['components'][0]['variant_id']=2
    assert await market_input(db,parent,definition,offer,guidance) is None

def profit_checks():
    from decimal import Decimal as D
    from app.services.playbook_commercial_quote import mode_economics, check_price_profit
    from app.schemas.commercial_quote import ModePolicy
    from pydantic import ValidationError
    costs=dict(build_labour=D('0'),packaging=D('0'),outbound_delivery=D('0'),insurance=D('0'),payment_fixed=D('0'),expected_failure_cost=D('0'),allocated_overhead=D('0'),other_variable_costs=D('0'))
    policy=Obj(vat_rate=D('0'),payment_rate=D('0'),warranty_rate=D('0'),returns_rate=D('0'))
    mode=Obj(costs=Obj(model_dump=lambda:costs),minimum_margin_fraction=D('.01'),minimum_contribution_gbp=D('0'),premium_gbp=D('0'))
    # Ten percent markup is only 9.09 percent margin and must fail.
    assert not check_price_profit(policy,mode,D('1000'),D('1100'))['passes']
    economics=mode_economics(policy,mode,D('1000'))
    assert economics['contribution'] >= economics['net']*D('.10')
    assert check_price_profit(policy,mode,D('1000'),economics['price'])['passes']
    for target in ('.12','.15'):
        mode.minimum_margin_fraction=D(target)
        policy.payment_rate=D('.0315');policy.warranty_rate=D('.05');policy.returns_rate=D('.02')
        costs['build_labour']=D('120');costs['outbound_delivery']=D('20')
        economics=mode_economics(policy,mode,D('1000'))
        assert economics['contribution'] >= economics['net']*D(target)
        assert not check_price_profit(policy,mode,D('1500'),economics['price'])['passes'], 'Increased actual costs did not block old price'
    try:
        ModePolicy.model_validate(dict(costs=costs,minimum_margin_fraction='.09',minimum_contribution_gbp='0',premium_gbp='0',workshop_working_days=1,courier_working_days=1,maximum_delivery_working_days=7))
    except ValidationError: pass
    else: raise AssertionError('Sub-10 percent margin policy accepted')

if __name__=='__main__':
    checks()
    profit_checks()
    asyncio.run(advice_checks())
    asyncio.run(evidence_checks())
    print('PASS: separate estimates, incomplete total withholding, local-only routing, evidence validation')
