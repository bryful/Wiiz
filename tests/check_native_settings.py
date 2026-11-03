"""Storage/boot checks against real ROMs plus SDL aliases and Q settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    exe = str(Path(sys.argv[1]).resolve())
    env = dict(os.environ, SDL_VIDEO_DRIVER='dummy', SDL_AUDIO_DRIVER='dummy', SDL_RENDER_DRIVER='software')
    with tempfile.TemporaryDirectory(dir=ROOT/'output', prefix='settings-check-') as folder:
        temp = Path(folder)
        for n in (1, 2, 3):
            for suffix in ('', 'p'):
                rom = ROOT/'.nes'/f'wiz{n}{suffix}.nes'
                result = subprocess.run([exe, '--storage-check', str(rom), str(temp/f'{n}{suffix}')],
                                        capture_output=True, text=True, check=True)
                assert f'STORAGE_OK scenario={n}' in result.stdout
                print(rom.name + ': ' + result.stdout.splitlines()[-1])

        rom = ROOT/'.nes/wiz1.nes'
        def play(name, script, frames=20, saves=None):
            keys = temp/(name+'.txt'); keys.write_text(script)
            args = [exe, '--smoke-turbo', str(rom), str(temp/(name+'.bmp')), str(frames), str(keys), '4']
            if saves is not None:
                args.append(str(saves))
            result = subprocess.run(args, env=env, capture_output=True, text=True, check=True)
            return result.stdout.splitlines()[-1]

        for key, bit in (('Return',1), ('Backspace',2), ('Space',8), ('Tab',4)):
            line = play(key, f'1 {key} down\n')
            assert f'held={bit} ' in line and 'save_format=sav' in line, line
        line = play('overlap', '1 X down\n2 Return down\n3 X up\n')
        assert 'held=1 ' in line, line
        line = play('back', '1 Q down\n2 Q up\n4 Backspace down\n5 Backspace up\n')
        assert 'menu=0' in line, line

        # Save/startup settings are grouped in their own page.
        rows = ['100 Q down', '101 Q up']
        for i in range(3):
            rows.extend((f'{104+i*3} Down down', f'{105+i*3} Down up'))
        rows.extend(('114 Return down','115 Return up','120 Return down','121 Return up',
                     '125 Return down','126 Return up','130 Down down','131 Down up',
                     '135 Return down','136 Return up','160 Escape down','161 Escape up'))
        saves = temp/'ui-saves'
        line = play('settings', '\n'.join(rows)+'\n', 180, saves)
        assert 'resets=1' in line and 'save_format=sav skip_maker=1 title_ready=1' in line, line
        assert (saves/'wiz1.sav').stat().st_size == 8192
        assert json.loads((saves/'wiz1.json').read_text())['format'] == 'wiiz-battery'

        # Invalid binary lengths must fail without modifying the supplied file.
        bad = temp/'bad'; bad.mkdir(); target = bad/'wiz1.sav'; target.write_bytes(b'bad')
        keys = temp/'empty.txt'; keys.write_text('')
        result = subprocess.run([exe,'--smoke-turbo',str(rom),str(temp/'bad.bmp'),'5',str(keys),'4',str(bad)],
                                env=env, capture_output=True)
        assert result.returncode != 0 and target.read_bytes() == b'bad'
        print('SDL aliases, overlapping aliases, Q format/skip settings, reset skip and invalid-SAV preservation: OK')


if __name__ == '__main__':
    main()
