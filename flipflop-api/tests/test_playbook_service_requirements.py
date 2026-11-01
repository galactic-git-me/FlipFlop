from app.services.playbook_service import (assemble_components, required_parts,
    unmodelled_required_components, withhold_incomplete_bom_prices,
    _candidate_source_prices, _plausible_role_candidate)


def _candidate_title(role):
    return {'cpu':'AMD Ryzen 5 5600G Processor', 'motherboard':'MSI B550M motherboard AM4',
        'ram':'DDR4 32GB RAM memory kit', 'gpu':'NVIDIA GeForce RTX 4060 Graphics Card',
        'storage':'1TB NVMe SSD', 'psu':'650W ATX PC power supply',
        'cooling':'CPU air cooler', 'case':'ATX mid-tower PC case'}.get(role,role)


def test_non_compute_upsells_require_a_measured_improvement_and_preserve_memory_contract():
    from app.services.playbook_service import _upgrade_quality_verified,_distinct_storage_devices
    base={'title':'64GB DDR5 ECC RDIMM RAM','engineering':{'reviewed':True,'ram_type':'ddr5'}}
    assert not _upgrade_quality_verified('ram',base,{**base,'title':'32GB DDR5 ECC RDIMM RAM'})
    assert not _upgrade_quality_verified('ram',base,{**base,'title':'128GB DDR5 non-ECC UDIMM RAM'})
    assert not _upgrade_quality_verified('ram',base,{**base,'title':'128GB DDR4 ECC RDIMM RAM',
        'engineering':{'reviewed':True,'ram_type':'ddr4'}})
    assert _upgrade_quality_verified('ram',base,{**base,'title':'128GB DDR5 ECC RDIMM RAM'})
    storage={'title':'2TB NVMe SSD','engineering':{'reviewed':True,'storage_interface':'nvme'}}
    assert not _upgrade_quality_verified('storage',storage,{**storage,'title':'1TB NVMe SSD'})
    assert _upgrade_quality_verified('storage',storage,{**storage,'title':'4TB NVMe SSD'})
    assert not _upgrade_quality_verified('storage',storage,{'title':'4TB SATA SSD',
        'engineering':{'reviewed':True,'storage_interface':'sata'}})
    assert not _upgrade_quality_verified('psu',{'engineering':{'reviewed':True,'wattage':850}},
        {'engineering':{'reviewed':True,'wattage':750}})
    assert _upgrade_quality_verified('psu',{'engineering':{'reviewed':True,'wattage':750}},
        {'engineering':{'reviewed':True,'wattage':850}})
    assert not _upgrade_quality_verified('cooling',{'engineering':{'reviewed':True}},
        {'engineering':{'reviewed':True}})
    assert not _distinct_storage_devices({'storage':{'listing_id':1},'storage_secondary':{'listing_id':1}})
    assert _distinct_storage_devices({'storage':{'listing_id':1},'storage_secondary':{'listing_id':2}})


def test_publication_rechecks_benefit_instead_of_trusting_a_quality_flag(monkeypatch):
    from app.services import playbook_service as service
    monkeypatch.setattr(service,'_supplier_fact_is_approvable',lambda *_:True)
    base={'role':'ram','title':'64GB DDR5 RAM','listing_price_gbp':'100',
        'engineering':{'reviewed':True,'ram_type':'ddr5'}}
    target={**base,'title':'32GB DDR5 RAM','listing_price_gbp':'200','catalogue_approved':True,
        'slot_id':1,'variant_id':2,'listing_id':3}
    upgrade={'role':'ram','component':target,'quality_verified':True,'compatibility_verified':True}
    offer={'components':[base],'upsells':[upgrade]}
    assert service._publication_upgrade_rows(offer)==[]
    target['title']='128GB DDR5 RAM'
    assert len(service._publication_upgrade_rows(offer))==1


