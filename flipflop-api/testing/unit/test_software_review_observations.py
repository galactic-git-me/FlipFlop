"""New stock observations must not discard exact software licence review facts."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from app.services.commercial_readiness import observation_data

URL = 'https://www.gamers-outlet.net/en/buy-windows-11-home-cd-key-retail-microsoft-global'


class SoftwareReviewObservationTests(unittest.TestCase):
    def source(self, *, reviewed=True, capture_url=URL, review_fingerprint='licence-facts'):
        now = datetime.now(timezone.utc)
        listing = SimpleNamespace(id=1, status='active', url=URL, source_name='Gamers Outlet',
            external_id='gamers_outlet:windows-home', raw_specs={
                'playbook_product_capture': {'status': 'captured', 'url': capture_url,
                    'digital_product': True, 'licence_review_required': True,
                    'licence_review_fingerprint': 'licence-facts',
                    'product_properties': {'License type (supplier listing)': 'oem'},
                    'delivery_working_days': 0, 'item_gbp': '3.47'},
                'playbook_licence_source_review': {'reviewed': reviewed,
                    'licence_review_fingerprint': review_fingerprint,
                    'reviewed_at': '2026-11-16T11:15:39+00:00'},
            })
        observation = SimpleNamespace(id=2, listing_id='gamers_outlet:windows-home',
            observed_at=now, condition_normalised='new', listing_type='buy_it_now',
            source='gamers_outlet', item_price=4.0, postage_price=0.0,
            delivery_working_days=3, delivery_estimate_source='vendor_default',
            prime_eligible=None, delivery_text=None, commercial_source_evidence={
                'url': URL, 'observed_at': now.isoformat(), 'item_gbp': '4.00',
                'delivery_gbp': '0.00', 'stock_status': 'available',
                'stock_evidence': 'https://schema.org/InStock',
            })
        return observation_data(listing, observation, None, None)

    def test_new_price_keeps_matching_licence_review_without_copying_old_commercial_facts(self):
        source = self.source()
        self.assertTrue(source.get('licence_source_reviewed'))
        self.assertEqual(source['licence_review_fingerprint'], 'licence-facts')
        self.assertEqual(source['product_properties']['License type (supplier listing)'], 'oem')
        self.assertEqual(source['item_gbp'], '4.00')
        self.assertEqual(source['delivery_working_days'], 3)
        self.assertEqual(source['delivery_estimate_source'], 'vendor_default')
        self.assertEqual(source['observation_id'], 2)

    def test_changed_licence_facts_do_not_reuse_review(self):
        self.assertFalse(self.source(review_fingerprint='previous-facts').get('licence_source_reviewed'))

    def test_unreviewed_source_remains_unreviewed(self):
        self.assertFalse(self.source(reviewed=False).get('licence_source_reviewed'))

    def test_other_product_capture_cannot_supply_licence_facts(self):
        self.assertFalse(self.source(capture_url=URL+'-other-product').get('licence_source_reviewed'))



class DigitalOfferPrecedenceTests(unittest.TestCase):
    def setUp(self):
        self.page = {'url': URL, 'identity_source': 'exact_retailer_product_page',
            'observed_at': '2026-11-27T01:00:00+00:00', 'fresh': True,
            'item_gbp': '3.47', 'delivery_gbp': '0.00', 'condition': 'new',
            'stock_status': 'available', 'stock_evidence': 'InStock',
            'licence_review_fingerprint': 'licence-facts',
            'delivery_working_days': 0, 'delivery_estimate_source': 'digital_delivery'}
        self.newer = {**self.page, 'observed_at': '2026-11-27T02:00:00+00:00',
            'identity_source': 'approved_catalogue_listing_link',
            'commercial_capture_verified': True,
            'delivery_working_days': 3, 'delivery_estimate_source': 'vendor_default'}

    def test_same_unchanged_digital_offer_keeps_complete_instant_delivery_capture(self):
        from app.services.commercial_readiness import prefer_exact_product_page_preview
        self.assertTrue(prefer_exact_product_page_preview(self.page, self.newer))

    def test_newer_price_or_stock_change_is_not_hidden_by_old_digital_capture(self):
        from app.services.commercial_readiness import prefer_exact_product_page_preview
        self.assertFalse(prefer_exact_product_page_preview(self.page, {**self.newer, 'item_gbp': '4.00'}))
        self.assertFalse(prefer_exact_product_page_preview(self.page, {**self.newer, 'stock_status': 'unavailable'}))

    def test_stale_or_other_product_digital_capture_is_not_reused(self):
        from app.services.commercial_readiness import prefer_exact_product_page_preview
        self.assertFalse(prefer_exact_product_page_preview({**self.page, 'fresh': False}, self.newer))
        self.assertFalse(prefer_exact_product_page_preview({**self.page, 'url': URL+'-other'}, self.newer))

if __name__ == '__main__':
    unittest.main()
