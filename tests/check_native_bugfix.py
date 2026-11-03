"""Exercise bundled Wiz1 fixes with the real binjnes core and SDL menu."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
exe = str(Path(sys.argv[1]).resolve())
env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
with tempfile.TemporaryDirectory(dir=root / 'output', prefix='bugfix-check-') as folder:
    for name in ('wiz1', 'wiz1p', 'WIZ2', 'WIZ3'):
        result = subprocess.run([exe, '--bugfix-check', str(root / '.nes' / (name + '.nes')),
                                 str(Path(folder) / name)], env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'BUGFIX_OK' in result.stdout
        print(name + ': ' + result.stdout.splitlines()[-1])
    rows = ['1 Q down', '2 Q up']
    for i in range(7):
        rows.extend((f'{4+i*3} Down down', f'{5+i*3} Down up'))
    rows.extend(('28 X down', '29 X up'))
    for i in range(10):
        rows.extend((f'{32+i*3} Down down', f'{33+i*3} Down up'))
    rows.extend(('65 X down', '66 X up'))
    replay = Path(folder) / 'menu.txt'
    replay.write_text('\n'.join(rows) + '\n')
    result = subprocess.run([exe, '--smoke-turbo', str(root / '.nes/wiz1.nes'),
                             str(root / 'output/bugfix-menu.bmp'), '75', str(replay), '4'],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'wiz1_bug_fix=1' in result.stdout, result.stdout
    print('SDL Q menu: Wiz1 bug Fix ON verified')
