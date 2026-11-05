"""Focused offline identity regressions: no database or provider calls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from app.gem_radar.product_identifiers import normalise_gtin, normalise_mpn, identity_conflicts
from app.gem_radar.cpk_pipeline import _valid_existing_cpk
from app.services.playbook_stored_offers import product_keys, same_product
from app.gem_radar.product_identity_registry import identifier_claims
from app.gem_radar.search_identity import last_resort_title_key

class IdentityChecks(unittest.TestCase):
    def test_claims_are_identifier_based_and_namespaced(self):
        claims=identifier_claims(title='Kingston NV3 1TB SNV3S/1000G',gtin='740617344790',
            source_url='https://www.amazon.co.uk/dp/B0DBR3DZWG')
        self.assertIn({'kind':'gtin','namespace':'gs1','value':'00740617344790'},claims)
        self.assertIn({'kind':'mpn','namespace':'kingston','value':'SNV3S/1000G'},claims)
        self.assertIn({'kind':'asin','namespace':'amazon.co.uk','value':'B0DBR3DZWG'},claims)
        self.assertEqual(identifier_claims(title='unknown part',source_url='https://vendor.example/B0DBR3DZWG'),[])

    def test_upc_ean_equivalence_and_checksum(self):
        self.assertEqual(normalise_gtin('740617344790'), '00740617344790')
        self.assertEqual(normalise_gtin('0740617344790'), '00740617344790')
        for value in ['740617344791','0000000000000','74061734479','N/A']:
            self.assertIsNone(normalise_gtin(value))

    def test_mpn_keeps_meaningful_variant_suffixes(self):
        self.assertEqual(normalise_mpn(' snv3s/1000g '),'SNV3S/1000G')
        self.assertNotEqual(normalise_mpn('SNV3S/1000G'),normalise_mpn('SNV3SM3/1T0'))

    def test_vendor_product_ids_are_namespaced_and_distinct_from_listing_ids(self):
        claims=identifier_claims(title='Intel Core i5-12400F',category='cpu',
            vendor_product_id='scan-LN12345',source_url='https://www.scan.co.uk/products/item')
        self.assertIn({'kind':'vendor_product_id','namespace':'scan.co.uk','value':'scan-LN12345'},claims)

    def test_epid_and_model_number_are_registered_aliases(self):
        claims=identifier_claims(title='AMD Ryzen 7 7800X3D',category='cpu',brand='AMD',
            model_number='100-100000910WOF',epid='123456789')
        self.assertIn({'kind':'model_number','namespace':'amd','value':'100-100000910WOF'},claims)
        self.assertIn({'kind':'epid','namespace':'ebay','value':'123456789'},claims)

    def test_asin_only_fallback_does_not_register_ambiguous_title_aliases(self):
        claims=identifier_claims(title='AMD Ryzen 7 7800X3D Processor',category='cpu',
            source_url='https://www.amazon.co.uk/dp/B0ABCDE123',
            include_title_alias=False,include_manufacturer_part=False)
        self.assertEqual(claims,[{'kind':'asin','namespace':'amazon.co.uk','value':'B0ABCDE123'}])

    def test_gpu_title_key_requires_partner_and_memory_tier(self):
        self.assertIsNone(last_resort_title_key('ASUS GeForce RTX 4070 12GB', 'gpu'))
        self.assertIsNone(last_resort_title_key('ASUS TUF RTX 4070 12GB', 'gpu'))
        self.assertEqual(last_resort_title_key('ASUS DUAL-RTX4070-O12G', 'gpu'),
                         ('title_product','gpu','asus','DUAL-RTX4070-O12G'))
        self.assertIsNone(last_resort_title_key('GeForce RTX 4070', 'gpu'))

    def test_real_wrong_ram_metadata_is_not_reused(self):
        title='Corsair VENGEANCE LPX DDR4 RAM 32GB (2x16GB) 3200MHz'
        data={'category':'ram','brand':'corsair','model':'vengeance-lpx',
              'specs':{'capacity_gb':8,'speed_mhz':3600,'type':'ddr4'}}
        self.assertFalse(_valid_existing_cpk(data,title))

    def test_wrong_manufacturer_is_not_reused(self):
        self.assertFalse(_valid_existing_cpk({'category':'psu','brand':'kolink','model':'power-supply'},
            'Lian Li RS 1200W RS Hub ATX Power Supply'))

    def test_exact_kingston_mpn_bridges_title_and_cpk_variation(self):
        amazon='Kingston NV3 NVMe PCIe 4.0 Internal SSD 1TB M.2 2280-SNV3S/1000G'
        ocuk='Kingston NV3 1TB PCI-e 4.0 NVMe M.2 Solid State Drive (SNV3S/1000G)'
        part={'role':'storage','title':amazon,'cpk':'171817f97851df4f'}
        other={'title':ocuk,'cpk':'39f5e120c5269634'}
        self.assertTrue(set(product_keys('storage',amazon)) & set(product_keys('storage',ocuk)))
        self.assertTrue(same_product(part,other))

    def test_same_bad_cpk_cannot_merge_different_manufacturer_parts(self):
        a={'role':'storage','title':'Samsung 990 PRO 2TB MZ-V9P2T0BW','cpk':'bad',
           'cpk_data':{'category':'ssd','brand':'samsung','model':'990-pro-2tb'}}
        b={'title':'Samsung 990 PRO 2TB MZ-V9P2T0CW','cpk':'bad',
           'cpk_data':{'category':'ssd','brand':'samsung','model':'990-pro-2tb'}}
        self.assertFalse(same_product(a,b))

    def test_family_only_alias_cannot_merge_specific_memory_kit(self):
        self.assertFalse(_valid_existing_cpk({'category':'ram','brand':'corsair','model':'vengeance-lpx'},
            'Corsair Vengeance LPX 32GB (2x16GB) DDR4 3200MHz'))

    def test_ram_kit_configurations_conflict(self):
        conflicts=identity_conflicts('Corsair Vengeance LPX 32GB (4x8GB) DDR4 3200MHz',
            {'category':'ram','brand':'corsair','model':'vengeance-lpx-32gb-2x16gb-ddr4-3200mhz'})
        self.assertIn('modules',conflicts)

if __name__=='__main__':unittest.main()
