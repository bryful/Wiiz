"""Compare confirmed item-use transitions with the original ROM code.

No UI hooks or patched ROM bytes: normal replacement code runs intact; SP
resolution resumes after the confirmation UI and retains its real continuation.
"""
import argparse
import json
from pathlib import Path
from item_spell_data import extract_data
from item_use_rules import replacement, sp_eligibility, resolve_sp
from verify_game_rules import machine
from trace_graphics import Bus, MPU


def cpu_for(bus, entry, y=0, x=0, returns=(0x6fff,)):
    cpu = MPU(memory=bus, pc=entry)
    if isinstance(bus, Bus):
        bus.cpu = cpu
    cpu.y, cpu.x = y, x
    for address in returns:
        cpu.stPushWord(address)
    return cpu


def advance(cpu, stops):
    for _ in range(30000):
        if cpu.pc in stops:
            return
        cpu.step()
    raise AssertionError(f'Timeout at {cpu.pc:04X}')


def prepare(bus, game, item, character=None):
    if character is not None:
        for i, value in enumerate(character):
            bus[0x6000 + i] = value
    ptr = 0x2e if game == 'wiz1' else 0x3d
    bus[ptr], bus[ptr + 1] = 0, 0x60
    if game == 'wiz1':
        for i, value in enumerate(bytes.fromhex(item['source']['raw_hex'])):
            bus[0x500 + i] = value
    else:
        source = item['source']['rom_offset'] - 0x10010 + 0x8000
        bus[0x55], bus[0x56] = source & 255, source >> 8


def seed(bus, game, roll):
    if game == 'wiz1':
        bus[0x40], bus[0x41] = 0, roll
    else:
        bus[0x1d], bus[0x1e] = roll, 0


def verify(rom):
    data = extract_data(rom)
    game = data['game']
    normal_cases = eligibility_cases = sp_cases = 0
    for item in data['items']:
        bus = machine(rom, game, 6 if game == 'wiz1' else 13)
        prepare(bus, game, item)
        flag_offset, id_offset = (0x4c, 0x54) if game == 'wiz1' else (0x43, 0x4b)
        # All RNG bytes for every actual record; repeat representative flag bits.
        for flags in (0, 0x80, 0xe0):
            for roll in range(256):
                expected = replacement(game, item, flags, roll)
                bus[0x6000 + flag_offset], bus[0x6000 + id_offset] = flags, item['id']
                seed(bus, game, roll)
                bus[0x6f] = id_offset
                entry = {'wiz1': 0xbf9d, 'wiz2': 0xb348, 'wiz3': 0xb19a}[game]
                cpu = cpu_for(bus, entry, y=id_offset)
                advance(cpu, {'wiz1': {0xbfbd}, 'wiz2': {0xb36d, 0xb376}, 'wiz3': {0xb1bf, 0xb1c8}}[game])
                actual = dict(item_id=bus[0x6000 + id_offset], flags=bus[0x6000 + flag_offset],
                              rng_consumed=bool(bus[0x40 if game == 'wiz1' else 0x1e]))
                assert actual == {k: expected[k] for k in actual}, (game, item['id'], roll, flags, actual, expected)
                if game != 'wiz1':
                    assert bus[0x6f] == item['stats']['use_spell_raw'] & 63
                normal_cases += 1
        # Original class gates. I also checks SP presence before the prompt.
        if game == 'wiz1' or item['stats']['special_power_raw'] != 0:
            for class_id in range(8):
                character = bytearray(128)
                character[0x0a] = class_id << 2
                prepare(bus, game, item, character)
                bus[0x252] = class_id
                entry = {'wiz1': 0xb675, 'wiz2': 0xb1ab, 'wiz3': 0xafff}[game]
                accepted, denied = {'wiz1': (0xb687, 0xb695), 'wiz2': (0xb1bd, 0xb200), 'wiz3': (0xb011, 0xb054)}[game]
                cpu = cpu_for(bus, entry)
                advance(cpu, {accepted, denied})
                assert (cpu.pc == accepted) == sp_eligibility(game, item, class_id)['eligible'], (game, item['id'], class_id)
                eligibility_cases += 1
        power = item.get('special_power')
        if not power or not power['executable_core']:
            continue
        class_id = next((i for i in range(8) if item['stats']['equip_mask'] & (1 << i)), None)
        if class_id is None:
            continue
        threshold = item['stats']['break_raw']
        rolls = sorted({0, 255, threshold, max(0, threshold - 1), min(255, threshold + 1)})
        # SP22 uses all 256 RNG bytes to resolve the previously unknown carry path.
        if power['id'] == 22:
            rolls = range(256)
        for flags in range(0, 256, 32):
            for roll in rolls:
                bus = machine(rom, game, 6 if game == 'wiz1' else 13)
                character = bytearray([17] * 128)
                character[0x0a], character[0x0b] = class_id << 2, class_id if game == 'wiz1' else 17
                character[0x1f:0x21] = (200).to_bytes(2, 'little')
                character[flag_offset], character[id_offset] = flags, item['id']
                expected = resolve_sp(game, character, item, roll=roll)
                prepare(bus, game, item, character)
                seed(bus, game, roll)
                bus[0x51], bus[0x5b] = 0, power['id']
                bus[0x40], bus[0x48] = flags, item['id']
                if game == 'wiz1':
                    # Effect -> queued replacement, both original code paths.
                    seed(bus, game, roll)  # $40 is RNG state in I, not a slot flag.
                    cpu = cpu_for(bus, power['handler_cpu_address'])
                    advance(cpu, {0xb6e2})
                    bus[0x4e], bus[0x3a] = 0, 0
                    advance(cpu, {0xbfbd})
                else:
                    continuation = power['handler_cpu_address'] + 2 if game == 'wiz2' else 0xafaa
                    cpu = cpu_for(bus, 0xb1bd if game == 'wiz2' else 0xb011, returns=(0x6fff, continuation))
                    advance(cpu, {0xb1d0 if game == 'wiz2' else 0xb024})
                    # Confirmation accepted; resume actual RNG/compare/replace.
                    cpu.pc = 0xb1e7 if game == 'wiz2' else 0xb03b
                    advance(cpu, {0x7000 if game == 'wiz2' else 0xafeb})
                    # Commit the working slot just as the inventory writeback does.
                    bus[0x6000 + flag_offset], bus[0x6000 + id_offset] = bus[0x40], bus[0x48]
                actual = bytes(bus[0x6000 + i] for i in range(128))
                assert actual == expected['character'], (game, item['id'], flags, roll, actual.hex(), expected['character'].hex())
                sp_cases += 1
    return dict(game=game, sha256=data['sha256'], matched=True, normal_replacement_cases=normal_cases,
                sp_eligibility_cases=eligibility_cases, confirmed_sp_transition_cases=sp_cases,
                scope='Confirmed use, RNG byte, record replacement and supported SP bodies. UI, normal-use context gates, derived stat rebuild and unknown SP bodies are excluded.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
