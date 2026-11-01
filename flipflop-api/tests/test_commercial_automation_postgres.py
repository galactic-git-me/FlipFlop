"""Guarded real-PostgreSQL commercial automation and migration checks."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from sqlalchemy import select, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.models.listing import Listing
from app.models.commerce_evidence import SupplierOfferEvidence, PriceQuoteSnapshot
from app.services.commercial_reconciliation import reconcile_commercial
import test_commercial_checkout_postgres as fixtures


class AutomationPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=fixtures.CommercialPostgresTests()
        await self.fixture.asyncSetUp()
        self.db=self.fixture.db
        suffix=uuid4().hex
        self.key=f'automation:{suffix}'
        self.url=f'https://www.overclockers.co.uk/{suffix}'
        self.db.add(Listing(external_id=suffix,source_id=1,source_name='overclockers',title='Exact CPU',
                            price=100,url=self.url,status='active'))
        self.db.add(SupplierOfferEvidence(part_key=self.key,supplier='overclockers',channel='retail',condition='new',
            item_gbp=Decimal('100'),delivery_gbp=0,fees_gbp=0,risk_gbp=2,
            observed_at=datetime.now(timezone.utc)-timedelta(hours=1),stock_confirmed=True,
            delivery_working_days=2,supplier_confidence=Decimal('0.9'),evidence_source='catalogue_import:1:reviewed',
            evidence_ref=self.url,captured_by_admin_id=0))
        await self.db.flush()
        self.source=dict(condition='new',source='overclockers',url=self.url,fresh=True,active_listing=True,
            item_gbp='110.00',delivery_gbp='0',observed_at=datetime.now(timezone.utc).isoformat(),
            delivery_working_days=2,delivery_estimate_source='scraped',prime_eligible=False,
            observation_id=123,fingerprint='a'*64,commercial_capture_verified=True,
            stock_status='available',stock_evidence='In stock')

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def run_refresh(self):
        async def preview(db,listing):
            return self.source if listing.url==self.url else None
        with patch('app.services.commercial_reconciliation.source_preview',side_effect=preview), patch(
            'app.services.commercial_reconciliation.readiness_index',AsyncMock(return_value={'items':[]})):
            return await reconcile_commercial(self.db,trigger='disposable_test')

    async def test_refresh_retry_and_negative_stock_are_persisted(self):
        first=await self.run_refresh();second=await self.run_refresh()
        self.assertEqual(first['imported'],1)
        self.assertEqual(second['imported'],0)
        self.source.update(stock_status='unavailable',stock_evidence='Out of stock',
                           observed_at=datetime.now(timezone.utc).isoformat(),fingerprint='b'*64)
        third=await self.run_refresh()
        self.assertEqual(third['imported'],1)
        rows=(await self.db.execute(select(SupplierOfferEvidence).where(
            SupplierOfferEvidence.part_key==self.key).order_by(SupplierOfferEvidence.id))).scalars().all()
        self.assertEqual([row.stock_confirmed for row in rows],[True,True,False])
        self.assertFalse(third['prices_published'])

    async def test_failure_is_durable_and_source_writes_roll_back(self):
        with patch('app.services.commercial_reconciliation.readiness_index',AsyncMock(side_effect=RuntimeError('private detail'))):
            with self.assertRaises(RuntimeError):
                await reconcile_commercial(self.db,trigger='disposable_failure')
        audit=(await self.db.execute(select(PriceQuoteSnapshot).where(
            PriceQuoteSnapshot.product_key=='commercial:reconciliation').order_by(PriceQuoteSnapshot.id.desc()).limit(1))).scalar_one()
        self.assertEqual(audit.status,'reconcile_failed')
        self.assertEqual(audit.decision_json['error_type'],'RuntimeError')
        self.assertNotIn('private detail',str(audit.decision_json))

    async def test_additive_migration_round_trip_preserves_listing_rows(self):
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261013_0002_commercial_observation_provenance.py'
        spec=importlib.util.spec_from_file_location('commercial_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        async with fixtures.engine.begin() as connection:
            def migrate(sync):
                count=sync.scalar(text('SELECT count(*) FROM gem_radar_listing_observations'))
                with Operations.context(MigrationContext.configure(sync)):
                    module.downgrade();module.upgrade()
                self.assertEqual(sync.scalar(text('SELECT count(*) FROM gem_radar_listing_observations')),count)
            await connection.run_sync(migrate)
