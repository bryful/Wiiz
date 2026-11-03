"""Log Wiz1 APU writes using the approximate MMC1 graphics tracer (no synthesis)."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from trace_graphics import Bus, MPU


class AudioBus(Bus):
    def __init__(self, data):
        super().__init__(data)
        self.writes = []

    def __setitem__(self, addr, value):
        if 0x4000 <= addr <= 0x4013 or addr in (0x4015, 0x4017):
            pc = self.cpu.pc
            mode = (self.control >> 2) & 3
            if mode < 2:
                bank = (self.prgbank & 14) + (pc >= 0xc000)
            elif mode == 2:
                bank = 0 if pc < 0xc000 else self.prgbank & 15
            else:
                bank = self.prgbank & 15 if pc < 0xc000 else len(self.prg) // 16384 - 1
            self.writes.append(dict(frame=self.frame + 1, cycle=self.cpu.processorCycles,
                pc=f'{pc:04X}', bank=bank, register=f'{addr:04X}', value=value & 255))
        super().__setitem__(addr, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--output', type=Path, default=Path('output/audio/trace.json'))
    args = parser.parse_args()
    if args.frames < 1:
        parser.error('--frames must be positive')
    data = args.rom.read_bytes()
    bus = AudioBus(data)
    cpu = MPU(memory=bus, pc=None)
    bus.cpu = cpu
    for frame in range(args.frames):
        bus.frame = frame
        bus.vblank = False
        while cpu.processorCycles < frame * 29781 + 27394:
            cpu.step()
        bus.vblank = True
        if bus.ctrl & 128:
            cpu.nmi()
        while cpu.processorCycles < (frame + 1) * 29781:
            cpu.step()
    result = dict(rom_sha256=hashlib.sha256(data).hexdigest(), frames=args.frames,
        limitation='Approximate CPU/PPU timing; no APU status, IRQ, DMC DMA or audio synthesis. PC is the CPU PC observed during the write.',
        register_counts=dict(Counter(w['register'] for w in bus.writes)),
        writer_counts=dict(Counter(f"{w['bank']:02X}:{w['pc']}" for w in bus.writes)),
        writes=bus.writes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'writes'}, indent=2))


if __name__ == '__main__':
    main()
