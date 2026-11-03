"""Actual-ROM roster swaps, same-person party resume, and SDL ordering UI."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
exe=str(Path(sys.argv[1]).resolve())
env=dict(os.environ,SDL_VIDEO_DRIVER='dummy',SDL_AUDIO_DRIVER='dummy',SDL_RENDER_DRIVER='software')
with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='roster-check-') as folder:
    temp=Path(folder)
    def check(name):
        p=subprocess.run([exe,'--roster-check',str(ROOT/'.nes'/(name+'.nes')),str(temp/name)],env=env,capture_output=True,text=True,timeout=180)
        if p.returncode:raise RuntimeError(name+': '+p.stdout+p.stderr)
        assert 'ROSTER_OK' in p.stdout
        return name+': '+p.stdout.splitlines()[-1]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(check,sys.argv[2:] or ('wiz1','WIZ2','WIZ3','wiz1p','wiz2p','wiz3p')):print(line,flush=True)
    def ui_check(name):
        rows=['900 Q down','901 Q up']
        for i in range(8):rows.extend((f'{904+i*3} Down down',f'{905+i*3} Down up'))
        rows.extend(('930 X down','931 X up','934 X down','935 X up'))
        # Move the first character to the last slot; clamp at the bottom.
        for i in range(20):rows.extend((f'{940+i*3} Down down',f'{941+i*3} Down up'))
        rows.extend(('1002 Return down','1003 Return up','1006 X down','1007 X up'))
        # Move back to slot 1, then cancel. Selection returns to slot 20.
        for i in range(20):rows.extend((f'{1010+i*3} Up down',f'{1011+i*3} Up up'))
        rows.extend(('1072 Z down','1073 Z up','1076 Return down','1077 Return up'))
        for i in range(20):rows.extend((f'{1080+i*3} Up down',f'{1081+i*3} Up up'))
        rows.extend(('1142 X down','1143 X up'))
        # Confirmed roster restored; make another preview and close Q to cancel.
        rows.extend(('1146 X down','1147 X up','1150 Down down','1151 Down up','1154 Q down','1155 Q up',
                     '1158 Q down','1159 Q up'))
        for i in range(8):rows.extend((f'{1162+i*3} Down down',f'{1163+i*3} Down up'))
        rows.extend(('1188 Return down','1189 Return up'))
        replay=temp/(name+'-menu.txt');replay.write_text('\n'.join(rows)+'\n')
        saves=temp/(name+'-ui-saves')
        p=subprocess.run([exe,'--smoke-turbo',str(ROOT/'.nes'/(name+'.nes')),str(ROOT/'output'/('roster-list-'+name+'.bmp')),'1200',str(replay),'4',str(saves)],env=env,capture_output=True,text=True,timeout=90)
        assert p.returncode==0,p.stdout+p.stderr
        assert 'roster_swaps=2' in p.stdout,p.stdout+p.stderr
        backups=sorted((saves/'backups'/name).glob('*before-roster.sav'))
        assert len(backups)==2
        original=backups[0].read_bytes();moved=backups[1].read_bytes();final=(saves/(name+'.sav')).read_bytes()
        first=name.lower().startswith('wiz1');start,stride,payload=(0,256,112) if first else (0x400,96,94)
        for i in range(20):
            part=slice(start+i*stride,start+i*stride+payload)
            source=0 if i==19 else i+1
            assert moved[part]==original[start+source*stride:start+source*stride+payload],(name,i)
            assert final[part]==original[part],(name,i)
        return name+': SDL 20-row list, X/Return pick/confirm, insertion 1->20->1, bounds, Z/Q cancel: OK'
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(ui_check,sys.argv[2:] or ('wiz1','WIZ2','WIZ3','wiz1p','wiz2p','wiz3p')):print(line,flush=True)
