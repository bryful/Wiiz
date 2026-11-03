import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROM = next((p for p in (ROOT / '.nes' / 'wiz1.nes', ROOT / 'wiz1.nes') if p.is_file()), ROOT / '.nes' / 'wiz1.nes')
sys.path.insert(0, str(ROOT / 'tools'))
from extract_monsters import SUPPORTED_SHA256
from verify_monsters import verify
from rom_profiles import profile_for


class MonsterExtractionTests(unittest.TestCase):
    @unittest.skipUnless(ROM.is_file(), 'Requires user-supplied wiz1.nes')
    def test_all_layouts_against_original_cpu_routine(self):
        rom = ROM.read_bytes()
        if hashlib.sha256(rom).hexdigest() != SUPPORTED_SHA256:
            self.skipTest('ROM revision has not been validated')
        report = verify(rom)
        self.assertEqual(report['checked_variants'], 202)
        self.assertTrue(report['matched'])

    def test_later_roms_against_original_cpu_routines(self):
        found = 0
        for name in ('WIZ2.NES', 'WIZ3.NES'):
            path = ROOT / '.nes' / name
            if not path.is_file():
                continue
            with self.subTest(rom=name):
                rom = path.read_bytes()
                profile = profile_for(rom)
                report = verify(rom)
                self.assertEqual(report['checked_variants'], profile['count'] * 2)
                self.assertTrue(report['matched'])
                found += 1
        if not found:
            self.skipTest('Requires user-supplied Wiz2/Wiz3 ROMs')


if __name__ == '__main__':
    unittest.main()
