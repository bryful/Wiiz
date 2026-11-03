"""Cross-check every map cell against each ROM's own cell-reading routine."""
import argparse
import hashlib
import json
from pathlib import Path
from dungeon_data import read_dungeons
from trace_graphics import Bus, MPU
from mmc3_cpu_bus import Mmc3CpuBus


def call(cpu, pc, limit=30000):
    cpu.pc, cpu.sp = pc, 0xff
    cpu.stPushWord(0x5fff)
    for _ in range(limit):
        if cpu.pc == 0x6000:
            return
        cpu.step()
    raise AssertionError(f'Routine timeout at {cpu.pc:04X}')


def verify(rom):
    data = read_dungeons(rom)
    game = data['game']
    if game == 'wiz1':
        bus = Bus(rom)
        bus.prgbank = 4
        cpu = MPU(memory=bus)
        bus.cpu = cpu
    else:
        bus = Mmc3CpuBus(rom)
        cpu = MPU(memory=bus)
        bus.registers[6:8] = [4, 13]
        # Execute the ROM routine that initializes six mutable floor-event tables.
        for address in range(0x6b88, 0x6d0e):
            bus[address] = 255
        call(cpu, 0x844d if game == 'wiz2' else 0x8433)
        for floor in data['floors']:
            actual = bytes(bus[0x6b88 + (floor['id'] - 1) * 65 + i] for i in range(64))
            expected = bytes(v for event in floor['event_descriptors'] for v in event['raw'])
            if actual != expected:
                raise AssertionError(f'Event defaults mismatch: {game}/{floor["id"]}')
        bus.registers[6:8] = [9, 13]
        bus[0x7e], bus[0x7f] = 9, 13
    count = 0
    for floor in data['floors']:
        for cell in floor['cells']:
            x, y = cell['x'], cell['y']
            if game == 'wiz1':
                bus[0x3d], bus[0x6e], bus[0x6f] = floor['id'], x, y
                call(cpu, 0x8000)
                wall, flag = bus[2], bus[3]
                if 'event' in cell:
                    actual = bytes(bus[0x273 + i] for i in range(4))
                    if actual != bytes(cell['event']['raw']):
                        raise AssertionError(f'Cell event mismatch: {game}/{floor["id"]}/{x}/{y}')
            else:
                bus[0xec], bus[0xea], bus[0xeb] = floor['id'], x, y
                cpu.x = 0
                call(cpu, 0xa469 if game == 'wiz2' else 0xa936)
                wall, flag = bus[0xc3], bus[0xcf]
                bus[0xc0], bus[0xc1] = x, y
                call(cpu, 0xa2d9 if game == 'wiz2' else 0xa7a6)
                if cpu.a != cell['encounter_area_id']:
                    raise AssertionError(f'Area mismatch: {game}/{floor["id"]}/{x}/{y}')
            if (wall, flag) != (cell['walls_raw'], cell['flags_raw']):
                raise AssertionError(f'Cell mismatch: {game}/{floor["id"]}/{x}/{y}')
            count += 1
    return dict(game=game, rom_sha256=hashlib.sha256(rom).hexdigest(), matched=True,
                floors=len(data['floors']), cells=count,
                checks=['wall bytes', 'cell flag bytes', 'event records or event defaults', 'encounter area IDs where present'],
                limitation='Validates ROM reads and initial event records; event meanings and live save-state changes are separate')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
