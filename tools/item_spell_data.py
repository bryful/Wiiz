"""Revision-specific item/spell tables. Unknown effect semantics remain raw."""
import hashlib
import unicodedata
from monster_data import decode_japanese, word, signed, bcd
from rom_profiles import profile_for


def text(codes, game, icons=False, english=False):
    if not icons:
        return decode_japanese(codes, game).strip()
    glyphs = ({0xee: '[薬]', 0xef: '[巻物]', **({0x64: ' of '} if english else {})}
              if game == 'wiz1' else {0xa0: ' of ', 0xa1: '{A1}', 0xa2: '[薬]', 0xa3: '[巻物]'})
    return unicodedata.normalize('NFKC', ''.join(glyphs.get(c, decode_japanese([c], game)) for c in codes)).strip()


def terminated(rom, start, stop=0):
    end = rom.index(stop, start, start + 256)
    return list(rom[start:end]), end + 1


def later_name(rom, pointer):
    offset = 0x10010 + pointer - 0x8000
    en, cursor = terminated(rom, offset)
    ja, _ = terminated(rom, cursor)
    return en, ja


def items(rom):
    game = profile_for(rom)['id']
    result = []
    for i in range({'wiz1': 101, 'wiz2': 110, 'wiz3': 138}[game]):
        if game == 'wiz1':
            offset = 0x10110 + i * 64
            raw = rom[offset:offset + 64]
            en_u, en = list(raw[1:1 + raw[0]]), list(raw[18:18 + raw[17]])
            names = []
            for table in (0xb010, 0xb0da):
                ptr = word(rom, table + i * 2)
                names.append(terminated(rom, 0x8010 + ptr - 0x8000, 255)[0])
            ja_u, ja = names
            s = raw[34:]
            fields = dict(kind=s[0], alignment_raw=s[1], cursed_raw=s[2], special_power_raw=s[3],
                          break_raw=s[4], replacement_item_id=s[5], price=bcd(s[6:12]),
                          initial_stock_raw=s[12], use_spell_raw=s[13], equip_mask=s[14],
                          healing=signed(s[15]), ac_modifier=-signed(s[16]), strength=signed(s[17]),
                          minimum_attacks=s[18], damage=dict(count=s[19], sides=s[20], bonus=s[21]),
                          critical_raw=s[22], remaining_raw_hex=s[23:].hex())
            fields['use_spell_id'] = None if s[13] == 255 else s[13]
        else:
            if game == 'wiz2':
                offset = 0x10010 + word(rom, 0x10010 + i * 2) - 0x8000
                raw = rom[offset:offset + 61]
                en, ja = list(raw[:16].rstrip(b'\x00 ')), list(raw[16:32].rstrip(b'\x00 '))
                u = 0x10010 + word(raw, 32) - 0x8000
                en_u, ja_u = list(rom[u:u + 16].rstrip(b'\x00 ')), list(rom[u + 16:u + 32].rstrip(b'\x00 '))
                s = raw[34:]
            else:
                offset = 0x10010 + i * 31
                raw = rom[offset:offset + 31]
                en, ja = later_name(rom, word(raw, 0))
                en_u, ja_u = later_name(rom, word(raw, 2))
                s = raw[4:]
            fields = dict(kind=s[0], alignment_raw=s[1], cursed_raw=s[2], special_power_raw=s[3],
                          break_raw=s[4], replacement_item_id=s[5], price=bcd(s[6:12]),
                          use_spell_raw=s[12], use_spell_id=(s[12] & 63) if s[12] else None,
                          equip_mask=s[13], healing=signed(s[14]), ac_modifier=-signed(s[15]),
                          strength=signed(s[16]), damage=dict(count=s[18], sides=s[17], bonus=s[19]),
                          minimum_attacks=s[20], critical_raw=s[21], remaining_raw_hex=s[22:].hex())
            if game == 'wiz3':
                fields.update(ac_modifier=-signed(s[18]), strength=signed(s[19]),
                              damage=dict(count=s[21], sides=s[20], bonus=s[22]),
                              minimum_attacks=s[23], critical_raw=s[24],
                              remaining_raw_hex=(s[15:18] + s[25:27]).hex())
        result.append(dict(id=i, name_en=text(en, game, True, True), name_ja=text(ja, game, True),
                           unknown_name_en=text(en_u, game, True, True), unknown_name_ja=text(ja_u, game, True),
                           name_codes=dict(en=en, ja=ja, unknown_en=en_u, unknown_ja=ja_u),
                           stats=fields, source=dict(rom_offset=offset, raw_hex=raw.hex())))
    return result


