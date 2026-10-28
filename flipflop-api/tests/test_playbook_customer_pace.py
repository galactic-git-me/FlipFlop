"""Customer pace contracts: per-component coverage and no Flexible deadline."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.playbook_pace_sources import component_pace_sources
from app.services.commercial_checkout import accepted_delivery, commercial_promised_date
from test_playbook_commercial_quote import policy_data


class CustomerPaceTests(unittest.TestCase):
    def part(self, days=1):
        url = 'https://www.overclockers.co.uk/test-cpu/PRO-AMD-02677.html'
        source = dict(url=url, source='overclockers', item_gbp='100', delivery_gbp='0',
            observed_at=datetime.now(timezone.utc).isoformat(), fresh=True,
            active_listing=True, stock_status='available', stock_evidence='In stock',
            commercial_capture_verified=True, condition='new', listing_type='buy_it_now',
            postage_verified=False, postage_assumption='owner-approved-zero-fallback',
            delivery_working_days=days, observation_id=1)
        return dict(role='cpu', variant_id=1, listing_id=1, title='AMD Ryzen 5 9600X',
                    source_url=url, source_observation=source)

    def test_each_component_has_three_pace_entries(self):
        result = component_pace_sources({'cpu': self.part()}, CellCommercialPolicy.model_validate(policy_data()))
        self.assertEqual(set(result), {'fast_track', 'standard', 'flexible'})
        self.assertTrue(all(rows[0]['available'] for rows in result.values()))
        self.assertFalse(result['flexible'][0]['delivery_promised'])

    def test_long_arrival_only_flexible(self):
        result = component_pace_sources({'cpu': self.part(45)}, CellCommercialPolicy.model_validate(policy_data()))
        self.assertFalse(result['fast_track'][0]['available'])
        self.assertFalse(result['standard'][0]['available'])
        self.assertTrue(result['flexible'][0]['available'])

    def test_unknown_stock_is_never_an_available_option(self):
        part = self.part()
        part['source_observation']['stock_status'] = 'unknown'
        result = component_pace_sources({'cpu': part}, CellCommercialPolicy.model_validate(policy_data()))
        self.assertTrue(all(not rows[0]['available'] for rows in result.values()))

    def test_missing_policy_does_not_crash_incomplete_build(self):
        result = component_pace_sources({'cpu': self.part()}, None)
        self.assertTrue(all(not rows[0]['available'] for rows in result.values()))

    def test_accepted_flexible_never_inherits_legacy_date(self):
        accepted = SimpleNamespace(decision_json={'mode':'flexible', 'quote':{
            'delivery_working_days':10}}, evidence_json={'build_config':{'curated_build_id':'FF-STU-02'}})
        delivery = accepted_delivery(accepted)
        self.assertIsNone(delivery['delivery_days'])
        self.assertIn('no promised delivery date', delivery['promise'])
        self.assertIsNone(commercial_promised_date({**delivery, 'delivery_days':10}))

if __name__ == '__main__':
    unittest.main()
