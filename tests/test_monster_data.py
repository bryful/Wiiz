from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from monster_data import bcd, decode_japanese, dice, read_monster
from verify_monster_data import verify


class MonsterDataTests(unittest.TestCase):
    def test_compound_kana_and_custom_hiragana(self):
        self.assertEqual(decode_japanese([0x51, 0x37, 0x53, 0x37, 0x5f, 0x35], 'wiz1'), 'バブリー')
        self.assertEqual(decode_japanese([0xea, 0x96, 0x92, 0x9f, 0x93], 'wiz3'), 'はかいそう')
        self.assertEqual(decode_japanese([0xb6, 0xde], 'wiz2'), 'ガ')

    def test_bcd_is_not_binary_and_rejects_invalid_digits(self):
        self.assertEqual(bcd(bytes.fromhex('012345')), 12345)
        with self.assertRaises(ValueError):
            bcd(bytes.fromhex('00fa00'))

    def test_zero_sided_special_is_not_given_a_fabricated_range(self):
        special = dice(bytes([1, 0, 1]))
        self.assertIsNone(special['minimum'])
        self.assertIsNone(special['maximum'])

    def test_all_records_against_rom_loaders_in_both_languages(self):
        paths = [ROOT / '.nes' / name for name in ('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES')]
        found = 0
        for path in paths:
            if not path.is_file():
                continue
            with self.subTest(rom=path.name):
                rom = path.read_bytes()
                report = verify(rom)
                self.assertTrue(report['matched'])
                self.assertEqual(report['loader_cases'], report['monster_count'] * 2)
                for monster_id in range(report['monster_count']):
                    data = read_monster(rom, monster_id)
                    self.assertNotIn('{', data['name_ja'])
                    self.assertNotIn('{', data['unknown_name_ja'])
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')

    @unittest.skipUnless((ROOT / '.nes/WIZ2.NES').is_file(), 'Requires Wiz2 ROM')
    def test_hydra_preserves_all_seven_attacks(self):
        monster = read_monster((ROOT / '.nes/WIZ2.NES').read_bytes(), 71)
        self.assertEqual(monster['stats']['attack_count'], 7)
        self.assertEqual(len(monster['stats']['attacks']), 7)
        self.assertEqual(monster['stats']['ac'], -1)


if __name__ == '__main__':
    unittest.main()
