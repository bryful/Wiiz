"""Original threshold/resistance and per-target affliction body comparisons."""
import argparse
import json
from pathlib import Path
from item_spell_data import extract_data
from monster_data import read_monster
from rom_profiles import profile_for
from affliction_rules import BASES, saving_threshold, resisted, inflict
from verify_game_rules import machine
from verify_status_rules import cpu_for, run

CONFIG = {
    'wiz1': dict(level=0x7c86, threshold=0xa54c, threshold_stop=0xa57c,
                 resistance=0x7dfe, status=0x7bb4, action=0x7cda, aux=0x7cb0, silence=0x7d04,
                 target_sleep=0xa5f1, target_manifo=0xaab2, target_montino=0xaaf3),
    'wiz2': dict(level=0x442, threshold=0x8f4d, threshold_stop=0x7000,
                 resistance=0x5ad, status=0x370, action=0x496, aux=0x6500, silence=0x4c0,
                 target_sleep=0x8fd0, target_manifo=0x8fd0, target_montino=0x9445),
    'wiz3': dict(level=0x462, threshold=0x8f2f, threshold_stop=0x7000,
                 resistance=0x5cd, status=0x390, action=0x4b6, aux=0x6500, silence=0x4e0,
                 target_sleep=0x8fb8, target_manifo=0x8fb8, target_montino=0x9425),
}


