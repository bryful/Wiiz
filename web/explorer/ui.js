(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const data = JSON.parse($('maps').textContent), game = WizExplorer.create(data);
  const canvas = $('view'), ctx = canvas.getContext('2d'), mini = $('map').getContext('2d');
  const names = ['北', '東', '南', '西'], compass = ['NORTH', 'EAST', 'SOUTH', 'WEST'];
  const storageKey = 'wiiz.explorer.wiz1.v1';
  const partyUI = WizPartyUI.create(game, () => render());
  const turnUI = WizTurnUI.create(game, () => render());
  let wasInBattle=false;
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function drawView() {
    const w = canvas.width, h = canvas.height, s = game.state;
    ctx.fillStyle = '#030609'; ctx.fillRect(0, 0, w, h);
    if (s.phase === 'outside' || game.cell().dark) return;
    const ceiling = ctx.createLinearGradient(0, 0, 0, h / 2);
    ceiling.addColorStop(0, '#1b2530'); ceiling.addColorStop(1, '#030609');
    ctx.fillStyle = ceiling; ctx.fillRect(0, 0, w, h / 2);
    const floor = ctx.createLinearGradient(0, h / 2, 0, h);
    floor.addColorStop(0, '#04080b'); floor.addColorStop(1, '#283039');
    ctx.fillStyle = floor; ctx.fillRect(0, h / 2, w, h / 2);

    for (let x = 0; x < w; x += 2) {
      const camera = 2 * (x + 1) / w - 1;
      const hit = WizView.cast(game, camera);
      const height = Math.min(h * 2, (w / (2 * WizView.FOV)) / Math.max(.05, hit.distance));
      const top = (h - height) / 2;
      if (hit.dark) { ctx.fillStyle = '#030609'; ctx.fillRect(x, top, 2, height); continue; }
      const light = Math.max(.14, Math.min(1, 1.2 / (1 + hit.distance * .27))) * (hit.vertical ? .78 : 1);
      const base = hit.door ? [137, 105, 62] : [120, 139, 150];
      const rgb = factor => `rgb(${base.map(v => Math.round(v * light * factor)).join(',')})`;
      ctx.fillStyle = rgb(1); ctx.fillRect(x, top, 2, height);
      if (hit.door) {
        if ((hit.u * 8) % 1 < .06 || hit.u < .035 || hit.u > .965) {
          ctx.fillStyle = rgb(.35); ctx.fillRect(x, top, 2, height);
        }
        ctx.fillStyle = rgb(.35);
        ctx.fillRect(x, top + height * .17, 2, Math.max(1, height * .025));
        ctx.fillRect(x, top + height * .81, 2, Math.max(1, height * .025));
        if (hit.u > .73 && hit.u < .80) { ctx.fillStyle = '#b9a474'; ctx.fillRect(x, top + height * .51, 2, Math.max(2, height * .025)); }
      } else {
        for (let row = 0; row <= 8; row++) {
          ctx.fillStyle = rgb(.57); ctx.fillRect(x, top + height * row / 8, 2, Math.max(1, height / 150));
          const u = (hit.u * 3 + (row % 2) / 2) % 1;
          if (row < 8 && u < .035) ctx.fillRect(x, top + height * row / 8, 2, height / 8);
        }
      }
    }
    const vignette = ctx.createRadialGradient(w / 2, h / 2, h * .12, w / 2, h / 2, w * .6);
    vignette.addColorStop(0, '#00000000'); vignette.addColorStop(1, '#00000099');
    ctx.fillStyle = vignette; ctx.fillRect(0, 0, w, h);
  }

  function drawMap() {
    const s = game.state, size = 14, pad = 20;
    mini.fillStyle = '#0a1015'; mini.fillRect(0, 0, 320, 320);
    let count = 0;
    for (const c of data.floors[s.floor - 1].cells) {
      if (!s.visited.has(`${s.floor}:${c.x}:${c.y}`)) continue;
      count++;
      const x = pad + c.x * size, y = pad + (19 - c.y) * size;
      mini.fillStyle = c.dark ? '#0e1216' : '#293a45'; mini.fillRect(x + 1, y + 1, size - 2, size - 2);
      if (c.dark) continue;
      for (let d = 0; d < 4; d++) {
        const e = game.edge(c.x, c.y, d);
        if (!e.raw) continue;
        mini.strokeStyle = e.raw === 1 || e.hidden ? '#9ca9ae' : '#dfbd7c';
        mini.lineWidth = e.raw >= 2 && !e.hidden ? 3 : 1;
        const lines = [[x, y, x + size, y], [x + size, y, x + size, y + size], [x, y + size, x + size, y + size], [x, y, x, y + size]];
        const line = lines[d]; mini.beginPath(); mini.moveTo(line[0], line[1]); mini.lineTo(line[2], line[3]); mini.stroke();
      }
      if (c.event?.kind === 'stairs') { mini.fillStyle = '#dfbd7c'; mini.fillRect(x + 5, y + 5, 4, 4); }
    }
    const cx = pad + (s.x + .5) * size, cy = pad + (19.5 - s.y) * size;
    const dx = game.dx[s.facing], dy = -game.dy[s.facing];
    mini.fillStyle = '#8bd2bd'; mini.beginPath();
    mini.moveTo(cx + dx * 6, cy + dy * 6);
    mini.lineTo(cx - dx * 4 + dy * 4, cy - dy * 4 - dx * 4);
    mini.lineTo(cx - dx * 4 - dy * 4, cy - dy * 4 + dx * 4);
    mini.closePath(); mini.fill();
    $('progress').textContent = `${count} / 400`;
  }

  function render() {
    const s = game.state;
    const b=game.battle.state,active=game.battle.active;
    $('encounter-status').textContent=game.encounterStatus();
    $('battle-panel').hidden=!b;
    $('battle-start').disabled=active||s.phase!=='exploring'||!game.party.canExplore();
    $('battle-attack').disabled=!active;$('battle-flee').disabled=!active;
    $('recover').disabled=active||!(s.phase==='outside'||(s.floor===1&&s.x===0&&s.y===0));
    for(const id of ['save','load','entrance'])$(id).disabled=active;
    if(b){
      $('battle-enemy').textContent=`${b.enemy.name} · 残り${b.enemies.filter(e=>e.hp>0).length}/${b.enemies.length}体 · ${b.round}ターン`;
      $('battle-target').innerHTML=b.enemies.map((e,i)=>`<option value="${i}" ${!e.hp?'disabled':''}>${i+1}. ${esc(e.name)} · HP ${e.hp}/${e.maxHp}${e.escaped?'（逃走）':!e.hp?'（倒した）':''}</option>`).join('');
      $('battle-target').value=String(b.target);$('battle-target').disabled=!active;
      $('battle-image').src=b.enemy.image;$('battle-image').hidden=!b.enemy.image;$('battle-log').textContent=b.log.join('\n');
    }
    if(active&&!wasInBattle)$('trial-battle').scrollIntoView?.({block:'center',behavior:'smooth'});
    wasInBattle=active;
    const members=game.party.model.members.map(id=>game.party.character(id));
    function spellOptions(id,characters,label){const old=$(id).value;$(id).innerHTML=characters.map(c=>`<option value="${c.id}">${esc(c.name)} · ${label(c)}</option>`).join('');$(id).value=characters.some(c=>String(c.id)===old)?old:String(characters[0]?.id??'');}
    const support=['DIOS','DIALKO','LATUMOFIS'].includes($('support-spell').value)?$('support-spell').value:'DIOS',supportKey=support.toLowerCase();
    const mages=members.filter(c=>c.hp>0&&c.status===0&&c.magic.halito>0),priests=members.filter(c=>c.hp>0&&c.status===0&&c.magic[supportKey]>0);
    spellOptions('halito-caster',mages,c=>`残り${c.magic.halito}回`);spellOptions('dios-caster',priests,c=>`残り${c.magic[supportKey]}回`);
    spellOptions('heal-target',members.filter(c=>c.hp>0&&c.status<5),c=>`HP ${c.hp}/${c.maxHp}`);
    $('cast-halito').disabled=!active||!mages.length;$('cast-dios').disabled=!priests.length||!members.some(c=>c.hp>0&&c.status<5&&(support==='DIOS'?c.hp<c.maxHp:support==='DIALKO'?c.status>0&&c.status<4:Boolean(c.poison)));
    $('cast-dios').textContent={DIOS:'ディオス',DIALKO:'ディアルコ',LATUMOFIS:'ラツモフィス'}[support];
    $('position').textContent = `B${s.floor}F · 東${s.x} / 北${s.y}`;
    $('steps').textContent = `${s.steps} 歩`;
    $('compass').textContent = `${compass[s.facing]} · ${names[s.facing]}`;
    $('log').innerHTML = s.log.map(line => `<div>${esc(line)}</div>`).join('');
    $('outside').hidden = s.phase !== 'outside';
    for (const id of ['forward', 'back', 'left', 'right', 'door', 'search']) $(id).disabled = active || s.phase !== 'exploring';
    $('stairs').disabled = active || s.phase !== 'exploring' || game.cell().event?.kind !== 'stairs' || !game.cell().event.destination;
    drawView(); drawMap(); partyUI.render();turnUI.render();
  }
  function act(action) {
    if (action === 'forward') game.move();
    else if (action === 'back') game.move(true);
    else if (action === 'left') game.turn(-1);
    else if (action === 'right') game.turn(1);
    else if (action === 'door') game.openDoor();
    else if (action === 'search') game.search();
    else if (action === 'stairs') game.stairs();
    else if (action === 'entrance' || action === 'enter') game.entrance();
    render();
  }
  for (const id of ['forward', 'back', 'left', 'right', 'door', 'search', 'stairs', 'entrance', 'enter']) $(id).addEventListener('click', () => act(id));
  for(const [id,fn] of [['battle-start',()=>game.encounter()],['battle-attack',()=>game.battle.planAll('attack')],['battle-flee',()=>game.battle.planAll('flee')],['turn-execute',()=>game.battle.execute()],['recover',()=>game.recover()]])$(id).addEventListener('click',()=>{try{fn();render();$('turn-message').textContent=id==='battle-attack'||id==='battle-flee'?'全員の指示を更新しました。「ターン実行」で進めます。':'';}catch(e){$('turn-message').textContent=e.message;}});
  $('battle-target').addEventListener('change',()=>{try{game.battle.choose(Number($('battle-target').value));render();}catch(e){$('battle-log').textContent=e.message;}});
  $('auto-encounters').checked=true;
  $('auto-encounters').addEventListener('change',()=>{game.setAutoEncounters($('auto-encounters').checked);render();});
  $('support-spell').addEventListener('change',()=>render());
  for(const [id,defaultName,caster,target] of [['cast-halito','HALITO','halito-caster','battle-target'],['cast-dios','DIOS','dios-caster','heal-target']])$(id).addEventListener('click',()=>{try{const name=id==='cast-dios'&&['DIOS','DIALKO','LATUMOFIS'].includes($('support-spell').value)?$('support-spell').value:defaultName;let message;if(game.battle.active){game.battle.plan(Number($(caster).value),{type:name.toLowerCase(),target:Number($(target).value)});message='呪文を指示しました。「ターン実行」で進めます。';}else message=game.castSpell(name,Number($(caster).value),Number($(target).value));render();$('spell-message').textContent=message;}catch(e){$('spell-message').textContent=e.message;}});
  $('save').addEventListener('click', () => {
    try { localStorage.setItem(storageKey, JSON.stringify(game.snapshot())); $('save-status').textContent = 'このブラウザーにパーティと探索記録を保存しました。'; }
    catch (_) { $('save-status').textContent = 'この環境では保存できません。現在の探索は続けられます。'; }
  });
  $('load').addEventListener('click', () => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (!saved) { $('save-status').textContent = '保存された探索記録がありません。'; return; }
      game.restore(saved); render(); $('save-status').textContent = game.state.log[0];
    } catch (_) { $('save-status').textContent = '探索記録を読み込めません。現在の位置は変更していません。'; }
  });
  document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing || e.target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName)) return;
    // Keep shortcuts stable with Japanese input and keyboard layouts. Consume game
    // keys on exploration buttons too, so Space/Enter cannot click a stale return button.
    const gameButtons = ['forward', 'back', 'left', 'right', 'door', 'search', 'stairs', 'entrance', 'enter'];
    if (e.target?.tagName === 'BUTTON' && !gameButtons.includes(e.target.id)) return;
    const codes = new Map([['ArrowUp', 'forward'], ['KeyW', 'forward'], ['ArrowDown', 'back'], ['KeyS', 'back'], ['ArrowLeft', 'left'], ['KeyA', 'left'], ['ArrowRight', 'right'], ['KeyD', 'right'], ['Space', 'door'], ['KeyF', 'search'], ['Enter', 'stairs'], ['NumpadEnter', 'stairs']]);
    const keys = new Map([['ArrowUp', 'forward'], ['w', 'forward'], ['ArrowDown', 'back'], ['s', 'back'], ['ArrowLeft', 'left'], ['a', 'left'], ['ArrowRight', 'right'], ['d', 'right'], [' ', 'door'], ['f', 'search'], ['Enter', 'stairs']]);
    const action = e.code ? codes.get(e.code) : keys.get(e.key?.length === 1 ? e.key.toLowerCase() : e.key);
    if (action) { e.preventDefault(); act(action); }
  });
  render();
})();
