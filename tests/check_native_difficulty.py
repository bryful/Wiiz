"""Difficulty bonuses and spell-free map against each installed FC ROM."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
exe = str(Path(sys.argv[1]).resolve())
env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
with tempfile.TemporaryDirectory(dir=ROOT/'output', prefix='difficulty-check-') as folder:
    def check(name):
        result = subprocess.run([exe, '--difficulty-check', str(ROOT/'.nes'/(name+'.nes')), str(Path(folder)/name)],
                                capture_output=True, text=True, env=env, timeout=180)
        if result.returncode:
            raise RuntimeError(name+': '+result.stdout+result.stderr)
        assert 'DIFFICULTY_OK' in result.stdout
        return name+': '+result.stdout.splitlines()[-1]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(check, ('wiz1', 'WIZ2', 'WIZ3', 'wiz1p', 'wiz2p', 'wiz3p')):
            print(line, flush=True)

    # SDL input path: open/close host map, select Q bonuses, and persist state.
    rom=ROOT/'.nes/wiz1.nes'
    saveFolder=Path(folder)/'wiz1'/'saves'
    rows=['1 Shift+F1 down','2 Shift+F1 up','10 M down','11 M up','20 F2 down','21 F2 up','30 X down','31 X up','40 Q down','41 Q up']
    for i in range(7):
        rows.extend((f'{44+i*3} Down down',f'{45+i*3} Down up'))
    rows.extend(('70 X down','71 X up','75 Down down','76 Down up','80 Down down','81 Down up','85 X down','86 X up','90 Down down','91 Down up','95 X down','96 X up','100 Down down','101 Down up','105 X down','106 X up','115 F3 down','116 F3 up'))
    replay=Path(folder)/'menu.txt';replay.write_text('\n'.join(rows)+'\n')
    result=subprocess.run([exe,'--smoke-turbo',str(rom),str(Path(folder)/'menu.bmp'),'118',str(replay),'4',str(saveFolder)],env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    assert "bonus_actions=3" in result.stdout,result.stdout+result.stderr
    states=(Path(folder)/'wiz1'/'states')
    opened=json.loads((states/'wiz1.stot2.state').read_text())['automap']
    closed=json.loads((states/'wiz1.stot3.state').read_text())['automap']
    assert opened['dialog'][0]==3 and closed['dialog'][0]==0
    assert closed['resume']==0 and closed['button']==0
    (ROOT/'output/difficulty-ui.bmp').write_bytes((Path(folder)/'menu.bmp').read_bytes())
    print('SDL M map, close without ROM input, Q experience/Gold/spells: OK',flush=True)
