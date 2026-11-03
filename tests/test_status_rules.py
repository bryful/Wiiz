from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_status_rules import verify
from status_rules import display_status_index, resurrect
from game_rng import scaled_roll


class StatusRuleTests(unittest.TestCase):
    def test_original_display_cures_resurrection_and_rng(self):
        found = 0
        for name in ('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES'):
            path = ROOT / '.nes' / name
            if not path.exists():
                continue
            with self.subTest(rom=name):
                report = verify(path.read_bytes())
                self.assertTrue(report['matched'])
                self.assertEqual(report['rng_byte_cases'], 65536)
                self.assertEqual(report['cure_cases'], 432)
                self.assertGreater(report['resurrection_cases'], 8000)
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')

    def test_scaling_preserves_wiz1_byte_carry_behavior(self):
        self.assertEqual(scaled_roll('wiz1', 17, 255, 255)['value'], 14)
        self.assertEqual(scaled_roll('wiz2', 17, 255, 255)['value'], 15)

    def test_poison_is_an_overlay_and_invalid_states_are_rejected(self):
        self.assertEqual(display_status_index(0, 1), 8)
        self.assertEqual(display_status_index(3, 1), 3)
        with self.assertRaises(ValueError):
            display_status_index(8, 0)
        with self.assertRaises(ValueError):
            resurrect('wiz2', 'DI', dict(status=5, poison=0, hp=1, max_hp=10, vitality=18), 0, 0)


if __name__ == '__main__':
    unittest.main()
