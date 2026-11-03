"""Real-ROM JSON migration/editing and native state/SDL slot integration."""
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
    with tempfile.TemporaryDirectory(dir=ROOT/'output', prefix='persistence-check-') as folder:
        temp = Path(folder)
        for scenario, name in enumerate(('wiz1.nes', 'WIZ2.NES', 'WIZ3.NES'), 1):
            result = subprocess.run([exe, '--persistence-check', str(ROOT/'.nes'/name), str(temp/str(scenario))],
                                    capture_output=True, text=True, check=True)
            assert f'PERSISTENCE_OK scenario={scenario}' in result.stdout
            print(result.stdout.splitlines()[-1])
            document = json.loads(next((temp/str(scenario)/'saves').glob('*.json')).read_text(encoding='utf-8'))
            assert document['characters'][0]['level'] == 17 and document['checksum_validation'] is False
            assert len(document['characters']) == 20
            battery = next((temp/str(scenario)/'saves').glob('*.json'))
            good = battery.read_bytes()
            battery.write_text('{ broken JSON', encoding='utf-8')
            refused = subprocess.run([exe, '--core-check', str(ROOT/'.nes'/name), str(battery.parent)],capture_output=True)
            assert refused.returncode != 0 and battery.read_bytes() == b'{ broken JSON'
            battery.write_bytes(good)
        # Exercise all F keys, Shift modifiers, and both actions on a Q-menu slot.
        lines = []
        tick = 5

        def press(key):
            nonlocal tick
            lines.extend((f'{tick} {key} down', f'{tick+1} {key} up'))
            tick += 4

        press('Shift+F1')  # Empty slot: report error and continue.
        for slot in range(1, 6):
            press(f'F{slot}')
        for slot in range(1, 6):
            press(f'Shift+F{slot}')
        press('Q')
        press('Down')
        press('X')  # State save / load page starts at slot 1.
        for _ in range(4):
            press('Down')
        press('X')  # Save slot 5 from menu.
        press('Right')
        press('X')  # Load slot 5 from menu.
        keys = temp/'keys.txt'; keys.write_text('\n'.join(lines)+'\n')
        result = subprocess.run([exe, '--smoke-turbo', str(ROOT/'.nes/wiz1.nes'), str(temp/'slots.bmp'),
                                 str(tick+5), str(keys), '4', str(temp/'ui/saves')],
                                capture_output=True, text=True, check=True, env=env)
        assert 'state_saves=6 state_loads=6 state_errors=1' in result.stdout, result.stdout
        assert 'menu=1' in result.stdout
        slots = list((temp/'ui/states').glob('*/slot*.json'))
        assert len(slots) == 5 and all(json.loads(p.read_text())['format'] == 'wiiz-state' for p in slots)
        keys.write_text('5 Shift+F1 down\n6 Shift+F1 up\n')
        result = subprocess.run([exe, '--smoke-turbo', str(ROOT/'.nes/wiz1.nes'), str(temp/'restarted.bmp'),
                                 '90', str(keys), '1', str(temp/'ui/saves')],
                                capture_output=True, text=True, check=True, env=env)
        assert 'state_saves=0 state_loads=1 state_errors=0' in result.stdout, result.stdout
        print('SDL shortcuts F1-F5 / Shift+F1-F5, Q slot 5 Save/Load and empty-slot recovery: OK')
        print('Restarted-process state load and invalid battery JSON preservation: OK')


if __name__ == '__main__':
    main()
