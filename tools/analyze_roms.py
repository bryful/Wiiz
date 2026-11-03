"""Extract supported Wizardry FC ROMs and build a common local report."""
import argparse
import html
import json
from pathlib import Path
from extract_chr import extract as extract_chr
from extract_monsters import extract as extract_monsters
from rom_profiles import profile_for
from extract_dungeons import extract as extract_dungeons
from extract_item_spells import extract as extract_item_spells
from build_explorer import build as build_explorer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom-dir', type=Path, default=Path('.nes'))
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--verify', action='store_true', help='Run original ROM routines using py65')
    args = parser.parse_args()
    results = []
    for rom_path in sorted(args.rom_dir.iterdir(), key=lambda p: p.name.lower()):
        if rom_path.suffix.lower() != '.nes' or not rom_path.is_file():
            continue
        rom = rom_path.read_bytes()
        profile = profile_for(rom)
        base = args.output if profile['id'] == 'wiz1' else args.output / profile['id']
        extract_chr(rom_path, base / 'chr')
        extract_monsters(rom_path, base / 'monsters')
        extract_dungeons(rom_path, base / 'dungeons')
        if profile['id'] == 'wiz1':
            build_explorer(rom_path, base / 'explorer')
        extract_item_spells(rom_path, base / 'items_spells')
        if args.verify:
            from verify_monsters import verify
            report = verify(rom)
            (base / 'monsters/verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            from verify_monster_data import verify as verify_data
            (base / 'monsters/data_verification.json').write_text(json.dumps(verify_data(rom), indent=2), encoding='utf-8')
            from verify_dungeons import verify as verify_maps
            (base / 'dungeons/verification.json').write_text(json.dumps(verify_maps(rom), indent=2), encoding='utf-8')
            from verify_item_spells import verify as verify_tables
            (base / 'items_spells/verification.json').write_text(json.dumps(verify_tables(rom), indent=2), encoding='utf-8')
            from verify_game_rules import verify as verify_rules
            (base / 'items_spells/rules_verification.json').write_text(json.dumps(verify_rules(rom), indent=2), encoding='utf-8')
            from verify_item_use import verify as verify_use
            (base / 'items_spells/use_verification.json').write_text(json.dumps(verify_use(rom), indent=2), encoding='utf-8')
            from verify_status_rules import verify as verify_status
            (base / 'items_spells/status_verification.json').write_text(json.dumps(verify_status(rom), indent=2), encoding='utf-8')
            from verify_afflictions import verify as verify_afflictions
            (base / 'items_spells/affliction_verification.json').write_text(json.dumps(verify_afflictions(rom), indent=2), encoding='utf-8')
        chr_info = json.loads((base / 'chr/manifest.json').read_text(encoding='utf-8'))
        monster_info = json.loads((base / 'monsters/monsters.json').read_text(encoding='utf-8'))
        report_path = base / 'monsters/verification.json'
        verification = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
        verified = bool(verification and verification['rom_sha256'] == monster_info['sha256'] and verification['matched'])
        results.append(dict(game=profile['id'], title=profile['title'], source=rom_path.name,
                            sha256=monster_info['sha256'], mapper=chr_info['mapper'],
                            prg_size=chr_info['prg_size'], chr_size=chr_info['chr_size'],
                            monster_count=monster_info['monster_count'], image_count=monster_info['image_count'],
                            unique_layouts=monster_info['unique_layouts'], verified=verified,
                            empty_variants=monster_info['empty_variants'],
                            runtime_palette_variants=monster_info['runtime_palette_variants'],
                            floor_count=10 if profile['id'] == 'wiz1' else 6,
                            base=base.relative_to(args.output).as_posix()))
    if not results:
        parser.error('No supported ROM files found')
    rows = []
    for item in results:
        prefix = '' if item['base'] == '.' else item['base'] + '/'
        notes = []
        if item['empty_variants']:
            notes.append(f'通常描画では空: {item["empty_variants"]}ケース')
        if item['runtime_palette_variants']:
            notes.append(f'一部色が状態依存: {item["runtime_palette_variants"]}ケース')
        play_link = '<a href="explorer/index.html">歩ける探索版</a> · ' if item['game'] == 'wiz1' else ''
        rows.append(f'<tr><td>{html.escape(item["title"])}</td><td>{item["mapper"]}</td><td>{item["monster_count"]}</td><td>{item["image_count"]}</td><td>{item["unique_layouts"]}</td><td>{"一致" if item["verified"] else "未実行"}</td><td>{play_link}<a href="{prefix}items_spells/index.html">アイテム・呪文</a> · <a href="{prefix}dungeons/index.html">ダンジョン {item["floor_count"]}階層</a> · <a href="{prefix}monsters/index.html">モンスター図鑑</a> · <a href="{prefix}chr/index.html">CHR一覧</a> · <a href="{prefix}monsters/atlas.png">画像アトラス</a></td><td>{"<br>".join(notes)}</td></tr>')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'analysis.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    (args.output / 'index.html').write_text('''<!doctype html><html lang="ja"><meta charset="utf-8"><title>Wizardry FC ROM解析</title><style>body{background:#11161e;color:#e8edf6;font:16px sans-serif;margin:32px}table{border-collapse:collapse}th,td{padding:16px;text-align:left;border-bottom:1px solid #344154}a{color:#86c8ff}p{color:#aab9ce}</style><h1>Wizardry FC ROM解析</h1><p>3作品のモンスター図鑑・ダンジョンマップ・アイテム・呪文。各作品の抽出結果を開けます。照合欄はROMの描画ルーチンとの一致です。</p><table><tr><th>作品</th><th>Mapper</th><th>モンスター種</th><th>PNG状態数</th><th>共有除外後の配置数</th><th>ROM処理と照合</th><th>抽出結果</th><th>注記</th></tr>''' + ''.join(rows) + '</table></html>', encoding='utf-8')
    print(f'Analysis index: {args.output / "index.html"}')


if __name__ == '__main__':
    main()
