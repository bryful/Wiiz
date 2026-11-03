"""Small, read-only SFC/GB survey for comparison with the verified FC data."""
import hashlib
import json
import re
from pathlib import Path

from dungeon_data import read_dungeons

ROOT = Path(__file__).resolve().parents[1]
HASHES = {
    'wiza1.gbc': '00609843f9670ad5d3ee069bf84fef1d07cf48d1aa6f9255efe1741257ad5a08',
    'wiza2.gbc': '87fb3a0e1f7a8990f77125fb968f556ad1a108cdc953e7a010d73f5cb9efbfca',
    'wiza3.gbc': '6553ffd786bfe49dc40145895225664f821ff0d1be66124a9f370bacae931ebc',
    'wiz123.smc': '15ba327d14108c5a68fc1d14fc3b112a0a7a1539aef9fa352374456b5d217f72',
}


def hits(data, needle):
    return [m.start() for m in re.finditer(re.escape(needle), data)]


def gb_header(data):
    check = 0
    for value in data[0x134:0x14d]:
        check = (check - value - 1) & 255
    return dict(title=data[0x134:0x13f].rstrip(b'\0').decode('ascii'),
                manufacturer=data[0x13f:0x143].decode('ascii'),
                cgb_flag=data[0x143], cartridge_type=data[0x147],
                rom_size_code=data[0x148], ram_size_code=data[0x149],
                header_checksum_ok=check == data[0x14d],
                global_checksum_ok=(sum(data) - sum(data[0x14e:0x150])) & 65535
                == int.from_bytes(data[0x14e:0x150], 'big'),
                entry_bytes=data[0x100:0x104].hex(' '))


def snes_header(data):
    prefix = len(data) % 0x8000
    payload = data[prefix:]
    h = payload[0x7fc0:0x8000]
    complement = int.from_bytes(h[28:30], 'little')
    checksum = int.from_bytes(h[30:32], 'little')
    return dict(copier_header_bytes=prefix,
                payload_sha256=hashlib.sha256(payload).hexdigest(),
                header_file_offset=prefix + 0x7fc0,
                title=h[:21].decode('ascii').rstrip(), map_mode=h[21],
                cartridge_type=h[22], rom_size_code=h[23], sram_size_code=h[24],
                reset_vector=int.from_bytes(h[60:62], 'little'),
                checksum=checksum, checksum_complement=complement,
                complement_ok=checksum ^ complement == 65535,
                payload_sum_ok=sum(payload) & 65535 == checksum)


def spell_names(data, filename):
    # 名称の配置だけを読む。効果ID・レベル・効果処理は未確定。
    if filename == 'wiz123.smc':
        result = []
        for offset in range(0x2204, 0x2628, 20):
            raw = data[offset:offset + 10].split(b'\0')[0]
            name = raw.decode('ascii')
            japanese = data[offset + 10:offset + 20].split(b'\0')[0]
            result.append(dict(file_offset=offset, name=name,
                               japanese_halfwidth=japanese.decode('shift_jis')))
        return result
    # 3作品の開始位置はHALITOの完全一致から求め、終端はKADORTOまで。
    starts = hits(data, b'HALITO\0\0\0')
    starts = [o for o in starts if o >= 0x80000 and data[o - 1:o] != b'A']
    if len(starts) != 1:
        raise ValueError(f'{filename}: ambiguous spell block: {starts}')
    start = starts[0]
    end = data.index(b'KADORTO\0\0\0', start) + len(b'KADORTO')
    return [dict(file_offset=start + m.start(1), name=m.group(1).decode('ascii'))
            for m in re.finditer(rb'([A-Z]+)\x00\x00\x00', data[start:end + 3])]


def snes_map_comparison(data):
    # 21階の完全一致位置から推定した1200-byte配置。実行時の参照は未追跡。
    result = []
    for filename, base in [('wiz1.nes', 0x38cb8), ('WIZ2.NES', 0x3bb98),
                           ('WIZ3.NES', 0x3d7b8)]:
        floors = read_dungeons((ROOT / '.nes' / filename).read_bytes())['floors']
        for index, floor in enumerate(floors):
            entry = dict(fc_rom=filename, floor=floor['id'], layers={})
            for layer, field, delta in [('walls', 'walls_raw', 0),
                                        ('flags', 'flags_raw', 400),
                                        ('area', 'area_raw', 800)]:
                if field not in floor['cells'][0]:
                    continue
                offset = base + index * 1200 + delta
                diffs = [dict(x=k % 20, y=k // 20, fc=cell[field], snes=data[offset + k],
                              fc_file_offset=cell['rom_offsets'][layer],
                              snes_file_offset=offset + k)
                         for k, cell in enumerate(floor['cells']) if cell[field] != data[offset + k]]
                entry['layers'][layer] = dict(snes_file_offset=offset, differences=diffs,
                                             equal_bytes=400 - len(diffs))
            result.append(entry)
    return result


def main():
    sources = []
    for filename in ('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES'):
        rom = (ROOT / '.nes' / filename).read_bytes()
        for floor in read_dungeons(rom)['floors']:
            walls = bytes(c['walls_raw'] for c in floor['cells'])
            sources.append((filename, floor['id'], walls))
    result = dict(offset_convention='All offsets are file offsets, including the SFC copier header.',
                  scope='Static headers, name layouts, exact FC wall matches, and candidate SFC map-layer comparison.',
                  roms=[])
    for folder, filename in [('.snes', 'wiz123.smc'), ('.gb', 'wiza1.gbc'),
                             ('.gb', 'wiza2.gbc'), ('.gb', 'wiza3.gbc')]:
        data = (ROOT / folder / filename).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha != HASHES[filename]:
            raise ValueError(f'{filename}: unverified ROM revision')
        names = spell_names(data, filename)
        matches = [dict(fc_rom=rom, floor=floor, file_offsets=hits(data, walls))
                   for rom, floor, walls in sources]
        result['roms'].append(dict(file=filename, size=len(data), sha256=sha,
            header=snes_header(data) if folder == '.snes' else gb_header(data),
            spell_name_candidates=names,
            literal_search={s: hits(data, s.encode('ascii')) for s in
                            ('DIOS', 'MALOR', 'TILTOWAIT', 'MURAMASA', 'WERDNA')},
            fc_wall_layers_checked=len(matches),
            fc_wall_exact_matches=[m for m in matches if m['file_offsets']]))
        if folder == '.snes':
            result['roms'][-1]['candidate_map_comparison'] = snes_map_comparison(data)
        else:
            start = names[0]['file_offset']
            end = names[-1]['file_offset'] + len('KADORTO') + 3
            result['roms'][-1]['spell_block'] = dict(start=start, end_exclusive=end,
                size=end - start, sha256=hashlib.sha256(data[start:end]).hexdigest())
    output = ROOT / 'output' / 'other_roms'
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'survey.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(target)
    for rom in result['roms']:
        print(rom['file'], rom['header'], 'names=', len(rom['spell_name_candidates']),
              'wall matches=', len(rom['fc_wall_exact_matches']))


if __name__ == '__main__':
    main()
