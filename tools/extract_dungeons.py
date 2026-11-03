"""Extract all floors and generate the local dungeon viewer."""
import argparse
import hashlib
import json
from pathlib import Path
from dungeon_data import read_dungeons
from dungeon_viewer import write_viewer


def extract(rom_path, output):
    rom = rom_path.read_bytes()
    data = read_dungeons(rom)
    data['sha256'] = hashlib.sha256(rom).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'maps.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    write_viewer(output, data)
    print(f'{data["game"]}: extracted {data["floor_count"]} floors / {data["floor_count"] * 400} cells to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = read_dungeons(args.rom.read_bytes())
    base = Path('output') if data['game'] == 'wiz1' else Path('output') / data['game']
    extract(args.rom, args.output or base / 'dungeons')
