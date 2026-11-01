"""Selection regressions: required architecture and adequate cost, no providers."""
from app.services.playbook_service import assemble_components, _selected_fit_passes, _plausible_role_candidate

def row(ident,role,title,price,days=3):
    return dict(variant_id=ident,listing_id=ident,role=role,title=title,
                listing_price_gbp=price,source_price_verified=True,rank=ident,
                source_observation=dict(fresh=True,commercial_capture_verified=True,
                    active_listing=True,stock_status='available',stock_evidence='In stock',
                    postage_verified=True,delivery_gbp='0',delivery_working_days=days))
def checks():
    assert _plausible_role_candidate('ram','KLEVV CRAS V RGB 128GB (2x64GB) 6000MHz C32 DDR5 Dual Channel Kit - Black')
    assert not _plausible_role_candidate('ram','Intel Core i5-12400F Desktop Processor, RAM DDR4 and DDR5 up to 128GB')
    definition={'components':{'storage':'4TB NVMe SSD'}}
    chosen,_=assemble_components(definition,[row(1,'storage','Crucial X10 External USB SSD 8TB','100')])
    assert 'storage' not in chosen, 'External drive replaces required internal NVMe'
    definition={'components':{'ram':'32GB LPDDR5X'}}
    chosen,_=assemble_components(definition,[row(1,'ram','Corsair 128GB DDR5 DIMM memory','2199')])
    assert 'ram' not in chosen, 'Desktop RAM replaces integrated LPDDR architecture'
    definition={'components':{'ram':'32GB DDR5'}}
    chosen,_=assemble_components(definition,[row(1,'ram','Corsair 128GB DDR5 DIMM memory','2199',2),row(2,'ram','Kingston 32GB DDR5 DIMM memory','100',3)])
    assert chosen['ram']['variant_id']==2, 'Faster ETA outranks adequate affordable RAM'
    chosen,_=assemble_components(definition,[row(1,'ram','Corsair 32GB DDR5 DIMM memory','200',2),row(2,'ram','Kingston 32GB DDR5 DIMM memory','100',3)])
    assert chosen['ram']['variant_id']==2, 'Equivalent adequate RAM ignores lower landed cost'
    definition={'components':{'cpu':'Ryzen 5 5600G','gpu':'Integrated Radeon'},'constraints':{'cpu':{'socket':'AM4'}}}
    incompatible=row(1,'cpu','AMD Ryzen 5 9600X Processor integrated graphics','100')
    incompatible['engineering']={'socket':'AM5','integrated_graphics':True}
    incompatible['performance_evidence']={'benchmark_source':'test','confidence_score':1,'overall_score':200}
    chosen,_=assemble_components(definition,[incompatible],performance_baselines={'cpu':{'metric':'overall_score','benchmark_source':'test','overall_score':100}})
    assert 'cpu' not in chosen, 'Benchmark substitution violates approved CPU socket architecture'
    from datetime import datetime, timezone
    observed=datetime.now(timezone.utc).isoformat()
    definition={'components':{'cpu':'AMD Ryzen Threadripper PRO 7975WX','gpu':'NVIDIA RTX 6000 Ada'},
                'constraints':{'cpu':{'socket':'sTR5'}}}
    exact=row(10,'cpu','AMD Ryzen Threadripper PRO 7975WX Processor','3409.33')
    exact.update(price_observed_at=observed,engineering={'socket':'str5'})
    exact['source_observation']['stock_status']='unavailable'
    replacement=row(11,'cpu','AMD Ryzen Threadripper PRO 9975WX Processor','3599.99')
    replacement.update(price_observed_at=observed,engineering={'socket':'str5'},
        performance_evidence={'benchmark_source':'passmark','confidence_score':.8,'overall_score':105304})
    baseline={'cpu':{'metric':'overall_score','benchmark_source':'passmark','overall_score':95566}}
    chosen,_=assemble_components(definition,[exact,replacement],performance_baselines=baseline)
    assert chosen['cpu']['variant_id']==11, 'Unavailable exact CPU hides a verified faster in-stock replacement'
    replacement['performance_evidence']['overall_score']=90000
    chosen,_=assemble_components(definition,[exact,replacement],performance_baselines=baseline)
    assert chosen['cpu']['variant_id']==10, 'A slower replacement bypasses the authored performance floor'
    unknown_case=[{'code':'BOARD_FIT','severity':'unknown','affected':['motherboard','case']}]
    assert _selected_fit_passes(unknown_case,{'cpu','motherboard','ram','gpu'},False)
    assert not _selected_fit_passes(unknown_case,{'cpu','motherboard','ram','gpu','case'},False), \
        'Search enumerates unrelated PSU/storage choices after the selected board/case pair is already unverified'
    workstation={'components':{'cpu':'AMD Ryzen Threadripper PRO 7975WX','case':'Fractal Design Define 7 XL'}}
    processor=row(20,'cpu','AMD Ryzen Threadripper PRO 7975WX Processor','3400')
    processor['engineering']={'socket':'str5','reviewed':True}
    chassis=row(21,'case','LANCOOL 217 Infinity - Black','109.99')
    chassis['engineering']={'reviewed':True,'supported_form_factors':['atx','ssi-eeb']}
    ordinary=row(22,'case','Budget ATX mid-tower PC case','20')
    ordinary['engineering']={'reviewed':True,'supported_form_factors':['atx']}
    chosen,_=assemble_components(workstation,[processor,chassis,ordinary])
    assert chosen.get('case',{}).get('variant_id')==21, 'Verified SSI-EEB replacement is rejected by the authored case brand'
    from app.services.playbook_component_facts import resolve_primary_engineering, manufacturer_facts
    board=resolve_primary_engineering({'role':'motherboard','title':'Asrock WRX90 WS EVO (sTR5) EEB Motherboard',
        'engineering':{'reviewed':True,'reviewed_by':'automation:retailer','form_factor':'e-atx'}})
    assert board['reviewed'] and board['form_factor']=='ssi-eeb' and board['ram_slots']==8
    assert board['primary_source_resolutions']['form_factor']['captured']=='e-atx'
    cpu=resolve_primary_engineering({'role':'cpu','title':'Ryzen 7 9800X3D Processor, No AM5 Cooler','engineering':{}})
    assert cpu['reviewed'] and cpu['socket']=='am5' and cpu['power_w']==120
    assert manufacturer_facts('case','LANCOOL 217 Infinity - Black')['installed_fans']==3
    assert not _plausible_role_candidate('case','LANCOOL 217 Infinity dust filter')
    assert not _plausible_role_candidate('case','LANCOOL 217 Infinity front panel')
    dimm=row(31,'ram','Silicon Power RDIMM 32GB (1x32GB) DDR5 memory kit','100')
    dimm.update(supplier_postage_gbp='5',landed_gbp='105',
        suggested_supplier_offer={'item_gbp':'100','delivery_gbp':'5','postage_verified':True})
    memory,_=assemble_components({'components':{'ram':'256GB DDR5 ECC RDIMM'}},[dimm])
    scaled=memory['ram']
    assert scaled['quantity']==8 and scaled['listing_price_gbp']=='800.00'
    assert scaled['suggested_supplier_offer']['item_gbp']=='100', 'BOM quantity overwrites the captured supplier unit price'
    from app.services.playbook_pricing_guidance import estimate
    from types import SimpleNamespace
    guidance=estimate({'components':[scaled]},{'components':{'ram':'256GB DDR5 ECC RDIMM'}},
        SimpleNamespace(),SimpleNamespace(opportunity_delivery_fallback_gbp=20))
    assert guidance['known_parts_subtotal_gbp']=='840.00', 'Draft cost omits separately procured DIMMs'
    first=row(41,'storage','4TB NVMe internal SSD','400')
    duplicate={**first,'role':'storage_secondary','variant_id':42}
    second=row(43,'storage_secondary','4TB SATA internal SSD','450')
    drives,_=assemble_components({'components':{'storage':'4TB NVMe SSD + 4TB project SSD'}},[first,duplicate,second])
    assert drives['storage_secondary']['listing_id']==43
    print('PASS: internal storage, authored memory family and adequate landed-cost selection')
if __name__=='__main__': checks()
