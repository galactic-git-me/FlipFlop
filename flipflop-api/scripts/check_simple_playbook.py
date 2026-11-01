"""Standalone deterministic checks; no database, services or provider requests."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace as NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.playbook_pricing_guidance import cost_plus_ten, economics, cached_advice, estimate
from app.services.playbook_stored_offers import suggested_offer, same_product, product_keys, offers_for_part, recorded_offer
from app.services.playbook_service import _plausible_role_candidate, _distinct_storage_devices, _ram_quantity, _candidate_performance, _candidate_key
from app.services.playbook_requirement_catalogue import matches_requirement
from app.services.playbook_planning_checks import case_conflicts
from app.services.playbook_component_facts import manufacturer_facts
from app.services.curated_catalogue_range import select_curated_range


async def check():
    for fixed in map(Decimal, ['0.01','41.20','500','1234.56','10000']):
        price = cost_plus_ten(fixed)
        _, _, cost, profit = economics(fixed, price)
        assert profit >= cost*Decimal('.10')
        _, _, cost_before, profit_before = economics(fixed, price-Decimal('.01'))
        assert profit_before < cost_before*Decimal('.10')
    assert not _plausible_role_candidate('cpu', 'Regiment Gaming PC AMD Ryzen 5 5600G 16GB')
    assert not _plausible_role_candidate('cpu','ExpertCenter SFF AMD Ryzen AI 7 350 16GB RAM 512GB SSD Windows 11')
    assert not _plausible_role_candidate('cooling','B GRADE Noctua NH-U14S TR5-SP6 CPU Cooler')
    assert not matches_requirement('storage_secondary','SanDisk Desk Drive SSD 8TB','8TB data SSD')
    assert not matches_requirement('storage_secondary','ORICO USB-C SSD Docking Station 40 TB','8TB data SSD')
    assert matches_requirement('gpu','PNY NVIDIA RTX 6000 ADA','NVIDIA RTX 6000 Ada 48GB')
    assert not matches_requirement('gpu','NVIDIA RTX A6000 48GB','NVIDIA RTX 6000 Ada 48GB')
    assert matches_requirement('ram','Silicon Power RDIMM 32GB (1x32GB) DDR5 C40 4800MHz Single Channel Kit','256GB (8x32GB) DDR5 ECC RDIMM')
    assert not matches_requirement('gpu','(No GPU) AORUS GeForce RTX 5090 Master Graphics Card Only as Decoration Collectible Model','NVIDIA RTX 5090 32GB')
    assert not matches_requirement('gpu','Medion Erazer Beast 16 X1 NVIDIA RTX 5090 32GB 16 QHD+ AMD Ryzen 9-9955HX','NVIDIA RTX 5090 32GB')
    ventus={'role':'gpu','cpk':'amazon-key','title':'MSI GeForce RTX 5090 32G VENTUS 3X OC Graphics Card'}
    scan={'observation_id':1,'cpk':'scan-key','title':'MSI NVIDIA GeForce RTX 5090 32GB VENTUS 3X OC Blackwell Graphics Card',
          'item_gbp':'4599.98','url':'https://www.scan.co.uk/products/ventus','delivery_gbp':None}
    assert same_product(ventus,scan)
    assert not same_product(ventus,{**scan,'title':'MSI GeForce RTX 5090 32GB GAMING TRIO OC'})
    assert not same_product(ventus,{**scan,'title':'MSI GeForce RTX 5080 16GB VENTUS 3X OC'})
    assert not same_product(ventus,{**scan,'title':'MSI GeForce RTX 5090 32GB VENTUS 3X'})
    index={key:[scan] for key in product_keys('gpu',scan['title'])}
    matches=offers_for_part(ventus,index)
    assert len(matches)==1 and matches[0]['observation_id']==1 and matches[0]['match_basis']=='exact_product_identity'
    from datetime import datetime, timezone
    capture={'id':1,'listing_id':100,'cpk':'x','title':scan['title'],'source':'scan','item_price':4599.98,
             'observed_at':datetime.now(),'recorded_product_url':scan['url'],'commercial_source_evidence':{}}
    assert recorded_offer(capture)['url_basis']=='same_listing_recorded_url'
    assert recorded_offer({**capture,'recorded_product_url':None}) is None
    assert recorded_offer({**capture,'commercial_source_evidence':{'stock_status':'unavailable'}}) is None
    unavailable={**ventus,'variant_id':1,'listing_price_gbp':'3000','price_observed_at':datetime.now(timezone.utc).isoformat(),
                 'source_observation':{'stock_status':'unavailable'}}
    available={**ventus,'variant_id':2,'listing_price_gbp':'6000','price_observed_at':datetime.now(timezone.utc).isoformat(),
               'source_observation':{'stock_status':'available'}}
    assert _candidate_key(available,ventus['title']) < _candidate_key(unavailable,ventus['title'])
    current={**available,'price_observed_at':datetime.now(timezone.utc).isoformat()}
    stale={**available,'listing_price_gbp':'3000','price_observed_at':'2026-01-01T00:00:00'}
    assert _candidate_key(current,ventus['title']) < _candidate_key(stale,ventus['title'])
    snapshot={**ventus,'source_url':scan['url'],'listing_price_gbp':'3000','price_observed_at':'2026-01-01T00:00:00'}
    latest={**scan,'observed_at':datetime.now(timezone.utc).isoformat(),'stock_status':'available'}
    assert suggested_offer(snapshot,[latest])['item_gbp']=='4599.98'
    from app.services.hardware_performance import _normalise_for_category
    key=('gpu',_normalise_for_category('gpu','PNY NVIDIA RTX 6000 ADA'))
    assert _candidate_performance('gpu','PNY NVIDIA RTX 6000 ADA',{key:NS(model='GRID RTX6000-1B')}) is None
    assert matches_requirement('motherboard','Asus Pro WS WRX90E-SAGE SE AMD sTR5 EEB Workstation Motherboard','ASUS Pro WS WRX90E-SAGE SE')
    module={'title':'Micron 64GB (1x64GB) DDR5 ECC RDIMM','listing_price_gbp':'100.00',
            'supplier_postage_gbp':'2.00','engineering':{},'planning_engineering':{},
            'suggested_supplier_offer':{'item_gbp':'100.00','delivery_gbp':'2.00'}}
    kit=_ram_quantity(module,256)
    assert kit['quantity']==4 and kit['listing_price_gbp']=='400.00'
    assert kit['supplier_postage_gbp']=='8.00' and kit['planning_engineering']['ram_modules']==4
    kz10={'planning_engineering':manufacturer_facts('case','iONZ KZ10 PC Case')}
    freezer={'planning_engineering':manufacturer_facts('cooling','ARCTIC Freezer 36 Black')}
    assert case_conflicts({'cooling':freezer},kz10)
    assert case_conflicts({'cooling':{'title':'ARCTIC Liquid Freezer III 360 AIO'}},kz10)
    c1={'planning_engineering':manufacturer_facts('case','APNX Creator C1 ChromaFlair Mid Tower Case')}
    assert not case_conflicts({'cooling':freezer},c1)
    d15={'planning_engineering':manufacturer_facts('cooling','Noctua NH-D15 G2 chromax.black')}
    assert case_conflicts({'cooling':d15},c1)
    assert _distinct_storage_devices({'storage':{'variant_id':1,'listing_id':100},
                                      'storage_secondary':{'variant_id':2,'listing_id':100}})
    assert not _distinct_storage_devices({'storage':{'variant_id':1,'listing_id':100},
                                          'storage_secondary':{'variant_id':1,'listing_id':100}})
    case = {'role':'case','title':'Lian Li A3 mATX Gaming PC Case Black','listing_price_gbp':'73.99'}
    assert not same_product(case, {'title':'Lian Li A3-MATX Front wood panel'})
    cooler = {'role':'cooling','title':'Thermalright AQUA ELITE 240 V3 Liquid CPU Cooler','listing_price_gbp':'35.90'}
    assert not same_product(cooler, {'title':'Thermalright Assassin X120 Refined SE CPU Air Cooler'})
    assert suggested_offer(case, [{'title':'Lian Li A3-MATX Front wood panel','item_gbp':'19.99'}])['item_gbp']=='73.99'
    rows = [NS(category='case',title=f'PC case {i}',rank=i,asin=str(i)) for i in range(1,121)]
    selected,_ = select_curated_range(rows, [])
    assert len(selected)==100 and max(row.rank for row in selected)==100

    parts = [{'role': role, 'title': title, 'listing_price_gbp':'10.00', 'cpk':role}
             for role,title in [('cpu','AMD Ryzen 5 5600X'),('gpu','NVIDIA RTX 3050 8GB'),
                                ('ram','16GB DDR4 RAM'),('storage','1TB NVMe SSD')]]
    offer={'components':parts}
    floor=cost_plus_ten(Decimal('100'))
    base={'estimated_price_gbp':str(floor),'cost_plus_10_floor_gbp':str(floor),
          'fixed_cost_gbp':'100','known_parts_subtotal_gbp':'40'}
    class DB:
        def __init__(self, rows=(), sales=None):
            self.rows=rows
            self.info={'simple_playbook_component_sales': sales or {}}
        async def execute(self,*args,**kwargs):
            return NS(scalars=lambda:NS(all=lambda:self.rows))
    parent=NS(id=1);definition={'id':'demo'}
    whole=NS(evidence_json={'candidates':[{'id':'sold1','kind':'sold','condition':'new',
        'title':'Gaming PC Ryzen 5 5600X RTX 3050 16GB 1TB','total_gbp':'500','url':'https://example.com/sold/1','blockers':[]}]})
    result=await cached_advice(DB([whole]),parent,definition,offer,deepcopy(base))
    assert result['price_basis']=='complete_pc_sold_median' and result['estimated_price_gbp']=='500.00'
    sales={(p['cpk'],'new'):{'condition':'new','median':20,'sample_count':1} for p in parts}
    result=await cached_advice(DB(sales=sales),parent,definition,offer,deepcopy(base))
    assert result['price_basis']=='component_sold_prices_plus_10_percent'
    sales.pop(('ram','new'))
    result=await cached_advice(DB(sales=sales),parent,definition,offer,deepcopy(base))
    assert result['price_basis']=='component_sold_prices_with_cost_fallback' and len(result['component_sold_context'])==3
    result=await cached_advice(DB(),parent,definition,offer,deepcopy(base))
    assert result['price_basis']=='cost_plus_10_percent'
    assert estimate({'components':[]},{'components':{}},parent,None)['estimated_price_gbp'] is None
    from app.services.playbook_service import required_parts
    complete = {'components':[{'role':role,'listing_price_gbp':'10.00','supplier_postage_gbp':None}
                              for role in required_parts({'components':{}})]}
    defaults = estimate(complete,{'components':{}},parent,None)
    assert defaults['cost_allowances_gbp']['outbound_delivery']=='15.00'
    assert defaults['known_parts_subtotal_gbp']=='80.00' and not defaults['gaps']
    assert defaults['estimated_price_gbp'] is not None
    complete['components'][0]['supplier_postage_gbp']='2.50'
    assumed_unknown = estimate(complete,{'components':{}},parent,NS(opportunity_delivery_fallback_gbp=0))
    assert assumed_unknown['known_parts_subtotal_gbp']=='80.00'
    complete['components'][0]['supplier_postage_assumption']='captured'
    recorded = estimate(complete,{'components':{}},parent,NS(opportunity_delivery_fallback_gbp=0))
    assert recorded['known_parts_subtotal_gbp']=='82.50'
    assert recorded['cost_allowances_gbp']['outbound_delivery']=='0.00'
    print('PASS: prices/profit, postage defaults, sold hierarchy, top-ten hardware and top-100 case ranges, exact product matching, RDIMM quantities and chassis/cooler incompatibilities; zero provider requests.')


if __name__=='__main__':
    asyncio.run(check())
