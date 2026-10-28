from types import SimpleNamespace

from app.services.curated_publication import publication_snapshot


def make_slot(slot_id, slot_type, variant_id, title, *, price=10):
    return {'slot_id':slot_id,'slot_type':slot_type,'tier_names':{},'variants_by_tier':{
        'budget':[],'mid':[{'id':variant_id,'title':title,'display_price':price,
            'availability':'active','customer_option':{}}],'high':[]}}


def base_definition(storage):
    return {'components':{
        'cpu':'CPU','motherboard':'Board','ram':'32GB DDR5','gpu':'GPU',
        'storage':storage,'cooling':'Cooler','psu':'Power Supply','case':'Corsair 4000D'}}


def test_published_multidrive_cell_keeps_both_slot_selections_and_prices_both_drives():
    definition=base_definition('4TB PCIe 4.0 NVMe SSD + 4TB project SSD')
    roles=['cpu','motherboard','ram','gpu','storage','storage_secondary','cooling','psu','case']
    variants={role:100+index for index,role in enumerate(roles)}
    slots=[make_slot(index+1,role,variants[role],definition['components'].get(role,role))
        for index,role in enumerate(roles)]
    slots[-1]['variants_by_tier']['mid'][0]['title']='Corsair 4000D'
    segment=SimpleNamespace(is_live=True,selling_price=2000,components=variants)
    cases=[{'id':301,'name':'Corsair 4000D','rrp_gbp':100}]

    snapshot=publication_snapshot(definition,segment,slots,cases)

    assert 'storage_secondary' in snapshot['components']
    assert snapshot['default_slot_selections'][6]==variants['storage_secondary']
    assert {slot['baseline_parts_total'] for slot in snapshot['slots']}=={180}
    assert len([slot for slot in snapshot['slots'] if slot['slot_type'].startswith('storage')])==2


def test_non_multidrive_cell_omits_an_unneeded_segment_alias_slot():
    definition=base_definition('4TB PCIe 4.0 NVMe SSD')
    roles=['cpu','motherboard','ram','gpu','storage','storage_secondary','cooling','psu','case']
    variants={role:200+index for index,role in enumerate(roles) if role!='storage_secondary'}
    slots=[make_slot(index+1,role,variants.get(role,999),
        'Corsair 4000D' if role=='case' else definition['components'].get(role,role)) for index,role in enumerate(roles)]
    segment=SimpleNamespace(is_live=True,selling_price=2000,components=variants)

    snapshot=publication_snapshot(definition,segment,slots,[{'id':301,'name':'Corsair 4000D','rrp_gbp':100}])

    assert not any(slot['slot_type']=='storage_secondary' for slot in snapshot['slots'])


def test_unused_segment_fan_slot_does_not_require_an_extra_part_for_a_complete_case():
    definition=base_definition('1TB NVMe SSD')
    definition['components']['gpu']='Integrated graphics'
    roles=['cpu','motherboard','ram','storage','cooling','psu','case']
    variants={role:300+index for index,role in enumerate(roles)}
    slots=[make_slot(index+1,role,variants[role],definition['components'][role]) for index,role in enumerate(roles)]
    slots.append({'slot_id':99,'slot_type':'fan','variants_by_tier':{'mid':[]}})
    slots.append({'slot_id':100,'slot_type':'gpu','variants_by_tier':{'mid':[]}})
    segment=SimpleNamespace(is_live=True,selling_price=1000,components=variants)
    result=publication_snapshot(definition,segment,slots,[{'id':301,'name':'Corsair 4000D','rrp_gbp':100}])
    assert 'fan' not in result['components'] and 'gpu' not in result['components']


def test_dual_boot_allows_only_explicit_official_free_software_at_zero():
    import pytest
    from app.services.curated_publication import PublicationError
    definition=base_definition('1TB NVMe SSD')
    definition['components']['os']='Windows 11 Pro + Ubuntu 24.04 LTS'
    roles=[*definition['components'],'os_secondary']
    variants={role:400+i for i,role in enumerate(roles)}
    slots=[make_slot(i+1,role,variants[role],definition['components'].get(role,'Ubuntu 24.04 LTS'),
        price=0 if role=='os_secondary' else 10) for i,role in enumerate(roles)]
    segment=SimpleNamespace(is_live=True,selling_price=1000,components=variants)
    cases=[{'id':301,'name':'Corsair 4000D','rrp_gbp':100}]
    with pytest.raises(PublicationError,match='priced os_secondary'):
        publication_snapshot(definition,segment,slots,cases)
    slots[-1]['variants_by_tier']['mid'][0]['official_free_software']=True
    assert publication_snapshot(definition,segment,slots,cases)['components']['os_secondary']=='Ubuntu 24.04 LTS'
