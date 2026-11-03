"""Check W1 loaders and later spell dispatch with original 6502 routines."""
import argparse
import json
from pathlib import Path
from item_spell_data import extract_data
from trace_graphics import Bus, MPU
from mmc3_cpu_bus import Mmc3CpuBus


def run(bus, entry, accumulator, stop=0x6000):
    cpu = MPU(memory=bus, pc=entry)
    if isinstance(bus, Bus):
        bus.cpu = cpu
    cpu.a = accumulator
    cpu.stPushWord(0x5fff)
    for _ in range(30000):
        if cpu.pc == stop:
            return
        cpu.step()
    raise AssertionError(f'CPU timeout at {cpu.pc:04X}')


def verify(rom):
    data = extract_data(rom)
    game = data['game']
    counts = dict(item_loader_cases=0, item_pointer_cases=0, spell_name_loader_cases=0, spell_dispatch_cases=0)
    if game == 'wiz1':
        for row in data['items']:
            for jp in (0, 1):
                bus = Bus(rom)
                bus.prgbank = 4
                bus[0xfb] = 4
                bus[0x7ab9] = jp
                run(bus, 0xd0b5, row['id'])
                actual = bytes(bus[0x500 + i] for i in range(64))
                raw = bytes.fromhex(row['source']['raw_hex'])
                assert actual[34:] == raw[34:], (game, row['id'], 'stats')
                if not jp:
                    assert actual == raw
                else:
                    for key, start in [('ja', 18), ('unknown_ja', 1)]:
                        expected = bytes(row['name_codes'][key])
                        assert actual[start:start + len(expected)] == expected
                counts['item_loader_cases'] += 1
        for row in data['spells']:
            for jp in (0, 1):
                bus = Bus(rom)
                bus[0xfb] = 0
                bus[0x7aba] = jp
                run(bus, 0xd083, row['id'])
                assert bytes(bus[0x283 + i] for i in range(10)) == bytes(row['name_codes']['ja' if jp else 'en'])
                counts['spell_name_loader_cases'] += 1
    else:
        for row in data['items']:
            bus = Mmc3CpuBus(rom)
            bus.registers[6:8] = [12, 13]
            bus[0x48] = row['id']
            run(bus, 0xc9e0 if game == 'wiz2' else 0xee93, row['id'])
            pointer = bus[0x55] + 256 * bus[0x56]
            expected = bytes.fromhex(row['source']['raw_hex'])
            assert bytes(bus[pointer + j] for j in range(len(expected))) == expected, (game, row['id'])
            counts['item_pointer_cases'] += 1
        for row in data['spells']:
            bus = Mmc3CpuBus(rom)
            bus.registers[6:8] = [12, 13]
            bus[0x6f] = row['id']
            run(bus, 0x8d35 if game == 'wiz2' else 0x8d09, 0,
                stop=row['effect']['handler_cpu_address'])
            counts['spell_dispatch_cases'] += 1
    return dict(game=game, sha256=data['sha256'], matched=True, **counts,
                limitation='W2/W3 item pointers and record bytes are verified, not full name loaders. Spell effects are not executed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
