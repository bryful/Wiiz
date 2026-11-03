"""Differential verification of rule kernels against original CPU routines."""
import argparse
import json
from pathlib import Path
from item_spell_data import extract_data
from game_rules import equipment_contribution, modify_ac, special_power_core, heal_hp
from monster_data import signed
from trace_graphics import Bus, MPU
from mmc3_cpu_bus import Mmc3CpuBus


def machine(rom, game, bank):
    if game == 'wiz1':
        bus = Bus(rom)
        bus.prgbank = bank
        bus[0xfb] = bank
    else:
        bus = Mmc3CpuBus(rom)
        bus.registers[6:8] = [8 if bank == 13 else 12, bank]
    return bus


def execute(bus, entry, a=0, x=0, stop=0x7000, carry=0):
    cpu = MPU(memory=bus, pc=entry)
    if isinstance(bus, Bus):
        bus.cpu = cpu
    cpu.a, cpu.x = a, x
    cpu.p = (cpu.p & ~1) | carry
    cpu.stPushWord(0x6fff)
    for _ in range(30000):
        if cpu.pc == stop:
            return cpu
        cpu.step()
    raise AssertionError(f'CPU timeout: {cpu.pc:04X}')


def verify(rom):
    data = extract_data(rom)
    game = data['game']
    equipment_cases = ac_cases = sp_cases = ac_spell_cases = healing_cases = healing_parameter_cases = sp_dispatch_cases = 0
    locations = {
        'wiz1': dict(strength=0x7ae2, attacks=0x7b60, critical_raw=0x7b0c, count=0x7d82, sides=0x7d88, bonus=0x7d8e),
        'wiz2': dict(strength=0x29e, attacks=0x31c, critical_raw=0x2c8, count=0x53e, sides=0x544, bonus=0x54a),
        'wiz3': dict(strength=0x2be, attacks=0x33c, critical_raw=0x2e8, count=0x55e, sides=0x564, bonus=0x56a),
    }[game]
    for item in data['items']:
        alignments = [0, 1, 2] if game == 'wiz1' else [None]
        for alignment in alignments:
            for strength, attacks, bonus, ac, crit in [(0, 1, 0, 10, 0), (-3, 4, 255, -10, 128), (127, 10, 2, 99, 1)]:
                state = dict(strength=strength, attacks=attacks, damage=dict(count=2, sides=2, bonus=bonus), ac=ac, critical_raw=crit)
                bus = machine(rom, game, 6 if game == 'wiz1' else 13)
                raw = bytes.fromhex(item['source']['raw_hex'])
                if game == 'wiz1':
                    for j, value in enumerate(raw):
                        bus[0x500 + j] = value
                    bus[0x253], bus[0x7dd0] = alignment, ac & 255
                    matches = bool(item['stats']['alignment_raw'] & (1 << alignment))
                else:
                    pointer = item['source']['rom_offset'] - 0x10010 + 0x8000
                    bus[0x55], bus[0x56] = pointer & 255, pointer >> 8
                    matches = True
                for key, addr in locations.items():
                    bus[addr] = (state['damage'][key] if key in ('count', 'sides', 'bonus') else state[key]) & 255
                execute(bus, data['rules']['equipment']['routine_cpu_address'])
                actual = dict(ac=signed(bus[0x7dd0]) if game == 'wiz1' else state['ac'],
                              strength=signed(bus[locations['strength']]), attacks=bus[locations['attacks']],
                              critical_raw=bus[locations['critical_raw']],
                              damage={key: bus[locations[key]] for key in ('count', 'sides', 'bonus')})
                expected = equipment_contribution(game, state, item, matches)
                assert actual == expected, (game, item['id'], alignment, state, actual, expected)
                equipment_cases += 1
    # Exhaust the valid signed AC input range for each observed spell delta.
    for current in range(-99, 100):
        for delta in (-4, -2, -1, 2, 3):
            bus = machine(rom, game, 2 if game == 'wiz1' else 12)
            addr = {'wiz1': 0x7d2e, 'wiz2': 0x4ea, 'wiz3': 0x50a}[game]
            entry = (0xa4c7 if delta < 0 else 0xa4b7) if game == 'wiz1' else (0x8efd if game == 'wiz2' else 0x8ec8)
            bus[addr] = current & 255
            execute(bus, entry, a=delta & 255)
            assert signed(bus[addr]) == modify_ac(current, delta), (game, current, delta)
            ac_cases += 1
    # Test deterministic SP body AFTER activation/eligibility, without UI hooks.
    for power in data['rules']['special_powers']:
        if not power['executable_core']:
            continue
        samples = [(value, race) for value in (0, 1, 17, 18, 19, 20, 21, 22, 23, 127)
                   for race in (range(5) if game == 'wiz3' and power['kind'] == 'attribute_increase' else [None])]
        for value, race in samples:
            for carry in ((0, 1) if power['kind'] == 'max_hp_increase' else (0,)):
                character = bytearray([value] * 128)
                if race is not None:
                    character[0x0a] = (race << 5) | (value & 31)
                if power['kind'] == 'max_hp_increase':
                    character[0x1f:0x21] = {0: 0, 1: 1, 17: 255, 18: 256, 19: 32765, 20: 32766, 21: 32767, 22: 1000, 23: 10000, 127: 32767}[value].to_bytes(2, 'little')
                expected = special_power_core(character, power, carry)
                bus = machine(rom, game, 6 if game == 'wiz1' else 13)
                for j, byte in enumerate(character):
                    bus[0x6000 + j] = byte
                pointer = 0x2e if game == 'wiz1' else 0x3d
                bus[pointer], bus[pointer + 1] = 0, 0x60
                bus[0x5b] = power['id']
                entry = power['handler_cpu_address']
                stop = 0xb6e2 if game == 'wiz1' else 0x7000
                if game == 'wiz2':
                    # Skip precisely the first JSR B1AB (activation prompt/check).
                    entry += 3
                execute(bus, entry, stop=stop, carry=carry)
                actual = bytes(bus[0x6000 + j] for j in range(128))
                assert actual == expected, (game, power['id'], value, actual.hex(), expected.hex())
                sp_cases += 1
    for power in data['rules']['special_powers']:
        bus = machine(rom, game, 6 if game == 'wiz1' else 13)
        if game == 'wiz1':
            bus[0x525] = power['id']
            entry = 0xb6d0
        elif game == 'wiz2':
            bus[0x55], bus[0x56] = 0, 0x60
            bus[0x6025] = power['id']
            entry = 0xaff2
        else:
            bus[0x5b] = power['id']
            entry = 0xafad
        execute(bus, entry, stop=power['handler_cpu_address'])
        sp_dispatch_cases += 1
    for spell in data['spells']:
        effect = spell['effect']
        if effect.get('kind') == 'ac_modifier':
            bus = machine(rom, game, 2 if game == 'wiz1' else 12)
            ac_address = {'wiz1': 0x7d2e, 'wiz2': 0x4ea, 'wiz3': 0x50a}[game]
            bus[0x90], bus[0x99], bus[0x6e], bus[0x6b81] = 1, 2, 6, 4
            if game == 'wiz1':
                bus[0x7d5a] = 1  # caster 2 selects enemy group 1, first index 6
            execute(bus, effect['handler_cpu_address'], x=2)
            target = effect['target']
            expected_targets = {'caster': [2], 'enemy_group': list(range(6, 15)),
                                'all_enemies': list(range(6, 42)),
                                'party': list(range(6 if game == 'wiz1' else 4))}[target]
            actual = {i: signed(bus[ac_address + i]) for i in range(42) if bus[ac_address + i]}
            assert actual == {i: effect['delta'] for i in expected_targets}, (game, spell['name_en'], actual)
            ac_spell_cases += 1
        elif effect.get('kind') == 'healing':
            bus = machine(rom, game, 2 if game == 'wiz1' else 12)
            stop = {'wiz1': 0xacb2, 'wiz2': 0x8deb, 'wiz3': 0x8dbd}[game]
            bus[0x7d5a] = 1
            cpu = execute(bus, effect['handler_cpu_address'], x=2, stop=stop)
            actual = (cpu.x, bus[0], bus[1]) if game == 'wiz1' else (bus[0x91], bus[0x92], bus[0x93])
            healing = effect['healing']
            assert actual == (healing['count'], healing['sides'], healing['bonus']), (game, spell['name_en'])
            healing_parameter_cases += 1
    if game != 'wiz1':
        # Begin just after dice rolling; execute real target/status checks and HP updates.
        status_addr, low, high, max_low, max_high = ((0x370, 0x39a, 0x3c4, 0x3ee, 0x418)
                                                   if game == 'wiz2' else (0x390, 0x3ba, 0x3e4, 0x40e, 0x438))
        for status in range(8):
            for current, maximum in [(0, 10), (255, 256), (32760, 32767)]:
                for amount in (0, 1, 8, 24, 255):
                    bus = machine(rom, game, 12)
                    bus[status_addr] = status
                    bus[low], bus[high] = current & 255, current >> 8
                    bus[max_low], bus[max_high] = maximum & 255, maximum >> 8
                    bus[0x90], bus[0x6e], bus[0xb0] = 1, 0, amount
                    execute(bus, 0x8dee if game == 'wiz2' else 0x8dc0)
                    actual = bus[low] + 256 * bus[high]
                    assert actual == heal_hp(current, maximum, status, amount), (game, current, status, amount, actual)
                    healing_cases += 1
    return dict(game=game, sha256=data['sha256'], matched=True, equipment_cases=equipment_cases,
                ac_cases=ac_cases, special_power_body_cases=sp_cases,
                special_power_dispatch_cases=sp_dispatch_cases, ac_spell_target_cases=ac_spell_cases,
                healing_parameter_cases=healing_parameter_cases, healing_hp_cases=healing_cases,
                scope='Original subroutines vs independent rule kernels. Full stat rebuild, SP activation/replacement and whole battle are not verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
