from app.models.motherboard_spec import MotherboardSpec
from app.models.playbook import PlaybookProposal
from app.services.motherboard_matching import match_exact_reviewed_motherboard_spec
from app.services.playbook_service import (approve_playbook_motherboard_spec,
    list_motherboard_engineering_suggestions, research_playbook_motherboard_specs,
    _source_engineering_values, _playbook_engineering_suggestion,
    approve_playbook_product_engineering)
from app.services.motherboard_spec_ai import title_verified_motherboard_facts
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
import pytest
from fastapi import HTTPException


def board(model, *, reviewed=True):
    return MotherboardSpec(canonical_model=model, socket='am4', ram_type='ddr4',
        ram_slots=4, form_factor='matx', reviewed=reviewed)


def test_source_connector_counts_are_consumable_by_fit_checker_and_detect_shortage():
    from app.services.studio_fit import evaluate_fit
    gpu=_source_engineering_values('gpu',{'Required power connectors':'2 x 8-pin'})
    psu=_source_engineering_values('psu',{'Power connectors':'1 x 8-pin; 1 x 12V-2x6'})
    assert gpu=={'gpu_power_connectors':{'8pin':2}}
    assert psu=={'psu_connectors':{'8pin':1,'12v2x6':1}}
    parts={'gpu':{**gpu,'reviewed':True},'psu':{**psu,'reviewed':True}}
    checks=evaluate_fit(parts,{})
    assert next(c for c in checks if c['code']=='POWER_CONNECTOR_8pin')['severity']=='error'
    assert _source_engineering_values('psu',{'Power connectors':'PCIe compatible'})=={}
    assert _source_engineering_values('psu',{'Power connectors':'1 x 8-pin; unknown'})=={}


def test_explicit_storage_bios_and_case_lists_keep_checker_types_without_inferred_defaults():
    board_specs=_source_engineering_values('motherboard',{
        'Supported storage interfaces':'NVMe; SATA','Supported M.2 lengths':'2242; 2280',
        'BIOS supported CPU IDs':'100-000000001; 100-000000002'})
    assert board_specs=={'storage_interfaces':['nvme','sata'],'m2_lengths':[2242,2280],
        'bios_cpu_ids':['100-000000001','100-000000002']}
    assert _source_engineering_values('cpu',{'CPU ID':'100-000000001'})=={'cpu_id':'100-000000001'}
    assert _source_engineering_values('case',{'Supported PSU form factors':'ATX; SFX'})=={'psu_form_factors':['atx','sfx']}
    assert _source_engineering_values('motherboard',{'Supported storage interfaces':'PCIe compatible'})=={}


def test_integrated_graphics_suggestion_uses_explicit_facts_and_preserves_negative_statements():
    assert _source_engineering_values('cpu',{'Integrated graphics':'Yes'})=={'integrated_graphics':True}
    assert _source_engineering_values('cpu',{},'Processor with integrated Radeon graphics')=={'integrated_graphics':True}
    assert _source_engineering_values('cpu',{},'Processor without integrated graphics')=={'integrated_graphics':False}
    assert _source_engineering_values('cpu',{},'Processor integrated graphics not included')=={'integrated_graphics':False}
    assert _source_engineering_values('cpu',{},'Processor graphics capability unknown')=={}


def test_memory_labels_preserve_generation_and_m2_does_not_invent_a_storage_protocol():
    assert _source_engineering_values('ram',{'Memory Technology':'DDR5 SDRAM'})=={'ram_type':'ddr5'}
    assert _source_engineering_values('storage',{'Interface':'M.2','M.2 Length':'2280'})=={'m2_length':2280}
    assert _source_engineering_values('storage',{'Interface':'SATA','M.2 Length':'2280'})=={'storage_interface':'sata','m2_length':2280}
    assert _source_engineering_values('motherboard',{'Available Memory Slots':'4','Total SATA Ports':'6'})=={'ram_slots':4,'sata_ports':6}
    assert _source_engineering_values('cpu',{'Socket':['Socket AM5','AM5'],'TDP':['65 W','65 watts']})=={'socket':'am5','power_w':65}
    assert _source_engineering_values('ram',{'Memory Technology':['DDR5 SDRAM','DDR5']})=={'ram_type':'ddr5'}