def test_authored_cpu_listing_titles_allow_trademarks_and_processor_word_without_allowing_accessories():
    assert _plausible_role_candidate('cpu','AMD RYZEN™ 7 9850X3D')
    assert _plausible_role_candidate('cpu','AMD Ryzen® Threadripper PRO 7975WX Processor')
    assert _plausible_role_candidate('cpu','Intel Core Ultra 5 Processor 250K Plus, LGA1851 Socket')
    assert not _plausible_role_candidate('cpu','AMD RYZEN™ 7 9850X3D clamshell packaging holder')
    assert not _plausible_role_candidate('cpu','Intel Core Ultra 5 Processor 250K Plus socket protector')


def test_benchmark_substitution_cannot_remove_required_integrated_graphics():
    definition={'components':{'cpu':'AMD Ryzen 5 5600G','gpu':'Radeon Vega integrated'}}
    baseline={'cpu':{'metric':'overall_score','overall_score':100,'benchmark_source':'test'}}
    candidate={'role':'cpu','title':'Intel Core i7-11700F Desktop Processor','variant_id':1,'listing_id':1,
        'listing_price_gbp':'100','performance_evidence':{'benchmark_source':'test','confidence_score':1,'overall_score':200}}
    selected,_=assemble_components(definition,[candidate],performance_baselines=baseline)
    assert 'cpu' not in selected
    candidate={**candidate,'title':'Intel Core i7-11700 Desktop Processor',
        'engineering':{'reviewed':True,'integrated_graphics':True}}
    selected,_=assemble_components(definition,[candidate],performance_baselines=baseline)
    assert selected['cpu']['variant_id']==1


def test_proart_z890_creator_facts_verify_core_fit_and_builtin_wireless():
    from app.services.playbook_component_facts import manufacturer_facts, resolve_primary_engineering
    from app.services.playbook_planning_checks import wireless_extra_required
    title='ASUS ProArt Z890-CREATOR WIFI LGA1851 ATX Motherboard'
    facts=manufacturer_facts('motherboard',title)
    verified=resolve_primary_engineering({'role':'motherboard','title':title,'engineering':{}})
    assert verified['socket']=='lga1851'
    assert verified['ram_type']=='ddr5'
    assert verified['form_factor']=='atx'
    assert facts['wifi'] is True and facts['bluetooth'] is True
    assert wireless_extra_required({'title':title,'planning_engineering':facts})==[]


def test_tuf_z890_plus_facts_correct_bad_two_slot_capture_and_builtin_wireless():
    from app.services.playbook_component_facts import manufacturer_facts, resolve_primary_engineering
    from app.services.playbook_planning_checks import wireless_extra_required
    title='ASUS TUF GAMING Z890-PLUS WIFI Intel ATX motherboard'
    facts=manufacturer_facts('motherboard',title)
    verified=resolve_primary_engineering({'role':'motherboard','title':title,
        'engineering':{'reviewed':True,'ram_slots':2,'source_url':'captured-retailer-title',
                       'reviewed_by':'automation:exact-source-rule'}})
    assert verified['ram_slots']==4
    assert facts['wifi'] is True and facts['bluetooth'] is True
    assert wireless_extra_required({'title':title,'planning_engineering':facts})==[]


def test_rog_crosshair_x870e_hero_fact_avoids_unneeded_wireless_extra():
    from app.services.playbook_component_facts import manufacturer_facts, resolve_primary_engineering
    from app.services.playbook_planning_checks import wireless_extra_required
    title='ASUS ROG Crosshair X870E Hero AMD ATX motherboard'
    facts=manufacturer_facts('motherboard',title)
    verified=resolve_primary_engineering({'role':'motherboard','title':title,'engineering':{}})
    assert (verified['socket'],verified['ram_type'],verified['ram_slots'],verified['form_factor'])==('am5','ddr5',4,'atx')
    assert wireless_extra_required({'title':title,'planning_engineering':facts})==[]


