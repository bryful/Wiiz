"""Verify Wiz1 new-character HP floor and Lord creation/save/reload."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
exe = str(Path(sys.argv[1]).resolve())
env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
with tempfile.TemporaryDirectory(dir=root / 'output', prefix='initial-hp-') as folder:
    for mode in ('--initial-hp-check', '--creation-hp-check'):
        for name in ('wiz1', 'wiz1p'):
            result = subprocess.run([exe, mode, str(root / '.nes' / (name + '.nes')),
                                     str(Path(folder) / (mode + name))], env=env,
                                    capture_output=True, text=True, timeout=180)
            assert result.returncode == 0, result.stdout + result.stderr
            print(mode, name, result.stdout.splitlines()[-1], flush=True)
