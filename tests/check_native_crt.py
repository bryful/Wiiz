"""Check the Lottes port against its equations and the real SDL menu/render path."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def bitmap(path):
    data=path.read_bytes();offset=struct.unpack_from('<I',data,10)[0]
    width,height=struct.unpack_from('<ii',data,18);bits=struct.unpack_from('<H',data,28)[0]
    assert bits in (24,32)
    stride=((width*bits+31)//32)*4
    rows=[]
    for y in range(abs(height)):
        at=offset+(abs(height)-1-y if height>0 else y)*stride
        rows.append([tuple(data[at+x*(bits//8):at+x*(bits//8)+3][::-1]) for x in range(width)])
    return width,abs(height),rows


def reference(source,x,y,mode):
    # Independent evaluation of upstream Horz3/Horz5/Horz7, Scan/Tri and Bloom.
    linear=lambda v:v/255/12.92 if v/255<=.04045 else ((v/255+.055)/1.055)**2.4
    sx,sy=x//3,y//3;dx=.5-(x%3+.5)/3;dy=.5-(y%3+.5)/3
    def horizontal(row,radius,scale):
        weights=[2**(scale*(dx+i)**2) for i in range(-radius,radius+1)]
        samples=[source[max(0,min(239,row))][max(0,min(255,sx+i))] for i in range(-radius,radius+1)]
        return [sum(linear(p[c])*w for p,w in zip(samples,weights))/sum(weights) for c in range(3)]
    hard=-4.5 if mode==1 else -3
    tri=[0.,0.,0.];glow=[0.,0.,0.]
    for off in (-1,0,1):
        p=horizontal(sy+off,2 if off==0 else 1,hard);weight=2**((-5 if mode==1 else -8)*(dy+off)**2)
        tri=[a+b*weight for a,b in zip(tri,p)]
    for off in (-2,-1,0,1,2):
        p=horizontal(sy+off,2 if abs(off)==2 else 3,hard if abs(off)==2 else -1.5);weight=2**(-2*(dy+off)**2)
        glow=[a+b*weight for a,b in zip(glow,p)]
    mix=.65 if mode==1 else 1.;amount=.025 if mode==1 else .07
    shade=1-(.035 if mode==1 else .07)*((x+.5)/768*2-1)**2*((y+.5)/720*2-1)**2
    result=[]
    for c in range(3):
        value=max(0,min(1,(linear(source[sy][sx][c])*(1-mix)+(tri[c]+glow[c]*amount)*mix)*shade))
        value=value*12.92 if value<.0031308 else 1.055*value**.41666-.055
        result.append(round(max(0,min(1,value))*255))
    return result


def main():
    exe=str(Path(sys.argv[1]).resolve());rom=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'.nes/wiz1.nes'
    env=dict(os.environ,SDL_VIDEO_DRIVER='dummy',SDL_AUDIO_DRIVER='dummy',SDL_RENDER_DRIVER='software')
    with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='crt-check-') as folder:
        temp=Path(folder)
        result=subprocess.run([exe,'--crt-check',str(rom),str(temp)],capture_output=True,text=True,check=True)
        assert 'CRT_OK presets=3 source_unchanged=1 off_exact=1' in result.stdout
        print(result.stdout.splitlines()[-1])
        w,h,source=bitmap(temp/'crt-0.bmp');assert (w,h)==(256,240)
        for mode in (1,2):
            w,h,image=bitmap(temp/f'crt-{mode}.bmp');assert (w,h)==(768,720)
            differences=0;maximum=0
            for y in range(3,717,19):
                for x in range(3,765,17):
                    expected=reference(source,x,y,mode)
                    maximum=max(maximum,max(abs(a-b) for a,b in zip(image[y][x],expected)))
                    differences+=image[y][x]!=source[y//3][x//3]
            assert maximum<=2,(mode,maximum)
            assert differences>100,(mode,differences)
        images=[];full=[]
        for cycles in (0,1,2,3):
            mode=cycles%3
            script='100 Q down\n101 Q up\n104 Down down\n105 Down up\n108 Down down\n109 Down up\n112 Return down\n113 Return up\n'
            for i in range(cycles):script+=f'{116+i*4} Right down\n{117+i*4} Right up\n'
            script+='132 Backspace down\n133 Backspace up\n'
            for opened in (True,False):
                keys=temp/f'ui-{cycles}-{opened}.txt';keys.write_text(script+('' if opened else '134 Q down\n135 Q up\n'))
                image=temp/f'ui-{cycles}-{opened}.bmp'
                result=subprocess.run([exe,'--smoke-turbo',str(rom),str(image),'140',str(keys),'4'],
                                        env=env,capture_output=True,text=True,check=True)
                assert f'crt={mode} menu_page=0' in result.stdout,result.stdout
                (images if opened else full).append(bitmap(image)[2])
        panel=lambda im:[row[140:884] for row in im[150:662]]
        assert panel(images[0])==panel(images[1])==panel(images[2])
        viewport=lambda im:[row[128:896] for row in im[90:810]]
        assert viewport(images[0])==viewport(images[3]) and viewport(full[0])==viewport(full[3])
        assert viewport(full[0])!=viewport(full[1])!=viewport(full[2])
        print('CRT equations within 2/255, presets, OFF restoration, submenu/back navigation and sharp Q panel: OK')


if __name__=='__main__':main()
