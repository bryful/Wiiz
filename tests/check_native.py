"""Compare native extraction against the existing ROM-verified Python extractor."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from dungeon_data import read_dungeons


def main():
    exe = Path(sys.argv[1]).resolve()
    seen = set()
    for rom in (ROOT / '.nes').iterdir():
        if rom.suffix.lower() != '.nes':
            continue
        data = read_dungeons(rom.read_bytes())
        payload = bytearray()
        for floor in data['floors']:
            for field in ('walls_raw', 'flags_raw'):
                payload.extend(cell[field] for cell in floor['cells'])
        expected = f"{data['floor_count']} {hashlib.sha256(payload).hexdigest()}"
        actual = subprocess.check_output([str(exe), '--check', str(rom)], text=True).strip()
        assert actual == expected, (rom.name, actual, expected)
        seen.add(data['game'])
        print(f"{data['game']}: {data['floor_count'] * 400} cells matched")
    assert seen == {'wiz1', 'wiz2', 'wiz3'}, seen
    (ROOT / 'output').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='native-check-') as temp:
        bad = Path(temp) / 'unsupported.nes'
        bad.write_bytes(b'NES\x1a' + bytes(1024))
        result = subprocess.run([str(exe), '--check', str(bad)], capture_output=True, text=True)
        assert result.returncode == 1 and 'Unsupported ROM revision' in result.stderr
        result = subprocess.run([str(exe), '--check', str(bad.parent / 'missing.nes')], capture_output=True)
        assert result.returncode == 1
    print('Unknown ROM and missing file rejected')


if __name__ == '__main__':
    main()
