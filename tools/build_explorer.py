"""Build the self-contained Wiz1 walking prototype from verified ROM map data."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from dungeon_data import read_dungeons
from item_spell_data import extract_data
from monster_data import read_monster
from encounter_data import read_encounters

ROOT = Path(__file__).resolve().parents[1]


def build(rom_path, output):
    rom = rom_path.read_bytes()
    data = read_dungeons(rom)
    if data['game'] != 'wiz1':
        raise ValueError('The first exploration prototype supports Wiz1 only')
    data['sha256'] = hashlib.sha256(rom).hexdigest()
    extracted = extract_data(rom)
    data['items'] = [dict(id=i['id'], name_ja=i['name_ja'], name_en=i['name_en'], stats=i['stats']) for i in extracted['items']]
    data['spells'] = extracted['spells']
    data['enemyRules'] = dict(spell_tables=dict(mage=list(rom[0x1dd20:0x1dd30]),priest=list(rom[0x1dd30:0x1dd40])))
    data['encounters'] = read_encounters(rom)
    data['monsters'] = []
    # Include every Wiz1 monster so all ten floor tables can be used offline.
    for monster_id in range(101):
        monster = read_monster(rom, monster_id)
        image = ROOT / f'output/monsters/{monster_id:03}_identified.png'
        data['monsters'].append(dict(id=monster_id, name_ja=monster['name_ja'], stats=monster['stats'],
                                    image='data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode('ascii') if image.exists() else ''))
    sources = ROOT / 'web/explorer'
    page = (sources / 'index.html').read_text(encoding='utf-8')
    for placeholder, value in [('__MAPS__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')),
                               ('__COMBAT_RULES__', (sources / 'combat-rules.js').read_text(encoding='utf-8')),
                               ('__ENEMY_RULES__', (sources / 'enemy-rules.js').read_text(encoding='utf-8')),
                               ('__PARTY__', (sources / 'party.js').read_text(encoding='utf-8')),
                               ('__BATTLE__', (sources / 'battle.js').read_text(encoding='utf-8')),
                               ('__ENCOUNTERS__', (sources / 'encounters.js').read_text(encoding='utf-8')),
                               ('__VIEW__', (sources / 'view.js').read_text(encoding='utf-8')),
                               ('__ENGINE__', (sources / 'engine.js').read_text(encoding='utf-8')),
                               ('__PARTY_UI__', (sources / 'party-ui.js').read_text(encoding='utf-8')),
                               ('__TURN_UI__', (sources / 'turn-ui.js').read_text(encoding='utf-8')),
                               ('__UI__', (sources / 'ui.js').read_text(encoding='utf-8'))]:
        page = page.replace(placeholder, value)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(page, encoding='utf-8')
    print(f'Wiz1 explorer: {output / "index.html"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path, nargs='?', default=Path('.nes/wiz1.nes'))
    parser.add_argument('--output', type=Path, default=Path('output/explorer'))
    args = parser.parse_args()
    build(args.rom, args.output)
