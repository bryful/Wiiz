/* Exploration prototype. ROM map data in, independent movement/state out. */
(function (root) {
  'use strict';
  const Party = typeof module !== 'undefined' && module.exports ? require('./party.js') : root.WizParty;
  const Battle = typeof module !== 'undefined' && module.exports ? require('./battle.js') : root.WizBattle;
  const Encounters = typeof module !== 'undefined' && module.exports ? require('./encounters.js') : root.WizEncounters;
  const DIRS = ['north', 'east', 'south', 'west'];
  const DX = [0, 1, 0, -1], DY = [1, 0, -1, 0];
  const wrap = n => (n % 20 + 20) % 20;
  const posKey = s => `${s.floor}:${s.x}:${s.y}`;
  const edgeKey = (s, d) => `${posKey(s)}:${d}`;
  function create(data,options={}) {
    if (data.game !== 'wiz1' || data.floors.length !== 10) throw Error('Wiz1 maps required');
    let s;
    let party = Party.create(data.items || []);
    const rng=options.rng||Math.random;
    const battle = Battle.create(()=>party,data.monsters||[],rng,data.spells||[],data.enemyRules||{});
    let autoEncounters=options.autoEncounters!==false,encounterSteps=0,encounterChecks=0;
    function cell(x = s.x, y = s.y, floor = s.floor) {
      return data.floors[floor - 1].cells[wrap(y) * 20 + wrap(x)];
    }
    function initial() {
      return { floor: 1, x: 0, y: 0, facing: 0, phase: 'exploring', steps: 0,
        visited: new Set(['1:0:0']), secrets: new Set(), opened: new Set(),
        log: ['迷宮に入った。北を向いている。'] };
    }
    function say(message) { s.log = [message, ...s.log].slice(0, 5); return message; }
    function edge(x, y, d) {
      const value = cell(x, y).edges[DIRS[d]];
      const key = `${s.floor}:${wrap(x)}:${wrap(y)}:${d}`;
      return { raw: value, hidden: value === 3 && !s.secrets.has(key),
        open: s.opened.has(key), key };
    }
    function eventText() {
      const c = cell(), event = c.event;
      if (c.dark) return '暗闇に包まれている。';
      if (!event) return '静かな通路が続いている。';
      if (event.kind === 'stairs' && event.destination) return event.destination.floor === 0 ? '地上へ戻る階段がある。' : '別の階層へ続く階段がある。';
      if (event.kind === 'teleport') return '転移地点に立っている。';
      return `未解析イベント（種類 ${event.type_raw ?? '不明'}）。効果は未実装。`;
    }
    function arrive() {
      s.visited.add(posKey(s));
      const seen = new Set();
      let moved = false;
      for (let i = 0; i < 16; i++) {
        const event = cell().event;
        if (!event || event.kind !== 'teleport' || !event.destination) break;
        if (seen.has(posKey(s))) { say('転移が循環しているため、この位置で停止した。'); return; }
        seen.add(posKey(s));
        const t = event.destination;
        if (t.floor === 0) { s.phase = 'outside'; say('地上へ帰還した。'); return; }
        s.floor = t.floor; s.x = t.x; s.y = t.y;
        s.visited.add(posKey(s)); moved = true;
        if (i === 15) { say('連続転移の上限に達したため停止した。'); return; }
      }
      say((moved ? '足元が揺らぎ、別の場所へ転移した。 ' : '') + eventText());
    }
    function move(backward = false) {
      if (battle.active) return say('戦闘中は移動できない。攻撃か逃走を選んでください。');
      if (s.phase !== 'exploring') return say('地上にいる。迷宮に入って探索を再開できる。');
      if (!party.canExplore()) return say('行動できるメンバーがいない。入口でパーティを編成してください。');
      const d = (s.facing + (backward ? 2 : 0)) % 4, e = edge(s.x, s.y, d);
      if (e.raw === 1 || e.hidden) return say('壁に阻まれた。');
      if ((e.raw === 2 || e.raw === 3) && !e.open) return say('扉が閉じている。扉の方を向いて「扉を開く」。');
      s.x = wrap(s.x + DX[d]); s.y = wrap(s.y + DY[d]); s.steps++;
      s.opened.clear(); arrive();
      for(const id of party.model.members){const c=party.character(id);if(c.poison&&c.hp>0&&c.status<5){c.hp=Math.max(0,c.hp-1);say(`${c.name}は毒で1ダメージを受けた。`);if(!c.hp){c.status=5;say(`${c.name}は毒で倒れた。`);}}}
      encounterSteps++;
      // Timing is a prototype rule; opponent selection uses the destination floor.
      const definition=data.encounters?.floors.find(f=>f.floor===s.floor);
      if(autoEncounters&&definition&&s.phase==='exploring'&&party.canExplore()&&!cell().event&&encounterSteps>=6){
        encounterChecks++;
        if(rng()<1/8){
        battle.start({monsterId:Encounters.pick(definition,rng),group:true,floor:s.floor});
        encounterSteps=0;encounterChecks=0;say('敵が現れた！ 戦闘欄で行動を選んでください。');
        }
      }
      return s.log[0];
    }
    function turn(delta) {
      if (battle.active) return;
      if (s.phase !== 'exploring') return;
      s.facing = (s.facing + delta + 4) % 4;
    }
    function openDoor() {
      if (battle.active) return;
      if (s.phase !== 'exploring') return;
      if (!party.canExplore()) return say('行動できるメンバーがいない。入口でパーティを編成してください。');
      const e = edge(s.x, s.y, s.facing);
      if (e.hidden || e.raw === 1) return say('正面には壁がある。');
      if (e.raw === 0) return say('正面に扉はない。');
      s.opened.add(e.key);
      move();
      return say('扉を開いて進んだ。 ' + s.log[0]);
    }
    function search() {
      if (battle.active) return;
      if (s.phase !== 'exploring') return;
      if (cell().dark) return say('暗闇で壁の様子が分からない。');
      const e = edge(s.x, s.y, s.facing);
      if (e.raw === 3 && e.hidden) {
        s.secrets.add(e.key); return say('壁を調べ、隠し扉を見つけた。');
      }
      return say('正面を調べたが、新しい発見はなかった。');
    }
    function stairs() {
      if (battle.active) return;
      if (s.phase !== 'exploring') return;
      const event = cell().event;
      if (!event || event.kind !== 'stairs' || !event.destination) return say('ここに使える階段はない。');
      const t = event.destination;
      s.opened.clear();
      if (t.floor === 0) { s.phase = 'outside'; return say('階段を上り、地上へ帰還した。'); }
      s.floor = t.floor; s.x = t.x; s.y = t.y; arrive();
      return say('階段を移動した。 ' + s.log[0]);
    }
    function entrance() {
      if (battle.active) return;
      encounterSteps=0;encounterChecks=0;
      s.floor = 1; s.x = 0; s.y = 0; s.facing = 0; s.phase = 'exploring';
      s.opened.clear(); s.visited.add(posKey(s)); say('迷宮の入口から探索を再開した。');
    }
    function snapshot() {
      if (battle.active) throw Error('戦闘を終えてから保存してください');
      return { version: 2, game: data.game, sha256: data.sha256, floor: s.floor, x: s.x, y: s.y,
        facing: s.facing, phase: s.phase, steps: s.steps,
        visited: [...s.visited], secrets: [...s.secrets], party: party.snapshot() };
    }
    function restore(value) {
      if (battle.active) throw Error('戦闘を終えてから読み込んでください');
      const v = typeof value === 'string' ? JSON.parse(value) : value;
      const integer = (n, low, high) => Number.isInteger(n) && n >= low && n <= high;
      if (!v || ![1, 2].includes(v.version) || v.game !== data.game || v.sha256 !== data.sha256 ||
          !integer(v.floor, 1, 10) || !integer(v.x, 0, 19) || !integer(v.y, 0, 19) ||
          !integer(v.facing, 0, 3) || !integer(v.steps, 0, Number.MAX_SAFE_INTEGER) ||
          !['exploring', 'outside'].includes(v.phase)) throw Error('探索記録の形式が違います');
      function keys(list, isEdge) {
        if (!Array.isArray(list) || list.length > (isEdge ? 16000 : 4000)) throw Error('探索記録が大きすぎます');
        return new Set(list.map(key => {
          if (typeof key !== 'string' || !/^\d+:\d+:\d+(?::\d+)?$/.test(key)) throw Error('不正な座標です');
          const p = key.split(':').map(Number);
          if (p.length !== (isEdge ? 4 : 3) || !integer(p[0], 1, 10) || !integer(p[1], 0, 19) || !integer(p[2], 0, 19) ||
              (isEdge && (!integer(p[3], 0, 3) || data.floors[p[0] - 1].cells[p[2] * 20 + p[1]].edges[DIRS[p[3]]] !== 3))) throw Error('不正な座標です');
          return p.join(':');
        }));
      }
      const visited = keys(v.visited, false), secrets = keys(v.secrets, true);
      const loadedParty = v.version === 1 ? party : Party.create(data.items || [], v.party);
      if (v.version === 2 && !v.party) throw Error('パーティ記録がありません');
      party = loadedParty;
      encounterSteps=0;encounterChecks=0;
      s = { floor: v.floor, x: v.x, y: v.y, facing: v.facing, phase: v.phase, steps: v.steps,
        visited, secrets, opened: new Set(), log: [] };
      s.visited.add(posKey(s)); say(v.version === 1 ? '旧探索記録を読み込んだ。現在のパーティは保持した。' : 'パーティと探索記録を読み込んだ。');
    }
    s = initial();
    function encounter(){if(s.phase!=='exploring')throw Error('迷宮内で戦闘を開始してください');battle.start({monsterId:0});encounterSteps=0;encounterChecks=0;}
    function recover(){if(battle.active||!(s.phase==='outside'||(s.floor===1&&s.x===0&&s.y===0)))throw Error('戦闘を終え、入口か地上で回復してください');for(const id of party.model.members){const c=party.character(id);c.hp=c.maxHp;c.status=0;c.poison=0;c.magic=Party.startingMagic(c.classId);}return say('試作用の全回復を行った。');}
    function castSpell(name,caster,target){return say(battle.castSpell(name,caster,target));}
    function setAutoEncounters(value){autoEncounters=Boolean(value);encounterSteps=0;encounterChecks=0;}
    function encounterStatus(){
      if(battle.active)return '遭遇：戦闘中';
      if(!autoEncounters)return '遭遇：OFF（歩行中に遭遇する、を有効にしてください）';
      if(!data.encounters)return '遭遇：データがありません。最新版を開き直してください';
      if(!data.encounters.floors.some(f=>f.floor===s.floor))return `遭遇：B${s.floor}Fの出現テーブルがありません`;
      if(s.phase!=='exploring')return '遭遇：地上では発生しません';
      if(!party.canExplore())return '遭遇：行動できるパーティがいません';
      if(cell().event)return '遭遇：ON · 階段・イベントのマスでは抽選しません';
      if(encounterSteps<5)return `遭遇：ON · B${s.floor}F · 抽選まであと${6-encounterSteps}歩（移動できた歩数）`;
      return `遭遇：ON · B${s.floor}F · 移動ごとに抽選中（判定${encounterChecks}回）`;
    }
    return { get state() { return s; }, get party() { return party; }, battle, encounter, recover, castSpell, setAutoEncounters, encounterStatus, cell, edge, move, turn, openDoor, search, stairs, entrance,
      snapshot, restore, eventText, data, directions: DIRS, dx: DX, dy: DY };
  }
  const api = { create, wrap };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.WizExplorer = api;
})(globalThis);
