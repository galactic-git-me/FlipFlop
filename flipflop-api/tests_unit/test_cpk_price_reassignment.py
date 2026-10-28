"""Offline transaction orchestration checks; no database connections."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import AsyncMock, patch
from app.gem_radar.cpk_market import upsert_listing_price, remove_listing_price

class PriceReassignmentChecks(unittest.IsolatedAsyncioTestCase):
    async def test_reassignment_repairs_old_and_new_product(self):
        db=AsyncMock()
        db.execute.return_value.scalar=lambda: 'old-product'
        with patch('app.gem_radar.cpk_market.recompute_market_price',new_callable=AsyncMock) as recalc:
            await upsert_listing_price(db,'new-product','listing',79.99,category='ssd')
        self.assertEqual([call.args[1] for call in recalc.await_args_list],['new-product','old-product'])
        self.assertEqual(db.execute.await_count,3)
        self.assertFalse(db.commit.called)

    async def test_same_product_recomputed_once(self):
        db=AsyncMock()
        db.execute.return_value.scalar=lambda: 'same'
        with patch('app.gem_radar.cpk_market.recompute_market_price',new_callable=AsyncMock) as recalc:
            await upsert_listing_price(db,'same','listing',79.99)
        self.assertEqual(recalc.await_count,1)

    async def test_quarantine_repairs_removed_contribution(self):
        db=AsyncMock()
        db.execute.return_value.scalar=lambda: 'old-product'
        with patch('app.gem_radar.cpk_market.recompute_market_price',new_callable=AsyncMock) as recalc:
            await remove_listing_price(db,'listing')
        recalc.assert_awaited_once_with(db,'old-product')
        self.assertIn('RETURNING cpk',str(db.execute.await_args.args[0]))
        self.assertFalse(db.commit.called)

    async def test_missing_contribution_needs_no_recalculation(self):
        db=AsyncMock()
        db.execute.return_value.scalar=lambda: None
        with patch('app.gem_radar.cpk_market.recompute_market_price',new_callable=AsyncMock) as recalc:
            await remove_listing_price(db,'listing')
        recalc.assert_not_awaited()

if __name__=='__main__': unittest.main()
