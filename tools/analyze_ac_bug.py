"""Run original/patched Wiz1 JP hit-calculation instructions with existing py65.

Patches are read as research inputs, applied in memory only, never redistributed.
This checks CPU slices, not complete NES execution or RNG distribution.
"""
import hashlib
import json
from pathlib import Path

from trace_graphics import Bus, MPU
from rom_profiles import profile_for


def patched(rom, path):
    raw = path.read_bytes()
    assert raw[:5] == b'PATCH'
    result = bytearray(rom)
    pos = 5
    while raw[pos:pos + 3] != b'EOF':
        offset = int.from_bytes(raw[pos:pos + 3], 'big')
        size = int.from_bytes(raw[pos + 3:pos + 5], 'big')
        pos += 5
        if size:
            data = raw[pos:pos + size]
            pos += size
        else:
            size = int.from_bytes(raw[pos:pos + 2], 'big')
            data = raw[pos + 2:pos + 3] * size
            pos += 3
        result[offset:offset + size] = data
    return bytes(result)


def threshold(rom, enemy=6, target=0, level=10, enemy_ac=-3,
              player_ac=10, poison=0, roster_page=0x60, parry=True,
              personal=0, maporfic=0):
    bus = Bus(rom)
    bus.prgbank = 6
    cpu = MPU(memory=bus)
    bus.cpu = cpu
    bus[0x27c], bus[0x27d] = target, enemy
    for i in range(6):
        bus[0x7dd0 + i] = player_ac & 255
        bus[0x7dd6 + i] = poison
        bus[0x7ddc + i] = roster_page
        bus[0x7d2e + i] = personal & 255
        bus[0x7cb0 + i] = 0 if parry else 1
    bus[0x281], bus[0x7e48] = maporfic & 255, level
    bus[0x7d2e + enemy] = enemy_ac & 255
    # CFBD loads monster data; start immediately after it with the same registers
    # as the following LDY/LDX instructions establish themselves.
    cpu.pc = 0xf9db
    for _ in range(100):
        if cpu.pc == 0xfa14:
            return bus[0x6b]
        cpu.step()
    raise AssertionError(f'timeout {cpu.pc:04x}')


def analyze():
    rom = Path('.nes/wiz1.nes').read_bytes()
    assert profile_for(rom)['id'] == 'wiz1'
    assert rom[0x1f9f8:0x1f9fb] == bytes.fromhex('ac7d02')
    paths = {p.name: p for p in Path('reference/patch/fc').rglob('*.ips')}
    versions = {'original': rom}
    for name in ('wizardry_pg_fc_fix.ips', 'wiz1patch.ips'):
        versions[name] = patched(rom, paths[name])
    cases = [
        ('murphy_ac10', {}, [25, 90, 90]),
        ('murphy_ac0', {'player_ac': 0}, [25, 40, 40]),
        ('murphy_ac-12', {'player_ac': -12}, [25, 0, 0]),
        ('murphy_no_parry', {'parry': False}, [35, 95, 95]),
        ('murphy_mamorlis3', {'enemy_ac': 6}, [70, 90, 90]),
        ('murphy_poison4', {'poison': 4}, [45, 90, 90]),
        ('murphy_maporfic', {'maporfic': -2}, [25, 80, 90]),
        ('murphy_personal', {'personal': -4}, [25, 70, 70]),
        ('ninja_g2_1', {'enemy': 15, 'level': 6, 'enemy_ac': 6}, [95, 70, 70]),
        ('ninja_g2_1_absent_rear', {'enemy': 15, 'level': 6, 'enemy_ac': 6, 'roster_page': 0}, [50, 70, 70]),
    ]
    rows = []
    for label, args, expected in cases:
        values = {name: (20 - threshold(data, **args)) * 5 for name, data in versions.items()}
        assert list(values.values()) == expected, (label, values, expected)
        rows.append(dict(case=label, inputs=args, nominal_hit_percent=values))
    # All 36 enemy indices and all defender slots: the patch removes dependence
    # on adjacent poison/roster data, including the positions highlighted online.
    checks = 0
    for data in versions.values():
        for enemy in range(6, 42):
            for target in range(6):
                for ac in (10, 0, -12):
                    for parry in (False, True):
                        value = threshold(data, enemy=enemy, target=target, player_ac=ac, parry=parry)
                        assert 1 <= value <= 20
                        if data != rom:
                            expected = max(0, min(95, (10 + ac - (2 if parry else 0)) * 5))
                            assert (20 - value) * 5 == expected
                        checks += 1
    return dict(rom_sha256=hashlib.sha256(rom).hexdigest(), cases=rows,
                instruction_slice_cases=checks + len(rows) * len(versions),
                patch_sha256={n: hashlib.sha256(paths[n].read_bytes()).hexdigest() for n in versions if n != 'original'},
                limitation='CPU slices with prepared RAM; no full battle, live emulator or RNG distribution validation')


if __name__ == '__main__':
    report = analyze()
    out = Path('output/ac-bug-analysis.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