def test_ram_assembly_prefers_smallest_authored_capacity_before_stock_priority():
    from app.services.playbook_service import assemble_components
    from datetime import datetime, timezone
    observed=datetime.now(timezone.utc).isoformat()
    candidates=[
        {'role':'ram','variant_id':1,'title':'Kingston DDR5 32GB (2x16GB) Desktop Memory Kit',
         'listing_price_gbp':'100','source_observation':{'stock_status':'unknown','observed_at':observed}},
        {'role':'ram','variant_id':2,'title':'Kingston DDR5 128GB (4x32GB) Desktop Memory Kit',
         'listing_price_gbp':'1000','source_observation':{'stock_status':'available','observed_at':observed}},
    ]
    definition={'components':{'ram':'32GB DDR5','cpu':'','motherboard':'','gpu':'integrated',
        'storage':'1TB NVMe SSD','psu':'650W','cooling':'CPU air cooler','case':'ATX PC case','os':''}}
    selected,_=assemble_components(definition,candidates)
    assert selected['ram']['title']=='Kingston DDR5 32GB (2x16GB) Desktop Memory Kit'


def test_playbook_benchmark_uses_labelled_overall_score_when_workload_metric_is_missing():
    from types import SimpleNamespace
    from app.services.playbook_service import _performance_context
    definition={'segment':'AI workstation','use':'Local AI','components':{
        'cpu':'AMD Ryzen 9 9950X','gpu':'NVIDIA GeForce RTX 5090 32GB'}}
    rows={
        ('cpu','amd_ryzen_9_9950x'):SimpleNamespace(model='AMD Ryzen 9 9950X',overall_score=65000,
            gaming_score=None,workstation_score=None,benchmark_source='passmark',confidence_score=.9,source_url='https://example.test/cpu'),
        ('gpu','nvidia_geforce_rtx_5090'):SimpleNamespace(model='NVIDIA GeForce RTX 5090',overall_score=28000,
            gaming_score=None,workstation_score=None,benchmark_source='passmark',confidence_score=.9,source_url='https://example.test/gpu'),
    }
    context=_performance_context(definition,rows)
    assert context['cpu']['metric']=='overall_score'
    assert context['cpu']['requested_metric']=='workstation_score'
    assert context['cpu']['workload_specific_metric_available'] is False
    assert context['gpu']['metric']=='overall_score'
    assert context['gpu']['requested_metric']=='workstation_score'
    assert context['gpu']['workload_specific_metric_available'] is False
    selected,_=assemble_components(definition,[{'role':'gpu','title':'NVIDIA GeForce RTX 6000 Ada 48GB Graphics Card',
        'variant_id':7,'listing_id':7,'listing_price_gbp':'1000','performance_evidence':{
            'benchmark_source':'passmark','confidence_score':.9,'overall_score':29000}}],
        performance_baselines=context)
    assert selected['gpu']['variant_id']==7


def test_draft_delivery_exposes_proposed_workshop_allowance_and_failed_fast_deadline():
    from types import SimpleNamespace
    from app.services.playbook_service import estimate_delivery_products
    roles=('cpu','motherboard','ram','storage','psu','cooling','case')
    parts={role:{'role':role,'slot_id':index,'variant_id':index,'case_catalogue_id':20 if role=='case' else None,
        'listing_price_gbp':'100.00','supplier_postage_gbp':'0.00','landed_gbp':'100.00',
        'source_observation':{'fresh':True,'active_listing':True,'stock_status':'available','delivery_working_days':7}}
        for index,role in enumerate(roles,1)}
    settings=SimpleNamespace(opportunity_delivery_fallback_gbp=10,speedy_curated_custom_days=7,
        standard_curated_custom_days=14,flexible_curated_custom_days=28,speedy_delivery_price_gbp=40)
    modes=estimate_delivery_products(parts,{'id':'TEST','tier':'Budget','components':{'gpu':'Integrated'}},
        SimpleNamespace(profit_strategy={}, pricing_model={}),settings)
    assert modes['fast_track']['recommended_price_gbp'] is None
    assert modes['fast_track']['estimated_delivery_working_days']==9
    assert modes['fast_track']['maximum_delivery_working_days']==7
    standard=modes['standard']
    assert standard['supplier_arrival_working_days']==7
    assert standard['workshop_working_days']==6
    assert standard['courier_working_days']==1
    assert standard['estimated_delivery_working_days']==14
    assert standard['workshop_wait_working_days'] is None
    assert standard['timing_basis']=='proposed_from_delivery_target'


