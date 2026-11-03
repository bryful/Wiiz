import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from trace_graphics import Bus


class MappingTests(unittest.TestCase):
    def setUp(self):
        header = b'NES\x1a' + bytes([8, 16, 16, 0]) + bytes(8)
        self.bus = Bus(header + b''.join(bytes([i]) * 16384 for i in range(8))
                       + b''.join(bytes([i]) * 4096 for i in range(32)))
        self.bus.cpu = type('Clock', (), {'processorCycles': 0, 'pc': 0})()

    def write_register(self, addr, value):
        for bit in range(5):
            self.bus.cpu.processorCycles += 3
            self.bus[addr] = (value >> bit) & 1

    def test_serial_prg_switch_and_fixed_bank(self):
        self.write_register(0xe000, 3)
        self.assertEqual(self.bus[0x8000], 3)
        self.assertEqual(self.bus[0xc000], 7)

    def test_chr_4k_and_8k_modes(self):
        self.write_register(0x8000, 28)
        self.write_register(0xa000, 7)
        self.write_register(0xc000, 12)
        self.assertEqual((self.bus.ppu_read(0), self.bus.ppu_read(4096)), (7, 12))
        self.write_register(0x8000, 12)
        self.assertEqual((self.bus.ppu_read(0), self.bus.ppu_read(4096)), (6, 7))

    def test_nametable_mirroring(self):
        self.bus.control = 2
        self.bus.ppu_write(0x2000, 123)
        self.assertEqual(self.bus.ppu_read(0x2800), 123)
        self.assertEqual(self.bus.ppu_read(0x2400), 0)
        self.bus.control = 3
        self.assertEqual(self.bus.ppu_read(0x2400), 123)

    def test_palette_alias_and_buffered_reads(self):
        self.bus.ppu_write(0x3f10, 32)
        self.assertEqual(self.bus.ppu_read(0x3f00), 32)
        self.bus.ppu_write(0x2000, 99)
        self.bus.addr = 0x2000
        self.assertEqual(self.bus[0x2007], 0)
        self.assertEqual(self.bus[0x2007], 99)
        self.bus.addr = 0x3f00
        self.assertEqual(self.bus[0x2007], 32)

    def test_controller_serial_order(self):
        self.bus.pad = 0x81
        self.bus[0x4016] = 1
        self.bus[0x4016] = 0
        self.assertEqual([self.bus[0x4016] & 1 for _ in range(10)], [1, 0, 0, 0, 0, 0, 0, 1, 1, 1])


if __name__ == '__main__':
    unittest.main()
