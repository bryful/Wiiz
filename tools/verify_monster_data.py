"""Compare decoded names and stat bytes with the original ROM loading routines."""
import argparse
import hashlib
import json
from pathlib import Path
from monster_data import read_monster
from rom_profiles import profile_for
from trace_graphics import Bus, MPU
from mmc3_cpu_bus import Mmc3CpuBus


def verify(rom):
    profile = profile_for(rom)
    total = 0
    for monster_id in range(profile['count']):
        data = read_monster(rom, monster_id)
        expected = bytes.fromhex(data['data_source']['stats_raw_hex'])
        for japanese in (False, True):
            if profile['id'] == 'wiz1':
                bus = Bus(rom)
                bus.prgbank = 5
                bus[0xfb] = 5
                bus[0x7ab8] = int(japanese)
                cpu = MPU(memory=bus, pc=0xcfc8)
                bus.cpu = cpu
                stat_address, known_address, unknown_address = 0x7e43, 0x7e24, 0x7e04
            else:
                bus = Mmc3CpuBus(rom)
                bus.registers[6:8] = [12, 13]
                bus[0x7e], bus[0x7f] = 12, 13
                wiz2 = profile['id'] == 'wiz2'
                bus[0x77f8 if wiz2 else 0x6d9f] = int(japanese)
                cpu = MPU(memory=bus, pc=0xff8f if wiz2 else 0xde97)
                stat_address, known_address, unknown_address = 0x240, 0x200, 0x220
            cpu.a = monster_id
            cpu.stPushWord(0x5fff)
            for _ in range(30000):
                if cpu.pc == 0x6000:
                    break
                cpu.step()
            else:
                raise AssertionError(f'Loader timeout: {profile["id"]}/{monster_id}')
            actual = bytes(bus[stat_address + i] for i in range(len(expected)))
            if actual != expected:
                raise AssertionError(f'Stat bytes differ: {profile["id"]}/{monster_id}')
            if japanese:
                for key, address in [('japanese_name_codes', known_address), ('japanese_unknown_name_codes', unknown_address)]:
                    codes = data[key]
                    if bytes(bus[address + i] for i in range(len(codes))) != bytes(codes):
                        raise AssertionError(f'Japanese name bytes differ: {profile["id"]}/{monster_id}/{key}')
            total += 1
    return dict(game=profile['id'], rom_sha256=hashlib.sha256(rom).hexdigest(),
                monster_count=profile['count'], loader_cases=total, matched=True,
                checked_outputs=['combat stat bytes in both language modes', 'Japanese known and unknown name bytes'],
                limitation='Byte loading is verified; field meanings are documented separately. Font decoding is inspected visually.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify(args.rom.read_bytes())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
