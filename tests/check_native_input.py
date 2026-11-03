"""Replay real SDL key events through the application's selection/menu/reset loop."""
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = str(Path(sys.argv[1]).resolve())
    env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
    with tempfile.TemporaryDirectory(dir=ROOT / 'output', prefix='input-check-') as temp:
        folder = Path(temp)
        roms = folder / 'roms'
        roms.mkdir()
        for filename in ('wiz1.nes', 'WIZ2.nes', 'WIZ3.nes'):
            shutil.copyfile(ROOT / '.nes' / filename, roms / filename)

        def replay(name, script, frames, expected):
            keys, image = folder / (name + '.txt'), folder / (name + '.bmp')
            keys.write_text(script, encoding='utf-8')
            result = subprocess.run([exe, '--smoke-library', str(roms), str(image), str(frames), str(keys)],
                                    capture_output=True, text=True, env=env)
            assert result.returncode == 0 and expected in result.stdout, result.stdout + result.stderr
            return image

        # Navigate to II, start with X, then Escape must reset the same game, not exit or select I.
        image = replay('reset', '1 Down down\n2 Down up\n3 X down\n4 X up\n10 Escape down\n11 Escape up\n',
                       30, 'SMOKE_OK game=Wizardry FC II menu=0 resets=1 frames=30')
        assert image.stat().st_size > 10000
        # Q pauses; Z returns; Q opens again. S is not consumed as an app menu key.
        replay('menu', '1 X down\n2 X up\n4 S down\n5 S up\n6 Q down\n7 Q up\n8 Z down\n9 Z up\n10 Q down\n11 Q up\n',
               20, 'SMOKE_OK game=Wizardry FC I menu=1 resets=0 frames=20')
        # Exit is selected inside the in-game overlay using only the agreed controls.
        replay('exit', '1 X down\n2 X up\n4 Q down\n5 Q up\n6 Up down\n7 Up up\n8 Up down\n9 Up up\n10 Up down\n11 Up up\n12 X down\n',
               30, 'SMOKE_OK game=Wizardry FC I menu=1 resets=0 frames=12')
        replay('crt-toggle', '1 X down\n2 X up\n4 Q down\n5 Q up\n6 Down down\n7 Down up\n8 Down down\n9 Down up\n10 Return down\n11 Return up\n12 Return down\n13 Return up\n14 Backspace down\n15 Backspace up\n16 Backspace down\n17 Backspace up\n20 Escape down\n21 Escape up\n',
               40, 'SMOKE_OK game=Wizardry FC I menu=0 resets=1 frames=40 fast_drawing=0')
        print('SDL input replay: game selection, same-ROM reset, Q/Z menu and menu exit OK')


if __name__ == '__main__':
    main()
