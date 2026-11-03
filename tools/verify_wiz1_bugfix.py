"""Compare the shipped byte table with all three user-supplied IPS inputs."""
from pathlib import Path
import re
from analyze_ac_bug import patched, threshold

root = Path(__file__).resolve().parents[1]
original = (root / '.nes/wiz1.nes').read_bytes()
fixed = original
for name in ('wiz1patch.ips', 'wizardry1_pg_fc_patch24_BoltacKAUYO.ips',
             'wizardry1_pg_fc_patch25_BoltacURUYO.ips'):
    fixed = patched(fixed, next((root / 'reference/patch/fc').rglob(name)))
rows = [(int(a, 16), int(b, 16), int(c, 16)) for a, b, c in re.findall(
    r'\{0x([0-9a-f]+),0x([0-9a-f]+),0x([0-9a-f]+)\}',
    (root / 'app/wiz1_bugfix_data.hpp').read_text())]
expected = [(i - 16, a, b) for i, (a, b) in enumerate(zip(original, fixed)) if a != b]
assert rows == expected
assert len(rows) == 116
assert (20 - threshold(fixed, player_ac=0)) * 5 == 40
assert (20 - threshold(fixed, player_ac=-12)) * 5 == 0
for name in ('wiz1.nes', 'wiz1p.nes'):
    data = (root / '.nes' / name).read_bytes()
    for offset, before, after in rows:
        assert data[offset + 16] == before, (name, hex(offset))
print('BUGFIX_DATA_OK: 116 bytes equal combined IPS; original and parameter variant compatible; AC CPU checks passed')
