"""Verify RNG, status display selection, cures and resurrection against ROM code."""
import argparse
import json
from pathlib import Path
from item_spell_data import extract_data
from status_rules import status_data, display_status_index, cure, resurrect
from game_rng import next_byte, scaled_roll
from verify_game_rules import machine
from trace_graphics import Bus, MPU


def cpu_for(bus, pc, x=0, a=0):
    cpu = MPU(memory=bus, pc=pc)
    if isinstance(bus, Bus):
        bus.cpu = cpu
    cpu.x, cpu.a = x, a
    cpu.stPushWord(0x6fff)
    return cpu


def run(cpu, stops=(0x7000,)):
    for _ in range(30000):
        if cpu.pc in stops:
            return
        cpu.step()
    raise AssertionError(f'Timeout {cpu.pc:04X}')


def put_word(bus, address, value):
    bus[address], bus[address + 1] = value & 255, value >> 8


def addresses(game):
    return (dict(status=0x7bb5, poison=0x7dd7, hp_lo=0x7bdf, hp_hi=0x7c09, max_lo=0x7c33, max_hi=0x7c5d)
            if game == 'wiz1' else
            dict(status=0x371, poison=0x593, hp_lo=0x39b, hp_hi=0x3c5, max_lo=0x3ef, max_hi=0x419)
            if game == 'wiz2' else
            dict(status=0x391, poison=0x5b3, hp_lo=0x3bb, hp_hi=0x3e5, max_lo=0x40f, max_hi=0x439))


def setup(bus, game, state, context, counter=0, accumulator=0):
    put_word(bus, 0x7fc0, 0x6000)
    put_word(bus, 0x3d, 0x6000)
    bus[0x6b83], bus[0x6e] = 0, 1
    bus[0x90], bus[0x28e] = int(context == 'battle'), int(context == 'battle')
    bus[0x7d58], bus[0x7ddd] = 1, 0x60
    bus[0x6010 if game == 'wiz1' else 0x600e] = state['vitality']
    bus[0x6023], bus[0x6054] = state['status'], state['poison']
    put_word(bus, 0x601d, state['hp'])
    put_word(bus, 0x601f, state['max_hp'])
    locations = addresses(game)
    for key in ('status', 'poison'):
        bus[locations[key]] = state[key]
    for key in ('hp', 'max'):
        value = state['hp' if key == 'hp' else 'max_hp']
        bus[locations[key + '_lo']], bus[locations[key + '_hi']] = value & 255, value >> 8
    low, high = (0x40, 0x41) if game == 'wiz1' else (0x1e, 0x1d)
    bus[low], bus[high] = counter, accumulator


def read_state(bus, game, context):
    if game != 'wiz1' and context == 'camp':
        return dict(status=bus[0x6023], poison=bus[0x6054], hp=bus[0x601d] + 256 * bus[0x601e],
                    max_hp=bus[0x601f] + 256 * bus[0x6020], vitality=bus[0x600e])
    p = addresses(game)
    return dict(status=bus[p['status']], poison=bus[p['poison']], hp=bus[p['hp_lo']] + 256 * bus[p['hp_hi']],
                max_hp=bus[p['max_lo']] + 256 * bus[p['max_hi']], vitality=bus[0x6010 if game == 'wiz1' else 0x600e])