def test_high_end_price_requires_reviewed_p75_and_keeps_margin_floor_below_cap():
    from types import SimpleNamespace
    from decimal import Decimal
    from unittest.mock import patch
    from app.services.playbook_service import estimate_delivery_products
    roles=('cpu','motherboard','ram','storage','gpu','psu','cooling','case')
    parts={role:{'role':role,'slot_id':index,'variant_id':index,'case_catalogue_id':20 if role=='case' else None,
        'listing_price_gbp':'100.00','supplier_postage_gbp':'0.00','landed_gbp':'100.00',
        'source_observation':{'fresh':True,'active_listing':True,'stock_status':'available','delivery_working_days':0}}
        for index,role in enumerate(roles,1)}
    settings=SimpleNamespace(opportunity_delivery_fallback_gbp=10,speedy_curated_custom_days=7,
        standard_curated_custom_days=14,flexible_curated_custom_days=28,speedy_delivery_price_gbp=40)
    parent=SimpleNamespace(profit_strategy={},pricing_model={})
    definition={'id':'HIGH','tier':'High-end','components':{role:role for role in roles}}
    without_market=estimate_delivery_products(parts,definition,parent,settings)
    assert without_market['standard']['recommended_price_gbp'] is None
    assert 'eight sold comparable' in without_market['standard']['reason']
    from app.schemas.commercial_quote import CellCommercialPolicy
    from tests.test_playbook_commercial_quote import policy_data
    from app.services.playbook_commercial_quote import supplier_meets_delivery_commitment
    raw=policy_data()
    for mode in raw['modes'].values():
        mode['costs']={key:'0' for key in mode['costs']}
        mode['minimum_contribution_gbp']='60'
        mode['minimum_margin_fraction']='0.10'
    raw['market'].update(sold_p75_gbp='2000',minimum_sold_sample_size=8,
        cap_method='sold_p75_linear_interpolation')
    for mode in raw['modes'].values():
        mode['maximum_delivery_working_days']=30
    policy=CellCommercialPolicy.model_validate(raw)
    with patch('app.services.playbook_service.automatic_policy',return_value=policy), \
         patch('app.services.playbook_service.component_delivery_eligibility',return_value={key:True for key in policy.modes}):
        affordable=estimate_delivery_products(parts,definition,parent,settings)
    assert Decimal(affordable['standard']['recommended_price_gbp']) <= Decimal('2000')
    raw['market']['sold_p75_gbp']='100'
    too_low=CellCommercialPolicy.model_validate(raw)
    with patch('app.services.playbook_service.automatic_policy',return_value=too_low), \
         patch('app.services.playbook_service.component_delivery_eligibility',return_value={key:True for key in too_low.modes}):
        blocked=estimate_delivery_products(parts,definition,parent,settings)
    assert blocked['standard']['recommended_price_gbp'] is None
    assert 'revise the build or leave unpublished' in blocked['standard']['reason']


