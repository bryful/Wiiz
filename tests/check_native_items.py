"""Targeted item-editor checks, using local ROMs and isolated generated saves."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('rom', type=Path)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--scenes', action='store_true')
    args = parser.parse_args()
    exe, rom, folder = (p.resolve() for p in (args.exe, args.rom, args.folder))
    folder.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha256(rom.read_bytes()).hexdigest()
    run = subprocess.run([str(exe), '--items-check', str(rom), str(folder)], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-1000:] + run.stderr
    assert 'ITEMS_OK' in run.stdout
    print(run.stdout.splitlines()[-1])
    if args.scenes:
        result = subprocess.run([str(exe), '--items-scenes-check', str(rom), str(folder)], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr
        assert 'ITEM_SCENES_OK' in result.stdout
        print(result.stdout.splitlines()[-1])
    env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')

    def play(name, tail):
        keys = folder / (name + '.txt')
        keys.write_text('1 Shift+F2 down\n2 Shift+F2 up\n10 I down\n11 I up\n' + tail)
        result = subprocess.run([str(exe), '--smoke-turbo', str(rom), str(folder / (name + '.bmp')), '65', str(keys), '4', str(folder / 'saves')], cwd=ROOT, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout[-1000:] + result.stderr
        assert 'state_errors=0' in result.stdout
        return result.stdout

    assert 'menu=1' in play('items', '')
    assert 'menu_page=7' in play('submenu', '20 X down\n21 X up\n')
    assert 'menu=0' in play('close', '20 Z down\n21 Z up\n')
    assert 'menu=0' in play('reload', '20 Shift+F2 down\n21 Shift+F2 up\n')
    assert before == hashlib.sha256(rom.read_bytes()).hexdigest(), 'ROM modified'
    print('ITEMS_SDL_OK open/submenu/close/state-load-exit ROM_unchanged=1')
    (folder / 'verification.json').write_text(json.dumps({'rom_file': rom.name, 'items_check': True, 'sdl': True, 'rom_unchanged': True, 'scenes': args.scenes}, indent=2) + '\n')


if __name__ == '__main__':
    main()
