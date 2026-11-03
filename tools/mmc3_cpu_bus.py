"""MMC3 CPU banking for isolated ROM routine verification. No PPU/APU emulation."""


class Mmc3CpuBus:
    def __init__(self, rom):
        if rom[:4] != b'NES\x1a' or ((rom[6] >> 4) | (rom[7] & 240)) != 4:
            raise ValueError('Expected Mapper 4')
        self.prg = rom[16:16 + rom[4] * 16384]
        self.ram = bytearray(0x8000)
        self.registers = [0, 2, 4, 5, 6, 7, 0, 1]
        self.select = 0

    def __getitem__(self, addr):
        if addr < 0x8000:
            return self.ram[addr & 2047] if addr < 0x2000 else self.ram[addr]
        last = len(self.prg) // 8192 - 1
        slots = [self.registers[6], self.registers[7], last - 1, last]
        if self.select & 64:
            slots[0], slots[2] = slots[2], slots[0]
        bank = slots[(addr - 0x8000) // 8192] % (last + 1)
        return self.prg[bank * 8192 + (addr & 8191)]

    def __setitem__(self, addr, value):
        value &= 255
        if addr < 0x8000:
            self.ram[addr & 2047 if addr < 0x2000 else addr] = value
        elif addr < 0xa000:
            if addr & 1:
                self.registers[self.select & 7] = value
            else:
                self.select = value
