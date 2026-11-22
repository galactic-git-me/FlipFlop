"""Engineering invariants; synthetic measurements are never catalogue data."""
from copy import deepcopy
from app.services.studio_fit import evaluate_fit, evaluate_playbook_fit, engineering_specs
import pytest


@pytest.fixture
def build():
    parts = {
        'cpu': dict(socket='AM5', power_w=120, cpu_id='test-cpu',integrated_graphics=True),
        'motherboard': dict(socket='AM5',ram_type='DDR5',ram_slots=4,form_factor='atx',storage_interfaces=['nvme'],m2_lengths=[2280],bios_cpu_ids=['test-cpu']),
        'gpu': dict(length_mm=300,power_w=250,recommended_psu_w=650,gpu_power_connectors={'8pin':2}),
        'ram': dict(ram_type='DDR5',ram_modules=2,ram_height_mm=35),
        'cooling': dict(cooler_type='air',height_mm=160,ram_clearance_mm=40,supported_sockets=['AM5']),
        'psu': dict(form_factor='atx',length_mm=150,wattage=750,psu_connectors={'8pin':2}),
        'storage': dict(storage_interface='nvme',m2_length=2280),
    }
    for spec in parts.values(): spec['reviewed']=True
    case = dict(form_factor='atx',max_gpu_length_mm=300,max_cooler_height_mm=160,engineering=dict(psu_form_factors=['atx'],max_psu_length_mm=180))
    return parts,case


def status(build,code):
    return next(c['severity'] for c in evaluate_fit(*build) if c['code']==code)


def test_complete_reviewed_build_and_exact_boundaries(build):
    assert not [c for c in evaluate_fit(*build) if c['severity'] in ('error','unknown')]
    assert status(build,'GPU_LENGTH')=='pass'
    assert status(build,'COOLER_HEIGHT')=='pass'


def test_catalogue_assembly_uses_real_fit_checks_to_replace_incompatible_first_choice(build):
    from app.services.playbook_service import assemble_components
    parts,case=build
    titles={'cpu':'AMD Ryzen 5 7600 Processor','motherboard':'AM5 DDR5 ATX motherboard',
        'gpu':'GeForce RTX 4060 Graphics Card','ram':'DDR5 32GB RAM kit',
        'storage':'1TB NVMe SSD','psu':'750W ATX PC power supply',
        'cooling':'CPU air cooler','case':'ATX mid-tower PC case'}
    specs={**parts,'case':{**case,**case['engineering'],'reviewed':True}}
    candidates=[{'role':role,'title':titles[role],'variant_id':index,'listing_id':index,
        'listing_price_gbp':'20.00','engineering':deepcopy(spec)}
        for index,(role,spec) in enumerate(specs.items(),1)]
    good_board=next(row for row in candidates if row['role']=='motherboard')
    bad_board={**good_board,'variant_id':99,'listing_id':99,'listing_price_gbp':'10.00',
        'engineering':{**good_board['engineering'],'ram_slots':1}}
    candidates.append(bad_board)
    def fit(selected,complete):
        chassis=(selected.get('case') or {}).get('engineering') or {}
        checks=evaluate_fit({role:part['engineering'] for role,part in selected.items() if role!='case'},
            {**chassis,'engineering':chassis})
        return not any(c['severity'] in ({'error','unknown'} if complete else {'error'}) for c in checks)
    greedy,_=assemble_components({'components':{}},candidates)
    assert greedy['motherboard']['variant_id']==99
    selected,blockers=assemble_components({'components':{}},candidates,fit_check=fit)
    assert not blockers
    assert selected['motherboard']['variant_id']==good_board['variant_id']
    assert fit(selected,True)


def test_playbook_candidate_search_does_not_require_workshop_specs_for_every_part(build):
    from app.services.playbook_service import assemble_components
    parts,case=build
    parts['gpu'].update(gpu_interface='pcie')
    parts['motherboard'].update(gpu_interfaces=['pcie'])
    parts['storage']['reviewed']=False
    parts['cooling']['reviewed']=False
    parts['psu']['reviewed']=False
    specs={**parts,'case':{**case,**case['engineering'],'reviewed':True}}
    titles={'cpu':'AMD Ryzen 5 7600 Processor','motherboard':'AM5 DDR5 ATX motherboard',
        'gpu':'GeForce RTX 4060 Graphics Card','ram':'DDR5 32GB RAM kit',
        'storage':'1TB NVMe SSD','psu':'750W ATX PC power supply',
        'cooling':'CPU air cooler','case':'ATX mid-tower PC case'}
    candidates=[{'role':role,'title':titles[role],'variant_id':index,'listing_id':index,
        'listing_price_gbp':'20.00','engineering':deepcopy(spec)}
        for index,(role,spec) in enumerate(specs.items(),1)]
    def fit(selected,complete):
        chassis=(selected.get('case') or {}).get('engineering') or {}
        checks=evaluate_playbook_fit({role:part['engineering'] for role,part in selected.items() if role!='case'},
            {**chassis,'engineering':chassis})
        return not any(check['severity'] in ({'error','unknown'} if complete else {'error'}) for check in checks)
    selected,blockers=assemble_components({'components':{}},candidates,fit_check=fit)
    assert not blockers
    assert set(selected)==set(specs)


