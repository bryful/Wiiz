"""Disassemble a selected 16 KiB PRG bank into CPU addresses."""
import argparse
from pathlib import Path
from trace_graphics import MPU
from py65.disassembler import Disassembler


def disassemble(rom, bank, start, end, bank_size=16384, base=0x8000):
    data = rom.read_bytes()
    offset = 16 + (512 if data[6] & 4 else 0)
    prg = data[offset:offset + data[4] * 16384]
    bus = bytearray(65536)
    bus[0xc000:] = prg[-16384:]
    block = prg[bank * bank_size:(bank + 1) * bank_size]
    bus[base:base + len(block)] = block
    cpu = MPU(memory=bus)
    decoder = Disassembler(cpu)
    pc = start
    while pc < end:
        size, instruction = decoder.instruction_at(pc)
        raw = ' '.join(f'{bus[pc + i]:02X}' for i in range(size))
        yield f'{pc:04X}  {raw:8s}  {instruction}'
        pc += size


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--bank', type=int, default=7)
    parser.add_argument('--start', type=lambda s: int(s, 16), required=True)
    parser.add_argument('--end', type=lambda s: int(s, 16), required=True)
    parser.add_argument('--bank-size', type=int, choices=(8192, 16384), default=16384)
    parser.add_argument('--base', type=lambda s: int(s, 16), default=0x8000)
    args = parser.parse_args()
    print('\n'.join(disassemble(args.rom, args.bank, args.start, args.end, args.bank_size, args.base)))