def test_compatible_assembly_backtracks_from_incompatible_first_board_and_respects_review():
    definition={'components':{'gpu':'Integrated'}}
    candidates=[{'role':role,'title':_candidate_title(role),'variant_id':index,'listing_id':100+index,
        'listing_price_gbp':'10.00','engineering':{'reviewed':True}}
        for index,role in enumerate(('cpu','motherboard','ram','storage','psu','cooling','case'),1)]
    candidates[1]['engineering']['ram_slots']=1
    candidates[2]['engineering']['ram_modules']=2
    alternative={**candidates[1],'variant_id':90,'listing_id':190,
        'listing_price_gbp':'11.00','engineering':{'reviewed':True,'ram_slots':4}}
    def fit(parts,complete):
        if 'ram' not in parts or 'motherboard' not in parts:return True
        return parts['ram']['engineering']['ram_modules']<=parts['motherboard']['engineering']['ram_slots']
    greedy,_=assemble_components(definition,[*candidates,alternative])
    assert greedy['motherboard']['variant_id']==2
    chosen,blockers=assemble_components(definition,[*candidates,alternative],fit_check=fit)
    assert not blockers
    assert chosen['motherboard']['variant_id']==90
    unreviewed={**alternative,'engineering':{'reviewed':False,'ram_slots':4}}
    chosen,blockers=assemble_components(definition,[*candidates,unreviewed],fit_check=fit)
    assert chosen['motherboard']['variant_id']==2
    assert any('No fully verified compatible' in item for item in blockers)
    _,blockers=assemble_components(definition,[*candidates,alternative],fit_check=fit,search_limit=1)
    assert any('bounded search limit' in item for item in blockers)


def test_assembly_prefers_exact_supplier_offer_with_fresh_stock_postage_and_short_eta():
    from datetime import datetime, timezone
    definition={'components':{'cpu':'AMD Ryzen 5 5600G','gpu':'Integrated'}}
    captured_at=datetime.now(timezone.utc).isoformat()
    candidates=[]
    for role in ('motherboard','ram','storage','psu','cooling','case'):
        candidates.append({'role':role,'title':_candidate_title(role),'variant_id':len(candidates)+1,
            'listing_id':len(candidates)+100,'listing_price_gbp':'10.00'})
    exact='AMD Ryzen 5 5600G Processor'
    candidates.extend([
        {'role':'cpu','title':exact,'variant_id':80,'listing_id':180,'listing_price_gbp':'89.00',
         'source_price_verified':True,'rank':1,'source_observation':{'fresh':True,'commercial_capture_verified':True,
            'active_listing':True,'stock_status':'unknown','delivery_working_days':7,'postage_verified':False,
            'condition':'new','observed_at':captured_at},'price_observed_at':captured_at},
        {'role':'cpu','title':exact,'variant_id':81,'listing_id':181,'listing_price_gbp':'94.00',
         'source_price_verified':True,'rank':8,'source_observation':{'fresh':True,'commercial_capture_verified':True,
            'active_listing':True,'stock_status':'available','stock_evidence':'In stock','delivery_working_days':1,
            'postage_verified':True,'condition':'new','observed_at':captured_at},'price_observed_at':captured_at},
    ])

    parts,blockers=assemble_components(definition,candidates)

    assert not blockers
    assert parts['cpu']['variant_id']==81


def test_multi_device_storage_requires_a_distinct_catalogue_variant_per_drive():
    definition={'components':{'storage':'4TB PCIe 4.0 NVMe SSD + 4TB project SSD'}}

    assert 'storage_secondary' in required_parts(definition)
    parts,blockers=assemble_components(definition,[])
    assert 'Automatic sourcing needs a matching storage_secondary catalogue product' in blockers
    assert parts=={}


