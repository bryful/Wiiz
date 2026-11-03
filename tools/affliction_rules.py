"""Selected-target KATINO/MANIFO/MONTINO effects after presentation waits."""
from game_rng import next_byte, scaled_roll

BASES = {'wiz1': dict(KATINO=50, MANIFO=50, MONTINO=40),
         'wiz2': dict(KATINO=50, MANIFO=50, MONTINO=40),
         'wiz3': dict(KATINO=10, MANIFO=10, MONTINO=8)}


def saving_threshold(game, base, caster_level, target_level, modifier=0):
    """Byte-exact thresholds; don't replace these with a shared percentage."""
    if game not in BASES or any(not 0 <= v <= 255 for v in (base, caster_level, target_level, modifier)):
        raise ValueError('Expected supported game and byte parameters')
    if base not in BASES[game].values() or modifier not in (0, 100):
        raise ValueError('Outside inspected spell parameters')
    if game == 'wiz1':
        difference = (target_level - caster_level) & 255
        if target_level < caster_level:
            value = (difference * 5) & 255
            threshold = (value + base) & 255 if value >= 128 else 5
            if value >= 128 and threshold >= 128:
                threshold = 5
        else:
            total = difference * 5
            threshold = 200 if difference * 4 > 255 or total > 255 or total + base > 255 else total + base
        if modifier:
            threshold = max(5, threshold - modifier)
        return threshold
    total = base + target_level
    if game == 'wiz2':
        value = 127 if total > 127 else total
        value = value - caster_level if value >= caster_level else 5
    else:
        value = min(255, total)
        value = value - caster_level if value >= caster_level else 1
        value = min(255, value * 5)
    return value - modifier if value >= modifier else 5


def resisted(game, resistance, rng_byte):
    if game not in BASES or not 0 <= resistance <= 255 or not 0 <= rng_byte <= 255:
        raise ValueError('Invalid resistance check')
    return rng_byte < resistance or (game != 'wiz1' and resistance == 255)


def inflict(game, spell, state, caster_level, target_level, resistance, counter, accumulator,
            katino_modifier_flag=False, target_is_enemy=True):
    """Apply one target; cast selection, monster loading and presentation excluded."""
    if game not in BASES or spell not in BASES[game]:
        raise ValueError('Unsupported affliction spell')
    if not 0 <= resistance <= 255:
        raise ValueError('Invalid resistance byte')
    if not 0 <= state['status'] <= 7 or any(not 0 <= state[k] <= 255 for k in ('action_raw', 'aux_action_raw', 'silence')):
        raise ValueError('Invalid target state')
    # Validate RNG even when this target will be skipped.
    next_byte(counter, accumulator)
    threshold = saving_threshold(game, BASES[game][spell], caster_level, target_level,
                                 100 if spell == 'KATINO' and katino_modifier_flag and target_is_enemy else 0)
    result, rng = dict(state), dict(counter=counter, accumulator=accumulator)
    eligible = state['status'] < 5 if spell == 'MONTINO' else state['status'] == 0
    outcome, calls = 'skipped_status', 0
    if eligible:
        first = next_byte(**rng)
        rng = {k: first[k] for k in ('counter', 'accumulator')}
        calls = 1
        outcome = 'resisted'
        if not resisted(game, resistance, first['value']):
            roll = scaled_roll(game, **rng, limit=100)
            rng = {k: roll[k] for k in ('counter', 'accumulator')}
            calls += 1
            outcome = 'saved'
            if threshold < roll['value']:
                outcome = 'applied'
                if spell == 'MONTINO':
                    duration = next_byte(**rng)
                    rng = {k: duration[k] for k in ('counter', 'accumulator')}
                    calls += 1
                    result['silence'] = (duration['value'] & 3) + 2
                else:
                    result.update(status=1, action_raw=255)
                    if game == 'wiz1':
                        result['aux_action_raw'] = 255
    return dict(state=result, rng=rng, rng_calls=calls, outcome=outcome, threshold=threshold)


def annotate(spells, game):
    for spell in spells:
        name = spell['name_en'].upper()
        if name not in BASES[game]:
            continue
        spell['effect'].update(status='affliction_rules', kind='status_infliction',
                              summary='沈黙カウンターを2〜5へ設定' if name == 'MONTINO' else '睡眠（状態コード1）を設定し、行動値をFFへ',
                              target='enemy_group', base_parameter=BASES[game][name],
                              accepted_status_codes=list(range(5)) if name == 'MONTINO' else [0],
                              success_comparison='saving_threshold < scaled_rng100',
                              resistance_ff_always_blocks=game != 'wiz1',
                              katino_flag_modifier=100 if name == 'KATINO' else 0,
                              threshold_helper_cpu_address={'wiz1': 0xa54c, 'wiz2': 0x8f40, 'wiz3': 0x8f22}[game],
                              player_target_slots=9,
                              limitation='対象決定と表示待ちの後。抵抗とレベル判定は作品別。沈黙値の減少処理は未解析。')
    return spells
