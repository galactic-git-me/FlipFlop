from decimal import Decimal
from types import SimpleNamespace as NS
from unittest import TestCase
from app.services.playbook_service import automatic_policy

class PricingAllowanceTests(TestCase):
    def test_missing_delivery_setting_uses_owner_allowances(self):
        settings = NS(speedy_curated_custom_days=3, standard_curated_custom_days=5,
                      flexible_curated_custom_days=10, speedy_delivery_price_gbp=49)
        policy = automatic_policy({'cpu': {'slot_id': 1, 'variant_id': 1, 'landed_gbp': '100'}},
            {'id': 'test', 'tier': 'Budget'}, NS(profit_strategy={}, pricing_model={}), settings,
            include_market=False, definition_sha256_override='a'*64)
        self.assertIsNotNone(policy)
        for mode in policy.modes.values():
            self.assertEqual(mode.costs.outbound_delivery, Decimal('20'))
            self.assertEqual(mode.costs.insurance, Decimal('15'))
            self.assertEqual(mode.costs.build_labour, Decimal('0'))
            self.assertEqual(mode.costs.packaging, Decimal('6'))

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

class ProposalOnlyRefreshTests(IsolatedAsyncioTestCase):
    async def test_proposal_only_refresh_never_maintains_live_offers(self):
        from app.services.playbook_service import refresh_playbooks
        db = AsyncMock()
        rows = Mock()
        rows.scalars.return_value.all.return_value = []
        db.execute.return_value = rows
        with patch('app.services.playbook_service.definitions', return_value={'builds': []}), \
             patch('app.services.playbook_service.paid_component_sales', AsyncMock(return_value={})), \
             patch('app.services.catalogue_cpk.reconcile_active_catalogue_cpks', AsyncMock(return_value={})), \
             patch('app.services.hardware_performance.load_benchmark_context', AsyncMock(return_value=({}, {}))), \
             patch('app.services.playbook_mvp.maintain_offers', AsyncMock()) as maintain:
            result = await refresh_playbooks(db, catalogue_sync={}, maintain_live_offers=False,resolve_missing=False)
        maintain.assert_not_awaited()
        self.assertEqual(result['maintenance']['published'], [])
        self.assertEqual(result['maintenance']['paused'], [])

class ConfiguredDeliveryTests(TestCase):
    def test_explicit_delivery_allowance_is_preserved_including_zero(self):
        for delivery in (0, 35):
            settings = NS(opportunity_delivery_fallback_gbp=delivery,
                speedy_curated_custom_days=3, standard_curated_custom_days=5,
                flexible_curated_custom_days=10, speedy_delivery_price_gbp=49)
            policy = automatic_policy({'cpu': {'slot_id': 1, 'variant_id': 1, 'landed_gbp': '100'}},
                {'id': 'test', 'tier': 'Budget'}, NS(profit_strategy={}, pricing_model={}), settings,
                include_market=False, definition_sha256_override='a'*64)
            self.assertEqual(policy.modes['standard'].costs.outbound_delivery, Decimal(delivery))