def test_multi_device_assembly_never_uses_one_listing_for_both_drives():
    definition={'components':{'storage':'4TB PCIe NVMe SSD + 4TB project SSD'}}
    candidates=[]
    for role in ('cpu','motherboard','ram','gpu','psu','cooling','case'):
        candidates.append({'role':role,'title':_candidate_title(role),'variant_id':len(candidates)+1,
            'listing_id':len(candidates)+100,'listing_price_gbp':'10.00'})
    candidates.extend([
        {'role':'storage','title':'4TB PCIe NVMe SSD','variant_id':20,'listing_id':120,'listing_price_gbp':'10.00'},
        {'role':'storage_secondary','title':'4TB SATA SSD','variant_id':21,'listing_id':120,'listing_price_gbp':'10.00'},
        {'role':'storage_secondary','title':'4TB SATA SSD','variant_id':22,'listing_id':122,'listing_price_gbp':'11.00'},
    ])

    parts,blockers=assemble_components(definition,candidates)

    assert not [blocker for blocker in blockers if 'storage' in blocker]
    assert parts['storage']['listing_id'] != parts['storage_secondary']['listing_id']
    assert parts['storage_secondary']['variant_id']==22


def test_led_strip_dc_adapter_cannot_be_selected_as_a_pc_power_supply():
    definition={'components':{'gpu':'Integrated'}}
    roles=('cpu','motherboard','ram','storage','psu','cooling','case')
    candidates=[{'role':role,'title':_candidate_title(role),'variant_id':index,'listing_id':100+index,
        'listing_price_gbp':'10.00'} for index,role in enumerate(roles,1)]
    bad_title=('12V 10A Power Supply, 120W DC Universal Regulated Switching Adapter '
        'Transformers for LED Strip Light, Probe Signal Lamp')
    candidates=[{**item,'title':bad_title} if item['role']=='psu' else item for item in candidates]

    parts,blockers=assemble_components(definition,candidates)

    assert 'psu' not in parts
    assert 'Automatic sourcing needs a matching psu catalogue product' in blockers

    valid={'role':'psu','title':'850W ATX PC power supply','variant_id':20,'listing_id':120,
        'listing_price_gbp':'80.00'}
    parts,blockers=assemble_components(definition,[*candidates,valid])
    assert not blockers
    assert parts['psu']['variant_id']==20


def test_catalogue_role_links_must_contain_a_real_component_identity():
    invalid={
        'cpu':'15PCS Computer CPU Case Tray Packaging Clamshell Holder Protector',
        'gpu':'Gigabyte replacement fan bracket for graphics card',
        'motherboard':'B550M AM4 socket protector tray',
        'ram':'DDR4 RGB RAM heat spreader cover only',
        'storage':'NVMe M.2 heatsink cover only',
        'psu':'12V 10A DC adapter for LED strip light',
        'cooling':'Laptop cooling pad with four fans',
        'case':'Phone case protective cover',
    }
    valid={
        'cpu':'AMD Ryzensets 5 9600X Processor',
        'gpu':'ASRock AMD Radeon AI PRO R9700 Creator 32GB',
        'motherboard':'MSI B550M PRO-VDH WIFI Motherboard M-ATX AM4',
        'ram':'CORSAIR VENGEANCE DDR4 RAM 32GB (2x16GB) kit',
        'storage':'Crucial P310 2TB SSD M.2 NVMe',
        'psu':'CORSAIR RM850e Fully Modular ATX Power Supply',
        'cooling':'Thermalright Peerless Assassin 120 SE CPU Air Cooler',
        'case':'NZXT H5 Flow ATX Mid-Tower PC Case',
    }

    assert all(not _plausible_role_candidate(role,title) for role,title in invalid.items())
    assert all(_plausible_role_candidate(role,title) for role,title in valid.items())


def test_equal_or_better_gpu_performance_does_not_drop_authored_vram_requirement():
    definition={'components':{'gpu':'NVIDIA GeForce RTX 5090 32GB'}}
    candidate={'role':'gpu','title':'NVIDIA GeForce RTX 5090 24GB Graphics Card','variant_id':1,
        'listing_id':11,'listing_price_gbp':'1000','performance_evidence':{
            'benchmark_source':'passmark','confidence_score':0.9,'overall_score':50000}}

    parts,blockers=assemble_components(definition,[candidate],performance_baselines={'gpu':{
        'metric':'overall_score','benchmark_source':'passmark','confidence_score':0.9,
        'overall_score':40000}})

    assert 'gpu' not in parts
    assert any('gpu catalogue candidate meets this cell requirement' in blocker for blocker in blockers)