def test_playbook_may_allow_a_build_without_a_dedicated_gpu(build):
    build[0].pop('gpu')

    checks = evaluate_fit(*build, gpu_required=False)

    assert not any(check['code'].startswith('GPU_') for check in checks)
    assert next(check for check in checks if check['code'] == 'POWER')['severity'] == 'pass'
    assert not [check for check in checks if check['severity'] in ('error', 'unknown')]


def test_gpu_free_build_requires_reviewed_integrated_graphics_evidence(build):
    parts,case=build
    parts.pop('gpu')
    parts['cpu']['integrated_graphics']=False
    checks=evaluate_fit(parts,case,gpu_required=False)
    assert next(c for c in checks if c['code']=='INTEGRATED_GRAPHICS')['severity']=='error'
    parts['cpu'].pop('integrated_graphics')
    checks=evaluate_fit(parts,case,gpu_required=False)
    assert next(c for c in checks if c['code']=='INTEGRATED_GRAPHICS')['severity']=='unknown'


def test_optional_gpu_is_still_checked_when_customer_selects_one(build):
    build[0]['gpu']['length_mm'] = 301

    checks = evaluate_fit(*build, gpu_required=False)

    assert next(check for check in checks if check['code'] == 'GPU_LENGTH')['severity'] == 'error'


@pytest.mark.parametrize('category,key,value,code',[
    ('cpu','socket','AM4','CPU_SOCKET'), ('gpu','length_mm',301,'GPU_LENGTH'),
    ('ram','ram_type','DDR4','RAM_TYPE'), ('ram','ram_height_mm',41,'RAM_CLEARANCE'),
    ('ram','ram_modules',5,'RAM_SLOTS'), ('cooling','height_mm',161,'COOLER_HEIGHT'),
    ('psu','length_mm',181,'PSU_LENGTH'), ('psu','wattage',600,'POWER'),
    ('psu','form_factor','sfx','PSU_FORMAT'), ('storage','m2_length',22110,'SSD_MOUNT'),
    ('storage','storage_interface','sata','SSD_INTERFACE'),
    ('motherboard','form_factor','eatx','BOARD_FIT'),
])
def test_conflicts(build,category,key,value,code):
    build[0][category][key]=value
    assert status(build,code)=='error'


def test_playbook_publication_gate_uses_only_the_agreed_basic_compatibility_checks(build):
    parts,case=build
    parts['gpu'].update(gpu_interface='pcie')
    parts['motherboard'].update(gpu_interfaces=['pcie'])
    parts['ram']['ram_modules']=5
    parts['psu']['length_mm']=250
    checks=evaluate_playbook_fit(parts,case)
    by_code={check['code']:check for check in checks}
    assert by_code['CPU_SOCKET']['stage']=='publication'
    assert by_code['RAM_TYPE']['stage']=='publication'
    assert by_code['BOARD_FIT']['stage']=='publication'
    assert by_code['GPU_INTERFACE']['severity']=='pass'
    assert by_code['RAM_SLOTS']['severity']=='warning'
    assert by_code['PSU_LENGTH']['severity']=='warning'

    parts['motherboard']['ram_type']='DDR4'
    checks=evaluate_playbook_fit(parts,case)
    assert next(check for check in checks if check['code']=='RAM_TYPE')['severity']=='error'