def verify(rom):
    data = extract_data(rom)
    game = data['game']
    byte_cases = scaled_cases = display_cases = cure_cases = resurrection_cases = 0
    bus = machine(rom, game, 2 if game == 'wiz1' else 12)
    low, high = (0x40, 0x41) if game == 'wiz1' else (0x1e, 0x1d)
    byte_entry = {'wiz1': 0xc2a1, 'wiz2': 0xf01b, 'wiz3': 0xed03}[game]
    for counter in range(256):
        for accumulator in range(256):
            bus[low], bus[high] = counter, accumulator
            cpu = cpu_for(bus, byte_entry)
            run(cpu)
            assert dict(counter=bus[low], accumulator=bus[high], value=cpu.a) == next_byte(counter, accumulator)
            byte_cases += 1
    for counter in (0, 1, 17, 255):
        for accumulator in range(256):
            for limit in (1, 25, 100, 255):
                bus[low], bus[high] = counter, accumulator
                cpu = cpu_for(bus, {'wiz1': 0xcdda, 'wiz2': 0xf028, 'wiz3': 0xed10}[game], a=limit)
                run(cpu)
                assert dict(counter=bus[low], accumulator=bus[high], value=cpu.a) == scaled_roll(game, counter, accumulator, limit), (game, counter, accumulator, limit)
                scaled_cases += 1
    labels = status_data(rom, game)
    if game == 'wiz1':
        for jp in (False, True):
            for code, row in enumerate(labels['statuses'] + [labels['poison_display']]):
                table = 0x65e0 if jp else 0x25e0
                ptr = int.from_bytes(rom[table + 2 * code:table + 2 * code + 2], 'little')
                offset = (0x4010 if jp else 0x10) + ptr - 0x8000
                assert list(rom[offset:offset + 6]) == row['name_codes']['ja' if jp else 'en']
                display_cases += 1
    else:
        writer = 0xf3f3 if game == 'wiz2' else 0xf46c
        for jp in (False, True):
            for status in range(8):
                for poison in (0, 255):
                    put_word(bus, 0x0e, 0x6000)
                    bus[0x6023], bus[0x6054] = status, poison
                    bus[0x77f7 if game == 'wiz2' else 0x6d9e] = int(jp)
                    cpu = cpu_for(bus, 0xf6f5 if game == 'wiz2' else 0xf779)
                    captured = []
                    for _ in range(1000):
                        if cpu.pc == 0x7000:
                            break
                        if cpu.pc == writer:
                            captured.append(cpu.a)
                            cpu.pc = (cpu.stPopWord() + 1) & 65535
                        else:
                            cpu.step()
                    else:
                        raise AssertionError('Display timeout')
                    code = display_status_index(status, poison)
                    row = labels['poison_display'] if code == 8 else labels['statuses'][code]
                    assert captured == row['name_codes']['ja' if jp else 'en']
                    display_cases += 1
    spells = {s['name_en'].upper(): s for s in data['spells']}
    message_stops = {0x7000, 0xe91a, 0xa3e2} if game == 'wiz1' else ({0x7000, 0xe5c9, 0x93f3} if game == 'wiz2' else {0x7000, 0xe2f7, 0x93d6})
    for spell in ('DIALKO', 'LATUMOFIS', 'MADI'):
        for context in ('camp', 'battle'):
            for status in range(8):
                for poison in (0, 1, 255):
                    for hp, maximum in ((0, 1), (255, 257), (32760, 32767)):
                        state = dict(status=status, poison=poison, hp=hp, max_hp=maximum, vitality=18)
                        setup(bus, game, state, context)
                        cpu = cpu_for(bus, spells[spell]['effect']['handler_cpu_address'])
                        run(cpu, message_stops)
                        actual = read_state(bus, game, context)
                        assert actual == cure(game, spell, state), (game, spell, context, state, actual)
                        cure_cases += 1
    for spell in ('DI', 'KADORTO'):
        for context in (('camp',) if game == 'wiz1' else ('camp', 'battle')):
            for status in range(8):
                for vitality in ((3, 4, 18, 22) if status in (5, 6) else (3, 18)):
                    for counter in ((0, 255) if status in (5, 6) else (0,)):
                        for accumulator in (range(256) if status in (5, 6) else (0, 128, 255)):
                            state = dict(status=status, poison=255, hp=0 if status >= 5 else 10, max_hp=257, vitality=vitality)
                            expected = resurrect(game, spell, state, counter, accumulator, context)
                            setup(bus, game, state, context, counter, accumulator)
                            bus[0x6f] = spells[spell]['id']
                            cpu = cpu_for(bus, spells[spell]['effect']['handler_cpu_address'])
                            run(cpu, message_stops)
                            actual = read_state(bus, game, context)
                            assert actual == expected['state'], (game, spell, context, status, vitality, counter, accumulator, actual, expected)
                            assert dict(counter=bus[low], accumulator=bus[high]) == expected['rng']
                            resurrection_cases += 1
    return dict(game=game, sha256=data['sha256'], matched=True, rng_byte_cases=byte_cases,
                rng_scaled_cases=scaled_cases, status_label_cases=display_cases, cure_cases=cure_cases,
                resurrection_cases=resurrection_cases,
                scope='RNG, selected-target cure/resurrection bodies; menu eligibility/resource use excluded. Later status display captures bytes before the text writer; I verifies label pointers.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
