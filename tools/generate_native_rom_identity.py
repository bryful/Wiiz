"""Generate embedded C++ fingerprints from shared JSON (no ROM files required)."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    config=json.loads((ROOT/'app/rom_identity_profiles.json').read_text())
    assert len(config['window_offsets'])==6 and all(len(p['signatures'])==6 for p in config['profiles'])
    lines=['// Generated from rom_identity_profiles.json; fingerprints only, no ROM data.','#pragma once',
           '#include <array>','#include <cstddef>',
           'struct IdentityFingerprint { int scenario,mapper;std::array<const char*,6> signatures;const char* fixed;const char* camp;const char* sound;const char* spell;const char* boot; };',
           'inline constexpr std::array<std::size_t,6> identityWindows={'+','.join(map(str,config['window_offsets']))+'};',
           'inline constexpr std::size_t identityWindowSize='+str(config['window_size'])+';',
           'inline constexpr unsigned identityMinMatches='+str(config['minimum_matches'])+';',
           'inline constexpr IdentityFingerprint identityFingerprints[]={']
    for p in config['profiles']:
        lines.append('{'+str(p['scenario'])+','+str(p['mapper'])+',{'+','.join('"'+s+'"' for s in p['signatures'])+'},"'+p['fixed_sha256']+'","'+p['camp_sha256']+'","'+p['sound_sha256']+'","'+p['spell_sha256']+'","'+p['boot_sha256']+'"},')
    lines.append('};');text='\n'.join(lines)+'\n';path=ROOT/'app/rom_identity_data.hpp'
    if args.check:
        if path.read_text()!=text:raise SystemExit('Embedded ROM fingerprints are stale; regenerate them')
    else:path.write_text(text)


if __name__=='__main__':main()
