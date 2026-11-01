"""Focused new deterministic source/identity checks. No live providers."""
import asyncio
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace as Obj
from app.services.commercial_readiness import _product_page_source_preview,prefer_exact_product_page_preview,same_listing_product
from app.services.playbook_service import assemble_components,_candidate_source_prices,_plausible_role_candidate,_planning_integrated_graphics

async def checks():
    digital_url='https://www.gamers-outlet.net/en/buy-windows-11-pro-cd-key-oem-microsoft-global-1'
    digital=Obj(id=2,external_id='digital-2',url=digital_url,price=4.68,status='active',source_name='Gamers Outlet',
        raw_specs={'playbook_product_capture':{'status':'captured','url':digital_url,
            'observed_at':datetime.now(timezone.utc).isoformat(),'item_gbp':'4.68','delivery_gbp':'0.00',
            'postage_verified':True,'digital_product':True,'condition':'new','stock_status':'available','stock_evidence':'In stock'}})
    digital_preview=await _product_page_source_preview(None,digital,archived=False)
    assert digital_preview['delivery_working_days']==0 and digital_preview['delivery_estimate_source']=='digital_delivery'
    from unittest.mock import patch,AsyncMock
    from app.services.playbook_service import _reviewed_supplier_source_is_current
    with patch('app.services.playbook_service._persisted_supplier_snapshot_is_current',AsyncMock(return_value=True)) as persisted:
        assert await _reviewed_supplier_source_is_current(None,{}, {'fingerprint':'reviewed-offer'},
            {'fingerprint':'different-catalogue-capture'},'reviewed-offer')
        assert not await _reviewed_supplier_source_is_current(None,{}, {'fingerprint':'reviewed-offer'},
            {'fingerprint':'different-catalogue-capture'},'unreviewed-offer')
        assert await _reviewed_supplier_source_is_current(None,{}, {'fingerprint':'reviewed-offer'},None,'reviewed-offer')
        assert persisted.await_count==2
    now=datetime.now(timezone.utc)
    url='https://www.amazon.co.uk/dp/B012345678'
    tracked='https://www.amazon.co.uk/Example/dp/B012345678/ref=abc'
    assert same_listing_product(url,tracked)
    assert not same_listing_product(url,'https://www.amazon.co.uk/dp/B012345679')
    capture=dict(status='captured',url=url,observed_at=now.isoformat(),item_gbp='100.00',delivery_gbp='0',postage_verified=True,delivery_working_days=2,stock_status='available',stock_evidence='In stock',condition='new')
    listing=Obj(id=1,external_id='B012345678',url=tracked,price=101,status='active',source_name='amazon',raw_specs={'playbook_product_capture':capture})
    page=await _product_page_source_preview(None,listing,archived=False)
    assert page and page['item_gbp']=='100.00' and page['postage_verified']
    card={**page,'observed_at':(now+timedelta(seconds=1)).isoformat(),'item_gbp':'101.00','identity_source':'approved_catalogue_listing_link','postage_verified':False,'stock_status':'unknown'}
    assert prefer_exact_product_page_preview(page,card)
    assert _candidate_source_prices(101,page)==(__import__('decimal').Decimal('100.00'),__import__('decimal').Decimal('0'),True)
    card['stock_status']='unavailable'
    assert not prefer_exact_product_page_preview(page,card)
    capture['last_capture_attempt']={'reason':'The exact Amazon ASIN is currently unavailable; no offer','attempted_at':(now+timedelta(seconds=1)).isoformat()}
    unavailable=await _product_page_source_preview(None,listing,archived=False)
    assert unavailable['stock_status']=='unavailable' and not unavailable['active_listing']
    candidate=dict(role='cpu',title='AMD Ryzen 5 5600',variant_id=1,listing_price_gbp=None,display_price=None)
    definition=dict(components=dict(cpu='AMD Ryzen 5 5600'))
    chosen,_=assemble_components(definition,[candidate])
    assert chosen['cpu']['variant_id']==1, 'Missing price hid a known component identity'

