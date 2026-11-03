"""Create/save/restart all five species via original FC menus, six ROMs."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
exe=str(Path(sys.argv[1]).resolve())
env=dict(os.environ,SDL_VIDEO_DRIVER='dummy',SDL_AUDIO_DRIVER='dummy',SDL_RENDER_DRIVER='software')
with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='creation-check-') as folder:
    def check(name):
        p=subprocess.run([exe,'--creation-check',str(ROOT/'.nes'/(name+'.nes')),str(Path(folder)/name)],env=env,capture_output=True,text=True,timeout=180)
        if p.returncode:raise RuntimeError(name+': '+p.stdout+p.stderr)
        assert 'CREATION_OK' in p.stdout
        return name+': '+p.stdout.splitlines()[-1]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(check,sys.argv[2:] or ('wiz1','WIZ2','WIZ3','wiz1p','wiz2p','wiz3p')):print(line,flush=True)
    rows=['1 Q down','2 Q up']
    for i in range(7):rows.extend((f'{4+i*3} Down down',f'{5+i*3} Down up'))
    rows.extend(('28 X down','29 X up'))
    for i in range(9):rows.extend((f'{32+i*3} Down down',f'{33+i*3} Down up'))
    rows.extend(('63 X down','64 X up'))
    replay=Path(folder)/'creation-menu.txt';replay.write_text('\n'.join(rows)+'\n')
    p=subprocess.run([exe,'--smoke-turbo',str(ROOT/'.nes/wiz1.nes'),str(ROOT/'output/creation-menu.bmp'),'70',str(replay),'4'],env=env,capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stdout+p.stderr
    assert 'assist_mask=16' in p.stdout,p.stdout+p.stderr
    print('SDL Q max creation bonus toggle: OK')
