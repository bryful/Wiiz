"""Wiz1 JP encounter ranges read from the verified ROM, not the USA addresses."""
from rom_profiles import profile_for
from game_rng import next_byte, scaled_roll

TABLE_CPU = 0xe26d
TABLE_ROM = 0x1c010 + TABLE_CPU - 0xc000


def read_encounters(rom):
    if profile_for(rom)['id'] != 'wiz1':
        raise ValueError('Wiz1 JP only')
    # E104 computes (floor-1)*15; E131 reads five bytes from this table.
    if rom[0x1e141:0x1e144] != bytes.fromhex('b96de2'):
        raise ValueError('Encounter table reference changed')
    floors = []
    for floor in range(1, 11):
        ranges = []
        for tier, weight in enumerate([12, 3, 1]):
            offset = TABLE_ROM + (floor - 1) * 15 + tier * 5
            base, step, repeats, width, threshold = rom[offset:offset + 5]
            if not width or base + step * repeats + width - 1 > 100:
                raise ValueError('Invalid encounter range')
            ranges.append(dict(tier=tier, weight=weight, base=base, step=step,
                               repeats=repeats, width=width, threshold=threshold,
                               rom_offset=offset, raw=list(rom[offset:offset + 5])))
        floors.append(dict(floor=floor, ranges=ranges, group_cap=min(floor+4, 9)))
    return dict(game='wiz1', table_cpu_address=TABLE_CPU, table_rom_offset=TABLE_ROM,
                floors=floors, note='ROM ranges; browser random source and encounter timing are prototype rules')


def select_range(row, counter, accumulator):
    """Exact JP $E063 helper, including the original RNG state transitions."""
    base = row['base']
    remaining = row['repeats']
    while True:
        n = next_byte(counter, accumulator)
        counter, accumulator = n['counter'], n['accumulator']
        if n['value'] >= row['threshold']:
            break
        base = (base + row['step']) & 255
        remaining = (remaining - 1) & 255
        if remaining == 0:
            break
    n = scaled_roll('wiz1', counter, accumulator, row['width'])
    return dict(value=(base + n['value']) & 255, counter=n['counter'], accumulator=n['accumulator'])