def range_checks():
    assert not _plausible_role_candidate('cpu','Ryzen 5 5600G CPU, Prime A520M-K Motherboard & 16GB RAM Pre-Built Bundle')
    assert not _plausible_role_candidate('cpu','AMD Ryzen 5 5600 60 Units Black')
    assert not _plausible_role_candidate('motherboard','motherboard Fit For MSI Z890 GAMING PLUS WIFI')
    assert _plausible_role_candidate('cpu','AMD Ryzen 5 5600G Processor with Wraith Stealth Cooler')
    assert _planning_integrated_graphics({'title':'AMD Ryzen 5 9600X Processor (radeon graphics included)'})
    assert not _planning_integrated_graphics({'title':'AMD Ryzen 7 5800X CPU'})
    from app.services.curated_catalogue_range import select_curated_range,_matches_requirement
    from app.services.playbook_service import _planning_socket,_planning_vram
    assert not _matches_requirement('gpu','ASUS GeForce RTX 5060 Ti 8GB','GeForce RTX 5060 Ti 16GB')
    assert _matches_requirement('gpu','MSI GeForce RTX 5060 Ti 16G GAMING','GeForce RTX 5060 Ti 16GB')
    assert _planning_vram({'title':'MSI GeForce RTX 5060 Ti 16G GAMING'})==16
    assert _planning_socket({'title':'ASUS ProArt Z890-CREATOR WIFI','engineering':{'socket':'LGA 1851'}})=='lga1851'
    assert _planning_socket({'title':'ASUS ProArt Z890-CREATOR WIFI','source_observation':{'product_properties':{'CPU socket':'LGA1851'}}})=='lga1851'
    assert _matches_requirement('storage_secondary','Example NVMe SSD 4TB','4TB build-cache SSD')
    assert not _matches_requirement('storage_secondary','Example HDD 4TB','4TB project SSD')
    rows=[Obj(category='storage',title='Example NVMe SSD 2TB',rank=i,asin=str(i)) for i in range(1,11)]
    rows += [Obj(category='storage',title='Example NVMe SSD 4TB',rank=i,asin=str(i)) for i in (11,12)]
    selected,_=select_curated_range(rows,[{'id':'dual','components':{'storage':'4TB NVMe + 4TB project SSD'}}])
    assert {'11','12'}.issubset({row.asin for row in selected}), 'Second drive was not retained'
    rows=[Obj(category='gpu',title='GeForce RTX 5060 Ti 8GB',rank=i,asin=str(i)) for i in range(1,11)]
    rows += [Obj(category='gpu',title='GeForce RTX 5060 Ti 16GB',rank=11,asin='16gb')]
    selected,_=select_curated_range(rows,[{'id':'vram','components':{'gpu':'GeForce RTX 5060 Ti 16GB'}}])
    assert '16gb' in {row.asin for row in selected}

def software_checks():
    from app.api.custom_builds import listing_is_software
    assert listing_is_software(Obj(raw_specs={'gamers_outlet':{'category':'os'}}))
    from app.services.commercial_quote_evidence import supplier_identity
    from app.services.commercial_source_validation import source_values, ImportEntry
    from app.services.playbook_service import _supplier_fact_is_approvable
    from fastapi import HTTPException
    url='https://www.gamers-outlet.net/en/buy-windows-11-pro-cd-key-oem-microsoft-global-1'
    source=dict(source='Gamers Outlet',url=url,observation_id=1,fingerprint='a'*64,
        observed_at=datetime.now(timezone.utc).isoformat(),fresh=True,active_listing=True,
        commercial_capture_verified=True,condition='new',listing_type='buy_it_now',
        stock_status='available',stock_evidence='In stock',item_gbp='4.68',delivery_gbp='0.00',
        postage_verified=True,delivery_working_days=0,licence_source_reviewed=True)
    entry=ImportEntry(part_key='variant:1',observation_id=1,source_fingerprint='a'*64,
        fees_gbp=0,risk_gbp=0,supplier_confidence=1,stock_confirmed=True)
    assert supplier_identity('Gamers Outlet',url)=='gamers_outlet'
    assert _supplier_fact_is_approvable({'role':'os','source_url':url},source)
    assert source_values(source,entry)['channel']=='software'
    source['licence_source_reviewed']=False
    assert not _supplier_fact_is_approvable({'role':'os','source_url':url},source)
    try: source_values(source,entry)
    except HTTPException as exc: assert exc.status_code==409
    else: raise AssertionError('Unreviewed Gamers Outlet source bypasses licence-source review')

if __name__=='__main__':
    asyncio.run(checks())
    range_checks()
    software_checks()
    print('PASS: exact ASIN identity, intact offer preference, unavailability blocking, unpriced component selection')
