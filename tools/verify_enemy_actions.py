"""Compare JP enemy spell choice/depletion with its ROM routine, using fixed RNG draws."""
import json
import hashlib
from pathlib import Path
from rom_profiles import profile_for
from trace_graphics import Bus, MPU


def expected(mage, priest, kind, count, raw, scaled, tables):
    school = 'mage' if mage and (kind == 1 or raw & 3) else 'priest' if priest and (kind == 2 or raw & 3) else None
    levels = dict(mage=mage, priest=priest)
    if not school:
        return 0, levels
    maximum = levels[school] - int(scaled % (count+2) == 1)
    levels[school] = max(1, maximum)
    if maximum == 0:
        return 0, levels
    level = maximum
    while raw >= 179:
        level -= 1
        if level == 0:
            level = 1
            break
    return tables[school][level*2 + int(raw >= 85)], levels


def verify(rom):
    if profile_for(rom)['id'] != 'wiz1':
        raise ValueError('Wiz1 JP only')
    bus = Bus(rom)
    cpu = MPU(memory=bus)
    bus.cpu = cpu
    tables = dict(mage=[bus[0xdd10+i] for i in range(16)], priest=[bus[0xdd20+i] for i in range(16)])
    count_cases = 0
    for kind in [0, 1, 2, 8]:
        for mage in range(8):
            for priest in range(8):
                for raw in [0, 1, 64, 84, 85, 178, 179, 255]:
                    for scaled in [0, 1, 2]:
                        for count in [1, 5, 9]:
                            bus[0x7ac9], bus[0x7acd], bus[0x7e43], bus[0x7ac5], bus[0x7cb6] = mage, priest, kind, count, 0
                            cpu.x, cpu.sp, cpu.pc = 6, 255, 0xdc84
                            cpu.stPushWord(0x5fff)
                            for _ in range(500):
                                if cpu.pc == 0x6000:
                                    break
                                if cpu.pc in (0xc2a1, 0xcdda):
                                    cpu.a = raw if cpu.pc == 0xc2a1 else scaled % cpu.a
                                    cpu.pc = cpu.stPopWord()+1
                                else:
                                    cpu.step()
                            assert cpu.pc == 0x6000
                            code, levels = expected(mage, priest, kind, count, raw, scaled, tables)
                            assert (bus[0x7cb6], bus[0x7ac9], bus[0x7acd]) == (code, levels['mage'], levels['priest']), (kind,mage,priest,raw,scaled,count)
                            count_cases += 1
    return dict(matched=True, rom_sha256=hashlib.sha256(rom).hexdigest(), cases=count_cases,
                spell_tables=tables, limitation='Spell choice/group depletion with fixed RNG draws only; effect saving throws, breath reduction and contact-effect probability are separate')


if __name__ == '__main__':
    result = verify(Path('.nes/wiz1.nes').read_bytes())
    out = Path('output/enemy_actions')
    out.mkdir(parents=True, exist_ok=True)
    (out/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
