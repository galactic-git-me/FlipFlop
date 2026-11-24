import pytest
from app.services.curated_build_policy import curated_slots, validate_curated_selection, definitions


def slot(category, *variants):
    return dict(slot_id=1, slot_type=category, variants_by_tier={'mid': list(variants), 'budget': [], 'high': []})


def variant(id, title, **option):
    return dict(id=id, title=title, display_price=100+id, gem_score=100-id, customer_option=option)


def test_core_and_os_cannot_be_swapped_or_removed():
    for category in ('cpu','gpu','motherboard','psu','cooling','os'):
        result = curated_slots([slot(category,variant(1,'Included'),variant(2,'Other'))])
        validate_curated_selection(result,{1:1})
        with pytest.raises(ValueError): validate_curated_selection(result,{1:2})
        with pytest.raises(ValueError): validate_curated_selection(result,{})


def test_ram_only_offers_one_choice_per_capacity_on_same_platform():
    result = curated_slots([slot('ram',variant(1,'16GB',capacity_gb=16,memory_type='DDR4'),variant(2,'32GB',capacity_gb=32,memory_type='DDR4'),variant(3,'Other brand 32GB',capacity_gb=32,memory_type='DDR4'),variant(4,'32GB DDR5',capacity_gb=32,memory_type='DDR5'))])
    assert [v['id'] for v in result[0]['variants_by_tier']['mid']] == [1,2]


def test_storage_offers_sata_nvme_and_capacity_not_hdds():
    result=curated_slots([slot('storage',variant(1,'1TB NVMe',capacity_gb=1000,interface='NVMe'),variant(2,'2TB SATA SSD',capacity_gb=2000,interface='SATA'),variant(3,'HDD',capacity_gb=4000,interface='HDD'))])
    assert [v['id'] for v in result[0]['variants_by_tier']['mid']] == [1,2]


def test_missing_exact_workbook_component_never_substitutes_another():
    result=curated_slots([slot('cpu',variant(1,'Ryzen 5 7600'))],{'components':{'cpu':'Ryzen 5 9600X'}})
    assert result[0]['default_variant_id'] is None
    assert result[0]['variants_by_tier']['mid'] == []


def test_workbook_definitions_preserve_all_builds_without_prices():
    data=definitions()
    assert len(data['builds'])==24
    assert len({b['segment'] for b in data['builds']})==8
    assert len(data['cases'])==183
    assert all(set(b)=={'id','segment','tier','name','description','use','components'} for b in data['builds'])


def test_database_price_is_preserved():
    result=curated_slots([slot('cpu',variant(1,'AMD Ryzen 5 5600'))],{'components':{'cpu':'AMD Ryzen 5 5600'}})
    assert result[0]['variants_by_tier']['mid'][0]['display_price']==101
