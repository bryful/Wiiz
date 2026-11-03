from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_game_rules import verify
from game_rules import modify_ac, heal_hp, special_power_core


class GameRuleTests(unittest.TestCase):
    def test_rules_against_original_cpu_subroutines(self):
        found = 0
        for name in ('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES'):
            path = ROOT / '.nes' / name
            if not path.exists():
                continue
            with self.subTest(rom=name):
                report = verify(path.read_bytes())
                self.assertTrue(report['matched'])
                self.assertEqual(report['ac_cases'], 199 * 5)
                self.assertEqual(report['ac_spell_target_cases'], 10)
                self.assertEqual(report['healing_parameter_cases'], 3)
                self.assertGreater(report['special_power_body_cases'], 0)
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')

    def test_unverified_ranges_and_unknown_effects_are_rejected(self):
        with self.assertRaises(ValueError):
            modify_ac(100, -1)
        with self.assertRaises(ValueError):
            heal_hp(11, 10, 0, 1)
        with self.assertRaises(ValueError):
            special_power_core(bytes(128), dict(executable_core=False))
        with self.assertRaises(ValueError):
            special_power_core(bytes(128), dict(executable_core=True, kind='max_hp_increase', max_hp_offset=31))


if __name__ == '__main__':
    unittest.main()
