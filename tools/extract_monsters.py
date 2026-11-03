"""Extract Wizardry FC monster sprite layouts and palettes from the verified ROM."""
import argparse
import hashlib
import json
from pathlib import Path
from nes_image import COLORS, rgba_png
from rom_profiles import profile_for
from monster_data import read_monster
from catalog_page import write_catalog

SUPPORTED_SHA256 = '38da945c819fab8255a1b3b8ad7c7ea162b51e8f09584501626d0aaa14a92e9a'
PRG3 = 0xc010
CHR_START = 0x20010
COUNT = 101


def decode_name(data):
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ '
    return ''.join(chars[c] if c < len(chars) else {0x35: '-', 0x2e: '?', 0x30: "'"}.get(c, f'{{{c:02X}}}') for c in data)


def parse_layout(rom, monster_id, identified):
    if profile_for(rom)['id'] != 'wiz1':
        from later_monsters import parse_layout as parse_later
        return parse_later(rom, monster_id, identified)
    if not 0 <= monster_id < COUNT:
        raise ValueError('Monster ID outside 0..100')
    bank = rom[PRG3:PRG3 + 16384]
    table = 0x12e if identified else 0xc7
    selector = bank[table + monster_id]
    pointer_offset = 0x195 + selector
    address = int.from_bytes(bank[pointer_offset:pointer_offset + 2], 'little')
    p = address - 0x8000
    if selector & 1 or not 0x27d <= p < 0x4000:
        raise ValueError('Invalid layout pointer')
    begin = p
    flags, dx, dy, extras = bank[p:p + 4]
    p += 4
    # Match ADC carry propagation in the ROM's header coordinate calculation.
    origin_x = (dx + 8) & 255
    origin_y = (dy + 0x4f + (dx + 8 > 255)) & 255
    sprites = []

    def sprite(x, y, token):
        tile = (token >> 2) | (flags & 0xc0)
        sprites.append(dict(x=x & 255, oam_y=y & 255, y=(y & 255) + 1,
                            tile=tile, palette=token & 3,
                            chr_bank=flags & 31,
                            rom_offset=CHR_START + (flags & 31) * 4096 + tile * 16))

    for _ in range(extras):
        x, y, token = bank[p:p + 3]
        sprite(origin_x + x, origin_y + y, token)
        p += 3
    for row in range(8):
        for col in range(8):
            token = bank[p]
            p += 1
            if token >> 1 == 0:
                continue
            if token >> 2 == 0:
                break
            sprite(origin_x + col * 8, origin_y + row * 8, token)
    palette = list(bank[p:p + 16])
    p += 16
    if len(sprites) > 63 or len(palette) != 16 or p - begin > 256:
        raise ValueError('Invalid record size')
    return dict(monster_id=monster_id, identified=identified, selector=selector,
                layout_address=address, layout_rom_offset=PRG3 + begin, record_size=p - begin,
                chr_bank=flags & 31, origin=[origin_x, origin_y + 1],
                palette=palette, sprites=sprites)