def test_playbook_match_uses_only_an_exact_reviewed_model():
    reference = board('MSI B550M PRO-VDH WIFI')

    assert match_exact_reviewed_motherboard_spec(
        'MSI B550M PRO-VDH WIFI Motherboard M-ATX', [reference]) is reference
    assert match_exact_reviewed_motherboard_spec(
        'MSI B550M PRO-VDH WIFI Motherboard M-ATX',
        [board('MSI B550M PRO-VDH WIFI', reviewed=False)]) is None
    assert match_exact_reviewed_motherboard_spec(
        'MSI B550M PRO-VDH Motherboard M-ATX', [reference]) is None


def test_playbook_exact_match_refuses_ambiguous_reviewed_models():
    first = board('MSI B550M')
    second = board('B550M')

    assert match_exact_reviewed_motherboard_spec('MSI B550M Motherboard', [first, second]) is None


def test_only_literal_listing_title_facts_can_support_compatibility():
    title='Board M-ATX, AM5, DDR5, 4 DIMM slots, supports maximum 128GB RAM'

    assert title_verified_motherboard_facts(title)=={
        'socket':'am5','ram_type':'ddr5','form_factor':'matx','ram_slots':4,'max_ram_gb':128}
    assert title_verified_motherboard_facts('X870 board ATX DDR5')=={
        'ram_type':'ddr5','form_factor':'atx','chipset':'x870'}
    assert title_verified_motherboard_facts(
        'GIGABYTE X870 EAGLE WIFI7 ATX board 2x M.2, 2x PCIe 5.0 x16')=={
            'chipset':'x870','form_factor':'atx','m2_slots':2,
            'pcie_x16_slots':2,'wifi':True}
    assert title_verified_motherboard_facts(
        'GIGABYTE X870E EAGLE X3D WIFI7 Motherboard AM5 DDR5 ATX')=={
            'socket':'am5','ram_type':'ddr5','chipset':'x870e','form_factor':'atx','wifi':True}


@pytest.mark.parametrize('role,properties,expected',[
    ('cpu',{'Socket':'AM5','TDP':'65 W'},{'socket':'am5','power_w':65}),
    ('motherboard',{'CPU Socket':'AM4','Memory Type':'DDR4','Memory Slots':'4','Form Factor':'Micro-ATX'},
        {'socket':'am4','ram_type':'ddr4','ram_slots':4,'form_factor':'matx'}),
    ('cooling',{'Socket Compatibility':'AM4, AM5, LGA 1700','Cooler Height':'155 mm'},
        {'supported_sockets':['am4','am5','lga1700'],'height_mm':155}),
    ('storage',{'Interface':'NVMe','M.2 Form Factor':'2280'},{'storage_interface':'nvme','m2_length':2280}),
])
def test_source_engineering_extraction_uses_only_explicit_labeled_facts(role,properties,expected):
    assert _source_engineering_values(role,properties)==expected


def test_source_engineering_extraction_ignores_ambiguous_values_and_unrelated_properties():
    assert _source_engineering_values('gpu',{'Product Dimensions':'40 x 30 x 10 cm',
        'Graphics Card Length':'320 mm','Length':'410 mm'})=={'length_mm':320}


@pytest.mark.parametrize('role,title,expected',[
    ('cpu','AMD Ryzen 5 5600X Processor 65W TDP, AM4 Socket',{'socket':'am4','power_w':65}),
    ('ram','Corsair Vengeance DDR4 32GB Kit (2x16GB)',{'ram_type':'ddr4','ram_modules':2}),
    ('storage','NVMe M.2 2280 PCIe SSD 2TB',{'storage_interface':'nvme','m2_length':2280}),
    ('psu','Seasonic Focus GX-850 850W 80 PLUS Gold Power Supply',{'wattage':850}),
])
def test_product_title_suggestions_retain_only_literal_fit_facts(role,title,expected):
    assert _source_engineering_values(role,{},title)==expected


