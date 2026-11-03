from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from dungeon_data import read_dungeons, DIRECTIONS
from dungeon_viewer import floor_svg
from verify_dungeons import verify


class DungeonTests(unittest.TestCase):
    def test_all_cells_against_original_rom_readers(self):
        found = 0
        for name in ('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES'):
            path = ROOT / '.nes' / name
            if not path.is_file():
                continue
            with self.subTest(rom=name):
                rom = path.read_bytes()
                data = read_dungeons(rom)
                report = verify(rom)
                self.assertTrue(report['matched'])
                self.assertEqual(report['cells'], data['floor_count'] * 400)
                for floor in data['floors']:
                    self.assertEqual(len(floor['cells']), 400)
                    for cell in floor['cells']:
                        self.assertEqual(sum(cell['edges'][direction] << (i * 2) for i, direction in enumerate(DIRECTIONS)), cell['walls_raw'])
                    ET.fromstring(floor_svg(floor))
                origin = data['floors'][0]['cells'][0]
                self.assertEqual(origin['edges'], dict(north=0, east=0, south=1, west=1))
                self.assertEqual(origin['event']['kind'], 'stairs')
                self.assertEqual(origin['event']['destination']['floor'], 0)
                found += 1
        if not found:
            self.skipTest('Requires user-supplied ROMs')

    @unittest.skipUnless((ROOT / '.nes/wiz1.nes').is_file(), 'Requires Wiz1 ROM')
    def test_direction_masks_match_rom_and_one_way_edges_are_preserved(self):
        rom = (ROOT / '.nes/wiz1.nes').read_bytes()
        self.assertEqual(rom[0x1d44e:0x1d452], bytes([3, 12, 48, 192]))
        data = read_dungeons(rom)
        self.assertGreater(sum(len(f['asymmetric_edges']) for f in data['floors']), 0)


if __name__ == '__main__':
    unittest.main()
