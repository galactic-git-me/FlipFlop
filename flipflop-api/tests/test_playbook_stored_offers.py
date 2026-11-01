from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.playbook_stored_offers import suggested_offer
from app.services.playbook_service import _persisted_supplier_snapshot_is_current


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


def test_newer_exact_catalogue_capture_replaces_older_low_supplier_price():
    now = datetime.utcnow()
    url = 'https://www.overclockers.co.uk/lian-li-rs-1200w/POW-LIA-06175.html'
    part = _part(url, '144.95', now.isoformat())
    old = _offer(url, '109.99', (now - timedelta(hours=2)).isoformat())

    selected = suggested_offer(part, [old])

    assert selected['item_gbp'] == '144.95'
    assert selected['match_basis'] == 'catalogue_identity'


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
