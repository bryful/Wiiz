"""Compare every frame/audio sample with an unmodified-ROM core, including transitions."""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def viewport(path):
    data = path.read_bytes()
    offset = struct.unpack_from('<I', data, 10)[0]
    width, height = struct.unpack_from('<ii', data, 18)
    bits = struct.unpack_from('<H', data, 28)[0]
    assert bits in (24, 32) and width == 1024 and abs(height) == 860
    stride = ((width * bits + 31) // 32) * 4
    rows = []
    for y in range(90, 810):
        row = abs(height) - 1 - y if height > 0 else y
        start = offset + row * stride
        rows.append(data[start + 128*(bits//8):start + 896*(bits//8)])
    return b''.join(rows)


def main():
    exe = str(Path(sys.argv[1]).resolve())
    rom = ROOT / '.nes' / 'wiz1.nes'
    original_hash = hashlib.sha256(rom.read_bytes()).hexdigest()
    result = subprocess.run([exe, '--drawing-check', str(rom)], capture_output=True, text=True, check=True)
    assert 'every_frame_pixels_equal=1' in result.stdout
    print(result.stdout.splitlines()[-1])
    result = subprocess.run([exe, '--drawing-check', str(rom), str(ROOT / 'tests/replays/wiz1-dungeon.txt'), '4300'],
                            capture_output=True, text=True, check=True)
    assert 'frames=4300 every_frame_pixels_equal=1' in result.stdout
    print(result.stdout.splitlines()[-1])
    result = subprocess.run([exe, '--drawing-check', str(rom), str(ROOT / 'tests/replays/wiz1-battle.txt'), '11000'],
                            capture_output=True, text=True, check=True)
    assert 'frames=11000 every_frame_pixels_equal=1' in result.stdout
    print(result.stdout.splitlines()[-1])
    env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
    with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='drawing-check-') as temp:
        images = []
        for mode in ('original', 'fast'):
            image = Path(temp) / (mode + '.bmp')
            subprocess.run([exe, '--smoke', str(rom), str(image), '600', str(ROOT / 'tests/replays/wiz1-dungeon.txt'), mode],
                           env=env, capture_output=True, check=True)
            images.append(viewport(image))
        assert images[0] == images[1], 'Dungeon viewport changed'
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == original_hash, 'Source ROM was modified'
    print('All transition frames/audio match the unmodified-ROM reference; legacy fast request is ignored; source ROM unchanged')


if __name__ == '__main__':
    main()
