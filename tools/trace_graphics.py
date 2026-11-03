"""Approximate headless NES execution for graphics investigation, not gameplay."""
import argparse
import json
from pathlib import Path
import sys
from nes_image import COLORS, rgb_png

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'output' / 'deps'))
from py65.devices.mpu6502 import MPU

class Bus:
    def __init__(self, data):
        if data[:4] != b'NES\x1a' or data[7] & 12 == 8:
            raise ValueError('Expected iNES 1.0')
        if (data[6] >> 4 | data[7] & 240) != 1:
            raise ValueError('This tracer supports MMC1 only')
        offset = 16 + (512 if data[6] & 4 else 0)
        self.chr_start = offset + data[4] * 16384
        if len(data) < self.chr_start + data[5] * 8192:
            raise ValueError('Truncated ROM')
        self.prg = data[offset:offset + data[4] * 16384]
        self.chr = data[offset + len(self.prg):offset + len(self.prg) + data[5] * 8192]
        if not self.chr:
            raise ValueError('CHR ROM required')
        self.ram, self.sram, self.vram, self.palette, self.oam = (bytearray(n) for n in (2048, 8192, 2048, 32, 256))
        self.control, self.chr0, self.chr1, self.prgbank = 12, 0, 0, 0
        self.shift, self.bits = 0, 0
        self.ctrl = self.mask = self.addr = self.latch = self.buffer = self.oamaddr = 0
        self.scroll = [0, 0]
        self.vblank = False
        self.frame = 0
        self.events = []
        self.cpu = None
        self.last_mapper_cycle = -100
        self.pad = self.padindex = self.strobe = 0

    def chr_offset(self, addr):
        if self.control & 16:
            bank = self.chr0 if addr < 4096 else self.chr1
        else:
            bank = (self.chr0 & 30) + (addr // 4096)
        return (bank * 4096 + addr % 4096) % len(self.chr)

    def nt_offset(self, addr):
        addr = (addr - 0x2000) % 4096
        table, sub = divmod(addr, 1024)
        mode = self.control & 3
        physical = [0, 1, table & 1, table >> 1][mode]
        return physical * 1024 + sub

    def pal_offset(self, addr):
        index = addr & 31
        return index - 16 if index in (16, 20, 24, 28) else index

    def ppu_read(self, addr):
        addr &= 0x3fff
        if addr < 0x2000:
            return self.chr[self.chr_offset(addr)]
        if addr < 0x3f00:
            return self.vram[self.nt_offset(addr)]
        return self.palette[self.pal_offset(addr)]

    def ppu_write(self, addr, value):
        addr &= 0x3fff
        if 0x2000 <= addr < 0x3f00:
            self.vram[self.nt_offset(addr)] = value
        elif addr >= 0x3f00:
            self.palette[self.pal_offset(addr)] = value & 63

    def __getitem__(self, addr):
        if addr < 0x2000:
            return self.ram[addr & 2047]
        if addr < 0x4000:
            reg = addr & 7
            if reg == 2:
                value = 128 if self.vblank else 0
                self.vblank = False
                self.latch = 0
                return value
            if reg == 4:
                return self.oam[self.oamaddr]
            if reg == 7:
                value = self.ppu_read(self.addr)
                old = self.buffer
                self.buffer = self.ppu_read((self.addr - 0x1000) & 0x3fff) if self.addr & 0x3fff >= 0x3f00 else value
                result = value if self.addr & 0x3fff >= 0x3f00 else old
                self.addr = (self.addr + (32 if self.ctrl & 4 else 1)) & 0x7fff
                return result
            return 0
        if addr == 0x4016:
            value = (self.pad >> min(self.padindex, 8)) & 1 if self.padindex < 8 else 1
            if not self.strobe:
                self.padindex += 1
            return value | 0x40
        if 0x6000 <= addr < 0x8000:
            return self.sram[addr - 0x6000]
        if addr >= 0x8000:
            mode = (self.control >> 2) & 3
            if mode < 2:
                bank = (self.prgbank & 14) + (addr >= 0xc000)
            elif mode == 2:
                bank = 0 if addr < 0xc000 else self.prgbank & 15
            else:
                bank = self.prgbank & 15 if addr < 0xc000 else len(self.prg) // 16384 - 1
            return self.prg[(bank * 16384 + (addr & 16383)) % len(self.prg)]
        return 0

    def __setitem__(self, addr, value):
        value &= 255
        if addr < 0x2000:
            self.ram[addr & 2047] = value
        elif addr < 0x4000:
            reg = addr & 7
            if reg == 0:
                self.ctrl = value
            elif reg == 1:
                self.mask = value
            elif reg == 3:
                self.oamaddr = value
            elif reg == 4:
                self.oam[self.oamaddr] = value
                self.oamaddr = (self.oamaddr + 1) & 255
            elif reg == 5:
                self.scroll[self.latch] = value
                self.latch ^= 1
            elif reg == 6:
                if not self.latch:
                    self.addr = (self.addr & 255) | ((value & 63) << 8)
                else:
                    self.addr = (self.addr & 0x7f00) | value
                self.latch ^= 1
            elif reg == 7:
                self.ppu_write(self.addr, value)
                self.addr = (self.addr + (32 if self.ctrl & 4 else 1)) & 0x7fff
        elif addr == 0x4014:
            for i in range(256):
                self.oam[(self.oamaddr + i) & 255] = self[(value << 8) + i]
        elif addr == 0x4016:
            self.strobe = value & 1
            if self.strobe:
                self.padindex = 0
        elif 0x6000 <= addr < 0x8000:
            self.sram[addr - 0x6000] = value
        elif addr >= 0x8000:
            cycle = self.cpu.processorCycles if self.cpu else 0
            if cycle == self.last_mapper_cycle:
                return
            self.last_mapper_cycle = cycle
            if value & 128:
                self.shift = self.bits = 0
                self.control |= 12
            else:
                self.shift |= (value & 1) << self.bits
                self.bits += 1
                if self.bits == 5:
                    name = ('control', 'chr0', 'chr1', 'prgbank')[(addr - 0x8000) // 8192]
                    setattr(self, name, self.shift)
                    self.events.append(dict(frame=self.frame, pc=f'{self.cpu.pc:04X}', register=name, value=self.shift))
                    self.shift = self.bits = 0

    def snapshot(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'nametables.bin').write_bytes(self.vram)
        (directory / 'palette.bin').write_bytes(self.palette)
        (directory / 'oam.bin').write_bytes(self.oam)
        pattern = bytes(self.ppu_read(i) for i in range(8192))
        (directory / 'pattern.bin').write_bytes(pattern)
        (directory / 'state.json').write_text(json.dumps(dict(frame=self.frame, pc=f'{self.cpu.pc:04X}',
            mmc1=dict(control=self.control, chr0=self.chr0, chr1=self.chr1, prg=self.prgbank),
            ppuctrl=self.ctrl, ppumask=self.mask, scroll=self.scroll, palette=list(self.palette)), indent=2))
        pixels = bytearray()
        base = 0x2000 + (self.ctrl & 3) * 1024
        tiles = []
        for ty in range(30):
            for tx in range(32):
                tile = self.ppu_read(base + ty * 32 + tx)
                attr = self.ppu_read(base + 960 + (ty // 4) * 8 + tx // 4)
                pal = (attr >> ((ty & 2) * 2 + (tx & 2))) & 3
                address = (0x1000 if self.ctrl & 16 else 0) + tile * 16
                chr_offset = self.chr_offset(address)
                tiles.append(dict(x=tx, y=ty, tile=tile, palette=pal, chr_bank=chr_offset // 4096,
                                  chr_offset=chr_offset, rom_offset=self.chr_start + chr_offset))
        (directory / 'tiles.json').write_text(json.dumps(tiles, indent=2))
        for y in range(240):
            for x in range(256):
                tx, ty = x // 8, y // 8
                tile = self.ppu_read(base + ty * 32 + tx)
                attr = self.ppu_read(base + 960 + (ty // 4) * 8 + tx // 4)
                pal = (attr >> (((ty & 2) * 2) + (tx & 2))) & 3
                a = (0x1000 if self.ctrl & 16 else 0) + tile * 16 + (y & 7)
                bit = 7 - (x & 7)
                color = ((self.ppu_read(a) >> bit) & 1) | (((self.ppu_read(a + 8) >> bit) & 1) << 1)
                if not self.mask & 8 or (x < 8 and not self.mask & 2):
                    color = 0
                idx = self.palette[pal * 4 + color] if color else self.palette[0]
                pixels.extend(bytes.fromhex(COLORS[idx & 63]))
        rgb_png(directory / 'background.png', 256, 240, pixels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--output', type=Path, default=Path('output/trace'))
    parser.add_argument('--press', action='append', default=[], metavar='FRAME:BUTTON:DURATION',
                        help='1-based frame; BUTTON: A,B,SELECT,START,UP,DOWN,LEFT,RIGHT')
    args = parser.parse_args()
    buttons = {name: 1 << i for i, name in enumerate(('A', 'B', 'SELECT', 'START', 'UP', 'DOWN', 'LEFT', 'RIGHT'))}
    presses = []
    for press in args.press:
        try:
            frame, button, duration = press.split(':')
            start, duration = int(frame), int(duration)
            if start < 1 or duration < 1:
                raise ValueError()
            presses.append((start - 1, start - 1 + duration, buttons[button.upper()]))
        except (ValueError, KeyError):
            parser.error(f'Invalid --press: {press}')
    bus = Bus(args.rom.read_bytes())
    cpu = MPU(memory=bus, pc=None)
    bus.cpu = cpu
    # Approximate NTSC frame and vblank timing. No APU, sprite-zero hit or raster emulation.
    frames = []
    for frame in range(args.frames):
        bus.frame = frame
        bus.pad = 0
        for start, end, button in presses:
            if start <= frame < end:
                bus.pad |= button
        bus.vblank = False
        while cpu.processorCycles < frame * 29781 + 27394:
            cpu.step()
        bus.vblank = True
        if bus.ctrl & 128:
            cpu.nmi()
        while cpu.processorCycles < (frame + 1) * 29781:
            cpu.step()
        if frame % 60 == 59 or frame == args.frames - 1:
            name = f'frame_{frame + 1:05d}'
            bus.snapshot(args.output / name)
            frames.append(name)
            print(f'{name}: PC=${cpu.pc:04X}, CHR={bus.chr0}/{bus.chr1}', flush=True)
    (args.output / 'mapper_events.json').write_text(json.dumps(bus.events, indent=2))
    (args.output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>PPU trace</title><style>body{background:#151922;color:white;font:16px sans-serif}img{image-rendering:pixelated;width:512px}section{display:inline-block;margin:16px}</style><h1>PPU背景の復元（近似実行）</h1><p>スプライト・スクロール・走査線効果は未描画。RGBは確認用。</p>' + ''.join(f'<section><h2>{name}</h2><img src="{name}/background.png"></section>' for name in frames), encoding='utf-8')


if __name__ == '__main__':
    main()
