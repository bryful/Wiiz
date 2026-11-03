"""Real-ROM casts and existing binjnes RAM/SRAM freeze checks."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
exe=str(Path(sys.argv[1]).resolve())
env=dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='assists-check-') as folder:
    def check(name):
        p=subprocess.run([exe,'--assists-check',str(ROOT/'.nes'/(name+'.nes')),str(Path(folder)/name)],env=env,capture_output=True,text=True,timeout=180)
        if p.returncode:raise RuntimeError(name+': '+p.stdout+p.stderr)
        assert 'ASSISTS_OK' in p.stdout
        return name+': '+p.stdout.splitlines()[-1]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(check,('wiz1','WIZ2','WIZ3','wiz1p','wiz2p','wiz3p')):print(line,flush=True)

    # SDL toggles are independent and reachable from the Q menu.
    rows=['1 Q down','2 Q up']
    for i in range(7):rows.extend((f'{4+i*3} Down down',f'{5+i*3} Down up'))
    rows.extend(('28 X down','29 X up'))
    for i in range(5):rows.extend((f'{32+i*3} Down down',f'{33+i*3} Down up'))
    rows.extend(('49 X down','50 X up'))
    for i in range(3):
        rows.extend((f'{54+i*8} Down down',f'{55+i*8} Down up',f'{58+i*8} X down',f'{59+i*8} X up'))
    replay=Path(folder)/'toggles.txt';replay.write_text('\n'.join(rows)+'\n')
    result=subprocess.run([exe,'--smoke-turbo',str(ROOT/'.nes/wiz1.nes'),str(ROOT/'output/assists-menu.bmp'),'85',str(replay),'4'],env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'assist_mask=15' in result.stdout,result.stdout+result.stderr
    print('SDL Q: MP / LOMILWA / LATUMAPIC / MAPORFIC toggles ON: OK',flush=True)
