"""Exercise real cores and SDL: complete game frames, 1x music, wall-clock repeat."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = str(Path(sys.argv[1]).resolve())
    rom = Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT / '.nes/wiz1.nes'
    original = hashlib.sha256(rom.read_bytes()).hexdigest()
    result = subprocess.run([exe, '--turbo-check', str(rom)], capture_output=True, text=True, check=True)
    for speed in (2, 4, 8):
        assert f'TURBO_OK speed={speed} game_frames={180*speed} music_samples=143872' in result.stdout
        assert f'REPEAT_OBSERVED speed={speed} consumed=18' in result.stdout
    assert 'SOUND_DRIVER_OK bgm=' in result.stdout
    print('\n'.join(s for s in result.stdout.splitlines() if '_OK' in s or 'REPEAT_OBSERVED' in s))
    env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
    with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='turbo-check-') as folder:
        temp = Path(folder)
        # Existing dungeon journey, expressed in host updates at 4x.
        rows, pressed = [], {}
        for line in (ROOT / 'tests/replays/wiz1-dungeon.txt').read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            f, key, action = line.split()
            tick = round(int(f)/4)
            if action == 'up':
                tick = max(tick, pressed[key]+1)
            else:
                pressed[key] = tick
            rows.append((tick, key, action))
        replay = temp / 'keys.txt'
        replay.write_text(''.join(f'{t} {k} {a}\n' for t, k, a in sorted(rows)))
        result = subprocess.run([exe, '--smoke-turbo', str(rom), str(temp/'dungeon.bmp'), '1100', str(replay), '4'],
                                env=env, capture_output=True, text=True, check=True)
        assert 'menu=0 resets=0 frames=1100 fast_drawing=0 speed=4' in result.stdout
        # Reset while accelerated, then cycle the setting and return using the agreed controls.
        replay.write_text('20 Escape down\n21 Escape up\n30 Q down\n31 Q up\n32 Down down\n33 Down up\n34 Down down\n35 Down up\n36 X down\n37 X up\n38 Down down\n39 Down up\n40 X down\n41 X up\n42 Z down\n43 Z up\n44 Z down\n45 Z up\n')
        result = subprocess.run([exe, '--smoke-turbo', str(rom), str(temp/'reset.bmp'), '90', str(replay), '4'],
                                env=env, capture_output=True, text=True, check=True)
        assert 'menu=0 resets=1 frames=90 fast_drawing=0 speed=8' in result.stdout
        replay.write_text('')
        for name in ('WIZ2.NES', 'WIZ3.NES'):
            result = subprocess.run([exe, '--smoke-turbo', str(ROOT/'.nes'/name), str(temp/'fallback.bmp'), '90', str(replay), '8'],
                                    env=env, capture_output=True, text=True, check=True)
            assert 'frames=90 fast_drawing=0 speed=8' in result.stdout
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == original
    print('SDL turbo dungeon, reset, speed selection, II/III turbo and unchanged source ROM: OK')


if __name__ == '__main__':
    main()
