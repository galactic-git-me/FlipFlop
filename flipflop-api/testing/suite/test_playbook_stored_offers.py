from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.playbook_stored_offers import (
    _apply_exact_product_page_capture,
    recorded_offer,
    suggested_offer,
)
from app.services.playbook_service import _persisted_supplier_snapshot_is_current
from app.services.commercial_quote_evidence import supplier_identity
from app.services.playbook_service import _supplier_fact_is_approvable


def _part(url, item, observed_at):
    return {
        'role': 'psu',
        'title': 'Lian Li RS 1200W ATX Power Supply',
        'source_url': url,
        'listing_price_gbp': str(item),
        'supplier_postage_gbp': None,
        'price_observed_at': observed_at,
        'source_observation': {
            'fresh': True,
            'commercial_capture_verified': True,
            'condition': 'new',
            'listing_type': 'buy_it_now',
            'stock_status': 'available',
            'stock_evidence': 'In stock',
            'postage_verified': False,
            'source': 'overclockers',
        },
    }


def _offer(url, item, observed_at):
    return {
        'observation_id': int(abs(hash(observed_at)) % 1_000_000),
        'title': 'Lian Li RS 1200W ATX Power Supply',
        'url': url,
        'item_gbp': str(item),
        'delivery_gbp': None,
        'observed_at': observed_at,
        'condition': 'new',
        'listing_type': 'buy_it_now',
        'stock_status': 'available',
        'stock_evidence': 'In stock',
        'commercial_capture_verified': True,
        'postage_verified': False,
    }


@pytest.mark.parametrize(('supplier', 'url'), [
    ('scan', 'https://www.scan.co.uk/products/corsair-rm750x'),
    ('ebuyer', 'https://www.ebuyer.com/corsair-rm750x'),
    ('computer_orbit', 'https://www.computerorbit.com/corsair-rm750x'),
    ('awd_it', 'https://www.awd-it.co.uk/corsair-rm750x.html'),
    ('ccl', 'https://www.cclonline.com/corsair-rm750x/'),
])
def test_fresh_exact_captured_uk_supplier_offer_can_pass_source_gate(supplier, url):
    source = {
        'source': supplier, 'url': url, 'item_gbp': '99.99', 'delivery_gbp': '0.00',
        'postage_verified': True, 'observed_at': datetime.now(timezone.utc).isoformat(),
        'fresh': True, 'commercial_capture_verified': True, 'active_listing': True,
        'condition': 'new', 'listing_type': 'buy_it_now', 'stock_status': 'available',
        'stock_evidence': 'In stock',
    }
    part = {'role': 'psu', 'source_url': url}

    assert supplier_identity(supplier, url) == supplier
    assert _supplier_fact_is_approvable(part, source)


@pytest.mark.parametrize(('supplier', 'url'), [
    ('scan', 'https://www.scan.co.uk/products/corsair-rm750x'),
    ('ebuyer', 'https://www.ebuyer.com/corsair-rm750x'),
    ('computer_orbit', 'https://www.computerorbit.com/corsair-rm750x'),
    ('awd_it', 'https://www.awd-it.co.uk/corsair-rm750x.html'),
    ('ccl', 'https://www.cclonline.com/corsair-rm750x/'),
])
def test_alternative_supplier_offer_still_requires_fresh_confirmed_stock(supplier, url):
    source = {
        'source': supplier, 'url': url, 'item_gbp': '99.99', 'delivery_gbp': '0.00',
        'postage_verified': True, 'observed_at': datetime.now(timezone.utc).isoformat(),
        'fresh': True, 'commercial_capture_verified': True, 'active_listing': True,
        'condition': 'new', 'listing_type': 'buy_it_now', 'stock_status': 'unknown',
        'stock_evidence': None,
    }

    assert not _supplier_fact_is_approvable({'role': 'psu', 'source_url': url}, source)


def test_newer_exact_catalogue_capture_replaces_older_low_supplier_price():
    now = datetime.utcnow()
    url = 'https://www.overclockers.co.uk/lian-li-rs-1200w/POW-LIA-06175.html'
    part = _part(url, '144.95', now.isoformat())
    old = _offer(url, '109.99', (now - timedelta(hours=2)).isoformat())

    selected = suggested_offer(part, [old])

    assert selected['item_gbp'] == '144.95'
    assert selected['match_basis'] == 'catalogue_identity'


