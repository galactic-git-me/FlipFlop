"""Offline registry decision checks; SQL is faked, not integration-tested."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import AsyncMock
from app.gem_radar.product_identity_registry import resolve_identifiers

class Rows:
    def __init__(self,rows): self.rows=rows
    def mappings(self): return self
    def all(self): return self.rows

class RegistryDecisions(unittest.IsolatedAsyncioTestCase):
    def database(self,*rows):
        db=AsyncMock()
        db.info={'component_identity_registry_available':True}
        db.execute.side_effect=[Rows(value) for value in rows]
        return db

    async def test_conflicting_source_part_number_cannot_fall_through(self):
        db=self.database()
        result=await resolve_identifiers(db,title='Samsung 990 PRO MZ-V9P2T0BW',mpn='MZ-V9P2T0CW')
        self.assertEqual(result['status'],'conflict')
        db.execute.assert_not_awaited()

    async def test_shadow_unknown_identity_does_not_allocate_or_write(self):
        db=self.database([])
        result=await resolve_identifiers(db,title='Kingston NV3 SNV3S/1000G',category='ssd',persist=False)
        self.assertEqual(result['status'],'proposed_new')
        self.assertNotIn('cpk',result)
        self.assertEqual(db.execute.await_count,1)
        self.assertTrue(str(db.execute.await_args.args[0]).lstrip().startswith('SELECT'))

    async def test_two_existing_identities_are_not_silently_merged(self):
        db=self.database([{'cpk':'one'},{'cpk':'two'}])
        result=await resolve_identifiers(db,title='Kingston NV3 SNV3S/1000G',persist=False)
        self.assertEqual(result['status'],'conflict')
        self.assertEqual(result['cpks'],['one','two'])

    async def test_exact_identifier_reuses_stable_product(self):
        data={'category':'ssd','brand':'kingston','model':'SNV3S/1000G',
              'variant_facts':{'capacity_gb':1000,'form_factor':'2280'}}
        db=self.database([{'cpk':'stable','identity':data,'kind':'mpn'}],
                         [{'kind':'mpn','namespace':'kingston','value':'SNV3S/1000G'}])
        result=await resolve_identifiers(db,title='Kingston NV3 1TB 2280 SNV3S/1000G',category='ssd',persist=False)
        self.assertEqual(result['status'],'matched')
        self.assertEqual(result['cpk'],'stable')
        self.assertEqual(result['data']['identity_match_rule'],'mpn')

if __name__=='__main__':unittest.main()
