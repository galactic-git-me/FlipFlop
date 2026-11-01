"""Pure projection tests: no database connections or external providers."""
from datetime import datetime
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock
from app.services.playbook_book import project_cell, record_cell_event, assignment_availability


class PlaybookBookTests(TestCase):
    def setUp(self):
        self.definition = {'id': 'G-1', 'segment': 'Gaming', 'tier': 'Budget', 'name': 'Gaming Budget'}
        self.parent = NS(id=10, pricing_model={}, market_selling_price=9999)
        self.segment = NS(id=1, is_live=False, selling_price=None,
                          availability_status='not_configured', software_profile=None, components={})

    def project(self, **kwargs):
        return project_cell(self.definition, self.segment, self.parent,
                            kwargs.get('proposals', []), kwargs.get('snapshots', []), kwargs.get('channels', []))

    def test_never_borrows_segment_wide_prices_or_other_cell_channels(self):
        product = NS(id=1, item_specifics={'curated_build_id': 'G-2'})
        listing = NS(channel='ebay', status='active', external_listing_id='123', updated_at=None)
        value = self.project(channels=[(product, listing)])
        self.assertIsNone(value['market'])
        self.assertIsNone(value['active_build_market_gbp'])
        self.assertIsNone(value['walk_away_price_gbp'])
        self.assertEqual([row['channel'] for row in value['distribution']], ['storefront'])
        self.assertEqual(value['distribution'][0]['status'], 'offline')

    def test_pending_proposal_does_not_replace_approved_offer_identity(self):
        self.parent.pricing_model = {'managed_offers': {'G-1': {'revision_sha256': 'approved'}},
                                    'commercial_cells': {'G-1': {'checkout_enabled': True, 'version': 2}}}
        proposal = NS(id=2, status='pending', proposed_data={'cell_id': 'G-1', 'revision_sha256': 'pending'},
                      proposed_at=datetime(2026, 10, 15), updated_at=datetime(2026, 10, 15),
                      resolved_at=None, resolved_by=None, reason='Changed source', rejection_reason=None)
        value = self.project(proposals=[proposal])
        self.assertEqual(value['offer_basis'], 'pending_proposal')
        self.assertEqual(value['offer']['revision_sha256'], 'pending')
        self.assertEqual(value['approved_offer']['revision_sha256'], 'approved')
        self.assertFalse(value['is_live'])

    def test_exact_cell_events_and_channels_are_exposed_without_raw_quote_evidence(self):
        snapshot = NS(id=3, product_key='playbook-cell:G-1', status='playbook_event',
                      created_at=datetime(2026, 10, 15), created_by_admin_id=0,
                      evidence_json={'event': 'taken_offline', 'reason': 'Stock unavailable',
                                     'before': {'is_live': True}, 'after': {'is_live': False},
                                     'private_quote_payload': 'must not leak'}, decision_json={})
        product = NS(id=1, item_specifics={'curated_build_id': 'G-1'})
        listing = NS(channel='ebay', status='active', external_listing_id='123', updated_at=None)
        value = self.project(snapshots=[snapshot], channels=[(product, listing)])
        self.assertEqual(value['history'][0]['reason'], 'Stock unavailable')
        self.assertNotIn('private_quote_payload', str(value))
        self.assertEqual(value['distribution'][1]['external_id'], '123')

    def test_unchanged_state_adds_no_event_and_changed_state_is_append_only(self):
        db = Mock()
        record_cell_event(db, 'G-1', 'updated', 'reason', {'price': 1}, {'price': 1})
        db.add.assert_not_called()
        record_cell_event(db, 'G-1', 'updated', 'reason', {'price': 1}, {'price': 2}, 7)
        event = db.add.call_args.args[0]
        self.assertEqual(event.status, 'playbook_event')
        self.assertEqual(event.created_by_admin_id, 7)
        self.assertEqual(event.evidence_json['before']['price'], 1)

    def test_assigned_availability_uses_current_listing_status_not_saved_cell_label(self):
        segment = NS(components={'cpu': 10, 'ram': 11}, availability_status='in_stock')
        self.assertEqual(assignment_availability(segment, {10: ('active', 'active'), 11: ('active', 'removed')}), 'out_of_stock')
        self.assertEqual(assignment_availability(segment, {10: ('active', 'active')}), 'out_of_stock')
        self.assertEqual(assignment_availability(NS(components={}), {}), 'not_configured')

    def test_approved_floor_requires_matching_definition_policy_and_selected_parts(self):
        from app.services.commercial_quote_evidence import definition_hash
        approved = {'revision_sha256': 'a'*64, 'approved_revision_sha256': 'a'*64,
                    'approved_policy_version': 2, 'approved_at': '2026-10-15T00:00:00Z',
                    'components': [{'role': 'cpu', 'variant_id': 7}],
                    'delivery_products': {'standard': {'profit_floor_gbp': '700.00'}}}
        policy = {'version': 2, 'definition_sha256': definition_hash(self.definition)}
        self.parent.pricing_model = {'managed_offers': {'G-1': approved}, 'commercial_cells': {'G-1': policy}}
        self.segment.components = {'cpu': 7}
        self.assertEqual(self.project()['walk_away_price_gbp'], '700.00')
        self.segment.components = {'cpu': 8}
        self.assertIsNone(self.project()['walk_away_price_gbp'])
        self.segment.components = {'cpu': 7}
        policy['version'] = 3
        self.assertIsNone(self.project()['walk_away_price_gbp'])

    def test_channel_assignment_conflicts_are_not_resolved_by_guessing(self):
        from app.services.playbook_book_evidence import resolve_cell_identity
        definitions = {'G-1': self.definition, 'G-2': {**self.definition, 'id': 'G-2'}}
        parents = {'Gaming': 10}
        self.assertEqual(resolve_cell_identity(None, {'curated_build_id':'G-1','playbook_id':10}, 10, definitions, parents), ('G-1', None))
        self.assertIsNone(resolve_cell_identity('G-1', {'curated_build_id':'G-2'}, 10, definitions, parents)[0])
        self.assertIsNone(resolve_cell_identity('G-1', {}, 11, definitions, parents)[0])
        self.assertIsNone(resolve_cell_identity('UNKNOWN', {}, 10, definitions, parents)[0])

    def test_proposal_costs_keep_vat_separate_and_expose_the_existing_floor(self):
        from decimal import Decimal
        from unittest.mock import patch
        from app.schemas.commercial_quote import CellCommercialPolicy
        from app.services.playbook_service import estimate_delivery_products, withhold_incomplete_bom_prices
        costs = {key:'0' for key in ('packaging','outbound_delivery','insurance','payment_fixed',
                 'expected_failure_cost','allocated_overhead','other_variable_costs')}
        costs['build_labour'] = '20.00'
        mode = {'costs':costs,'minimum_contribution_gbp':'50.00','minimum_margin_fraction':'0.20',
                'premium_gbp':'0','workshop_working_days':1,'courier_working_days':1,'maximum_delivery_working_days':3}
        policy = CellCommercialPolicy.model_validate({'version':1,'definition_sha256':'a'*64,
            'required_part_keys':['variant:1'],'condition':'new','vat_rate':'0.20',
            'payment_rate':'0.03','warranty_rate':'0.05','returns_rate':'0.02',
            'modes':{name:mode for name in ('fast_track','standard','flexible')}})
        part={'listing_price_gbp':'100.00','supplier_postage_gbp':'0.00','landed_gbp':'100.00',
              'source_observation':{'delivery_working_days':0}}
        with patch('app.services.playbook_service.required_parts',return_value={'cpu':1}), \
             patch('app.services.playbook_service.automatic_policy',return_value=policy), \
             patch('app.services.playbook_service.component_delivery_eligibility',return_value={name:True for name in policy.modes}):
            result=estimate_delivery_products({'cpu':part},{},None,None)
        standard=result['standard']
        self.assertEqual(standard['profit_floor_gbp'],'231.84')
        self.assertEqual(standard['estimated_total_cost_gbp'],'143.20')
        self.assertEqual(standard['net_revenue_gbp'],'193.20')
        self.assertEqual(standard['vat_gbp'],'38.64')
        self.assertEqual(Decimal(standard['net_revenue_gbp'])-Decimal(standard['estimated_total_cost_gbp']),Decimal('50.00'))
        withheld=withhold_incomplete_bom_prices(result,['second drive unmodelled'])
        self.assertIsNone(withheld['standard']['profit_floor_gbp'])
        self.assertIsNone(withheld['standard']['estimated_total_cost_gbp'])


from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch


class PlaybookRebuildTests(IsolatedAsyncioTestCase):
    async def test_stored_fact_rebuild_reuses_sync_and_never_runs_the_remote_default_sync(self):
        from app.services.playbook_service import run_playbook_rebuild
        session=AsyncMock()
        context=AsyncMock()
        context.__aenter__.return_value=session
        sync_result={'created':0}
        with patch('app.database.AsyncSessionLocal',return_value=context), \
             patch('app.services.playbook_service.sync_bestseller_catalogues',AsyncMock(return_value=sync_result)) as sync, \
             patch('app.services.playbook_service.refresh_playbooks',AsyncMock(return_value={'cells':24,'complete_hardware':1,'ready_for_approval':0})) as refresh:
            result=await run_playbook_rebuild(1)
        sync.assert_awaited_once_with(session,check_free_software=False)
        self.assertEqual(refresh.await_args.kwargs['catalogue_sync'],sync_result)
        self.assertFalse(result['published'])
