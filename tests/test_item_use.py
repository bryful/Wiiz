from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_item_use import verify
from item_use_rules import replacement, resolve_sp


class ItemUseTests(unittest.TestCase):
    def test_original_rng_replacement_class_gates_and_sp_continuations(self):
        found = 0
        for name, count in [('wiz1.nes', 101), ('WIZ2.NES', 110), ('WIZ3.NES', 138)]:
            path = ROOT / '.nes' / name
            if not path.exists():
                continue
            with self.subTest(rom=name):
                report = verify(path.read_bytes())
                self.assertTrue(report['matched'])
                self.assertEqual(report['normal_replacement_cases'], count * 256 * 3)
                self.assertGreater(report['confirmed_sp_transition_cases'], 0)
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')

    def test_missing_rng_and_mismatched_slot_are_rejected(self):
        item = dict(id=1, stats=dict(break_raw=128, replacement_item_id=0,
                                    special_power_raw=1, equip_mask=255), special_power=dict(executable_core=False))
        with self.assertRaises(ValueError):
            replacement('wiz2', item, 0, None)
        character = bytearray(128)
        with self.assertRaises(ValueError):
            resolve_sp('wiz2', character, item, roll=0)
        character[0x4b] = 1
        with self.assertRaises(ValueError):
            resolve_sp('wiz2', character, item, roll=0)
        self.assertEqual(character[0x4b], 1)


if __name__ == '__main__':
    unittest.main()
