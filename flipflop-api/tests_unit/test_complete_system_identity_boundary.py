"""Real scraped titles: whole PCs must not link to component price cohorts."""
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.gem_radar.identity import is_full_system_listing
from app.gem_radar import cpk_pipeline
from app.services.playbook_stored_offers import product_keys, recorded_offer

COMPONENTS = [
 'KingSpec 2TB NVMe SSD PCIe Gen4 x4 M.2 2280 Internal Solid State Drive for PS5 Gaming PC Laptop',
 'Lexar NM610PRO SSD 1TB Internal M.2 PCIe NVMe Flash Drive for Notebook Desktop PC',
 'Valkyrie V240 Lite ARGB All-in-One AIO CPU Liquid Cooler White',
 'PCZZOI ATX Mid Tower PC Gaming Case Wood Walnut front Black',
 'Akasa Evo Blue AK-922 CPU Cooler Intel LGA775 Vintage Retro Gaming PC',
 'Asus TUF Gaming A15 FA506ICB AMD Ryzen 5 Motherboard DANJIMB18A0',
 'Microsoft Windows 11 Pro OEM Licence Key',
 'Intel Core i5 6600T Processor CPU LGA1151 Socket SR2L9 2.70GHz Quad Desktop Pc',
 'ARCTIC Liquid Freezer II 360 Multi Compatible All-in-One CPU Water Cooler',
 'Lian Li Lancool 207 Digital Tempered Glass Mid Tower PC ATX Case Black',
 'iONZ Gaming PC Computer Mini Tower Case M/ATX Tempered Glass',
 'I7 Mid Tower Case Black Tempered Glass USB Audio Gaming Pc',
]
SYSTEMS = [
 'AWD-IT Astraeus AMD Ryzen 5 Radeon RX 9070 GRE 16GB RAM 1TB SSD Windows 11 Prebuilt Gaming PC',
 'AWD-IT Hecate AMD Ryzen 5 NVIDIA RTX 5050 16GB RAM 512GB SSD Windows 11 Prebuilt Gaming PC',
 'FAST OFFICE PC Enterprise Edition AMD Ryzen 5 32GB RAM 1TB NVMe W11 Pro',
 'ASUS TUF Gaming A16 NVIDIA RTX 5050 16GB 16 WUXGA 165Hz AMD Ryzen 7 260 Gaming L',
 'HP Pavilion Desktop Computer Intel Core i5 16GB RAM 512GB SSD',
]

class BoundaryChecks(unittest.TestCase):
 def test_components_are_not_systems(self):
  for title in COMPONENTS:
   with self.subTest(title=title):self.assertFalse(is_full_system_listing(title))
 def test_systems_are_rejected(self):
  for title in SYSTEMS:
   with self.subTest(title=title):self.assertTrue(is_full_system_listing(title))
 def test_full_pc_has_no_supplier_component_keys(self):
  self.assertEqual(product_keys('cpu',SYSTEMS[0]),[])
 def test_full_pc_never_becomes_a_component_supplier_offer(self):
  self.assertIsNone(recorded_offer({'title':SYSTEMS[0]}))

class IngestionChecks(unittest.IsolatedAsyncioTestCase):
 async def test_rejected_system_clears_stale_identity_and_price(self):
  db=AsyncMock()
  with patch.object(cpk_pipeline,'remove_listing_price',new_callable=AsyncMock) as remove:
   result=await cpk_pipeline.assign_cpk_and_accumulate_price(db,'fixture',SYSTEMS[0],'cpu','new',999)
   self.assertIsNone(result)
   remove.assert_awaited_once_with(db,'fixture')
  statements=[str(call.args[0]) for call in db.execute.await_args_list]
  self.assertTrue(any('DELETE FROM gem_radar_listing_cpk' in sql for sql in statements))
  self.assertTrue(any('UPDATE gem_radar_scored_listings' in sql for sql in statements))

if __name__=='__main__':unittest.main()
