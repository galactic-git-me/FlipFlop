"""Retailer CAS labels retain exact RAM requirements without inferring SKU facts."""
import unittest
from app.services.playbook_service import _ram_layout_facts
from app.services.playbook_requirement_catalogue import matches_requirement

TITLE = 'Corsair Vengeance EXPO/XMP 64GB (2X32GB) DDR5 PC5-48000C30 6000MHz Dual Channel'
REQUIREMENT = '64GB (2x32GB) DDR5-6000 CL30'


class RamCasLabelTests(unittest.TestCase):
    def test_explicit_pc_bandwidth_suffix_is_a_cas_label(self):
        self.assertEqual(_ram_layout_facts(TITLE)['cas_latency'], 30)
        self.assertTrue(matches_requirement('ram', TITLE, REQUIREMENT))

    def test_explicit_standalone_c_label_is_supported(self):
        title = 'Corsair Vengeance 64GB (2x32GB) DDR5 C30 6000MHz Dual Channel Kit'
        self.assertEqual(_ram_layout_facts(title)['cas_latency'], 30)
        self.assertTrue(matches_requirement('ram', title, REQUIREMENT))

    def test_slower_latency_and_wrong_capacity_remain_ineligible(self):
        self.assertFalse(matches_requirement('ram', TITLE, REQUIREMENT.replace('CL30', 'CL28')))
        self.assertFalse(matches_requirement('ram', TITLE.replace('64GB (2X32GB)', '32GB (2X16GB)'), REQUIREMENT))

    def test_sku_digits_alone_do_not_establish_latency(self):
        title = 'Corsair 64GB (2x32GB) DDR5 6000MHz CMK64GX5M2B6000C30'
        self.assertIsNone(_ram_layout_facts(title)['cas_latency'])
        self.assertFalse(matches_requirement('ram', title, REQUIREMENT))

    def test_explicit_slower_cl_specification_keeps_precedence(self):
        self.assertEqual(_ram_layout_facts(TITLE+' CL36')['cas_latency'], 36)
        self.assertFalse(matches_requirement('ram', TITLE+' CL36', REQUIREMENT))


if __name__ == '__main__':
    unittest.main()
