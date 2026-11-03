"""Names and combat parameters read from the three verified FC ROM revisions."""
import unicodedata
from rom_profiles import profile_for


def decode_japanese(codes, game):
    if game == 'wiz1':
        mapping = dict(enumerate('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ '))
        mapping.update({0x25: '■', 0x2e: '?', 0x30: "'", 0x35: 'ー', 0x36: '\u309a', 0x37: '\u3099'})
        mapping.update({0x38 + i: c for i, c in enumerate('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンァィェォッャュョ')})
        mapping.update({0x6e + i: c for i, c in enumerate('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんっゃゅょ')})
    else:
        mapping = {i: chr(i) for i in range(32, 127)}
        mapping.update({i: bytes([i]).decode('shift_jis') for i in range(0xa1, 0xe0)})
        mapping.update({0x86 + i: c for i, c in enumerate('をぁぃぅぇぉゃゅょっ')})
        mapping.update({0x91 + i: c for i, c in enumerate('あいうえおかきくけこさしすせそ')})
        mapping.update({0xe0 + i: c for i, c in enumerate('たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん\u3099\u309a')})
    text = ''.join(mapping.get(c, f'{{{c:02X}}}') for c in codes)
    return unicodedata.normalize('NFKC', text)


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], 'little')


def signed(value):
    return value - 256 if value >= 128 else value


def dice(raw):
    count, sides, bonus = raw
    return dict(count=count, sides=sides, bonus=bonus,
                expression=f'{count}d{sides}' + (f'+{bonus}' if bonus else ''),
                minimum=count + bonus if sides else None, maximum=count * sides + bonus if sides else None,
                note='' if sides else '面数0の特殊値。範囲は未確定')


def bcd(raw):
    digits = [n for byte in raw for n in (byte >> 4, byte & 15)]
    if any(d > 9 for d in digits):
        raise ValueError('Invalid packed decimal')
    return int(''.join(map(str, digits)))


def read_monster(rom, monster_id):
    profile = profile_for(rom)
    game = profile['id']
    if not 0 <= monster_id < profile['count']:
        raise ValueError('Invalid monster ID')
    if game == 'wiz1':
        record = 0x14010 + monster_id * 128
        data = rom[record:record + 0x6f]
        codes = []
        for table in (0xefda, 0xef10):  # known and unknown Japanese-name pointer tables
            pointer = word(rom, table + monster_id * 2)
            start = 0xc010 + pointer - 0x8000
            end = rom.index(255, start, start + 32)
            codes.append(list(rom[start:end]))
        known, unknown = codes
        encounter = dice(data[0x42:0x45])
        hp = dice(data[0x45:0x48])
        attack_count = data[0x49]
        attacks = [dice(data[0x4a + i * 3:0x4d + i * 3]) for i in range(attack_count)]
        values = dict(ac=signed(data[0x48]), mage_spell_level=data[0x62], priest_spell_level=data[0x63],
                      experience=bcd(data[0x6c:0x6f]), energy_drain=data[0x5c], healing=signed(data[0x5d]),
                      magic_resistance_raw=data[0x66], status_flags_raw=data[0x68], katino_modifier_flag=bool(data[0x68] & 0x10))
        values.update(monster_type=data[0x40], breath_element_raw=data[0x65], element_resistance_raw=data[0x67])
        fields = dict(encounter=0x42, hp=0x45, ac=0x48, attack_count=0x49, attacks=0x4a,
                      mage_spell_level=0x62, priest_spell_level=0x63, experience=0x6c,
                      magic_resistance_raw=0x66, status_flags_raw=0x68,
                      monster_type=0x40, breath_element_raw=0x65, element_resistance_raw=0x67)
        stats_start, stats_raw = record + 0x40, data[0x40:0x6f]
    else:
        from later_monsters import names
        info = names(rom, monster_id, profile)
        record = info['monster_record_offset']
        stats_start = record + (50 if game == 'wiz2' else 4)
        base = rom[stats_start:stats_start + 26]
        attack_count = base[0x19]
        length = 26 + attack_count * 3
        data = rom[stats_start:stats_start + length]
        known = info['japanese_name_codes']
        unknown = info['japanese_unknown_name_codes']
        encounter, hp = dice(data[2:5]), dice(data[5:8])
        attacks = [dice(data[26 + i * 3:29 + i * 3]) for i in range(attack_count)]
        values = dict(ac=signed(data[8]), mage_spell_level=data[15], priest_spell_level=data[16],
                      experience=bcd(data[22:25]), energy_drain=data[9], healing=signed(data[10]),
                      magic_resistance_raw=data[18], status_flags_raw=data[20], katino_modifier_flag=bool(data[20] & 0x10))
        fields = {name: stats_start - record + offset for name, offset in
                  dict(encounter=2, hp=5, ac=8, attack_count=25, attacks=26,
                       mage_spell_level=15, priest_spell_level=16, experience=22,
                       magic_resistance_raw=18, status_flags_raw=20).items()}
        stats_raw = data
    if attack_count > 9 or max(values['mage_spell_level'], values['priest_spell_level']) > 7:
        raise ValueError('Unexpected combat parameter range')
    return dict(name_ja=decode_japanese(known, game), unknown_name_ja=decode_japanese(unknown, game),
                japanese_name_codes=known, japanese_unknown_name_codes=unknown,
                stats=dict(encounter=encounter, hp=hp, level=hp['count'], attack_count=attack_count,
                           attacks=attacks, **values),
                data_source=dict(record_rom_offset=record, stats_rom_offset=stats_start,
                                 stats_raw_hex=stats_raw.hex(), field_record_offsets=fields))
