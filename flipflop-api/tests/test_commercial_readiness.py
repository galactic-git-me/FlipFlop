"""Readiness/import boundaries without connecting to a database."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from app.api.commercial_readiness import import_collected_evidence, save_commercial_draft
from app.services.commercial_source_validation import ImportEntry, source_values
from app.services.commercial_readiness import (catalogue_required_roles, catalogue_selected_roles,
    draft_errors, empty_draft, definition_hash)
from app.services.commercial_quote_evidence import latest_listing_observations, supplier_identity
from test_playbook_commercial_quote import policy_data

class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.definition = {'id':'cell', 'segment':'Gaming'}
        self.draft = empty_draft(self.definition, 1, {1:[101,'cpu']}, [1,'case'])
        self.entry = ImportEntry(part_key='cpu', observation_id=1, source_fingerprint='a'*64,
                                fees_gbp='0', risk_gbp='0', supplier_confidence='0.9', stock_confirmed=True)
        self.source = dict(condition='new', source='amazon', url='https://www.amazon.co.uk/dp/EXACT',
            fresh=True, active_listing=True, item_gbp='100.12', delivery_gbp='3.50',
            observed_at=datetime.now(timezone.utc).isoformat(), delivery_working_days=2,
            delivery_estimate_source='scraped', prime_eligible=False, observation_id=1, fingerprint='a'*64)

    def test_unknown_costs_remain_unknown(self):
        _, errors = draft_errors(self.draft)
        self.assertTrue(errors)
        self.assertEqual(self.draft['modes']['standard']['costs']['build_labour'],'0.00')
        self.assertIsNone(self.draft['modes']['standard']['costs']['outbound_delivery'])
        self.assertFalse(self.draft['checkout_enabled'])

    def test_required_catalogue_roles_match_playbook_assembly_for_integrated_and_multi_device_builds(self):
        integrated = {'components': {
            'cpu': 'AMD Ryzen AI 5 340 (integrated)',
            'gpu': 'AMD Radeon 840M integrated',
            'storage': '1TB NVMe SSD',
            'os': 'Windows 11 Home',
        }}
        workstation = {'components': {
            'cpu': 'AMD Threadripper PRO',
            'gpu': 'NVIDIA RTX 6000 Ada',
            'storage': '4TB NVMe SSD + 8TB data SSD',
            'os': 'Ubuntu 24.04 LTS + Windows 11 Pro dual-boot',
        }}

        integrated_roles = catalogue_required_roles(integrated)
        workstation_roles = catalogue_required_roles(workstation)

        self.assertNotIn('gpu', integrated_roles)
        self.assertIn('os', integrated_roles)
        self.assertIn('storage_secondary', workstation_roles)
        self.assertIn('os_secondary', workstation_roles)

    def test_readiness_counts_service_selected_catalogue_products_not_legacy_storefront_slots(self):
        required = {'cpu', 'gpu', 'case', 'os'}
        proposal = SimpleNamespace(proposed_data={'components': [
            {'role': 'cpu', 'variant_id': 12},
            {'role': 'gpu', 'variant_id': 13},
            {'role': 'case', 'case_catalogue_id': 8},
            {'role': 'os', 'variant_id': 15},
            {'role': 'ram', 'variant_id': 16},
            {'role': 'motherboard', 'variant_id': None},
        ]})

        self.assertEqual(catalogue_selected_roles(proposal, required), required)

    def test_complete_financial_policy_requires_reviewed_case(self):
        raw = policy_data()
        _, errors = draft_errors(raw)
        self.assertIn('checkout_case', {e['field'] for e in errors})

    def test_import_preserves_price_and_observation_time(self):
        result = source_values(self.source, self.entry)
        self.assertEqual(str(result['item_gbp']), '100.12')
        self.assertEqual(result['observed_at'].isoformat(), self.source['observed_at'])
        self.assertTrue(result['stock_confirmed'])

    def test_marketplace_seller_name_is_not_mistaken_for_the_supplier_platform(self):
        amazon = source_values({**self.source, 'source':'Storage Kit'}, self.entry)
        self.assertEqual(amazon['supplier'], 'amazon')
        self.assertEqual(amazon['channel'], 'retail')

        ebay = source_values({**self.source, 'source':'Some eBay Seller',
                              'url':'https://www.ebay.co.uk/itm/123456'}, self.entry)
        self.assertEqual(ebay['supplier'], 'ebay')
        self.assertEqual(ebay['channel'], 'marketplace')

    def test_royalcdkeys_digital_software_requires_its_exact_source_review(self):
        source={**self.source,'source':'RoyalCDKeys',
            'url':'https://royalcdkeys.com/en-gb/products/windows-11-pro-oem-cd-key',
            'item_gbp':'5.73','delivery_gbp':'0.00','delivery_working_days':0}
        with self.assertRaises(HTTPException):
            source_values(source,self.entry)

        result=source_values({**source,'licence_source_reviewed':True},self.entry)
        self.assertEqual(result['supplier'],'royalcdkeys')
        self.assertEqual(result['channel'],'software')
        self.assertEqual(result['delivery_working_days'],0)

    def test_stale_or_inactive_cannot_be_confirmed(self):
        for field in ('fresh', 'active_listing'):
            with self.assertRaises(HTTPException):
                source_values({**self.source, field:False}, self.entry)
        negative = self.entry.model_copy(update={'stock_confirmed':False})
        self.assertFalse(source_values({**self.source, 'fresh':False}, negative)['stock_confirmed'])

    def test_fractional_penny_and_missing_prices_rejected(self):
        for price in ('NaN', '-1', '100.001', 'None'):
            with self.assertRaises(HTTPException):
                source_values({**self.source, 'item_gbp':price}, self.entry)

    def test_stock_review_is_required(self):
        data=self.entry.model_dump();data.pop('stock_confirmed')
        with self.assertRaises(ValidationError):
            ImportEntry.model_validate(data)

    def test_new_negative_supersedes_supplier_alias_and_channel(self):
        now=datetime.now(timezone.utc)
        old=SimpleNamespace(id=1, part_key='cpu', supplier='Amazon', channel='manual', evidence_ref=self.source['url'], observed_at=now, stock_confirmed=True)
        new=SimpleNamespace(id=2, part_key='cpu', supplier='amazon', channel='retail', evidence_ref=self.source['url'], observed_at=now+timedelta(seconds=1), stock_confirmed=False)
        self.assertEqual(latest_listing_observations([old,new]),[new])
        self.assertEqual(supplier_identity('Overclockers UK',''), 'overclockers')
        self.assertEqual(supplier_identity('Amazon','https://['), 'amazon')

    async def test_manual_commercial_draft_is_disabled(self):
        with self.assertRaises(HTTPException) as error:
            await save_commercial_draft(1, 'cell', MagicMock(), SimpleNamespace(id=1))
        self.assertEqual(error.exception.status_code, 409)

    async def test_manual_evidence_entry_is_disabled(self):
        with self.assertRaises(HTTPException) as error:
            await import_collected_evidence(1, 'cell', MagicMock(), SimpleNamespace(id=1))
        self.assertEqual(error.exception.status_code, 409)