def verify(rom):
    data = extract_data(rom)
    game, cfg = data['game'], CONFIG[data['game']]
    bus = machine(rom, game, 2 if game == 'wiz1' else 12)
    thresholds = resistances = effects = monster_fields = group_cases = 0
    for base in sorted(set(BASES[game].values())):
        for caster in range(256):
            for target in range(256):
                bus[cfg['level']], bus[cfg['level'] + 6] = caster, target
                bus[0x0f], bus[0xb4] = base, 0
                cpu = cpu_for(bus, cfg['threshold'], x=0, a=base)
                cpu.y = 6
                run(cpu, {cfg['threshold_stop']})
                assert bus[0x0f] == saving_threshold(game, base, caster, target), (game, base, caster, target, bus[0x0f])
                thresholds += 1
        if game != 'wiz1':
            for caster in (0, 1, 127, 128, 255):
                for target in range(256):
                    bus[cfg['level']], bus[cfg['level'] + 6] = caster, target
                    bus[0x0f], bus[0xb4] = base, 100
                    cpu = cpu_for(bus, cfg['threshold'], x=0)
                    cpu.y = 6
                    run(cpu)
                    assert bus[0x0f] == saving_threshold(game, base, caster, target, 100)
                    thresholds += 1
    group = bus[0xdd36] if game == 'wiz1' else None
    for resistance in range(256):
        for value in range(256):
            if game == 'wiz1':
                bus[0x40], bus[0x41], bus[0x27c] = 0, value, 0
                bus[cfg['resistance'] + group] = resistance
                cpu = cpu_for(bus, 0xa534)
                cpu.y = 6
                run(cpu)
                actual = bool(cpu.a)
            else:
                bus[0x1e], bus[0x1d], bus[0x6e] = 0, value, 6
                bus[cfg['resistance'] + 6] = resistance
                cpu = cpu_for(bus, 0x8fda if game == 'wiz2' else 0x8fc2)
                blocked, allowed = ((0x900c, 0x8feb) if game == 'wiz2' else (0x8ff4, 0x8fd3))
                run(cpu, {blocked, allowed})
                actual = cpu.pc == blocked
            assert actual == resisted(game, resistance, value), (game, resistance, value)
            resistances += 1
    spells = {s['name_en'].upper(): s for s in data['spells']}
    # Check the original common group initializers in both caster directions.
    group_stops = {'wiz1': dict(KATINO=0xa5e8, MANIFO=0xaaac, MONTINO=0xaaed),
                   'wiz2': dict(KATINO=0x8fb2, MANIFO=0x8fa6, MONTINO=0x9441),
                   'wiz3': dict(KATINO=0x8f9a, MANIFO=0x8f91, MONTINO=0x9421)}[game]
    for spell in BASES[game]:
        for caster in (0, 6):
            bus[0x90], bus[0x99], bus[0x6e], bus[0x6b81] = 1, caster, 6, 3
            bus[0x7d58] = 1
            cpu = cpu_for(bus, spells[spell]['effect']['handler_cpu_address'], x=caster)
            run(cpu, {group_stops[spell]})
            actual = (bus[0x27d], bus[0x27e]) if game == 'wiz1' else (bus[0x6e], bus[0xb2])
            expected = (6, 9) if caster == 0 else (0, 6 if game == 'wiz1' else 3)
            assert actual == expected, (game, spell, caster, actual)
            group_cases += 1
    for spell in BASES[game]:
        for guard in ((False, True) if spell == 'KATINO' else (False,)):
            for caster, target in ((1, 1), (20, 1), (1, 20)):
                for resistance in (0, 128, 255):
                    for status in (0, 1, 4, 5, 7):
                        for counter in (0, 255):
                            for accumulator in range(0, 256, 17):
                                state = dict(status=status, action_raw=0x12, aux_action_raw=0x34, silence=7)
                                expected = inflict(game, spell, state, caster, target, resistance, counter, accumulator, guard)
                                bus[cfg['level']], bus[cfg['level'] + 6] = caster, target
                                for key, field in [('status', 'status'), ('action_raw', 'action'), ('aux_action_raw', 'aux'), ('silence', 'silence')]:
                                    bus[cfg[field] + 6] = state[key]
                                if game == 'wiz1':
                                    bus[cfg['resistance'] + group] = resistance
                                    bus[0x27c], bus[0x27d], bus[0x27e] = 0, 6, 1
                                    bus[0x7e6b] = 0x10 if guard else 0
                                    bus[0x40], bus[0x41] = counter, accumulator
                                else:
                                    bus[cfg['resistance'] + 6] = resistance
                                    bus[0x99], bus[0x6e], bus[0xb2] = 0, 6, 1
                                    bus[0xb4] = 100 if guard else 0
                                    bus[0x6f] = spells[spell]['id']
                                    bus[0x1e], bus[0x1d] = counter, accumulator
                                entry = cfg['target_sleep' if spell == 'KATINO' else 'target_manifo' if spell == 'MANIFO' else 'target_montino']
                                cpu = cpu_for(bus, entry)
                                cpu.y = 6
                                # Exclude presentation waits/messages; their RNG timing belongs
                                # to the caller. All effect/comparison/RNG instructions run intact.
                                excluded = {0xa3e2} if game == 'wiz1' else ({0xe4f3, 0x93f3} if game == 'wiz2' else {0xe221, 0x93d6})
                                for _ in range(10000):
                                    if cpu.pc == 0x7000:
                                        break
                                    if cpu.pc in excluded:
                                        cpu.pc = (cpu.stPopWord() + 1) & 65535
                                    else:
                                        cpu.step()
                                else:
                                    raise AssertionError('Effect timeout')
                                actual = {key: bus[cfg[field] + 6] for key, field in [('status', 'status'), ('action_raw', 'action'), ('aux_action_raw', 'aux'), ('silence', 'silence')]}
                                assert actual == expected['state'], (game, spell, guard, caster, target, resistance, status, counter, accumulator, actual, expected)
                                low, high = (0x40, 0x41) if game == 'wiz1' else (0x1e, 0x1d)
                                assert dict(counter=bus[low], accumulator=bus[high]) == expected['rng'], (game, spell, 'RNG')
                                effects += 1
    for monster_id in range(profile_for(rom)['count']):
        monster = read_monster(rom, monster_id)
        bus = machine(rom, game, 2 if game == 'wiz1' else 13)
        if game != 'wiz1':
            bus[0x7e], bus[0x7f] = 12, 13
        cpu = cpu_for(bus, {'wiz1': 0xcfc8, 'wiz2': 0xff8f, 'wiz3': 0xde97}[game], a=monster_id)
        run(cpu)
        magic, flags, level = (0x7e69, 0x7e6b, 0x7e48) if game == 'wiz1' else (0x252, 0x254, 0x245)
        assert (bus[magic], bus[flags], bus[level]) == (monster['stats']['magic_resistance_raw'], monster['stats']['status_flags_raw'], monster['stats']['level'])
        monster_fields += 1
    return dict(game=game, sha256=data['sha256'], matched=True, threshold_cases=thresholds,
                resistance_cases=resistances, target_effect_cases=effects, monster_field_cases=monster_fields, group_cases=group_cases,
                scope='Selected enemy target after selection/loading. Presentation waits/messages bypassed. No full turn or natural recovery verification.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
