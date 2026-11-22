"""Import persistence checks, using only the guarded disposable DB fixture."""
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from uuid import uuid4
from sqlalchemy import select
from app.api.commercial_readiness import store_reviewed_sources
from app.database import AsyncSessionLocal
from app.models.commerce_evidence import SupplierOfferEvidence


class ReadinessPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncSessionLocal()
        self.key = f'readiness:{uuid4().hex}'
        self.pending = [{
            'part_key': self.key, 'supplier': 'amazon', 'channel': 'retail', 'condition': 'new',
            'item_gbp': Decimal('123.45'), 'delivery_gbp': Decimal('0.00'),
            'fees_gbp': Decimal('0.00'), 'risk_gbp': Decimal('0.00'),
            'supplier_confidence': Decimal('0.9000'), 'stock_confirmed': True,
            'observed_at': datetime.now(timezone.utc), 'delivery_working_days': 2,
            'delivery_estimate_source': 'scraped', 'prime_eligible': False,
            'evidence_ref': 'https://www.amazon.co.uk/dp/READINESS',
            'evidence_source': 'catalogue_import:123:aaaaaaaaaaaaaaaa',
        }]

    async def asyncTearDown(self):
        await self.db.close()

    async def test_retry_reuses_evidence_and_preserves_source_time(self):
        first = await store_reviewed_sources(self.db, self.pending, 0)
        await self.db.commit()
        second = await store_reviewed_sources(self.db, self.pending, 0)
        await self.db.commit()
        self.assertEqual((len(first[0]), len(second[1])), (1, 1))
        rows = (await self.db.execute(select(SupplierOfferEvidence).where(SupplierOfferEvidence.part_key == self.key))).scalars().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].observed_at, self.pending[0]['observed_at'])
        self.assertEqual(str(rows[0].item_gbp), '123.45')