def spells(rom):
    game = profile_for(rom)['id']
    config = {
        'wiz1': (21, 0x1ef94, [0x3df5, 0x3df5 + 210, 0x7df5, 0x7df5 + 210], 0xa404),
        'wiz2': (21, 0x1a9ac, [0x1e10, 0x1f10, 0x5e10, 0x5f10], 0x18d56),
        'wiz3': (24, 0x1ae6c, [0x1bade, 0x1bba0, 0x1bc77, 0x1bd0a], 0x18d1e),
    }
    mage_count, bounds_offset, roots, handlers = config[game]
    bounds = [list(rom[bounds_offset:bounds_offset + 8]), list(rom[bounds_offset + 8:bounds_offset + 16])]
    if game == 'wiz1':
        bounds[1] = [n - mage_count for n in rom[bounds_offset + 7:bounds_offset + 15]]
    names = []
    for index, root in enumerate(roots):
        count = mage_count if index % 2 == 0 else 29
        rows = []
        for j in range(count):
            if game == 'wiz1':
                codes = list(rom[root + j * 10:root + (j + 1) * 10])
            else:
                codes, root = terminated(rom, root)
            rows.append(codes)
        names.append(rows)
    result = []
    for i in range(mage_count + 29):
        school = int(i >= mage_count)
        index = i - mage_count if school else i
        en, ja = names[school][index], names[school + 2][index]
        handler = word(rom, handlers + i * 2)
        # Damage routines consume three immediate/inline bytes. Keep other effects unresolved.
        handler_offset = (0x8010 + handler - 0x8000) if game == 'wiz1' else (0x18010 + handler - 0x8000)
        effect = dict(status='unresolved', handler_cpu_address=handler, handler_rom_offset=handler_offset)
        next_handler = min((word(rom, handlers + j * 2) for j in range(mage_count + 29)
                            if word(rom, handlers + j * 2) > handler), default=handler + 96)
        code = rom[handler_offset:handler_offset + min(96, next_handler - handler)]
        if game == 'wiz1':
            parameters = []
            for address in (0x274, 0x275, 0x276):
                found = [code[k + 1] for k in range(len(code) - 4)
                         if code[k] == 0xa9 and code[k + 2:k + 5] == bytes([0x8d, address & 255, address >> 8])]
                parameters.append(found[0] if len(found) == 1 else None)
            if all(p is not None for p in parameters) and bytes.fromhex('2058a4') in code:
                effect.update(status='damage_parameters', damage=dict(count=parameters[0], sides=parameters[1]),
                              element_raw=parameters[2])
        if game != 'wiz1':
            helper = 0x8e5b if game == 'wiz2' else 0x8e2d
            marker = bytes([0x20, helper & 255, helper >> 8])
            p = code.find(marker)
            if p >= 0 and p + 6 <= len(code):
                count, sides, element = code[p + 3:p + 6]
                effect.update(status='damage_parameters', damage=dict(count=count, sides=sides),
                              element_raw=element, parameter_rom_offset=handler_offset + p + 3)
        row = dict(id=i, name_en=text(en, game), name_ja=text(ja, game), name_codes=dict(en=en, ja=ja),
                   school=['mage', 'priest'][school], level=next(n for n in range(1, 8) if bounds[school][n - 1] <= index < bounds[school][n]),
                   effect=effect, source=dict(handler_pointer_rom_offset=handlers + i * 2))
        if game == 'wiz1':
            flags = rom[0x1efa3 + i]
            row['usage'] = dict(battle=bool(flags & 128), camp=bool(flags & 64), selection_raw=flags & 63, raw=flags)
        result.append(row)
    return result


def extract_data(rom):
    profile = profile_for(rom)
    from rule_data import special_powers, annotate_spells, equipment_rules
    from item_use_rules import metadata as use_metadata
    from status_rules import status_data, annotate as annotate_status
    from affliction_rules import annotate as annotate_afflictions
    game = profile['id']
    powers = special_powers(rom, game)
    extracted_items = items(rom)
    for item in extracted_items:
        power = item['stats']['special_power_raw']
        item['special_power'] = powers[power] if 0 <= power < len(powers) else None
        item['use_rules'] = use_metadata(game, item)
        replacement = extracted_items[item['stats']['replacement_item_id']]
        item['use_rules']['replacement_name_ja'] = replacement['name_ja']
    return dict(game=profile['id'], title=profile['title'], sha256=hashlib.sha256(rom).hexdigest(),
                notes=['SP職業条件・使用後の変化判定・一部SP状態遷移・AC呪文・回復・治療・蘇生・睡眠/沈黙付与を解析。戦闘全体と自然回復は解析中。',
                       '呪文のhandlerと一部ダメージ定数を抽出。未解析の効果・対象範囲は生値を保持。',
                       '名前内の[薬]・[巻物]はROMフォントの絵文字。'],
                items=extracted_items, spells=annotate_afflictions(annotate_status(annotate_spells(rom, game, spells(rom)), game), game),
                rules=dict(equipment=equipment_rules(game), special_powers=powers, status=status_data(rom, game)))
