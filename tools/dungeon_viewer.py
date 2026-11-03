"""SVG dungeon maps and a self-contained local viewer."""
import html
import json
from nes_image import rgb_png

SIZE, PAD = 28, 32


def marker(cell, floor_id):
    event = cell.get('event')
    if not event:
        return ''
    if event['kind'] == 'stairs':
        return 'S'
    return 'T' if event['kind'] == 'teleport' else '?'


def floor_svg(floor):
    shapes = []
    total = PAD * 2 + SIZE * 20
    for i in range(20):
        shapes.append(f'<text x="{PAD + (i + .5) * SIZE}" y="{total - 10}" class="axis">{i}</text>')
        shapes.append(f'<text x="17" y="{PAD + (19 - i + .65) * SIZE}" class="axis">{i}</text>')
    for cell in floor['cells']:
        x, y = cell['x'], cell['y']
        left, top = PAD + x * SIZE, PAD + (19 - y) * SIZE
        shapes.append(f'<rect x="{left}" y="{top}" width="{SIZE}" height="{SIZE}" fill="#172230" stroke="#2b394b" stroke-width=".5"/>')
        if 'area_raw' in cell:
            hue = (cell['encounter_area_id'] * 47) % 360
            shapes.append(f'<rect class="area" x="{left}" y="{top}" width="{SIZE}" height="{SIZE}" fill="hsl({hue} 40% 30%)" opacity=".7"/>')
        if cell['dark']:
            shapes.append(f'<rect class="dark" x="{left}" y="{top}" width="{SIZE}" height="{SIZE}" fill="#0a101a"/>')
        if cell['chamber']:
            shapes.append(f'<rect class="chamber" x="{left + 3}" y="{top + 3}" width="{SIZE - 6}" height="{SIZE - 6}" fill="#774d9c" opacity=".36"/>')
        for direction, opposite, nx, ny in [('north', 'south', x, y + 1), ('east', 'west', x + 1, y), ('south', 'north', x, y - 1), ('west', 'east', x - 1, y)]:
            value = cell['edges'][direction]
            interior = 0 <= nx < 20 and 0 <= ny < 20
            same = interior and floor['cells'][ny * 20 + nx]['edges'][opposite] == value
            if not value or (same and direction in ('south', 'west')):
                continue
            inset = 2 if interior and not same else 0
            coords = dict(north=(left, top + inset, left + SIZE, top + inset),
                          east=(left + SIZE - inset, top, left + SIZE - inset, top + SIZE),
                          south=(left, top + SIZE - inset, left + SIZE, top + SIZE - inset),
                          west=(left + inset, top, left + inset, top + SIZE))
            x1, y1, x2, y2 = coords[direction]
            color = '#e3eaf2' if value == 1 else '#efba67' if value == 2 else '#e18de8'
            dash = ' stroke-dasharray="3 2"' if value == 3 else ''
            shapes.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"{dash}/>')
            if value == 2:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                w, h = (9, 5) if y1 == y2 else (5, 9)
                shapes.append(f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" fill="#172230" stroke="{color}" stroke-width="1.5"/>')
        text = marker(cell, floor['id'])
        if text:
            shapes.append(f'<text class="event" x="{left + SIZE / 2}" y="{top + SIZE / 2 + 5}" fill="#9be2da">{text}</text>')
    # Transparent hit targets come last, above shared edges and markers.
    for cell in floor['cells']:
        x, y = cell['x'], cell['y']
        shapes.append(f'<rect data-cell="{x},{y}" x="{PAD + x * SIZE}" y="{PAD + (19 - y) * SIZE}" width="{SIZE}" height="{SIZE}" fill="transparent"><title>東{x} / 北{y}</title></rect>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" role="img" aria-label="{floor["label"]} 20×20マップ"><style>text{{font:13px sans-serif;text-anchor:middle}}.axis{{fill:#aab9ce}}.event{{pointer-events:none;font-weight:bold}}.area{{display:none}}</style><rect width="100%" height="100%" fill="#11161e"/>{"".join(shapes)}</svg>'


def preview_png(floor, path):
    width = PAD * 2 + SIZE * 20
    pixels = bytearray(bytes.fromhex('11161e') * width * width)

    def rect(x, y, w, h, color):
        color = bytes.fromhex(color)
        for yy in range(max(0, int(y)), min(width, int(y + h))):
            for xx in range(max(0, int(x)), min(width, int(x + w))):
                p = (yy * width + xx) * 3
                pixels[p:p + 3] = color

    for cell in floor['cells']:
        x, y = PAD + cell['x'] * SIZE, PAD + (19 - cell['y']) * SIZE
        rect(x, y, SIZE, SIZE, '0a101a' if cell['dark'] else '172230')
        if cell['chamber']:
            rect(x + 3, y + 3, SIZE - 6, SIZE - 6, '3a304f')
    for cell in floor['cells']:
        x, y = PAD + cell['x'] * SIZE, PAD + (19 - cell['y']) * SIZE
        for direction, v in cell['edges'].items():
            if not v:
                continue
            color = 'e3eaf2' if v == 1 else 'efba67' if v == 2 else 'e18de8'
            if direction in ('north', 'south'):
                yy = y if direction == 'north' else y + SIZE - 2
                rect(x, yy, SIZE, 2, color)
                if v == 2:
                    rect(x + 10, yy - 2, 8, 6, color)
            else:
                xx = x if direction == 'west' else x + SIZE - 2
                rect(xx, y, 2, SIZE, color)
                if v == 2:
                    rect(xx - 2, y + 10, 6, 8, color)
        if 'event' in cell:
            color = '9be2da' if cell['event']['kind'] == 'stairs' else '74aed9' if cell['event']['kind'] == 'teleport' else 'd59e6c'
            rect(x + 11, y + 11, 6, 6, color)
    rgb_png(path, width, width, pixels)


def write_viewer(output, data):
    svgs = []
    for floor in data['floors']:
        svg = floor_svg(floor)
        (output / f'floor_{floor["id"]:02d}.svg').write_text(svg, encoding='utf-8')
        preview_png(floor, output / f'floor_{floor["id"]:02d}.png')
        svgs.append(svg)
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GAME_TITLE ダンジョン</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{background:#11161e;color:#e8edf6;font:15px system-ui,sans-serif;margin:0}header,main{max-width:1200px;margin:auto;padding:24px}h1{margin:8px 0;font-size:28px}p{line-height:1.7;color:#b2c1d4}.controls{display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin-top:20px}select,button{background:#223145;color:#e8edf6;border:1px solid #51617b;border-radius:5px;padding:10px;cursor:pointer}main{display:grid;grid-template-columns:minmax(400px,700px) 1fr;gap:24px;padding-top:0}#map svg{display:block;width:100%;height:auto}#map{min-width:0}.hide-dark .dark,.hide-chamber .chamber,.hide-events .event,.hide-area .area{display:none}aside{padding:20px;background:#1c2531;border:1px solid #344154;border-radius:8px;align-self:start}dl{display:grid;grid-template-columns:80px 1fr;gap:12px}dt{color:#aab9ce}dd{margin:0}h2{font-size:20px;margin-top:0}code{word-break:break-all;font-size:12px}a{color:#86c8ff}.legend{font-size:13px}#event-list{max-height:260px;overflow:auto;padding:0;list-style:none}#event-list button{margin:3px 0;width:100%;text-align:left;font-size:12px}details{font-size:12px;border-top:1px solid #344154;padding-top:12px;margin-top:20px}summary{cursor:pointer}#map [data-cell]{cursor:pointer}button:disabled{opacity:.5;cursor:default}@media(max-width:800px){main{grid-template-columns:1fr}}</style>
<header><h1>GAME_TITLE ダンジョンマップ</h1><p>左下が東0・北0。マスを選ぶと壁とイベントを確認できます。両端は20マスで循環します。</p><div class="controls"><label>階層 <select id="floor"></select></label><label><input type="checkbox" id="dark" checked>ダークゾーン</label><label><input type="checkbox" id="chamber" checked>玄室</label><label><input type="checkbox" id="events" checked>イベント</label><label id="area-label"><input type="checkbox" id="area">玄室管理IDで色分け</label></div><p class="legend">白：壁 ／ 橙：扉 ／ 紫破線：隠し扉 ／ ↑↓：階段 ／ T：座標移動 ／ ?：未分類イベント</p></header>
<main><div id="map" class="hide-area"></div><aside><h2 id="position"></h2><dl id="cell-info"></dl><p id="event-info"></p><button id="destination" hidden>移動先を表示</button><p><a id="svg-link">SVGで保存</a> · <a href="maps.json">共通JSON</a></p><details><summary>解析情報</summary><p id="raw"></p><p>ROM初期状態を表示。イベントの条件分岐やセーブ後の変化は未反映です。非対称の壁は両側の値を残して描画しています。</p></details><h3>この階のイベント</h3><ul id="event-list"></ul></aside></main>
<script>
const data=MAP_DATA, svgs=SVG_DATA;
const byId=id=>document.getElementById(id), directions={north:'北',east:'東',south:'南',west:'西'}, edgeNames=data.edge_types;
let floorIndex=0,selected={x:0,y:0};
function eventLabel(event){if(!event)return 'なし';return {stairs:'階段',teleport:'座標移動',inline:'マス内コード（未分類）',unclassified:'未分類イベント'}[event.kind]||'未分類';}
function selectCell(x,y){selected={x,y};const floor=data.floors[floorIndex],cell=floor.cells[y*20+x];byId('position').textContent=`${floor.label} 東${x}・北${y}`;byId('cell-info').innerHTML=Object.entries(directions).map(([k,v])=>`<dt>${v}</dt><dd>${edgeNames[cell.edges[k]]}</dd>`).join('')+`<dt>地形</dt><dd>${[cell.dark?'ダークゾーン':'',cell.chamber?'玄室':''].filter(Boolean).join('・')||'通常'}</dd>`;const e=cell.event,target=e&&e.destination;byId('event-info').textContent=`イベント：${eventLabel(e)}`+(target?` → ${target.floor===0?'城':`B${target.floor}F`} 東${target.x}・北${target.y}`:'');byId('destination').hidden=!target;byId('destination').disabled=!target||target.floor===0;byId('destination').onclick=()=>{floorIndex=data.floors.findIndex(f=>f.id===target.floor);byId('floor').value=String(floorIndex);showFloor();selectCell(target.x,target.y);};byId('raw').textContent=`壁 0x${cell.walls_raw.toString(16).padStart(2,'0')} / フラグ 0x${cell.flags_raw.toString(16).padStart(2,'0')} / ROM 0x${cell.rom_offsets.walls.toString(16)}`+(cell.area_raw!==undefined?` / 玄室管理ID ${cell.encounter_area_id}（生値${cell.area_raw}）`:'')+(e?` / event slot ${e.slot} / record ${e.raw.map(v=>v.toString(16).padStart(2,'0')).join(' ')}`:'');const svg=byId('map').querySelector('svg');svg.querySelector('#selection')?.remove();const r=document.createElementNS('http://www.w3.org/2000/svg','rect');r.id='selection';for(const [k,v] of Object.entries({x:32+x*28+4,y:32+(19-y)*28+4,width:20,height:20,fill:'none',stroke:'#61e1ff','stroke-width':2,'pointer-events':'none'}))r.setAttribute(k,v);svg.append(r);}
function showFloor(){const floor=data.floors[floorIndex];byId('map').innerHTML=svgs[floorIndex];byId('svg-link').href=`floor_${String(floor.id).padStart(2,'0')}.svg`;byId('event-list').innerHTML=floor.cells.filter(c=>c.event).map(c=>`<li><button data-event-cell="${c.x},${c.y}">東${c.x}・北${c.y}：${eventLabel(c.event)}</button></li>`).join('');selectCell(0,0);}
byId('floor').innerHTML=data.floors.map((f,i)=>`<option value="${i}">${f.label}</option>`).join('');byId('floor').addEventListener('change',e=>{floorIndex=Number(e.target.value);showFloor();});
for(const key of ['dark','chamber','events','area'])byId(key).addEventListener('change',()=>byId('map').classList.toggle(`hide-${key}`,!byId(key).checked));
byId('area-label').hidden=data.game==='wiz1';byId('map').addEventListener('click',e=>{const hit=e.target.closest('[data-cell]');if(hit){const [x,y]=hit.dataset.cell.split(',').map(Number);selectCell(x,y);}});byId('event-list').addEventListener('click',e=>{const hit=e.target.closest('[data-event-cell]');if(hit){const [x,y]=hit.dataset.eventCell.split(',').map(Number);selectCell(x,y);}});showFloor();
</script></html>'''
    page = page.replace('↑↓：階段', 'S：階段').replace('`B${target.floor}F`', '`階層 ${target.floor}`')
    page = page.replace('.hide-dark .dark,', '#map:not(.hide-area) .area{display:block}.hide-dark .dark,')
    page = page.replace('GAME_TITLE', html.escape(data['title'])).replace('MAP_DATA', json.dumps(data)).replace('SVG_DATA', json.dumps(svgs))
    (output / 'index.html').write_text(page, encoding='utf-8')
