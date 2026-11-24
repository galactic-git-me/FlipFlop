"""Research identities must preserve model variants and distinguish whole PCs."""
from scripts.collect_playbook_sold_research import query_blockers
from app.services.playbook_service import _plausible_role_candidate
from app.services.playbook_requirement_sources import requirement_source_gaps


def checks():
    variants = [
        ('7600 5060 Ti gaming PC', 'Ryzen 7600 RTX 5060 8GB', True),
        ('7600 5060 Ti gaming PC', 'Ryzen 7600 RTX 5060 Ti 16GB', False),
        ('RTX 4070 Ti SUPER PC', 'RTX 4070 Ti PC', True),
        ('RTX 4070 Ti SUPER PC', 'RTX 4070 Ti SUPER PC', False),
        ('RX 9060 XT PC', 'RX9060XT PC', False),
        ('5600G desktop PC', 'Ryzen 5600GT PC', True),
        ('RTX5060 Ti PC', 'RTX5060Ti PC', False),
        ('7600 gaming PC', '7600X3D gaming PC', True),
        ('7975WX RTX 6000 Ada workstation', 'Threadripper PRO 5975WX RTX 6000 Ada', True),
        ('7975WX RTX 6000 Ada workstation', 'Threadripper PRO 7975WX RTX 6000 Ada', False),
        ('14900K desktop PC', 'Intel Core i9 14900KF desktop PC', True),
    ]
    for query, title, blocked in variants:
        assert bool(query_blockers(query, title)) == blocked, (query, title)
    roles = [
        ('gpu', 'Gaming PC - Ryzen 5 5500, RTX 5050 8GB Graphics Card, 16GB RAM, 1TB SSD', False),
        ('cpu', 'Gaming PC - AMD Ryzen 5 5500, RTX 5050 8GB', False),
        ('gpu', 'MSI Gaming RTX 5050 8G Shadow 2X OC Graphics Card', True),
        ('cpu', 'AMD Ryzen 5 7600 Desktop Processor', True),
        ('gpu', 'MSI RTX 5050 Graphics Card for Gaming PC', True),
    ]
    for role, title, valid in roles:
        assert bool(_plausible_role_candidate(role, title)) == valid, (role, title)
    definition = {'components': {'cpu': 'Ryzen 5 5600', 'gpu': 'GeForce RTX 5050 8GB'}}
    selected = {'components': [
        {'role': 'cpu', 'title': 'AMD Ryzen 5 5600 Processor'},
        {'role': 'gpu', 'title': 'ASUS GeForce RTX 5050 8GB Graphics Card'},
    ]}
    missing = requirement_source_gaps(definition, selected)
    assert 'cpu' not in missing and 'gpu' not in missing
    assert 'motherboard' in missing
    selected['components'][0]['source_observation']={'fresh':True,'stock_status':'unavailable','active_listing':False}
    assert 'cpu' in requirement_source_gaps(definition, selected), 'Unavailable selected parts suppress replacement discovery'
    selected['components'][0]['source_observation']={'fresh':True,'stock_status':'available','active_listing':True}
    assert 'cpu' not in requirement_source_gaps(definition, selected)
    selected['components'][0]['title'] = 'AMD Ryzen 5 5600X Processor'
    assert 'cpu' in requirement_source_gaps(definition, selected)
    selected['components'][1]['title'] = 'AMD Radeon RX 9060 XT 16GB'
    assert 'gpu' in requirement_source_gaps(definition, selected)
    print('PASS: sold-query variants, component identity and default discovery checks')


if __name__ == '__main__':
    checks()