async def test_playbook_research_is_free_review_only_and_approval_is_explicit(db):
    title='MSI B550M PRO-VDH WIFI Motherboard M-ATX, AM4, DDR4'
    db.add(PlaybookProposal(action='UPDATE',status='pending',proposed_data={
        'cell_id':'TEST-CELL','components':[{'role':'motherboard','listing_id':83,
            'title':title,'source_url':'https://www.amazon.co.uk/dp/B000000000'}],
        'upsells':[]},demand_signals={'source':'catalogue_playbook_service_v1'}))
    await db.flush()
    with patch('app.services.playbook_motherboard_sources.capture_official_motherboard_facts',
               AsyncMock(return_value=None)) as manufacturer_capture, \
         patch('app.services.motherboard_spec_ai.extract_motherboard_spec',
               AsyncMock(side_effect=AssertionError('literal title facts need no model call'))) as extract:
        research=await research_playbook_motherboard_specs(db)
    manufacturer_capture.assert_awaited_once_with(title)
    extract.assert_not_awaited()
    assert research['created_count']==1 and research['reviewed'] is False and research['published'] is False
    rows=(await db.execute(select(MotherboardSpec))).scalars().all()
    suggestion=rows[0]
    assert suggestion.reviewed is False and suggestion.source=='listing_title'
    assert (suggestion.socket,suggestion.chipset,suggestion.ram_type,suggestion.form_factor)==('am4','b550','ddr4','matx')
    assert suggestion.wifi is True
    assert suggestion.raw_ai_response['playbook_source_url']=='https://www.amazon.co.uk/dp/B000000000'
    listed=await list_motherboard_engineering_suggestions(db)
    assert len(listed)==1 and listed[0]['listing_title_facts_captured'] is True
    assert listed[0]['source_basis']=='exact_catalogue_listing_title'
    approved=await approve_playbook_motherboard_spec(db,suggestion.id,SimpleNamespace(email='operator@example.test'))
    assert approved['reviewed'] is True and approved['published'] is False


async def test_conflicting_approved_board_records_cannot_silently_certify_fit(db):
    from app.models.listing import Listing
    from app.models.playbook import Playbook
    from app.models.catalogue import PlaybookSlot,CatalogueVariant
    from app.services.playbook_service import _catalogue_candidates
    parent=Playbook(name='Exact source conflict test')
    db.add(parent)
    await db.flush()
    slot=PlaybookSlot(playbook_id=parent.id,slot_type='motherboard')
    listing=Listing(external_id='conflicting-reviewed-board',source_id=0,source_name='amazon',
        title='MSI B550M PRO-VDH WIFI Motherboard M-ATX AM4 DDR4',price=100,
        url='https://www.amazon.co.uk/dp/B000000000',status='active',
        raw_specs={'configurator':{'reviewed':True,'socket':'am5'}})
    db.add_all([slot,listing,board('MSI B550M PRO-VDH WIFI')]);await db.flush()
    db.add(CatalogueVariant(listing_id=listing.id,slot_id=slot.id,status='active',display_price=120,
        tier='budget',curated_for_builds=True));await db.flush()
    candidates=await _catalogue_candidates(db,parent.id,'curated',source_cache={listing.id:None})
    assert len(candidates)==1
    assert candidates[0]['engineering']['reviewed'] is False
    assert candidates[0]['engineering']['reference_conflicts']==['socket']


async def test_hidden_catalogue_variants_are_never_playbook_candidates(db):
    from app.models.listing import Listing
    from app.models.playbook import Playbook
    from app.models.catalogue import PlaybookSlot,CatalogueVariant
    from app.services.playbook_service import _catalogue_candidates
    parent=Playbook(name='Hidden variant exclusion test')
    db.add(parent)
    await db.flush()
    slot=PlaybookSlot(playbook_id=parent.id,slot_type='motherboard')
    hidden=Listing(external_id='hidden-board-candidate',source_id=0,source_name='amazon',
        title='MSI B550M PRO-VDH WIFI Motherboard M-ATX AM4 DDR4',price=100,
        url='https://www.amazon.co.uk/dp/B000000001',status='active')
    pending=Listing(external_id='pending-board-candidate',source_id=0,source_name='amazon',
        title='Gigabyte B550M DS3H Motherboard M-ATX AM4 DDR4',price=110,
        url='https://www.amazon.co.uk/dp/B000000002',status='active')
    db.add_all([slot,hidden,pending]);await db.flush()
    db.add_all([
        CatalogueVariant(listing_id=hidden.id,slot_id=slot.id,status='hidden',display_price=120,
            tier='budget',curated_for_builds=True),
        CatalogueVariant(listing_id=pending.id,slot_id=slot.id,status='pending_review',display_price=130,
            tier='budget',curated_for_builds=True),
    ])
    await db.flush()

    candidates=await _catalogue_candidates(db,parent.id,'curated',source_cache={hidden.id:None,pending.id:None})

    assert [candidate['listing_id'] for candidate in candidates]==[pending.id]


