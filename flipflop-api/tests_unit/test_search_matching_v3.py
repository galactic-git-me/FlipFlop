"""Offline checks for incremental search capture, query and fallback changes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from app.gem_radar.product_identifiers import normalise_brand,title_part_numbers
from app.gem_radar.search_identity import search_result_identity,preferred_search_query,last_resort_title_key,unique_title_candidate

class SearchV3Checks(unittest.TestCase):
    def test_manufacturer_aliases(self):
        for a,b in [('Kingston Technology','KINGSTON'),('ASUSTeK Computer Inc.','ASUS'),('Micro-Star International','MSI'),('Western Digital','WD_BLACK')]:
            self.assertEqual(normalise_brand(a),normalise_brand(b))

    def test_additional_part_formats_preserve_variant_suffixes(self):
        for code in ['CC-H61FB-R1','ACFRE00124A','CP2K16G60C36U5B','PVV532G600C30K','LD5U16G60C26BR-RGD','SA400S37/480G','P210S256G25','PRIME-RTX5080-O16G-EVO']:
            self.assertEqual(title_part_numbers(code),{code})
        self.assertNotEqual(search_result_identity('NZXT H6 Flow CC-H61FB-R1','case')['cpk'],search_result_identity('NZXT H6 Flow CC-H61FB-01','case')['cpk'])

    def test_query_uses_evidenced_metadata_mpn_absent_from_title(self):
        identity=search_result_identity('1TB Kingston NV3 SSD','ssd',mpn='SNV3S/1000G')
        self.assertEqual(preferred_search_query('1TB Kingston NV3 SSD',identity['data'],'storage'),'kingston SNV3S/1000G')

    def test_cpu_suffixes_stay_distinct(self):
        self.assertNotEqual(last_resort_title_key('Intel Core i7 14700K Processor','cpu'),last_resort_title_key('Intel Core i7 14700KF Processor','cpu'))

    def test_same_ram_specs_with_different_word_order(self):
        a='Corsair Vengeance LPX 32GB (2x16GB) DDR4 3200MHz CL16 Black'
        b='CORSAIR Vengeance LPX Black DDR4 CL16 3200MHz 32GB (2 x 16GB)'
        self.assertEqual(last_resort_title_key(a,'ram'),last_resort_title_key(b,'ram'))
        self.assertNotEqual(last_resort_title_key(a,'ram'),last_resort_title_key(b.replace('Black','White'),'ram'))
        self.assertIsNone(last_resort_title_key('Corsair 32GB DDR4 RAM','ram'))

    def test_ssd_heatsink_variant_is_distinct(self):
        a='Samsung 990 PRO 2TB M.2 2280 SSD'
        self.assertNotEqual(last_resort_title_key(a,'ssd'),last_resort_title_key(a+' with heatsink','ssd'))

    def test_ram_rgb_and_sl_variants_are_distinct(self):
        a='Corsair Vengeance RGB PRO 32GB (2x16GB) DDR4 3200MHz CL16 Black'
        self.assertNotEqual(last_resort_title_key(a,'ram'),last_resort_title_key(a.replace('RGB PRO','RGB PRO SL'),'ram'))
        b='Patriot Viper Venom 32GB (2x16GB) DDR5 6000MHz CL30'
        self.assertNotEqual(last_resort_title_key(b,'ram'),last_resort_title_key(b+' RGB','ram'))

    def test_case_name_fallback_preserves_colour_and_rgb(self):
        a=search_result_identity('NZXT H6 Flow CC-H61FB-01','case')
        key=last_resort_title_key('NZXT H6 Flow CC-H61FB-01','case',a['data'])
        self.assertEqual(key,last_resort_title_key('Quick viewNZXT H6 Flow Black Compact Chassis','case'))
        self.assertNotEqual(key,last_resort_title_key('NZXT H6 Flow White Compact Chassis','case'))

    def test_known_mpn_source_alias_reuses_validated_cpu_identity(self):
        from app.gem_radar.cpk_pipeline import _valid_existing_cpk
        data=search_result_identity('AMD Ryzen 7 9800X3D 100-100001084WOF','cpu')['data']
        self.assertTrue(_valid_existing_cpk(data,'AMD Ryzen 7 9800X3D Processor'))
        self.assertFalse(_valid_existing_cpk(data,'AMD Ryzen 7 9700X Processor'))

    def test_title_fallback_refuses_distinct_evidenced_skus(self):
        a={'category':'cpu','brand':'amd','model':'ryzen-7-9800x3d','identity_claims':[{'kind':'mpn','value':'one'}]}
        b={**a,'identity_claims':[{'kind':'mpn','value':'two'}]}
        self.assertIsNone(unique_title_candidate('AMD Ryzen 7 9800X3D',[('one',a),('two',b)]))
        match=unique_title_candidate('AMD Ryzen 7 9800X3D',[('one',a)])
        self.assertEqual(match[0],'one');self.assertEqual(match[1]['identity_match_rule'],'title_product')

if __name__=='__main__':unittest.main()
