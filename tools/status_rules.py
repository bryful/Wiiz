"""Status labels, cures and resurrection rules derived from the supported ROMs."""
from monster_data import decode_japanese
from game_rng import scaled_roll

FIELDS = ('status', 'poison', 'hp', 'max_hp', 'vitality')


def status_data(rom, game):
    en, ja, stride = {'wiz1': (0x278d, 0x678d, 6), 'wiz2': (0x1f72f, 0x1f77f, 8),
                      'wiz3': (0x1f7b3, 0x1f803, 8)}[game]
    rows = []
    for i in range(9):
        english = list(rom[en + stride * i:en + stride * (i + 1)])
        japanese = list(rom[ja + stride * i:ja + stride * (i + 1)])
        label = decode_japanese(english, game).strip()
        if game == 'wiz1':
            label = label.replace('ー', '-')
        rows.append(dict(code=i, name_en=label, name_ja=decode_japanese(japanese, game).strip(),
                         name_codes=dict(en=english, ja=japanese),
                         source=dict(en_rom_offset=en + stride * i, ja_rom_offset=ja + stride * i)))
    return dict(statuses=rows[:8], poison_display=rows[8],
                note='毒は状態コード8ではなく別の値。正常時の表示で毒を優先する。')


def display_status_index(status, poison):
    if not 0 <= status <= 7 or not 0 <= poison <= 255:
        raise ValueError('Invalid display status')
    return 8 if status == 0 and poison else status


def checked(state):
    if not 0 <= state['status'] <= 7 or not 0 <= state['poison'] <= 255:
        raise ValueError('Invalid status/poison value')
    if not 0 <= state['hp'] <= state['max_hp'] <= 32767 or not 0 <= state['vitality'] <= 22:
        raise ValueError('Outside verified HP/vitality range')
    return dict(state)


def cure(game, spell, state):
    """Apply selected DIALKO/LATUMOFIS/MADI; no cast eligibility or messages."""
    if game not in ('wiz1', 'wiz2', 'wiz3') or spell not in ('DIALKO', 'LATUMOFIS', 'MADI'):
        raise ValueError('Unsupported cure')
    result = checked(state)
    if spell == 'DIALKO' and state['status'] < 4:
        result['status'] = 0
    elif spell == 'LATUMOFIS' and (game == 'wiz1' or state['status'] < 5):
        result['poison'] = 0
    elif spell == 'MADI' and state['status'] < 5:
        result.update(status=0, poison=0, hp=state['max_hp'])
    return result


def resurrect(game, spell, state, counter, accumulator, context='camp'):
    """Apply DI/KADORTO using exact RNG scaling and return updated RNG state.

    Dead/ashed/lost input must have zero current HP. Full spell selection,
    resource consumption and UI messages remain outside this function.
    """
    if game not in ('wiz1', 'wiz2', 'wiz3') or spell not in ('DI', 'KADORTO') or context not in ('camp', 'battle'):
        raise ValueError('Unsupported resurrection')
    if game == 'wiz1' and context != 'camp':
        raise ValueError('Wiz1 resurrection is verified for camp use only')
    if not 0 <= counter <= 255 or not 0 <= accumulator <= 255:
        raise ValueError('RNG state must contain two bytes')
    result = checked(state)
    if state['max_hp'] < 1:
        raise ValueError('Resurrection requires a positive maximum HP')
    if state['status'] >= 5 and state['hp'] != 0:
        raise ValueError('Dead/ashed/lost inputs require zero HP')
    rng = dict(counter=counter, accumulator=accumulator)
    if game != 'wiz1' and spell == 'DI' and context == 'battle':
        return dict(state=result, rng=rng, attempted=False, success=False)
    eligible = state['status'] == 5 or (spell == 'KADORTO' and state['status'] == 6)
    if not eligible:
        return dict(state=result, rng=rng, attempted=False, success=False)
    success = False
    vitality = state['vitality']
    if vitality >= 4:
        roll = scaled_roll(game, counter, accumulator, 25 if game == 'wiz1' else 100)
        rng = {k: roll[k] for k in ('counter', 'accumulator')}
        if game == 'wiz1':
            success = roll['value'] <= vitality
            if success:
                result['vitality'] -= 1
        else:
            result['vitality'] -= 1
            success = roll['value'] <= 4 * result['vitality']
    if success:
        result['status'] = 0
        if game == 'wiz1':
            result['poison'] = 0
        result['hp'] = 1 if spell == 'DI' else state['max_hp']
    else:
        result['status'] = state['status'] + 1 if game == 'wiz1' or vitality >= 4 else 7
        result['hp'] = 0
    return dict(state=result, rng=rng, attempted=True, success=success)


def annotate(spells, game):
    for spell in spells:
        name = spell['name_en'].upper()
        if name in ('DIALKO', 'LATUMOFIS', 'MADI'):
            summaries = dict(DIALKO='睡眠・恐怖・麻痺を治療（状態コード4未満）',
                             LATUMOFIS='毒の値を0へ' + ('（死亡以上にも適用）' if game == 'wiz1' else '（状態コード5未満）'),
                             MADI='石化までの状態と毒を治療し、HPを最大値へ')
            spell['effect'].update(status='cure_rules', kind='status_cure', summary=summaries[name], target='selected_ally',
                                   accepted_status_codes=list(range(4 if name == 'DIALKO' else 8 if name == 'LATUMOFIS' and game == 'wiz1' else 5)),
                                   limitation='対象決定後の効果。発動条件・消費・メッセージは別。')
        elif name in ('DI', 'KADORTO'):
            spell['effect'].update(status='resurrection_rules', kind='resurrection', target='selected_ally',
                                   summary=('死亡をHP1で蘇生' if name == 'DI' else '死亡・灰を最大HPで蘇生'),
                                   effect_contexts=['camp', 'battle'] if game != 'wiz1' and name == 'KADORTO' else ['camp'],
                                   accepted_status_codes=[5] if name == 'DI' else [5, 6],
                                   minimum_vitality_for_roll=4,
                                   success_rule='scaled25 <= vitality_before' if game == 'wiz1' else 'scaled100 <= 4 * (vitality_before - 1)',
                                   vitality_cost='success_only' if game == 'wiz1' else 'before_roll_when_vitality_at_least_4',
                                   clears_poison_on_success=game == 'wiz1',
                                   low_vitality_failure='next_status' if game == 'wiz1' else 'lost',
                                   limitation='成功判定・生命力低下・失敗時の状態変化は作品別。死亡以上の現在HPは0を前提。')
    return spells
