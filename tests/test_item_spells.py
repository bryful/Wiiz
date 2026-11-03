from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from item_spell_data import extract_data
from verify_item_spells import verify


class ItemSpellTests(unittest.TestCase):
    def test_original_routines_and_cross_game_layout_differences(self):
        found = 0
        for name, item_count, spell_count in [('wiz1.nes', 101, 50), ('WIZ2.NES', 110, 50), ('WIZ3.NES', 138, 53)]:
            path = ROOT / '.nes' / name
            if not path.exists():
                continue
            with self.subTest(rom=name):
                rom = path.read_bytes()
                self.assertTrue(verify(rom)['matched'])
                data = extract_data(rom)
                self.assertEqual(len(data['items']), item_count)
                self.assertEqual(len(data['spells']), spell_count)
                muramasa = next(r for r in data['items'] if r['name_en'].upper() == 'MURAMASA BLADE')
                self.assertEqual(muramasa['stats']['damage'], dict(count=10, sides=5, bonus=0))
                self.assertEqual(muramasa['stats']['equip_mask'], 32)
                armor = next(r for r in data['items'] if r['name_en'].upper() == 'BREAST PLATE')
                self.assertLess(armor['stats']['ac_modifier'], 0)
                halito = data['spells'][0]
                self.assertEqual(halito['name_ja'], 'ハリト')
                self.assertEqual(halito['effect']['damage'], dict(count=1, sides=8))
                for r in data['items']:
                    self.assertNotIn('{', r['name_en'])
                    self.assertNotIn('{', r['name_ja'])
                if data['game'] == 'wiz3':
                    melito = data['spells'][6]
                    self.assertEqual((melito['name_en'], melito['level']), ('Melito', 2))
                    self.assertEqual(data['spells'][24]['school'], 'priest')
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')


if __name__ == '__main__':
    unittest.main()