def test_dual_boot_requires_both_catalogue_software_items():
    definition={'components':{'os':'Ubuntu 24.04 LTS + Windows 11 Pro dual-boot'}}

    assert required_parts(definition)[-2:]==('os','os_secondary')
    _,blockers=assemble_components(definition,[])
    assert 'Automatic sourcing needs a matching os_secondary catalogue product' in blockers
    assert unmodelled_required_components(definition)==[]


def test_zero_cost_official_linux_download_completes_the_secondary_os_catalogue_slot():
    definition={'components':{'os':'Ubuntu 24.04 LTS + Windows 11 Pro dual-boot'}}
    candidates=[{'role':role,'title':_candidate_title(role),'variant_id':index,'listing_id':100+index,
        'listing_price_gbp':'10.00'} for index,role in enumerate(
            ('cpu','motherboard','ram','gpu','storage','case','psu','cooling'),1)]
    candidates.extend([
        {'role':'os','title':'Windows 11 Pro OEM','variant_id':10,'listing_id':20,
         'listing_price_gbp':'70.00'},
        {'role':'os_secondary','title':'Ubuntu 24.04 LTS Desktop (official free download)',
         'variant_id':11,'listing_id':21,'listing_price_gbp':'0.00'},
    ])

    parts,blockers=assemble_components(definition,candidates)

    assert not blockers
    assert parts['os_secondary']['listing_price_gbp']=='0.00'
    assert parts['os_secondary']['listing_id']!=parts['os']['listing_id']


def test_only_verified_official_free_software_can_use_a_zero_cost_candidate_price():
    source={'fresh':True,'commercial_capture_verified':True,'item_gbp':'0.00',
        'delivery_gbp':'0.00','postage_verified':True,'evidence_kind':'official_free_software'}

    assert _candidate_source_prices(0,source)==(0,0,True)
    assert _candidate_source_prices(0,{**source,'evidence_kind':'supplier_listing'})==(None,None,False)


def test_unverified_catalogue_snapshot_never_falls_back_as_a_current_supplier_price():
    from decimal import Decimal
    stale={'fresh':False,'commercial_capture_verified':False,'item_gbp':'89.99',
        'delivery_gbp':'0.00','postage_verified':False}
    current={'fresh':True,'commercial_capture_verified':True,'item_gbp':'91.49',
        'delivery_gbp':'0.00','postage_verified':False}

    assert _candidate_source_prices(74.99,None)==(None,None,False)
    assert _candidate_source_prices(74.99,stale)==(None,None,False)
    assert _candidate_source_prices(74.99,current)==(Decimal('91.49'),None,True)


def test_official_free_software_preview_has_download_availability_not_supplier_stock():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from app.services.commercial_readiness import official_free_software_preview
    from app.services.commerce_pricing import Condition, FulfilmentMode, SupplierOffer, supplier_allowed

    listing=SimpleNamespace(id=7,external_id='playbook-free-software:ubuntu-24.04',
        price=0,status='active',url='https://releases.ubuntu.com/24.04/ubuntu-24.04.5.1-desktop-amd64.iso')
    source={'kind':'official_free_os_download','distribution':'Ubuntu','authored_release':'24.04',
        'download_url':listing.url,'available':True,'observed_at':datetime.now(timezone.utc).isoformat()}
    preview=official_free_software_preview(listing,source)

    assert preview['evidence_kind']=='official_free_software'
    assert preview['stock_status']=='available'
    assert 'no physical stock' in preview['stock_evidence'].lower()
    offer=SupplierOffer(supplier='Ubuntu',channel='software',condition=Condition.NEW,
        item_gbp=0,delivery_gbp=0,fees_gbp=0,risk_gbp=0,observed_at=preview['observed_at'],
        stock_confirmed=True,approved=True,delivery_working_days=0)
    assert all(supplier_allowed(mode,offer) for mode in FulfilmentMode)
    assert not supplier_allowed(FulfilmentMode.STANDARD,SupplierOffer(**{
        **offer.__dict__,'item_gbp':1}))
    assert official_free_software_preview(listing,{**source,'download_url':'https://evil.example/os.iso'}) is None


