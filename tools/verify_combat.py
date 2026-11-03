"""Compare attack arithmetic slices against verified Wiz1 JP ROM instructions."""
import json
import hashlib
from pathlib import Path
from rom_profiles import profile_for
from combat_rules import base_stats, player_threshold, enemy_threshold, signed, player_priority, enemy_priority
from trace_graphics import Bus, MPU


def run(cpu, start, stop):
    cpu.pc = start
    for _ in range(3000):
        if cpu.pc == stop:
            return
        cpu.step()
    raise AssertionError(f'Timeout {cpu.pc:04x}')


def verify(rom):
    if profile_for(rom)['id'] != 'wiz1':
        raise ValueError('Wiz1 JP only')
    bus = Bus(rom)
    bus.prgbank = 6
    cpu = MPU(memory=bus)
    bus.cpu = cpu
    bases = players = enemies = 0
    bus[0x2e], bus[0x2f] = 0, 0x60
    for cls in range(8):
        for level in [1, 2, 3, 4, 5, 10, 50, 254, 255, 256, 999]:
            for strength in range(26):
                cpu.x, cpu.sp = 0, 255
                cpu.stPushWord(0x6fff)
                bus[0x252], bus[0x7dc4], bus[0x7dca] = cls, level & 255, level >> 8
                bus[0x600d] = strength
                run(cpu, 0xaefa, 0x7000)
                actual = dict(hit=signed(bus[0x7ae2]), attacks=bus[0x7b60], damage_bonus=bus[0x7d8e])
                assert actual == base_stats(cls, level, strength), (cls, level, strength, actual)
                bases += 1
    for hit in range(-128, 128):
        for ac in range(-99, 100):
            for group in [1, 4]:
                cpu.x, cpu.y = 0, 6
                bus[0x6b], bus[0x7d34], bus[0x7ae2] = 19+group, ac & 255, hit & 255
                run(cpu, 0xbd39, 0xbd54)
                assert bus[0x6b] == player_threshold(hit, ac, group), (hit, ac, group)
                players += 1
    for parry in [False, True]:
        for referenced in [0, 1, 6, 10, 96, 127, 128, 255]:
            for level in [1, 5, 20, 25, 127, 255]:
                for ac in range(-99, 100):
                    cpu.y = 21 if parry else 19
                    bus[0x27d], bus[0x7dd6], bus[0x7e48], bus[0x7d34] = 6, referenced, level, ac & 255
                    run(cpu, 0xf9e7, 0xfa14)
                    assert bus[0x6b] == enemy_threshold(level, ac, referenced, parry), (parry, referenced, level, ac)
                    enemies += 1
    order_cases = 0
    for agility in range(19):
        for rolled in range(10):
            bus[0x6011], bus[0x38] = agility, 0
            cpu.sp = 255
            cpu.stPushWord(0x6fff)
            cpu.pc = 0xbf39
            for _ in range(100):
                if cpu.pc == 0x7000:
                    break
                if cpu.pc == 0xcdda:
                    cpu.a = rolled
                    cpu.pc = cpu.stPopWord()+1
                else:
                    cpu.step()
            assert cpu.pc == 0x7000
            assert bus[0x7cda] == player_priority(agility, rolled)
            order_cases += 1
    for rolled in range(256):
        cpu.a, cpu.x = rolled, 6
        run(cpu, 0xdc47, 0xdc4f)
        assert bus[0x7ce0] == enemy_priority(rolled)
        order_cases += 1
    return dict(matched=True, rom_sha256=hashlib.sha256(rom).hexdigest(), base_cases=bases, order_cases=order_cases,
                player_cases=players, enemy_cases=enemies,
                limitation='Arithmetic slices only; browser intentionally uses defender AC instead of original enemy-index bug; full combat/RNG sequence not verified')


if __name__ == '__main__':
    result = verify(Path('.nes/wiz1.nes').read_bytes())
    out = Path('output/combat')
    out.mkdir(parents=True, exist_ok=True)
    (out/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