def render(rom, layout):
    canvas = bytearray(256 * 240 * 4)
    # Lowest OAM index wins, including when sprites overlap.
    for sprite in reversed(layout['sprites']):
        raw = rom[sprite['rom_offset']:sprite['rom_offset'] + 16]
        for y in range(8):
            for x in range(8):
                color = ((raw[y] >> (7 - x)) & 1) | (((raw[y + 8] >> (7 - x)) & 1) << 1)
                px, py = sprite['x'] + x, sprite['y'] + y
                if color and 0 <= px < 256 and 0 <= py < 240:
                    rgb = bytes.fromhex(COLORS[layout['palette'][sprite['palette'] * 4 + color] & 63])
                    pos = (py * 256 + px) * 4
                    canvas[pos:pos + 4] = rgb + b'\xff'
    visible = [(i // 4 % 256, i // 4 // 256) for i in range(3, len(canvas), 4) if canvas[i]]
    if not visible:
        return 1, 1, bytes(4), [0, 0, 1, 1]
    left, top = map(min, zip(*visible))
    right, bottom = map(max, zip(*visible))
    width, height = right - left + 1, bottom - top + 1
    cropped = b''.join(canvas[((top + y) * 256 + left) * 4:((top + y) * 256 + left + width) * 4] for y in range(height))
    return width, height, cropped, [left, top, width, height]


def extract(rom_path, output):
    rom = rom_path.read_bytes()
    sha = hashlib.sha256(rom).hexdigest()
    profile = profile_for(rom)
    count = profile['count']
    title = profile['title']
    output.mkdir(parents=True, exist_ok=True)
    monsters = []
    cell, columns = (96 if profile['id'] == 'wiz1' else 160), 16
    atlas_width = cell * columns
    atlas_height = cell * ((count * 2 + columns - 1) // columns)
    atlas = bytearray(atlas_width * atlas_height * 4)
    for monster_id in range(count):
        if profile['id'] == 'wiz1':
            entry = 0x14010 + monster_id * 128
            raw = rom[entry + 0x21:entry + 0x21 + rom[entry + 0x20]]
            unknown_raw = rom[entry + 1:entry + 1 + rom[entry]]
            info = dict(name=decode_name(raw), unknown_name=decode_name(unknown_raw),
                        name_codes=list(raw), unknown_name_codes=list(unknown_raw))
        else:
            from later_monsters import names
            info = names(rom, monster_id, profile)
        info.update(read_monster(rom, monster_id))
        variants = []
        for identified in (False, True):
            layout = parse_layout(rom, monster_id, identified)
            width, height, pixels, bbox = render(rom, layout)
            filename = f'{monster_id:03d}_{"identified" if identified else "unknown"}.png'
            rgba_png(output / filename, width, height, pixels)
            index = monster_id * 2 + int(identified)
            ax, ay = (index % columns) * cell + 8, (index // columns) * cell + 8
            if width > cell - 16 or height > cell - 16:
                raise ValueError('Sprite exceeds atlas cell')
            for y in range(height):
                start = ((ay + y) * atlas_width + ax) * 4
                atlas[start:start + width * 4] = pixels[y * width * 4:(y + 1) * width * 4]
            layout.update(image=filename, bounds=bbox, atlas_rect=[ax, ay, width, height])
            variants.append(layout)
        monsters.append(dict(id=monster_id, **info, variants=variants))
        for v in variants:
            v['preview_note'] = ('一部の色は実行時状態に依存（仮表示）' if v.get('unresolved_palette_indices') else
                                 '通常描画ルーチンでは画像なし（特殊処理未解析）' if v.get('empty') else '')
    manifest = dict(sha256=sha, game=profile['id'], title=title, mapper=profile['mapper'],
                    monster_count=count, image_count=count * 2,
                    unique_layouts=len({v['layout_address'] for m in monsters for v in m['variants']}),
                    atlas=dict(image='atlas.png', width=atlas_width, height=atlas_height),
                    runtime_palette_variants=sum(bool(v.get('unresolved_palette_indices')) for m in monsters for v in m['variants']),
                    empty_variants=sum(bool(v.get('empty')) for m in monsters for v in m['variants']),
                    color_note='Palette indices from ROM; RGB uses diagnostic NES conversion', monsters=monsters)
    rgba_png(output / 'atlas.png', atlas_width, atlas_height, atlas)
    (output / 'monsters.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    write_catalog(output, manifest)
    print(f'{title}: extracted {count * 2} images, {manifest["unique_layouts"]} unique layouts to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    profile = profile_for(args.rom.read_bytes())
    default = Path('output/monsters') if profile['id'] == 'wiz1' else Path('output') / profile['id'] / 'monsters'
    extract(args.rom, args.output or default)
