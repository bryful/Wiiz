"""Exercise the adopted core on the user's verified ROMs, without touching user saves."""
from pathlib import Path
import subprocess
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = str(Path(sys.argv[1]).resolve())
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output, prefix='core-check-') as temp:
        folder = Path(temp)
        # Regression fixtures use only the three identified revisions; other ROMs may coexist.
        for name in ('wiz1.nes','WIZ2.NES','WIZ3.NES'):
            rom = ROOT / '.nes' / name
            save_dir = folder / rom.stem
            result = subprocess.run([exe, '--core-check', str(rom), str(save_dir)], capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            assert 'CORE_OK' in result.stdout, result.stdout
            saves = list(save_dir.glob('*.json'))
            assert len(saves) == 1
            document = json.loads(saves[0].read_text(encoding='utf-8'))
            assert document['format'] == 'wiiz-battery' and len(document['characters']) == 20
            assert document['checksum_validation'] is False
            print(rom.name + ': ' + result.stdout.splitlines()[-1])
        # Mixed extensions, unknown revision, arbitrary filename, ignored non-ROM file.
        catalog = folder / 'roms'
        catalog.mkdir()
        original = ROOT / '.nes' / 'wiz1.nes'
        (catalog / 'renamed.NES').write_bytes(original.read_bytes())
        (catalog / 'unsupported.nes').write_bytes(b'NES\x1a' + bytes(1024))
        (catalog / 'notes.txt').write_text('not a ROM')
        result = subprocess.run([exe, '--scan', str(catalog)], capture_output=True, text=True, check=True)
        assert 'Wizardry FC I' in result.stdout and 'supported=1 rejected=1' in result.stdout
        (catalog / 'renamed.NES').unlink()
        (catalog / 'unsupported.nes').unlink()
        result = subprocess.run([exe, '--scan', str(catalog)], capture_output=True, text=True, check=True)
        assert 'supported=0 rejected=0' in result.stdout
        print('Folder scan: renamed ROM, mixed extensions, unknown ROM and empty folder OK')


if __name__ == '__main__':
    main()
