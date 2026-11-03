"""Run after a native rebuild: family detection, p-ROM boot and raw fallback."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    exe=str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='edited-rom-check-') as folder:
        temp=Path(folder);roms=temp/'roms';roms.mkdir()
        for n in (1,2,3):
            original=ROOT/'.nes'/f'wiz{n}.nes';patched=ROOT/'.nes'/f'wiz{n}p.nes'
            # Arbitrary filename: no filename-based scenario inference.
            renamed=roms/f'custom{n}.NES';renamed.write_bytes(patched.read_bytes())
            result=subprocess.run([exe,'--core-check',str(renamed),str(temp/f'save{n}')],capture_output=True,text=True,check=True)
            assert 'CORE_OK' in result.stdout
            doc=json.loads(next((temp/f'save{n}').glob('*.json')).read_text())
            assert doc['format']=='wiiz-battery' and doc['scenario']==n
            a=subprocess.check_output([exe,'--check',str(original)])
            b=subprocess.check_output([exe,'--check',str(renamed)])
            assert a==b
            print(f'Edited ROM {n}: native core 720 frames, structured JSON and map extraction OK')
        scan=subprocess.check_output([exe,'--scan',str(roms)],text=True)
        assert 'supported=3 rejected=0' in scan,scan
        # Change an unused tail byte in the camp bank: same Wiz family, unknown layout profile.
        fallback=bytearray((ROOT/'.nes/wiz1.nes').read_bytes());fallback[16+0x1bfff]^=1
        path=temp/'fallback.nes';path.write_bytes(fallback)
        subprocess.run([exe,'--core-check',str(path),str(temp/'raw')],capture_output=True,check=True)
        doc=json.loads(next((temp/'raw').glob('*.json')).read_text())
        assert doc['format']=='wiiz-battery-raw' and len(doc['bytes'])==8192
        print('Unknown-layout Wiz revision: native emulation and raw JSON SRAM roundtrip OK')


if __name__=='__main__':main()
