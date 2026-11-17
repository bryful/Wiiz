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
        # From Character, wrap up to Change race, then confirm each choice.
        record=slice(start,start+payload)
        expected=bytearray(final[record])
        race_shift=0 if first else 5
        class_offset,class_shift=(11,0) if first else (10,2)
        race=(expected[10]>>race_shift)&7
        job=(expected[class_offset]>>class_shift)&7
        race_step=-1 if race==4 else 1
        class_step=-1 if job==7 else 1
        keys=['Q']+['Down']*7+['X','Up','Up','Up','X','Up' if race_step<0 else 'Down',
                            'X','Down','X','Up' if class_step<0 else 'Down','X']
        # Title -> castle -> town edge -> training ground.
        training=['X','Down','Down','Down','Down','X','X']
        events=[(900+i*40,key) for i,key in enumerate(training)]
        events.extend((1180+i*4,key) for i,key in enumerate(keys))
        replay.write_text(''.join(f'{frame} {key} down\n{frame+1} {key} up\n' for frame,key in events))
        p=subprocess.run([exe,'--smoke-turbo',str(ROOT/'.nes'/(name+'.nes')),str(temp/(name+'-identity.bmp')),'1290',str(replay),'4',str(saves)],env=env,capture_output=True,text=True,timeout=90)
        assert p.returncode==0,p.stdout+p.stderr
        edits=sorted((saves/'backups'/name).glob('*before-roster.sav'))
        assert len(edits)==4,(name,len(edits),p.stdout)
        expected[10]=(expected[10]&~(7<<race_shift))|((race+race_step)<<race_shift)
        assert edits[-1].read_bytes()[record]==expected,(name,'race')
        expected[class_offset]=(expected[class_offset]&~(7<<class_shift))|((job+class_step)<<class_shift)
        assert (saves/(name+'.sav')).read_bytes()[record]==expected,(name,'class')
        return name+': SDL roster order and training-ground race/class edits: OK'
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(ui_check,sys.argv[2:] or ('wiz1','WIZ2','WIZ3','wiz1p','wiz2p','wiz3p')):print(line,flush=True)
