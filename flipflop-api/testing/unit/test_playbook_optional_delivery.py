"""Optional unavailable paces must not prevent a reviewed Standard offer."""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from app.services import playbook_service as service
from app.services.playbook_commercial_quote import quote_delivery_modes


class ProposalDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def offer(self, unavailable):
        roles = ('cpu', 'gpu')
        parts = {role: {'role': role, 'variant_id': i, 'slot_id': i,
            'listing_id': i, 'title': role.upper()+' product',
            'source_url': f'https://supplier.example/{role}',
            'source_observation': {'fresh': True, 'active_listing': True,
                'stock_status': 'available', 'condition': 'new'},
            'catalogue_approved': True, 'photo_ready': True, 'media_ready': True,
            'engineering': {}}
            for i, role in enumerate(roles, 1)}
        policy = SimpleNamespace(enabled_modes=list(service.MODES),
            modes={mode: object() for mode in service.MODES})
        assessments = {mode: ({'offerable': False, 'reason': 'No eligible source for '+mode}
            if mode in unavailable else {'offerable': True, 'price_gbp': '100.00',
                'contribution_gbp': '20.00', 'true_cost_gbp': '80.00',
                'net_revenue_gbp': '100.00', 'delivery_working_days': 5})
            for mode in service.MODES}
        estimates = {mode: {'recommended_price_gbp': '100.00',
            'estimated_profit_gbp': '20.00', 'reason': 'pending source review'}
            for mode in service.MODES}
        patches = {
            'required_roles': lambda _: roles,
            'required_parts': lambda _: roles,
            'required_hardware_parts': lambda _: roles,
            'assemble_components': lambda *args, **kwargs: (parts, []),
            '_performance_context': lambda *args: {},
            '_candidate_performance': lambda *args: None,
            'automatic_policy': lambda *args, **kwargs: policy,
            'component_delivery_eligibility': lambda *args: dict.fromkeys(service.MODES, True),
            '_evaluate_playbook_fit': lambda *args, **kwargs: [],
            'estimate_delivery_products': lambda *args, **kwargs: estimates,
        }
        definition = {'id': 'TEST-CELL', 'segment': 'Test', 'tier': 'Budget',
            'name': 'Test build', 'components': {'cpu': 'CPU product', 'gpu': 'GPU product'}}
        parent = SimpleNamespace(id=7, profit_strategy={}, pricing_model={})
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: []))))
        with ExitStack() as stack:
            for name, value in patches.items():
                stack.enter_context(patch.object(service, name, value))
            stack.enter_context(patch('app.services.playbook_planning_checks.wireless_extra_required', return_value=[]))
            stack.enter_context(patch('app.services.playbook_pace_sources.component_pace_sources', AsyncMock(return_value={})))
            stack.enter_context(patch('app.services.commercial_quote_evidence.assess_stored_cell', AsyncMock(return_value=({'modes': assessments}, {}))))
            stack.enter_context(patch('app.services.commercial_checkout.current_capacity_ids', AsyncMock(return_value={})))
            return await service.build_cell_offer(db, definition, parent, SimpleNamespace(), [], benchmark_index={})

    async def test_unavailable_fast_track_keeps_reason_without_blocking_standard(self):
        offer = await self.offer({'fast_track'})
        self.assertEqual(offer['blockers'], [])
        self.assertFalse(offer['delivery_products']['fast_track']['available'])
        self.assertIn('No eligible source', offer['delivery_products']['fast_track']['reason'])
        self.assertTrue(offer['delivery_products']['standard']['available'])
        self.assertFalse(offer['purchasable'])

    async def test_unavailable_standard_still_blocks_publication(self):
        offer = await self.offer({'standard'})
        self.assertTrue(any(row.startswith('standard:') for row in offer['blockers']))
        self.assertFalse(offer['delivery_products']['standard']['available'])

    async def test_both_optional_paces_can_remain_unavailable(self):
        offer = await self.offer({'fast_track', 'flexible'})
        self.assertEqual(offer['blockers'], [])
        self.assertTrue(offer['delivery_products']['standard']['available'])
        self.assertFalse(offer['delivery_products']['flexible']['available'])


class PublicationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = service.automatic_policy(
            {'cpu': {'role': 'cpu', 'slot_id': 1, 'variant_id': 1, 'landed_gbp': '100.00'}},
            {'id': 'TEST', 'tier': 'Budget', 'components': {'cpu': 'CPU'}},
            SimpleNamespace(profit_strategy={}, pricing_model={}),
            SimpleNamespace(opportunity_delivery_fallback_gbp=15,
                speedy_delivery_price_gbp=0, speedy_curated_custom_days=5,
                standard_curated_custom_days=9, flexible_curated_custom_days=14),
            include_market=False)
        self.delivery = {mode: {'available': True, 'recommended_price_gbp': '150.00'}
                         for mode in service.MODES}

    def test_publication_and_checkout_exclude_unavailable_fast_track(self):
        self.delivery['fast_track'] = {'available': False, 'recommended_price_gbp': None}
        policy = service.publication_delivery_policy(self.policy, {'delivery_products': self.delivery})
        self.assertEqual(policy.enabled_modes, ['standard', 'flexible'])
        self.assertEqual(self.policy.enabled_modes, ['fast_track', 'standard', 'flexible'])
        quotes = quote_delivery_modes(policy, [], {})
        self.assertFalse(quotes['modes']['fast_track']['offerable'])
        self.assertIn('not enabled', quotes['modes']['fast_track']['reason'])

    def test_unavailable_or_unpriced_standard_cannot_publish(self):
        for quote in ({'available': False, 'recommended_price_gbp': '150.00'},
                      {'available': True, 'recommended_price_gbp': None}):
            with self.subTest(quote=quote):
                delivery = {**self.delivery, 'standard': quote}
                with self.assertRaises(HTTPException) as error:
                    service.publication_delivery_policy(self.policy, {'delivery_products': delivery})
                self.assertEqual(error.exception.status_code, 409)

    def test_only_standard_can_be_enabled(self):
        delivery = {mode: {**quote, 'available': mode == 'standard'}
                    for mode, quote in self.delivery.items()}
        policy = service.publication_delivery_policy(self.policy, {'delivery_products': delivery})
        self.assertEqual(policy.enabled_modes, ['standard'])

    def test_all_eligible_paces_remain_enabled(self):
        policy = service.publication_delivery_policy(self.policy, {'delivery_products': self.delivery})
        self.assertEqual(policy.enabled_modes, ['fast_track', 'standard', 'flexible'])


if __name__ == '__main__':
    unittest.main()
