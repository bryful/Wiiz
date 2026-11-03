"""Execute original 6502 creation routines for analysis; no game/ROM patches.
Uses the project's existing py65 dependency, not a replacement gameplay core.
Rendering/frame waits and RNG draws for II/III are substituted only in the
branch tests; I exhaustively executes the original RNG for all 65536 states.
"""
import argparse
import hashlib
import json
from pathlib import Path
from trace_graphics import MPU
from rom_identity import inspect_wizardry

RACES=('human','elf','dwarf','gnome','hobbit')
CONFIG={
  1:dict(generate=0x9d5d,stop=0x9d7c,table=0xef52,step=8,pool=0x25b,stats=0x254,base=None,index=0x2c,inc=0x9e2e,dec=0x9e4a,ends=(0x9e5e,0x9db9)),
  2:dict(generate=0xdbdf,stop=0xdc04,table=0xdc20,step=6,pool=0x40,stats=0x4d,base=0x53,index=0x36,inc=0xd579,dec=0xd58a,ends=(0x7000,),rng=0xf028,wait=0xe3b0,proc=9,cap=0xdc1b),
  3:dict(generate=0xdbaf,stop=0xdbd4,table=0xdc0b,step=6,pool=0x40,stats=0x4d,base=0x53,index=0x36,inc=0xd559,dec=0xd56d,ends=(0x7000,),rng=0xed10,wait=0xfead,proc=15),
}

def memory(rom,game):
    start=16+(512 if rom[6]&4 else 0)
    prg=rom[start:start+rom[4]*16384]
    out=bytearray(65536)
    out[0xc000:]=prg[-16384:]
    if game==1:out[0x8000:0xc000]=prg[6*16384:7*16384]
    return out

def run(cpu,stops,draws=None,rng=None,wait=None):
    for _ in range(20000):
        if cpu.pc in stops:return
        if draws is not None and cpu.pc==rng:
            cpu.a=next(draws)
            cpu.pc=(cpu.stPopWord()+1)&65535
        elif wait is not None and cpu.pc==wait:
            cpu.pc=(cpu.stPopWord()+1)&65535
        else:cpu.step()
    raise AssertionError(f'Routine did not stop at {cpu.pc:04X}')

def analyze(path,game):
    rom=path.read_bytes()
    identity=inspect_wizardry(rom)
    if identity['scenario']!=game or not identity['known_layout']:
        raise ValueError('Unverified ROM code layout')
    m=memory(rom,game);c=CONFIG[game];cpu=MPU(memory=m)
    bases=[list(m[c['table']+r*c['step']:c['table']+r*c['step']+6]) for r in range(5)]
    if game==1:
        seen=set();witness={}
        for state in range(65536):
            m[0x40]=state&255;m[0x41]=state>>8
            cpu.pc=c['generate'];cpu.sp=255;cpu.p=0x30
            run(cpu,(c['stop'],))
            result=m[c['pool']];seen.add(result);witness.setdefault(result,state)
        maximum=[max(seen)]*5;cases=65536
        generation=dict(minimum=min(seen),maximum=max(seen),reachable_values_without_nmi=sorted(seen),rng_states=cases,maximum_witness=witness[max(seen)])
    else:
        seen=[set() for _ in range(5)];cases=0
        for race in range(5):
            for first in range(5):
                for proc_count in range(8):
                    m[0x41]=race;cpu.pc=c['generate'];cpu.sp=255;cpu.p=0x30
                    draws=iter([first]+[c['proc']]*proc_count+[0])
                    run(cpu,(c['stop'],),draws,c['rng'],c['wait'])
                    seen[race].add(m[c['pool']]);cases+=1
        maximum=[max(v) for v in seen]
        generation=dict(rng_draw_branch_cases=cases,maximum_by_race=maximum,reachable_values_by_race=[sorted(v) for v in seen])
    allocation=[]
    for race,base in enumerate(bases):
        for offset,value in enumerate(base):
            m[c['stats']+offset]=value
            if c['base'] is not None:m[c['base']+offset]=value
        if game==1:
            ptr=c['table']+race*c['step'];m[0x34]=ptr&255;m[0x35]=ptr>>8
        m[c['pool']]=64
        for stat in range(6):
            m[c['index']]=stat
            for _ in range(40):
                before=m[c['stats']+stat];cpu.pc=c['inc'];cpu.sp=255;cpu.p=0x30;cpu.stPushWord(0x6fff)
                run(cpu,c['ends'])
                if m[c['stats']+stat]==before:break
        upper=list(m[c['stats']:c['stats']+6]);remaining=m[c['pool']]
        assert remaining==64-sum(v-b for v,b in zip(upper,base))
        # Refund all points through the original decrement handler too.
        for stat in range(6):
            m[c['index']]=stat
            for _ in range(40):
                before=m[c['stats']+stat];cpu.pc=c['dec'];cpu.sp=255;cpu.p=0x30;cpu.stPushWord(0x6fff)
                run(cpu,c['ends'])
                if m[c['stats']+stat]==before:break
        assert list(m[c['stats']:c['stats']+6])==base and m[c['pool']]==64
        allocation.append(dict(race=RACES[race],base=base,upper=upper,spendable=sum(v-b for v,b in zip(upper,base)),remaining_from_64=remaining,natural_maximum=maximum[race]))
    return dict(rom_name=path.name,sha256=hashlib.sha256(rom).hexdigest(),scenario=game,generation=generation,allocation=allocation,
                verified_scope='Original arithmetic/branch and allocation routines with py65; not full UI or character-save execution')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('output/creation-bonus-analysis.json'));args=parser.parse_args()
    result=[]
    for name,game in [('wiz1',1),('WIZ2',2),('WIZ3',3),('wiz1p',1),('wiz2p',2),('wiz3p',3)]:
        item=analyze(Path('.nes')/(name+'.nes'),game);result.append(item)
        print(name,'natural max:',[r['natural_maximum'] for r in item['allocation']], 'capacity:',[r['spendable'] for r in item['allocation']],flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