def test_official_ubuntu_offer_import_is_typed_as_software_not_retail_stock():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from app.services.commercial_readiness import official_free_software_preview
    from app.services.commercial_source_validation import ImportEntry, source_values

    index='https://releases.ubuntu.com/24.04/'
    download=index+'ubuntu-24.04.5.1-desktop-amd64.iso'
    listing=SimpleNamespace(id=7,external_id='playbook-free-software:ubuntu-24.04',
        price=0,status='active',url=index)
    preview=official_free_software_preview(listing,{'kind':'official_free_os_download',
        'distribution':'Ubuntu','authored_release':'24.04','index_url':index,
        'download_url':download,'available':True,'observed_at':datetime.now(timezone.utc).isoformat()})
    entry=ImportEntry(part_key='variant:11',observation_id=7,source_fingerprint=preview['fingerprint'],
        fees_gbp='0',risk_gbp='0',supplier_confidence='1',stock_confirmed=True)

    values=source_values(preview,entry)

    assert values['supplier']=='Ubuntu'
    assert values['channel']=='software'
    assert values['item_gbp']==0
    assert values['delivery_gbp']==0
    assert values['evidence_ref']==index


def test_curated_slots_resolve_dual_boot_to_exact_windows_edition_and_free_ubuntu():
    from app.services.curated_build_policy import curated_slots
    slots=[
        {'slot_id':1,'slot_type':'os','variants_by_tier':{'mid':[
            {'id':101,'title':'Windows 11 Home OEM','display_price':20},
            {'id':102,'title':'Windows 11 Pro OEM','display_price':30}]},'tier_names':{}},
        {'slot_id':2,'slot_type':'os_secondary','variants_by_tier':{'mid':[
            {'id':103,'title':'Ubuntu 24.04 LTS Desktop (official free download)','display_price':0}]},'tier_names':{}},
    ]
    definition={'components':{'os':'Ubuntu 24.04 LTS + Windows 11 Pro dual-boot'}}

    result=curated_slots(slots,definition)

    assert [slot['default_variant_id'] for slot in result]==[102,103]
    single_os=curated_slots(slots,{'components':{'os':'Windows 11 Home'}})
    assert [slot['default_variant_id'] for slot in single_os]==[101,None]


def test_optional_virtualized_software_does_not_count_as_a_physical_catalogue_item():
    definitions=[
        {'components':{'os':'Windows 11 Pro + WSL2'}},
        {'components':{'os':'Windows 11 Pro + Ubuntu VM'}},
        {'components':{'os':'Windows 11 Pro + Ubuntu option'}},
    ]

    assert all(unmodelled_required_components(definition)==[] for definition in definitions)


def test_incomplete_multi_part_bom_cannot_keep_single_part_prices_or_upsells():
    delivery={mode:{'available':True,'recommended_price_gbp':'100.00',
        'estimated_profit_gbp':'20.00','difference_from_standard_gbp':'0.00'}
        for mode in ('fast_track','standard','flexible')}
    missing=unmodelled_required_components({'components':{
        'storage':'4TB NVMe SSD + 4TB project SSD + 2TB cache SSD'}})

    result=withhold_incomplete_bom_prices(delivery,missing)

    assert all(not offer['available'] for offer in result.values())
    assert all(offer['recommended_price_gbp'] is None for offer in result.values())
    assert all(offer['estimated_profit_gbp'] is None for offer in result.values())
    assert all(offer['recommended_component_variant_ids']==[] for offer in result.values())