def test_newer_exact_product_page_capture_supersedes_older_supplier_observation():
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    url = 'https://www.overclockers.co.uk/amd-ryzen-5-9600x/PRO-AMD-02677.html'
    row = {
        'id': 123, 'listing_id': 'captured:overclockers:abc', 'cpk': 'cpu:amd:9600x',
        'cpk_data': {'category': 'cpu'}, 'title': 'AMD Ryzen 5 9600X Processor',
        'source': 'overclockers', 'item_price': Decimal('158.99'), 'mpn': None,
        'commercial_source_evidence': {'url': url, 'item_gbp': '158.99',
            'stock_status': 'available', 'stock_evidence': 'Old stock capture'},
        'observed_at': now - timedelta(hours=2), 'category': 'cpu', 'search_tags': [],
        'recorded_product_url': url,
    }
    listing = SimpleNamespace(id=19216, url=url, title='AMD Ryzen 5 9600X Processor',
        source_name='overclockers', raw_specs={'playbook_product_capture': {
            'title': 'AMD Ryzen 5 9600X Six Core Processor', 'mpn': 'PRO-AMD-02677',
        }})
    preview = {
        'identity_source': 'exact_retailer_product_page', 'commercial_capture_verified': True,
        'fresh': True, 'condition': 'new', 'listing_type': 'buy_it_now', 'url': url,
        'observed_at': now.isoformat(), 'item_gbp': '158.99', 'delivery_gbp': '7.99',
        'postage_verified': True, 'stock_status': 'available', 'stock_evidence': 'In stock',
        'delivery_working_days': 2, 'delivery_estimate_source': 'retailer_page_displayed_estimate',
        'prime_eligible': None,
    }

    updated = _apply_exact_product_page_capture(row, listing, preview)
    offer = recorded_offer(updated)

    assert updated['listing_db_id'] == listing.id
    assert offer['item_gbp'] == '158.99'
    assert offer['delivery_gbp'] == '7.99'
    assert offer['delivery_working_days'] == 2
    assert offer['delivery_estimate_source'] == 'retailer_page_displayed_estimate'


def test_exact_product_page_capture_does_not_replace_newer_supplier_observation():
    now = datetime.now(timezone.utc)
    url = 'https://www.overclockers.co.uk/amd-ryzen-5-9600x/PRO-AMD-02677.html'
    row = {'recorded_product_url': url, 'observed_at': now}
    listing = SimpleNamespace(id=19216, url=url, raw_specs={'playbook_product_capture': {}})
    preview = {'identity_source': 'exact_retailer_product_page',
        'commercial_capture_verified': True, 'fresh': True, 'condition': 'new',
        'listing_type': 'buy_it_now', 'url': url,
        'observed_at': (now - timedelta(hours=1)).isoformat(), 'item_gbp': '158.99'}

    assert _apply_exact_product_page_capture(row, listing, preview) is row


def test_newer_exact_supplier_capture_replaces_catalogue_capture_and_old_history():
    now = datetime.utcnow()
    url = 'https://www.overclockers.co.uk/lian-li-rs-1200w/POW-LIA-06175.html'
    part = _part(url, '144.95', (now - timedelta(hours=2)).isoformat())
    old = _offer(url, '109.99', (now - timedelta(hours=4)).isoformat())
    newer = _offer(url, '149.95', (now - timedelta(hours=1)).isoformat())

    selected = suggested_offer(part, [old, newer])

    assert selected['item_gbp'] == '149.95'
    assert selected['observation_id'] == newer['observation_id']


@pytest.mark.asyncio
async def test_newer_different_retailer_capture_does_not_invalidate_exact_supplier_offer():
    from app.models.gem_radar_observation import GemRadarListingObservation

    now = datetime.now(timezone.utc)
    supplier_url = 'https://www.overclockers.co.uk/amd-ryzen-5-9600x/PRO-AMD-02677.html'
    observation = SimpleNamespace(
        commercial_source_evidence={
            'url': supplier_url,
            'item_gbp': '179.99',
            'stock_status': 'available',
            'stock_evidence': 'In stock',
        },
        condition_normalised='new',
        listing_type='buy_it_now',
        source='overclockers',
    )
    db = SimpleNamespace(get=AsyncMock(return_value=observation))
    proposed = {
        'observation_id': 1051519,
        'url': supplier_url,
        'source': 'overclockers',
        'item_gbp': '179.99',
        'observed_at': (now - timedelta(hours=2)).isoformat(),
    }
    part = {'source_url': supplier_url}
    current_catalogue_capture = {
        'url': 'https://www.amazon.co.uk/dp/B0D6NN6TM7',
        'observed_at': now.isoformat(),
    }

    assert await _persisted_supplier_snapshot_is_current(db, part, proposed, current_catalogue_capture)
    db.get.assert_awaited_once_with(GemRadarListingObservation, 1051519)
