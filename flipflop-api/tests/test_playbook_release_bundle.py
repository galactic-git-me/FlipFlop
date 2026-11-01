from copy import deepcopy
import pytest
from app.services.playbook_release_bundle import materialize_reviewed_sources


def fixture():
    return {'source': 'reviewed-dev', 'cases':[], 'listings': [
        {'id': 1, 'external_id': 'amazon:CPU', 'url': 'https://www.amazon.co.uk/dp/CPU', 'title': 'Exact CPU',
         'source_name': 'amazon', 'price': 200, 'raw_specs': {}},
        {'id': 2, 'external_id': 'gamers-outlet:windows', 'url': 'https://www.gamers-outlet.net/windows',
         'source_name': 'gamers_outlet', 'price': 3.34, 'raw_specs': {'licence_review': 'retain'}},
    ], 'variants': [{'id': 10, 'listing_id': 1, 'status': 'hidden', 'reject_reason': 'freshness:active'},
                    {'id': 20, 'listing_id': 2, 'status': 'active'}],
        'proposals': [{'proposed_data': {'components': [
            {'role': 'cpu', 'variant_id': 10, 'listing_id': 1, 'catalogue_approved': True, 'title': 'Exact CPU',
             'source_observation': {'commercial_capture_verified': True, 'observed_at': '2026-10-27T18:00:00+00:00',
               'url': 'https://www.overclockers.co.uk/exact-cpu.html', 'source': 'overclockers',
               'condition': 'new', 'stock_status': 'available', 'item_gbp': '175.00',
               'delivery_gbp': '0', 'postage_verified': False, 'fingerprint': 'captured-proof'}},
            {'role': 'os', 'variant_id': 20, 'listing_id': 2},
        ]}}]}


def test_promotes_exact_reviewed_supplier_without_rewriting_product_or_windows_anchor():
    source = fixture()
    before = deepcopy(source)
    result = materialize_reviewed_sources(source)
    assert source == before
    assert result['listings'][:2] == before['listings']
    cpu = result['proposals'][0]['proposed_data']['components'][0]
    row = next(row for row in result['listings'] if row['id'] == cpu['listing_id'])
    assert row['price'] == 175 and row['source_name'] == 'overclockers'
    capture = row['raw_specs']['playbook_product_capture']
    assert capture['observed_at'] == '2026-10-27T18:00:00+00:00'
    assert capture['postage_verified'] is False
    assert capture['original_capture_fingerprint'] == 'captured-proof'
    assert result['variants'][0]['listing_id'] == row['id']
    assert result['variants'][1] == before['variants'][1]


def test_refuses_unverified_capture_or_rejected_catalogue_variant():
    source = fixture()
    source['proposals'][0]['proposed_data']['components'][0]['source_observation']['commercial_capture_verified'] = False
    with pytest.raises(ValueError, match='evidence is incomplete'):
        materialize_reviewed_sources(source)
    source = fixture()
    source['variants'][0]['status'] = 'rejected'
    with pytest.raises(ValueError, match='explicit catalogue review'):
        materialize_reviewed_sources(source)


def test_product_review_survives_supplier_change_but_not_new_conflicting_facts_or_identity():
    from app.models.listing import Listing
    from app.services.playbook_service import invalidate_conflicting_product_engineering
    source=fixture()
    part=source['proposals'][0]['proposed_data']['components'][0]
    part['engineering']={'reviewed':True,'socket':'am5',
        'source_url':'https://www.amazon.co.uk/dp/CPU','reviewed_by':'operator'}
    result=materialize_reviewed_sources(source)
    data=result['listings'][-1]
    listing=Listing(**deepcopy(data))
    assert invalidate_conflicting_product_engineering(listing,'cpu') is False
    assert listing.raw_specs['configurator']['source_url']=='https://www.amazon.co.uk/dp/CPU'
    listing.raw_specs['playbook_product_capture']['product_properties']={'CPU Socket':'AM4'}
    assert invalidate_conflicting_product_engineering(listing,'cpu') is True
    assert listing.raw_specs['configurator']['reviewed'] is False
    listing=Listing(**deepcopy(data))
    listing.title='Different CPU'
    assert invalidate_conflicting_product_engineering(listing,'cpu') is True


def test_windows_supplier_cannot_be_replaced_by_a_matched_hardware_offer():
    from datetime import datetime, timezone
    from app.services.playbook_service import _current_suggested_supplier_source
    part={'role':'os','listing_id':17,'source_url':'https://www.gamers-outlet.net/windows',
        'suggested_supplier_offer':{'url':'https://www.amazon.co.uk/dp/B000000000',
            'commercial_capture_verified':True,'condition':'new','listing_type':'buy_it_now',
            'stock_status':'available','stock_evidence':'In Stock','observed_at':datetime.now(timezone.utc).isoformat(),
            'item_gbp':'1.00','delivery_gbp':'0.00','postage_verified':True}}
    assert _current_suggested_supplier_source(part) is None
