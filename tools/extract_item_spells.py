"""Export item/spell tables and an offline searchable viewer."""
import argparse
import json
from pathlib import Path
from item_spell_data import extract_data


PAGE = '''<!doctype html><html lang="ja"><meta charset="utf-8"><title>アイテム・呪文</title>
<style>body{background:#101620;color:#e5edf8;font:16px system-ui;margin:24px}a{color:#8ccfff}input,select,button{font:inherit;padding:8px;background:#202e40;color:inherit;border:1px solid #526780;border-radius:5px}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #344154}small,p{color:#b6c4d8}details{max-width:700px}pre{white-space:pre-wrap;overflow-wrap:anywhere}#controls{display:flex;gap:10px;flex-wrap:wrap;position:sticky;top:0;background:#101620;padding:12px 0}h1{font-size:26px}</style>
<h1 id="title"></h1><p>ROMから抽出した名前・価格・装備情報・呪文レベル。SP・AC呪文・基本回復量と使用後の変化条件を表示します。変化条件のrは0〜255の乱数バイトで、通常使用の場面判定と未解析効果は詳細を参照してください。</p>
<details><summary>状態コードと毒の扱い</summary><p>毒は状態コード8ではなく別の値です。正常時は毒の表示を優先します。</p><table><thead><tr><th>コード</th><th>日本語</th><th>英語</th></tr></thead><tbody id="statusrows"></tbody></table></details>
<div id="controls"><select id="mode"><option value="items">アイテム</option><option value="spells">呪文</option></select><input id="query" placeholder="日本語・英語・IDで検索" aria-label="検索"><select id="school"><option value="">全系統</option><option value="mage">魔術師</option><option value="priest">僧侶</option></select><span id="count"></span><a href="data.json">JSON</a></div>
<table><thead id="head"></thead><tbody id="rows"></tbody></table>
<script id="data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const targets={caster:'術者',enemy_group:'敵1グループ',all_enemies:'敵全体',party:'味方全体',selected_ally:'味方1人'};
const dice=d=>d.count+'d'+d.sides+(d.bonus?'+'+d.bonus:'');
function effectText(e){if(e.kind==='status_infliction')return esc(e.summary)+'<br><small>抵抗・レベル判定あり。味方の詠唱時は敵1グループ。</small>';if(e.kind==='ac_modifier')return 'AC '+(e.delta>0?'+':'')+e.delta+' / '+targets[e.target]+'<br><small>戦闘中・下限−99 / 上限99</small>';if(e.kind==='healing')return 'HP回復 '+dice(e.healing)+' / 味方1人<br><small>最大HPまで・状態コード5未満</small>';if(e.kind==='status_cure')return esc(e.summary)+'<br><small>味方1人・詳細に適用条件を表示</small>';if(e.kind==='resurrection')return esc(e.summary)+'<br><small>成功判定あり・生命力低下と失敗処理は作品別</small>';return e.damage?dice(e.damage)+' (属性生値 '+e.element_raw+')<br><small>ダメージ定数・詳細効果は解析中</small>':'未解析';}
function useText(r){const u=r.use_rules;return esc(r.special_power?.summary??'—')+'<details><summary>使用後の変化</summary><small>通常使用: '+esc(u.normal.condition)+(r.stats.special_power_raw>0&&r.special_power?'<br>SP: '+esc(u.sp.condition):'')+'<br>条件成立時 → '+esc(u.replacement_name_ja)+' (#'+u.replacement_item_id+')<br>通常使用は使用効果が選ばれた後、SPは発動確認後の判定。</small></details>';}
$('title').textContent=data.title+' アイテム・呪文';
$('statusrows').innerHTML=data.rules.status.statuses.map(s=>'<tr><td>'+s.code+'</td><td>'+esc(s.name_ja)+'</td><td>'+esc(s.name_en)+'</td></tr>').join('');
function render(){const mode=$('mode').value,q=$('query').value.trim().toLowerCase(),school=$('school').value;
$('school').hidden=mode!=='spells';
const selected=data[mode].filter(r=>(!q||[r.id,r.name_ja,r.name_en,r.unknown_name_ja,r.unknown_name_en].join(' ').toLowerCase().includes(q))&&(mode!=='spells'||!school||r.school===school));
$('count').textContent=selected.length+' / '+data[mode].length+' 件';
$('head').innerHTML='<tr><th>ID</th><th>名前</th>'+(mode==='items'?'<th>価格</th><th>装備可能</th><th>AC補正 / ダメージ</th><th>SP・使用後の変化</th>':'<th>系統 / レベル</th><th>解析済みの効果・定数</th>')+'<th>詳細・ROM参照</th></tr>';
$('rows').innerHTML=selected.map(r=>{let cells;if(mode==='items'){const s=r.stats,d=s.damage,jobs=['戦士','魔術師','僧侶','盗賊','司教','侍','君主','忍者'].filter((_,i)=>s.equip_mask&(1<<i)).join('・');cells='<td>'+s.price.toLocaleString()+'</td><td>'+jobs+'</td><td>'+s.ac_modifier+' / '+(d.count&&d.sides?dice(d):'—')+'</td><td>'+useText(r)+'</td>';}else{cells='<td>'+(r.school==='mage'?'魔術師':'僧侶')+' Lv.'+r.level+'</td><td>'+effectText(r.effect)+'</td>';}
return '<tr><td>'+r.id+'</td><td>'+esc(r.name_ja)+'<br><small>'+esc(r.name_en)+'</small></td>'+cells+'<td><details><summary>抽出値を表示</summary><pre>'+esc(JSON.stringify(r,null,2))+'</pre></details></td></tr>';}).join('');}
for(const id of ['mode','query','school'])$(id).addEventListener(id==='query'?'input':'change',render);render();
</script></html>'''


def extract(rom_path, output):
    data = extract_data(rom_path.read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    (output / 'data.json').write_text(payload + '\n', encoding='utf-8')
    (output / 'index.html').write_text(PAGE.replace('__DATA__', payload.replace('<', '\\u003c')), encoding='utf-8')
    print(f'{data["game"]}: {len(data["items"])} items, {len(data["spells"])} spells -> {output}')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    extract(args.rom, args.output)