async def test_product_spec_suggestion_requires_exact_unchanged_capture_and_explicit_approval(db):
    from app.models.listing import Listing
    from app.services.playbook_service import list_playbook_product_engineering_suggestions
    url='https://www.amazon.co.uk/dp/B000000000'
    listing=Listing(external_id='engineering-test-1',source_id=1,source_name='Amazon UK',title='Example AM5 CPU',
        price=150,url=url,raw_specs={'configurator':{'reviewed':False,'power_w':30},'playbook_product_capture':{'status':'captured','url':url,
            'title':'Example AM5 CPU','observed_at':'2026-10-15T00:00:00+00:00',
            'product_properties':{'Socket':'AM5','TDP':'65 W'}}})
    db.add(listing)
    db.add(PlaybookProposal(action='UPDATE',status='pending',proposed_data={'cell_id':'TEST-CELL',
        'components':[{'role':'cpu','listing_id':1,'title':listing.title,'source_url':url}],
        'upsells':[]},demand_signals={'source':'catalogue_playbook_service_v1'}))
    await db.flush()
    proposal=(await db.execute(select(PlaybookProposal))).scalar_one()
    part=proposal.proposed_data['components'][0]
    part['listing_id']=listing.id
    proposal.proposed_data={**proposal.proposed_data,'components':[part]}
    suggestion=_playbook_engineering_suggestion(listing,'cpu')
    assert suggestion['suggested_specs']=={'socket':'am5','power_w':65}
    assert suggestion['reviewed_value_changes']=={}
    assert len(await list_playbook_product_engineering_suggestions(db))==1
    with pytest.raises(HTTPException) as stale:
        await approve_playbook_product_engineering(db,listing.id,'0'*64,SimpleNamespace(email='operator@example.test'))
    assert stale.value.status_code==409
    approved=await approve_playbook_product_engineering(db,listing.id,suggestion['fingerprint'],
        SimpleNamespace(email='operator@example.test'))
    assert approved['reviewed'] is True and approved['published'] is False
    assert listing.raw_specs['configurator']['reviewed'] is True
    assert listing.raw_specs['configurator']['socket']=='am5'
    assert listing.raw_specs['configurator']['power_w']==65
    assert listing.raw_specs['configurator']['source_url']==url
    assert await list_playbook_product_engineering_suggestions(db)==[]
    raw=dict(listing.raw_specs)
    raw['playbook_product_capture']={**raw['playbook_product_capture'],
        'product_properties':{'Socket':'AM5','TDP':'95 W'}}
    listing.raw_specs=raw
    assert len(await list_playbook_product_engineering_suggestions(db))==1
    from app.services.playbook_service import invalidate_conflicting_product_engineering
    from app.services.studio_fit import engineering_specs
    assert invalidate_conflicting_product_engineering(listing,'cpu') is True
    assert engineering_specs(listing.raw_specs)['reviewed'] is False
    assert listing.raw_specs['configurator_review_history'][0]['review']['power_w']==65
    suggestion=_playbook_engineering_suggestion(listing,'cpu')
    with pytest.raises(HTTPException) as confirmation_required:
        await approve_playbook_product_engineering(db,listing.id,suggestion['fingerprint'],SimpleNamespace(email='operator@example.test'))
    assert confirmation_required.value.status_code==409
    await approve_playbook_product_engineering(db,listing.id,suggestion['fingerprint'],
        SimpleNamespace(email='operator@example.test'),replace_reviewed_values=True)
    assert engineering_specs(listing.raw_specs)['reviewed'] is True
    assert listing.raw_specs['configurator']['power_w']==95
    assert 'review_invalidation' not in listing.raw_specs['configurator']
    raw=dict(listing.raw_specs)
    raw['playbook_product_capture']={**raw['playbook_product_capture'],
        'product_properties':{'Socket':'AM5','TDP':['65 W','95 W']}}
    listing.raw_specs=raw
    assert invalidate_conflicting_product_engineering(listing,'cpu') is True
    suggestion=_playbook_engineering_suggestion(listing,'cpu')
    assert suggestion['conflicted_fields']==['power_w']
    assert len(await list_playbook_product_engineering_suggestions(db))==1
    with pytest.raises(HTTPException) as contradictory:
        await approve_playbook_product_engineering(db,listing.id,suggestion['fingerprint'],
            SimpleNamespace(email='operator@example.test'),replace_reviewed_values=True)
    assert contradictory.value.status_code==409
    assert engineering_specs(listing.raw_specs)['reviewed'] is False
