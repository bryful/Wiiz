"""Effect metadata derived from per-revision routine addresses and parameters."""
from monster_data import word, signed

SP_TABLES = {'wiz1': (0x1b6fe, 24), 'wiz2': (0x1b02e, 31), 'wiz3': (0x1afc3, 28)}
ATTRIBUTES = ['ちから', 'ちえ', 'しんこうしん', 'せいめいりょく', 'すばやさ', 'うん']
AC_TARGETS = {'MOGREF': 'caster', 'SOPIC': 'caster', 'PORFIC': 'caster',
              'DILTO': 'enemy_group', 'MORLIS': 'enemy_group',
              'MAMORLIS': 'all_enemies', 'MAMORILS': 'all_enemies',
              'MASOPIC': 'party', 'KALKI': 'party', 'MATU': 'party', 'BAMATU': 'party'}


def special_powers(rom, game):
    table, count = SP_TABLES[game]
    noop = {'wiz1': 0xb71e, 'wiz2': 0xb0f3, 'wiz3': 0xb123}[game]
    rows = []
    for i in range(count):
        handler = word(rom, table + i * 2)
        row = dict(id=i, game=game, kind='unresolved', summary='未解析', executable_core=False,
                   handler_cpu_address=handler, handler_rom_offset=0x10010 + handler,
                   pointer_rom_offset=table + i * 2)
        if handler == noop:
            row.update(kind='no_effect_body', summary='効果本体なし（発動・変化処理とは別）')
        elif 1 <= i <= 6:
            # I implements only power 1. III's cap depends on race.
            row.update(kind='attribute_increase', summary=ATTRIBUTES[i - 1] + ' +1',
                       character_offset=(0x0c if game == 'wiz1' else 0x0a) + i,
                       cap=18 if game != 'wiz3' else None, executable_core=True)
            if game == 'wiz3':
                row['race_caps'] = [rom[0x1dc1b + race * 6 + i - 1] + 10 for race in range(5)]
                row['summary'] += '（種族別上限）'
        elif game != 'wiz1' and 7 <= i <= 12:
            row.update(kind='attribute_decrease', summary=ATTRIBUTES[i - 7] + ' −1（下限0）',
                       character_offset=i + 4, executable_core=True)
        elif i == 17:
            row.update(kind='class_ninja', summary='忍者へ転職（職業値の変更）', executable_core=True)
        elif game == 'wiz3' and i == 16:
            row.update(kind='class_lord', summary='君主へ転職（職業値の変更）', executable_core=True)
        elif i == 22:
            summary = {'wiz1': '最大HP・現在HP +1', 'wiz2': '最大HP +1〜2（発動時の比較結果に依存）', 'wiz3': '最大HP +1（発動経路を含めて照合）'}[game]
            row.update(kind='max_hp_increase', summary=summary,
                       max_hp_offset=0x1f if game != 'wiz1' else None, executable_core=game != 'wiz1')
            if game != 'wiz1':
                row['activation_increment_rule'] = '1 + (rng_byte >= break_raw)' if game == 'wiz2' else '1'
        elif i == 23:
            row.update(kind='party_full_heal', summary='状態コード5未満の仲間のHPを最大値へ')
        elif game == 'wiz3' and i == 13:
            row.update(kind='age_raw_decrease', summary='年齢格納値が20以上なら −1（単位未確定）', executable_core=True)
        elif game == 'wiz3' and i == 20:
            row.update(kind='status_code', summary='灰（状態コード6）へ変更', value=6, executable_core=True)
        rows.append(row)
    return rows


def annotate_spells(rom, game, spells):
    """Only named, inspected families. Keep unknown mechanics explicitly partial."""
    ac_helper = {'wiz1': (0xa4b7, 0xa4c7), 'wiz2': (0x8efd,), 'wiz3': (0x8ec8,)}[game]
    healing_helper = {'wiz2': 0x8dc6, 'wiz3': 0x8da3}.get(game)
    addresses = sorted({s['effect']['handler_cpu_address'] for s in spells})
    for spell in spells:
        name = spell['name_en'].upper()
        effect = spell['effect']
        handler = effect['handler_cpu_address']
        limit = min((x for x in addresses if x > handler), default=handler + 96)
        start = effect['handler_rom_offset']
        code = rom[start:start + min(96, limit - handler)]
        if name in AC_TARGETS:
            constants = []
            for k in range(len(code) - 1):
                if code[k] == 0xa9 and signed(code[k + 1]) in (-4, -2, -1, 2, 3):
                    constants.append(signed(code[k + 1]))
            # Each inspected AC handler has one relevant immediate delta.
            if len(constants) == 1 and any(bytes([op, h & 255, h >> 8]) in code for h in ac_helper for op in (0x20, 0x4c)):
                effect.update(status='ac_parameters', kind='ac_modifier', delta=constants[0],
                              target=AC_TARGETS[name], minimum=-99, maximum=99,
                              scope='battle', semantics='AC値へ加算。負値は改善。',
                              limitation='対象範囲の照合はパーティ側の詠唱。敵側からの詠唱は未検証。')
        if name in ('DIOS', 'DIAL', 'DIALMA'):
            if game == 'wiz1':
                sides = next(code[k + 1] for k in range(len(code) - 3) if code[k:k + 1] == b'\xa9' and code[k + 2:k + 4] == b'\x85\x00')
                count = next(code[k + 1] for k in range(len(code) - 1) if code[k] == 0xa2)
                bonus = 0
            else:
                assert code[:3] == bytes([0x20, healing_helper & 255, healing_helper >> 8])
                count, sides, bonus = code[3:6]
            effect.update(status='healing_parameters', kind='healing', target='selected_ally',
                          healing=dict(count=count, sides=sides, bonus=bonus),
                          status_requirement='status_code < 5', capped_at_max_hp=True,
                          limitation='発動可否・メッセージ処理は別。')
    return spells


def equipment_rules(game):
    return dict(scope='装備済み1品の戦闘パラメータ加算部分。基礎値の再計算・装備可否判定は含まない。',
                attack_count_rule='max(current, item)' if game == 'wiz1' else 'clamp_signed_byte(current + item, 1, 10)',
                strength_rule='8ビット加算後、負値なら0' if game == 'wiz3' else '8ビット加算',
                ac_in_kernel=game == 'wiz1',
                routine_cpu_address={'wiz1': 0xafba, 'wiz2': 0xb435, 'wiz3': 0xb266}[game])
