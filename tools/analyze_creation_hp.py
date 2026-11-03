"""Execute Wiz1 initial-HP ROM instructions and RNG with existing py65."""
import hashlib
import json
from pathlib import Path
from collections import Counter
from analyze_creation_bonus import memory, run
from analyze_ac_bug import patched
from trace_graphics import MPU


def analyze(rom):
    m = memory(rom, 1)
    assert m[0xa27f:0xa294] == bytes.fromhex('ae5202bd15a320dacd187d1ba3a022912ea020912e')
    cpu = MPU(memory=m)
    rows = []
    for cls, name in enumerate(('fighter', 'mage', 'priest', 'thief', 'bishop', 'samurai', 'lord', 'ninja')):
        counts = Counter()
        witnesses = {}
        for state in range(65536):
            m[0x40], m[0x41] = state & 255, state >> 8
            m[0x252], m[0x2e], m[0x2f] = cls, 0, 0x60
            m[0x6021] = m[0x601f] = 0
            cpu.pc, cpu.sp, cpu.p = 0xa27f, 255, 0x30
            run(cpu, (0xa294,))
            hp = (m[0x6021] << 8) | m[0x6022]
            current = (m[0x601f] << 8) | m[0x6020]
            assert current == hp
            counts[hp] += 1
            witnesses.setdefault(hp, state)
        rows.append(dict(class_id=cls, name=name, rng_bound=m[0xa315 + cls],
                         base=m[0xa31b + cls], hp_histogram=dict(sorted(counts.items())),
                         zero_witness=witnesses.get(0)))
    return dict(sha256=hashlib.sha256(rom).hexdigest(), classes=rows)


if __name__ == '__main__':
    result = {}
    for name in ('wiz1', 'wiz1p'):
        rom = Path(f'.nes/{name}.nes').read_bytes()
        result[name] = analyze(rom)
        fixed = patched(rom, next(Path('reference/patch/fc').rglob('wiz1patch.ips')))
        assert memory(rom, 1)[0xa27f:0xa329] == memory(fixed, 1)[0xa27f:0xa329]
        for row in result[name]['classes']:
            print(name, row['name'], row['hp_histogram'], 'zero RNG witness:', row['zero_witness'], flush=True)
    Path('output/creation-hp-analysis.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
