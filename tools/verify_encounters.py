"""Compare extracted JP encounter ranges against the original 6502 helper."""
import json
import hashlib
from pathlib import Path
from encounter_data import read_encounters, select_range
from trace_graphics import Bus, MPU
from verify_dungeons import call
from monster_data import read_monster
from game_rng import scaled_roll


def verify(rom):
    data = read_encounters(rom)
    bus = Bus(rom)
    cpu = MPU(memory=bus)
    bus.cpu = cpu
    matched = 0
    for floor in data['floors']:
        for row in floor['ranges']:
            for counter in range(0, 256, 17):
                for accumulator in range(0, 256, 17):
                    for i, value in enumerate(row['raw']):
                        bus[8+i] = value
                    bus[0x40], bus[0x41] = counter, accumulator
                    call(cpu, 0xe063)
                    expected = select_range(row, counter, accumulator)
                    if (cpu.a, bus[0x40], bus[0x41]) != (expected['value'], expected['counter'], expected['accumulator']):
                        raise AssertionError((floor['floor'], row['tier'], counter, accumulator))
                    matched += 1
    dice_cases = 0
    for floor in data['floors']:
        for monster_id in range(101):
            dice = read_monster(rom, monster_id)['stats']['encounter']
            for counter, accumulator in [(0, 0), (1, 255), (255, 0), (255, 255), (17, 51), (102, 204), (204, 102), (51, 17)]:
                bus[0x7e45], bus[0x7e46], bus[0x7e47] = dice['count'], dice['sides'], dice['bonus']
                bus[0x3d], bus[0x40], bus[0x41] = floor['floor'], counter, accumulator
                cpu.x = 1
                call(cpu, 0xe22b)
                total = dice['bonus']
                if dice['sides']:
                    for _ in range(dice['count']):
                        n = scaled_roll('wiz1', counter, accumulator, dice['sides'])
                        counter, accumulator = n['counter'], n['accumulator']
                        total += n['value'] + 1
                expected = min(total & 255, floor['group_cap'])
                if (cpu.a, bus[0x40], bus[0x41]) != (expected, counter, accumulator):
                    raise AssertionError(('count', floor['floor'], monster_id, expected, cpu.a))
                dice_cases += 1
    return dict(matched=True, rom_sha256=hashlib.sha256(rom).hexdigest(), cases=matched, count_cases=dice_cases,
                zero_sides_rule='Return bonus without consuming RNG', floors=10, table_rom_offset=data['table_rom_offset'],
                limitation='Range/count helpers and RNG verified; encounter trigger timing and following groups remain separate')


if __name__ == '__main__':
    result = verify(Path('.nes/wiz1.nes').read_bytes())
    out = Path('output/encounters')
    out.mkdir(parents=True, exist_ok=True)
    (out/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (out/'encounters.json').write_text(json.dumps(read_encounters(Path('.nes/wiz1.nes').read_bytes()), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result))
