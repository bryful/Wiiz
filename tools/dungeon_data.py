"""Decode the dungeon layers of the three hash-verified ROMs."""
from rom_profiles import profile_for

WIDTH = HEIGHT = 20
DIRECTIONS = ('north', 'east', 'south', 'west')
EDGE_NAMES = ('通路', '壁', '扉', '隠し扉')


def word(rom, offset):
    return int.from_bytes(rom[offset:offset + 2], 'little')


def read_dungeons(rom):
    profile = profile_for(rom)
    game = profile['id']
    floors = []
    for floor_id in range(1, 11 if game == 'wiz1' else 7):
        if game == 'wiz1':
            base = 0x10010
            walls = base + word(rom, base + 0x5c + floor_id * 2) - 0x8000
            flags = base + word(rom, base + 0x70 + floor_id * 2) - 0x8000
            events = base + word(rom, base + 0x84 + floor_id * 2) - 0x8000
            areas = None
            stair_type, teleport_type = 0, 2
        else:
            walls = 0x12010 + word(rom, 0x12010 + floor_id * 2) - 0x8000
            flags, areas = walls + 400, walls + 800
            pointer_location = 0x8549 if game == 'wiz2' else 0x8548
            events = word(rom, pointer_location) + 16 + (floor_id - 1) * 64
            stair_type, teleport_type = (2, 10) if game == 'wiz2' else (1, 2)
        descriptors = []
        for slot in range(16):
            offset = events + slot * 4
            raw = list(rom[offset:offset + 4])
            kind = 'stairs' if raw[0] == stair_type else 'teleport' if raw[0] == teleport_type else 'unclassified'
            descriptor = dict(slot=slot, type_raw=raw[0], kind=kind, parameters=raw[1:], raw=raw, rom_offset=offset)
            if kind in ('stairs', 'teleport'):
                x, y, target_floor = raw[1:]
                if x < 20 and y < 20 and target_floor <= (10 if game == 'wiz1' else 6):
                    descriptor['destination'] = dict(x=x, y=y, floor=target_floor)
            descriptors.append(descriptor)
        cells = []
        for y in range(20):
            for x in range(20):
                index = y * 20 + x
                wall, flag = rom[walls + index], rom[flags + index]
                edges = {name: (wall >> (i * 2)) & 3 for i, name in enumerate(DIRECTIONS)}
                cell = dict(x=x, y=y, walls_raw=wall, flags_raw=flag, edges=edges,
                            dark=bool(flag & 64), chamber=bool(flag & 128),
                            rom_offsets=dict(walls=walls + index, flags=flags + index))
                if areas is not None:
                    raw = rom[areas + index]
                    limit, fallback = (136, 30) if game == 'wiz2' else (83, 0)
                    cell.update(area_raw=raw, encounter_area_id=raw if raw < limit else fallback)
                    cell['rom_offsets']['area'] = areas + index
                if flag & 32:
                    slot = flag & (15 if game == 'wiz1' else 31)
                    if slot < 16:
                        cell['event'] = descriptors[slot]
                    else:
                        cell['event'] = dict(slot=slot, type_raw=None, kind='inline', parameters=[], raw=[], rom_offset=None)
                cells.append(cell)
        # Preserve differences on opposite sides; one-way edges must not be silently merged.
        asymmetric = []
        for cell in cells:
            x, y = cell['x'], cell['y']
            for direction, opposite, nx, ny in [('east', 'west', (x + 1) % 20, y), ('north', 'south', x, (y + 1) % 20)]:
                other = cells[ny * 20 + nx]
                if cell['edges'][direction] != other['edges'][opposite]:
                    asymmetric.append(dict(x=x, y=y, direction=direction, value=cell['edges'][direction], opposite_value=other['edges'][opposite]))
        floors.append(dict(id=floor_id, label=f'階層 {floor_id}', width=20, height=20,
                           sources=dict(walls=walls, flags=flags, area=areas, events=events),
                           event_descriptors=descriptors, cells=cells, asymmetric_edges=asymmetric))
    return dict(game=game, title=profile['title'], floor_count=len(floors), width=20, height=20,
                coordinates='x eastward, y northward; origin at southwest; neighbors wrap modulo 20',
                edge_types=list(EDGE_NAMES), floors=floors)
