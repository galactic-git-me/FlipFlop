"""Exact MSI radio facts may satisfy connectivity without an unnecessary adapter."""
import unittest
from app.services.playbook_component_facts import manufacturer_facts, resolve_primary_engineering
from app.services.playbook_planning_checks import wireless_extra_required

TITLE = 'MSI B850 GAMING PLUS WIFI6E Motherboard, ATX - Supports AMD Ryzen 9000/8000/7000'
SOURCE = 'https://www.msi.com/Motherboard/B850-GAMING-PLUS-WIFI6E/Specification'


class MsiRadioReferenceTests(unittest.TestCase):
    def test_exact_board_uses_official_socket_memory_form_factor_and_radios(self):
        facts = manufacturer_facts('motherboard', TITLE)
        self.assertEqual(facts.get('source_url'), SOURCE)
        self.assertEqual(facts['socket'], 'am5')
        self.assertEqual(facts['ram_type'], 'ddr5')
        self.assertEqual(facts['form_factor'], 'atx')
        self.assertEqual(facts['ram_slots'], 4)
        self.assertEqual(facts['m2_slots'], 2)
        self.assertTrue(facts['wifi'])
        self.assertTrue(facts['bluetooth'])
        part = {'role': 'motherboard', 'title': TITLE, 'engineering': {}}
        resolved = resolve_primary_engineering(part)
        self.assertTrue(resolved['reviewed'])
        self.assertEqual(resolved['engineering_reference'], SOURCE)
        self.assertEqual(wireless_extra_required({**part, 'engineering': resolved}), [])

    def test_similarly_named_boards_do_not_inherit_the_reference(self):
        for title in ('MSI B850M GAMING PLUS WIFI6E Motherboard',
                      'MSI B850 GAMING PLUS WIFI Motherboard',
                      'MSI B850 GAMING PLUS MAX WIFI Motherboard'):
            with self.subTest(title=title):
                self.assertNotEqual(manufacturer_facts('motherboard', title).get('source_url'), SOURCE)

    def test_conflicting_human_review_requires_review_instead_of_being_overwritten(self):
        part = {'role': 'motherboard', 'title': TITLE, 'engineering': {
            'wifi': False, 'reviewed': True, 'reviewed_by': 'owner'}}
        resolved = resolve_primary_engineering(part)
        self.assertFalse(resolved['reviewed'])
        self.assertFalse(resolved['wifi'])
        self.assertIn('wifi', resolved['reference_conflicts'])


if __name__ == '__main__':
    unittest.main()
