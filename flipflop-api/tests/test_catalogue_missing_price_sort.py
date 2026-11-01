from types import SimpleNamespace as NS
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

class CatalogueMissingPriceTests(IsolatedAsyncioTestCase):
    async def test_equal_rank_candidates_with_missing_price_do_not_crash(self):
        from app.services.playbook_service import _catalogue_candidates
        slot=NS(slot_type='gpu')
        rows=[(NS(status='active',id=i),NS(price=price,raw_specs={'bestseller':{'rank':1}},title='placeholder'),slot)
              for i,price in enumerate((99.0,None,0.0),1)]
        result=Mock();result.all.return_value=rows
        boards=Mock();boards.scalars.return_value.all.return_value=[]
        db=AsyncMock();db.execute.side_effect=[result,boards]
        with patch('app.services.playbook_stored_offers.stored_offers',AsyncMock(return_value={})), \
             patch('app.services.playbook_service._plausible_role_candidate',return_value=False), \
             patch('app.services.shared_variant_assets.final_assets_by_variant',AsyncMock(return_value={})):
            self.assertEqual(await _catalogue_candidates(db,1,'curated'),[])
