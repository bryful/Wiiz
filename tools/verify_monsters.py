"""Cross-check every extracted layout against execution of the original 6502 routine."""
import argparse
import hashlib
import json
from pathlib import Path
from extract_monsters import parse_layout
from trace_graphics import Bus, MPU
from rom_profiles import profile_for


def verify(rom):
    sha = hashlib.sha256(rom).hexdigest()
    profile = profile_for(rom)
    checked = 0
    digest = hashlib.sha256()
    for monster_id in range(profile['count']):
        for identified in (False, True):
            if profile['mapper'] == 1:
                bus = Bus(rom)
                bus.prgbank = 3
                cpu = MPU(memory=bus, pc=0x8000)
                bus.cpu = cpu
                bus[0x7ad2] = monster_id
                bus[0x238] = int(identified)
            else:
                from mmc3_cpu_bus import Mmc3CpuBus
                bus = Mmc3CpuBus(rom)
                bus.registers[6:8] = profile['prg_banks']
                cpu = MPU(memory=bus, pc=profile['routine'])
                bus[profile['id_address']] = monster_id
                bus[0x95] = int(not identified)
                bus[0xc0], bus[0xc1] = profile['origin']
                bus[0x7e], bus[0x7f] = profile['prg_banks']
            cpu.stPushWord(0x5fff)
            for _ in range(20000):
                if cpu.pc == 0x6000:
                    break
                cpu.step()
            else:
                raise AssertionError(f'ROM routine did not return: {monster_id}/{identified}')
            layout = parse_layout(rom, monster_id, identified)
            if profile['mapper'] == 1:
                expected_oam = bytes(v for s in layout['sprites'] for v in (s['oam_y'], s['tile'], s['palette'], s['x']))
                checks = dict(oam=bus.ram[0x704:0x704 + len(expected_oam)] == expected_oam,
                          palette=bus.ram[0x70:0x80] == bytes(layout['palette']),
                          chr_bank=bus.ram[0x44] == layout['chr_bank'],
                          oam_end=bus.ram[0x1a] == 4 + len(expected_oam))
            else:
                expected_oam = bytearray([239] * 256)
                for i, s in enumerate(layout['sprites']):
                    expected_oam[i * 4:i * 4 + 4] = bytes([s['oam_y'], s['tile'], s['attributes'], s['x']])
                colors = layout['palette_values'] + [0] * (12 - len(layout['palette_values']))
                checks = dict(oam=bus.ram[0x700:0x800] == expected_oam,
                              palette=bus.ram[0xf0:0xfc] == bytes(colors),
                              chr_bank=layout.get('empty') or bus.ram[0x7a:0x7c] == bytes([layout['chr_register'], (layout['chr_register'] + 1) & 255]),
                              restored_prg=bus.registers[6:8] == profile['prg_banks'])
            if not all(checks.values()):
                raise AssertionError(f'ROM mismatch: {monster_id}/{identified}: {checks}')
            digest.update(expected_oam + bytes(layout['palette']) + bytes([layout['chr_bank']]))
            checked += 1
    routine = 'PRG bank 3 / CPU $8000' if profile['mapper'] == 1 else f'8KiB PRG bank {profile["code_bank"]} / CPU ${profile["routine"]:04X}'
    return dict(rom_sha256=sha, game=profile['id'], checked_variants=checked, matched=True,
                routine=routine, initial_ram='zero-filled',
                checked_outputs=['OAM entries', 'sprite palette buffer', 'CHR bank', 'OAM end or restored PRG banks'],
                output_sha256=digest.hexdigest(),
                limitation='Validates layout decoding against ROM instructions, not analog RGB or hardware timing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify(args.rom.read_bytes())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
