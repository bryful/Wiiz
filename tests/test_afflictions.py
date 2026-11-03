from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from affliction_rules import saving_threshold, resisted, inflict
from verify_afflictions import verify


class AfflictionTests(unittest.TestCase):
    def test_original_threshold_resistance_and_target_bodies(self):
        found = 0
        for name in ('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES'):
            path = ROOT / '.nes' / name
            if not path.exists():
                continue
            with self.subTest(rom=name):
                report = verify(path.read_bytes())
                self.assertTrue(report['matched'])
                self.assertEqual(report['resistance_cases'], 65536)
                self.assertEqual(report['target_effect_cases'], 5760)
                self.assertEqual(report['group_cases'], 6)
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')

    def test_resistance_ff_and_skipped_targets_keep_distinct_semantics(self):
        self.assertFalse(resisted('wiz1', 255, 255))
        self.assertTrue(resisted('wiz2', 255, 255))
        state = dict(status=1, action_raw=18, aux_action_raw=52, silence=7)
        result = inflict('wiz3', 'KATINO', state, 1, 1, 0, 255, 255)
        self.assertEqual(result['state'], state)
        self.assertEqual(result['rng_calls'], 0)
        self.assertEqual(result['rng'], dict(counter=255, accumulator=255))

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            saving_threshold('wiz2', 50, -1, 1)
        with self.assertRaises(ValueError):
            resisted('wiz3', 256, 0)
        with self.assertRaises(ValueError):
            inflict('wiz3', 'KATINO', dict(status=1, action_raw=0, aux_action_raw=0, silence=0), 1, 1, 256, 0, 0)


if __name__ == '__main__':
    unittest.main()
