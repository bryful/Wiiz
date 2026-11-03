"""Wizardry program-family fingerprints, independent of character/CHR edits."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def identity_profiles():
    return json.loads((Path(__file__).resolve().parents[1]/'app/rom_identity_profiles.json').read_text())


def inspect_wizardry(rom):
    if len(rom)<16 or rom[:4]!=b'NES\x1a':
        raise ValueError('Not an iNES ROM')
    if rom[7]&12==8:
        raise ValueError('NES 2.0 ROM identification is not implemented')
    mapper=(rom[6]>>4)|(rom[7]&240)
    offset=16+(512 if rom[6]&4 else 0)
    size=rom[4]*16384
    chr_size=rom[5]*8192
    if size<32768 or not chr_size or offset+size+chr_size>len(rom):
        raise ValueError('Truncated or unsupported iNES ROM')
    prg=rom[offset:offset+size];fixed=size-16384;config=identity_profiles()
    digest=lambda start,count:hashlib.sha256(prg[start:start+count]).hexdigest()
    signatures=[digest(fixed+n,config['window_size']) for n in config['window_offsets']]
    matches=[p for p in config['profiles'] if p['mapper']==mapper and
             sum(a==b for a,b in zip(signatures,p['signatures']))>=config['minimum_matches']]
    if len(matches)!=1:
        raise ValueError('Unrecognized or ambiguous Wizardry program identity')
    profile=matches[0]
    layout=(size==131072 and digest(fixed,16384)==profile['fixed_sha256'] and
            digest(0x18000,16384)==profile['camp_sha256'])
    enhanced=(profile['scenario']==1 and layout and digest(0x8000,16384)==profile['sound_sha256'])
    enhancements=layout and digest(0x8000 if profile['scenario']==1 else 0xa000,16384 if profile['scenario']==1 else 8192)==profile['sound_sha256'] and (profile['scenario']==1 or digest(0xc000,16384)==profile['spell_sha256'])
    return dict(scenario=profile['scenario'],mapper=mapper,prg_offset=offset,prg_bytes=size,
                chr_bytes=chr_size,known_layout=layout,enhanced_wiz1=enhanced,enhanced=enhancements,verified_boot=enhancements and digest(0x18000 if profile["scenario"]==1 else 0x8700,0x100 if profile["scenario"]==1 else 0x300)==profile["boot_sha256"])