@pytest.mark.parametrize(('role','title','current','expected'),[
    ('cpu','AMD Ryzen 5 9600X Tray',{'socket':'am4','reviewed':True,
        'reviewed_by':'automation:exact-source-rule'},{'socket':'am5','integrated_graphics':True}),
    ('cpu','AMD Ryzen Threadripper PRO 7975WX',{'socket':'sp6','reviewed':True,
        'reviewed_by':'automation:exact-source-rule'},{'socket':'str5','integrated_graphics':False}),
    ('cpu','Intel Core Ultra 5 250K Plus',{}, {'socket':'lga1851','integrated_graphics':True}),
    ('cpu','Intel Core Ultra 7 270K Plus',{}, {'socket':'lga1851','integrated_graphics':True}),
    ('cpu','AMD Ryzen 7 9700X',{}, {'socket':'am5','integrated_graphics':True}),
    ('motherboard','ASUS PRIME X870-P AMD ATX',{'ram_slots':1,'reviewed':True,
        'reviewed_by':'automation:exact-source-rule'},{'ram_slots':4,'ram_type':'ddr5','form_factor':'atx'}),
])
def test_exact_manufacturer_reference_resolves_known_retailer_spec_mismatches(role,title,current,expected):
    from app.services.playbook_component_facts import resolve_primary_engineering
    part={'role':role,'title':title,'engineering':current}

    resolved=resolve_primary_engineering(part)

    assert resolved['reviewed'] is True
    assert all(resolved[key]==value for key,value in expected.items())
    assert resolved['reviewed_by']=='automation:exact-manufacturer-reference'


def test_exact_product_properties_supply_only_explicit_gpu_interface():
    from types import SimpleNamespace
    from app.services.playbook_service import _apply_exact_source_core_engineering, _source_engineering_values
    props={'Graphics Card Interface':'PCI-Express x16'}
    assert _source_engineering_values('gpu',props)['gpu_interface']=='pcie'
    listing=SimpleNamespace(id=4,url='https://shop.example/gpu/123.html',title='ASUS RTX 5060 Ti')

    resolved=_apply_exact_source_core_engineering('gpu',listing,
        {'url':listing.url,'product_properties':props,'observed_at':'2026-10-26T00:00:00+00:00'}, {})

    assert resolved['gpu_interface']=='pcie'
    assert resolved['reviewed'] is True
    assert resolved['source_url']==listing.url


def test_gpu_interface_is_not_guessed_from_a_different_source_url():
    from types import SimpleNamespace
    from app.services.playbook_service import _apply_exact_source_core_engineering
    listing=SimpleNamespace(id=4,url='https://shop.example/gpu/123.html',title='ASUS RTX 5060 Ti')

    resolved=_apply_exact_source_core_engineering('gpu',listing,
        {'url':'https://shop.example/search?q=gpu','product_properties':{'Graphics Card Interface':'PCI Express'}}, {})

    assert resolved=={}


def test_unreviewed_and_nan_are_unknown(build):
    build[0]['gpu']['reviewed']=False
    assert status(build,'GPU_LENGTH')=='unknown'
    build[0]['gpu']['reviewed']=True
    build[0]['gpu']['length_mm']=float('nan')
    assert status(build,'GPU_LENGTH')=='unknown'


def test_radiator_reduces_gpu_space(build):
    build[0]['cooling']['front_radiator_depth_mm']=30
    assert status(build,'GPU_LENGTH')=='error'


def test_cpu_specific_bios_required(build):
    build[0]['cpu']['cpu_id']='different-cpu'
    assert status(build,'BIOS')=='unknown'


def test_every_selected_nvme_drive_must_fit_the_board_m2_slot_count(build):
    build[0]['motherboard']['m2_slots']=1
    build[0]['storage_secondary']={'reviewed':True,'storage_interface':'nvme','m2_length':2280}
    assert status(build,'M2_SLOT_COUNT')=='error'
    build[0]['motherboard']['m2_slots']=2
    assert status(build,'M2_SLOT_COUNT')=='pass'


def test_connectors(build):
    build[0]['psu']['psu_connectors']={'8pin':1}
    assert status(build,'POWER_CONNECTOR_8pin')=='error'


def test_evaluation_does_not_mutate_selection(build):
    before=deepcopy(build)
    evaluate_fit(*build)
    assert build==before


def test_two_sata_drives_need_both_motherboard_ports_and_case_bays(build):
    parts,case=build
    parts['storage']={'reviewed':True,'storage_interface':'sata'}
    parts['storage_secondary']={'reviewed':True,'storage_interface':'sata'}
    parts['motherboard'].update(storage_interfaces=['sata'],sata_ports=1)
    case['engineering']['sata_bays']=2
    assert status(build,'SATA_PORT_COUNT')=='error'
    assert status(build,'SATA_BAY_COUNT')=='pass'
    parts['motherboard']['sata_ports']=2
    assert not [c for c in evaluate_fit(*build) if c['severity'] in ('error','unknown')]


def test_only_whitelisted_public_engineering_leaves_service():
    assert engineering_specs({'supplier_cost':1,'configurator':{'socket':'AM5','supplier_cost':2,'reviewed':True}})=={'socket':'AM5','reviewed':True}
    assert engineering_specs('not an object')=={}


def test_empty_build_is_not_certified():
    assert any(c['severity']=='unknown' for c in evaluate_fit({},None))
