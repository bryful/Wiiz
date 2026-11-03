"""Local, self-contained monster catalog UI."""
import html


def esc(value):
    return html.escape(str(value), quote=True)


def write_catalog(output, manifest):
    cards = []
    for monster in manifest['monsters']:
        s = monster['stats']
        hp = s['hp']
        hp_range = f'{hp["minimum"]}〜{hp["maximum"]}' if hp['minimum'] is not None else '特殊値'
        attacks = ' / '.join(d['expression'] for d in s['attacks']) or 'なし'
        variants = []
        for v in monster['variants']:
            variants.append(f'<figure><div class="sprite"><img alt="{esc(monster["name_ja"])}" src="{v["image"]}" width="{v["bounds"][2] * 3}" height="{v["bounds"][3] * 3}"></div><figcaption>{"確定" if v["identified"] else "不確定"}</figcaption><p class="note">{esc(v["preview_note"])}</p></figure>')
        search = ' '.join(str(monster.get(k, '')) for k in ('id', 'name', 'unknown_name', 'name_ja', 'unknown_name_ja'))
        source = monster['data_source']
        notes = [d['note'] for d in [s['encounter'], hp, *s['attacks']] if d['note']]
        card = f'''<article data-id="{monster['id']}" data-exp="{s['experience']}" data-ac="{s['ac']}" data-hp="{hp['maximum'] or 0}" data-magic="{int(bool(s['mage_spell_level'] or s['priest_spell_level']))}" data-search="{esc(search)}">
<span class="id">#{monster['id']:03d} · LV {s['level']}</span><h2>{esc(monster['name_ja'])}</h2><p class="english">{esc(monster['name'])}</p><p class="unknown">不確定名：{esc(monster['unknown_name_ja'])}</p>
<div class="pair">{''.join(variants)}</div>
<dl class="key-stats"><div><dt>HP</dt><dd>{hp_range}</dd></div><div><dt>AC</dt><dd>{s['ac']}</dd></div><div><dt>経験値</dt><dd>{s['experience']:,}</dd></div></dl>
<dl class="parameters"><dt>HPダイス</dt><dd>{esc(hp['expression'])}</dd><dt>出現数ダイス</dt><dd>{esc(s['encounter']['expression'])}</dd><dt>攻撃</dt><dd>{s['attack_count']}回 · {esc(attacks)}</dd><dt>呪文レベル</dt><dd>魔術師系 {s['mage_spell_level']} / 僧侶系 {s['priest_spell_level']}</dd></dl>
<p class="note">{esc(' / '.join(sorted(set(notes))))}</p>
<details><summary>解析情報</summary><p>レコード：0x{source['record_rom_offset']:06X}<br>能力値：0x{source['stats_rom_offset']:06X}</p><code>{source['stats_raw_hex']}</code></details></article>'''
        cards.append(card)
    title = esc(manifest['title'])
    page = f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} モンスター図鑑</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#11161e;color:#e8edf6;font:15px system-ui,sans-serif}}header,main{{max-width:1480px;margin:auto;padding:24px}}header{{padding-top:36px}}h1{{font-size:30px;margin:0 0 8px}}header p{{color:#aab9ce;line-height:1.7}}.toolbar{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0 12px}}input,select{{background:#1c2531;color:#e8edf6;border:1px solid #52647c;border-radius:6px;padding:12px;font:inherit}}input{{flex:1;min-width:240px}}label{{display:flex;align-items:center;gap:8px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,390px),1fr));gap:22px;padding-top:0}}article{{background:#1c2531;border:1px solid #344154;border-radius:10px;padding:22px;min-width:0}}article[hidden]{{display:none}}h2{{font-size:23px;margin:6px 0}}p{{margin:8px 0}}.id,.english,.unknown,dt{{color:#aab9ce}}.id{{font-size:12px;letter-spacing:.08em}}.english{{font-size:13px}}.unknown{{font-size:13px}}.pair{{display:flex;gap:12px;margin:18px 0}}figure{{margin:0;width:50%;min-width:0}}.sprite{{background:#080c12;height:240px;display:flex;align-items:center;justify-content:center;border-radius:6px}}img{{image-rendering:pixelated;max-width:100%;max-height:232px;object-fit:contain}}figcaption{{text-align:center;font-size:12px;color:#aab9ce;margin:8px 0}}.note{{font-size:12px;color:#edc382;line-height:1.6}}dl{{margin:0}}.key-stats{{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #344154;border-bottom:1px solid #344154;padding:15px 0;margin:16px 0}}.key-stats dt{{font-size:12px}}.key-stats dd{{font-size:23px;margin:5px 0 0;font-variant-numeric:tabular-nums}}.parameters{{display:grid;grid-template-columns:110px 1fr;gap:10px;font-size:13px}}.parameters dd{{margin:0;overflow-wrap:anywhere}}details{{border-top:1px solid #344154;margin-top:16px;padding-top:12px;font-size:12px;color:#aab9ce}}summary{{cursor:pointer}}code{{word-break:break-all}}a{{color:#86c8ff}}</style>
<header><h1>{title} モンスター図鑑</h1><p>{manifest['monster_count']}種。ROMから読み出した日本語名・能力値と、不確定／確定の画像を比較できます。<br>HPは通常のダイス式の範囲です。画像のRGBは確認用で、特殊値・状態依存の色には注記しています。</p>
<div class="toolbar"><input id="search" aria-label="名前またはIDで検索" placeholder="日本語名・英語名・IDで検索"><label>並び順<select id="sort"><option value="id">ID順</option><option value="exp">経験値が高い順</option><option value="hp">最大HPが高い順</option><option value="ac">ACが低い順</option></select></label><label>呪文<select id="magic"><option value="all">すべて</option><option value="1">あり</option><option value="0">なし</option></select></label></div><p><span id="count">{manifest['monster_count']}</span>件表示 · <a href="monsters.json">共通JSONデータ</a></p></header>
<main>{''.join(cards)}</main><script>
const articles=[...document.querySelectorAll('article')], search=document.querySelector('#search'), sort=document.querySelector('#sort'), magic=document.querySelector('#magic');
const normalize=s=>s.normalize('NFKC').toLowerCase();
function update(){{const query=normalize(search.value.trim());let count=0;articles.forEach(a=>{{a.hidden=!(normalize(a.dataset.search).includes(query)&&(magic.value==='all'||a.dataset.magic===magic.value));if(!a.hidden)count++;}});const key=sort.value;[...articles].sort((a,b)=>{{const d=Number(a.dataset[key])-Number(b.dataset[key]);return (key==='exp'||key==='hp'?-d:d)||Number(a.dataset.id)-Number(b.dataset.id);}}).forEach(a=>document.querySelector('main').append(a));document.querySelector('#count').textContent=count;}}
search.addEventListener('input',update);sort.addEventListener('change',update);magic.addEventListener('change',update);
</script></html>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
