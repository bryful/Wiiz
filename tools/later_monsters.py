"""Wizardry FC II/III compressed sprite streams (MMC3 cartridges)."""
from rom_profiles import profile_for


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], 'little')


def names(rom, monster_id, profile):
    table = profile['names_file']
    record = table + word(rom, table + monster_id * 2) - 0x8000
    if profile['id'] == 'wiz2':
        raw = rom[record:record + 16].rstrip(b' ')
        unknown_record = table + word(rom, record + 48) - 0x8000
        unknown_raw = rom[unknown_record:unknown_record + 16].rstrip(b' ')
        return dict(name=raw.decode('ascii'), unknown_name=unknown_raw.decode('ascii'), name_codes=list(raw),
                    unknown_name_codes=list(unknown_raw),
                    japanese_unknown_name_codes=list(rom[unknown_record + 32:unknown_record + 48].rstrip(b' ')),
                    japanese_name_codes=list(rom[record + 32:record + 48].rstrip(b' ')),
                    monster_record_offset=record)

    def strings(pointer):
        offset = table + pointer - 0x8000
        values = []
        for _ in range(3):
            end = rom.index(0, offset, offset + 128)
            values.append(rom[offset:end])
            offset = end + 1
        return values

    known = strings(word(rom, record))
    unknown = strings(word(rom, record + 2))
    return dict(name=known[0].decode('ascii'), unknown_name=unknown[0].decode('ascii'),
                name_codes=list(known[0]), unknown_name_codes=list(unknown[0]),
                japanese_name_codes=list(known[2]), japanese_unknown_name_codes=list(unknown[2]), monster_record_offset=record)


def parse_layout(rom, monster_id, identified):
    profile = profile_for(rom)
    if not 0 <= monster_id < profile['count']:
        raise ValueError('Monster ID outside profile range')
    code_file = 16 + profile['code_bank'] * 8192
    if identified:
        index = monster_id + profile['pointer_bias']
    else:
        value = rom[code_file + profile['unknown_table'] - profile['code_base'] + monster_id]
        index = value // 2 if profile['id'] == 'wiz2' else value
    pointer = word(rom, profile['pointer_table_file'] + index * 2)
    # High pointer byte bit7 means no image in the ROM routine.
    if pointer & 0x8000:
        return dict(monster_id=monster_id, identified=identified, selector=index,
                    layout_address=pointer, layout_rom_offset=profile['pointer_table_file'] + index * 2,
                    record_size=0, chr_bank=0, palette=[15] * 16, palette_values=[], sprites=[], empty=True)
    start = profile['record_base'] + pointer
    p = start
    chr_register = (rom[p] + profile['chr_bias']) & 255
    if profile['id'] == 'wiz2' and chr_register >= 64:
        chr_register |= 128
    chr_bank = chr_register & 127  # physical 128 KiB CHR address lines
    tile = rom[p + 1]
    p += 2
    colors = []
    while rom[p] < 128:
        colors.append(rom[p])
        p += 1
        if len(colors) > 12:
            raise ValueError('Too many palette colors')
    palette_values = colors[:]
    colors += [0] * (12 - len(colors))
    palette = [value for i in range(4) for value in [15, *colors[i * 3:i * 3 + 3]]]
    attrs = profile['attributes']
    ox, oy = profile['origin']
    y = 0
    sprites = []
    for _ in range(256):
        value = rom[p]
        p += 1
        if value == 255:
            break
        if value == 254:
            attrs = (attrs + 1) & 255
        elif value >= 128:
            y = ((value & 127) + oy) & 255
        else:
            x = (value + ox) & 255
            # Tile 0..63 uses MMC3 R2, tile 64..127 uses R3.
            bank_1k = (chr_bank + tile // 64) & 127
            sprites.append(dict(x=x, oam_y=y, y=y + 1, tile=tile,
                                attributes=attrs, palette=attrs & 3,
                                chr_bank=bank_1k,
                                rom_offset=0x20010 + bank_1k * 1024 + (tile & 63) * 16))
            tile = (tile + 1) & 255
            if tile == 0:
                break
    else:
        raise ValueError('Unterminated sprite stream')
    if len(sprites) > 64:
        raise ValueError('OAM overflow')
    unresolved = set()
    for s in sprites:
        raw = rom[s['rom_offset']:s['rom_offset'] + 16]
        for y in range(8):
            for x in range(8):
                color = ((raw[y] >> (7 - x)) & 1) | (((raw[y + 8] >> (7 - x)) & 1) << 1)
                if color and s['palette'] * 3 + color > len(palette_values):
                    unresolved.add(s['palette'] * 4 + color)
    return dict(monster_id=monster_id, identified=identified, selector=index,
                layout_address=pointer, layout_rom_offset=start, record_size=p - start,
                chr_bank=chr_bank, chr_register=chr_register, palette=palette,
                palette_values=palette_values, origin=[ox, oy + 1], sprites=sprites,
                chr_bank_unit=1024, unresolved_palette_indices=sorted(unresolved),
                palette_note='Only palette_values are written by this record; absent values use diagnostic zero fill')
