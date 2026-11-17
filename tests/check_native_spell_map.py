"""Actual FC-I casts and SDL map input, with no changes to user saves or ROMs."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = str(Path(sys.argv[1]).resolve())
    rom = Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'.nes/wiz1.nes'
    original = hashlib.sha256(rom.read_bytes()).hexdigest()
    env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
    with tempfile.TemporaryDirectory(dir=ROOT/'output', prefix='spell-map-check-') as folder:
        temp = Path(folder)
        result = subprocess.run([exe, '--map-prepare', str(rom), str(temp)], capture_output=True, text=True, check=True)
        assert 'SPELL_MAP_OK' in result.stdout and 'actual_spells=2' in result.stdout
        print(result.stdout.splitlines()[-1])
        states = temp/'states'
        assert json.loads((states/f'{rom.stem}.stot4.state').read_text())['automap']['dialog'][0] == 1
        assert json.loads((states/f'{rom.stem}.stot5.state').read_text())['automap']['dialog'][0] == 2

        def play(name, script, frames=100):
            keys=temp/(name+'.txt');keys.write_text(script)
            image=temp/(name+'.bmp')
            subprocess.run([exe,'--smoke-turbo',str(rom),str(image),str(frames),str(keys),'4',str(temp/'saves')],
                           env=env,capture_output=True,check=True)
            return image

        image=play('dumapic','1 Shift+F4 down\n2 Shift+F4 up\n',30)
        data=image.read_bytes();offset=struct.unpack_from('<I',data,10)[0];width,height=struct.unpack_from('<ii',data,18);bits=struct.unpack_from('<H',data,28)[0]
        assert width==1024 and abs(height)==860 and bits in (24,32)
        stride=((width*bits+31)//32)*4
        # Unexplored tiles cannot disclose walls/events: their interiors stay uniformly gray.
        for x,y in ((10,10),(19,19),(1,0)):
            px,py=80+x*32+16,120+(19-y)*32+16
            row=abs(height)-1-py if height>0 else py
            blue,green,red=data[offset+row*stride+px*(bits//8):][:3]
            assert (red,green,blue)==(96,96,96)
        play('close','1 Shift+F4 down\n2 Shift+F4 up\n10 Z down\n13 Z up\n80 F1 down\n81 F1 up\n')
        assert json.loads((states/f'{rom.stem}.stot1.state').read_text())['automap']['dialog'][0]==0
        play('warp','1 Shift+F5 down\n2 Shift+F5 up\n10 Up down\n13 Up up\n20 X down\n23 X up\n80 F1 down\n81 F1 up\n')
        a=json.loads((states/f'{rom.stem}.stot1.state').read_text())['automap']
        assert a['dialog'][0]==0 and a['dialog'][6:]==[0,1] and a['explored'][20]==1
        play('cancel','1 Shift+F5 down\n2 Shift+F5 up\n10 S down\n13 S up\n20 A down\n23 A up\n30 Z down\n33 Z up\n80 F1 down\n81 F1 up\n')
        a=json.loads((states/f'{rom.stem}.stot1.state').read_text())['automap']
        assert a['dialog'][0]==0 and a['dialog'][5]==1 and sum(a['explored'])==1
        print('SDL DUMAPIC close, MALOR target/floor/confirm/cancel, and hidden unexplored geometry: OK')
    assert hashlib.sha256(rom.read_bytes()).hexdigest()==original


if __name__=='__main__':
    main()
