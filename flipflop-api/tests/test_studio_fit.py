"""Engineering invariants; synthetic measurements are never catalogue data."""
from copy import deepcopy
from app.services.studio_fit import evaluate_fit, engineering_specs
import pytest


@pytest.fixture
def build():
    parts = {
        'cpu': dict(socket='AM5', power_w=120, cpu_id='test-cpu'),
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


def test_connectors(build):
    build[0]['psu']['psu_connectors']={'8pin':1}
    assert status(build,'POWER_CONNECTOR_8pin')=='error'


def test_evaluation_does_not_mutate_selection(build):
    before=deepcopy(build)
    evaluate_fit(*build)
    assert build==before


def test_only_whitelisted_public_engineering_leaves_service():
    assert engineering_specs({'supplier_cost':1,'configurator':{'socket':'AM5','supplier_cost':2,'reviewed':True}})=={'socket':'AM5','reviewed':True}
    assert engineering_specs('not an object')=={}


def test_empty_build_is_not_certified():
    assert any(c['severity']=='unknown' for c in evaluate_fit({},None))
