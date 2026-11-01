"""New offline checks for the agreed search-results-only matching policy."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import AsyncMock
from app.gem_radar.search_identity import search_result_identity
from app.gem_radar.product_identity_registry import resolve_identifiers

class SearchPolicyChecks(unittest.IsolatedAsyncioTestCase):
    def test_same_exact_part_across_titles_and_sources(self):
        a=search_result_identity('Kingston NV3 1TB M.2 2280 SNV3S/1000G','ssd')
        b=search_result_identity('1TB Kingston NV3 PCIe 4 NVMe SSD','ssd',mpn='SNV3S/1000G')
        self.assertEqual(a['cpk'],b['cpk'])
        self.assertEqual(a['data']['identity_match_rule'],'manufacturer_mpn')

    def test_kingston_ram_capacity_suffix_is_preserved(self):
        a=search_result_identity('Kingston Fury 16GB DDR5 KF556C40BB-16','ram')
        b=search_result_identity('Kingston Fury 32GB DDR5 KF556C40BB-32','ram')
        self.assertNotEqual(a['cpk'],b['cpk'])
        self.assertTrue(a['data']['model'].endswith('-16'))

    def test_aftermarket_part_suffix_is_preserved(self):
        a=search_result_identity('Crucial P1 500GB CT500P1SSD8','ssd')
        b=search_result_identity('Crucial compatible P1 512GB CT500P1SSD8-OS','ssd')
        self.assertNotEqual(a['cpk'],b['cpk'])

    def test_conflicting_memory_quantity_is_not_merged(self):
        result=search_result_identity('Corsair LPX 16GB (1x16GB) DDR4 CMK32GX4M2B3200C16','ram')
        self.assertEqual(result['status'],'conflict')

    def test_retailer_sku_or_barcode_is_not_promoted_to_mpn(self):
        for bad in ['STO-KNG-02942','LN151058','740617344790']:
            self.assertIsNone(search_result_identity('Kingston NV3 1TB','ssd',mpn=bad))

    def test_missing_mpn_leaves_title_resolution_to_last_resort(self):
        self.assertIsNone(search_result_identity('Samsung 990 PRO 2TB','ssd'))

    def test_complete_build_does_not_inherit_component_identity(self):
        self.assertIsNone(search_result_identity('Gaming PC Ryzen 5 RTX 3060 16GB 1TB SNV3S/1000G','ssd'))

    async def test_mpn_works_without_optional_registry_migration(self):
        db=AsyncMock();db.info={'component_identity_registry_available':False}
        from unittest.mock import MagicMock
        result_rows=MagicMock();result_rows.scalars.return_value.all.return_value=[]
        db.execute.return_value=result_rows
        result=await resolve_identifiers(db,title='Kingston NV3 1TB SNV3S/1000G',category='ssd')
        self.assertEqual(result['status'],'matched')
        self.assertEqual(result['data']['identity_match_rule'],'manufacturer_mpn')
        self.assertEqual(db.execute.await_count,1)

if __name__=='__main__':unittest.main()
