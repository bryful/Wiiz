"""Check both Q selectors against name codes and the actual ROM CHR tiles."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os,struct,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
exe=str(Path(sys.argv[1]).resolve())
env=dict(os.environ,SDL_VIDEO_DRIVER='dummy',SDL_AUDIO_DRIVER='dummy',SDL_RENDER_DRIVER='software')
def pixel(raw,x,y):
    offset=struct.unpack_from('<I',raw,10)[0]
    width,height=struct.unpack_from('<ii',raw,18)
    depth=struct.unpack_from('<H',raw,28)[0]
    stride=((width*depth+31)//32)*4
    row=height-1-y if height>0 else y
    pos=offset+row*stride+x*(depth//8)
    b,g,r=raw[pos:pos+3]
    return (r,g,b)
with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='name-check-') as tmp:
    def check(name):
        folder=Path(tmp)/name;folder.mkdir()
        rom=(ROOT/'.nes'/(name+'.nes')).read_bytes()
        game=1 if name.lower().startswith('wiz1') else 2
        rows=['900 Q down','901 Q up']
        for i in range(6):rows += [f'{904+i*3} Down down',f'{905+i*3} Down up']
        rows += ['934 X down','935 X up']
        init=folder/'init.txt';init.write_text('\n'.join(rows)+'\n')
        saves=folder/'saves'
        p=subprocess.run([exe,'--smoke-turbo',str(ROOT/'.nes'/(name+'.nes')),str(folder/'init.bmp'),'950',str(init),'4',str(saves)],env=env,capture_output=True,text=True,timeout=60)
        assert p.returncode==0,p.stdout+p.stderr
        for page,steps,rowheight in [('bonus',7,88),('roster',8,88)]:
            rows=['900 Q down','901 Q up']
            for i in range(steps):rows += [f'{904+i*3} Down down',f'{905+i*3} Down up']
            rows += ['934 X down','935 X up']
            # Select next character; the display must follow the target.
            rows += ['942 Right down','943 Right up'] if page=='bonus' else ['942 Down down','943 Down up']
            replay=folder/(page+'.txt');replay.write_text('\n'.join(rows)+'\n')
            bmp=folder/(page+'.bmp');saves=folder/'saves'
            p=subprocess.run([exe,'--smoke-turbo',str(ROOT/'.nes'/(name+'.nes')),str(bmp),'950',str(replay),'4',str(saves)],env=env,capture_output=True,text=True,timeout=60)
            assert p.returncode==0,p.stdout+p.stderr
            data=(saves/(name+'.sav')).read_bytes()
            for row,slot in ([(1,2)] if page=='bonus' else [(1,2),(5,6)]):
                start=(slot-1)*256 if game==1 else 0x400+(slot-1)*96
                c=data[start:];assert not c[0] or 0<c[1]<=8
                font=16+(512 if rom[6]&4 else 0)+rom[4]*16384+(4 if game==1 else 1)*4096
                raw=bmp.read_bytes()
                for y in range(8):
                    for x in range(64):
                        tile=font+c[2+x//8]*16
                        expected=c[0] and x//8<c[1] and bool(rom[tile+y]&(128>>(x%8)))
                        for dy in range(4):
                            for dx in range(4):
                                actual=pixel(raw,640+x*4+dx,182+row*rowheight+y*4+dy)==(240,240,240)
                                assert actual==expected,(name,page,row,x,y)
            (ROOT/'output'/f'name-{name}-{page}.bmp').write_bytes(bmp.read_bytes())
        return name+': Q bonus / roster target names match ROM font pixels; character selection OK'
    with ThreadPoolExecutor(max_workers=3) as pool:
        for line in pool.map(check,('wiz1','WIZ2','WIZ3','wiz1p','wiz2p','wiz3p')):print(line,flush=True)
