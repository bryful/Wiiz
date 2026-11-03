const fs=require('node:fs'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const Enemy=require('../web/explorer/enemy-rules.js'),Battle=require('../web/explorer/battle.js'),Party=require('../web/explorer/party.js'),Explorer=require('../web/explorer/engine.js');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const code=`import sys,json
sys.path.insert(0,'tools')
from verify_enemy_actions import expected
from affliction_rules import saving_threshold
from pathlib import Path
r=Path('.nes/wiz1.nes').read_bytes()
t=dict(mage=list(r[0x1dd20:0x1dd30]),priest=list(r[0x1dd30:0x1dd40]))
print(json.dumps(dict(selection=[expected(m,p,k,c,b,s,t) for k in [0,1,2,8] for m in range(8) for p in range(8) for b in [0,1,64,84,85,178,179,255] for s in [0,1,2] for c in [1,5,9]],sleep=[saving_threshold('wiz1',50,c,t) for c in range(1,26) for t in range(1,26)])))`;
const py=spawnSync('python',['-c',code],{encoding:'utf8',maxBuffer:4*1024*1024});assert.equal(py.status,0,py.stderr);const expected=JSON.parse(py.stdout);let i=0;
for(const k of [0,1,2,8])for(let m=0;m<8;m++)for(let p=0;p<8;p++)for(const b of [0,1,64,84,85,178,179,255])for(const s of [0,1,2])for(const c of [1,5,9]){
 const magic={mage:m,priest:p},action=Enemy.spell(magic,k,c,()=>b,n=>s%n,data.enemyRules.spell_tables),ref=expected.selection[i++];assert.equal(action?(action.spellId+1)*2:0,ref[0]);assert.deepEqual(magic,ref[1]);
}
i=0;for(let c=1;c<=25;c++)for(let t=1;t<=25;t++)assert.equal(Enemy.sleepThreshold(c,t),expected.sleep[i++]);
assert(data.monsters.slice(0,6).every(m=>!m.stats.mage_spell_level&&!m.stats.priest_spell_level&&!m.stats.breath_element_raw&&!(m.stats.status_flags_raw&7)));
assert(data.monsters[7].stats.status_flags_raw&4);assert(data.monsters[8].stats.status_flags_raw&2);
function setup(id,extra={}){
 const p=Party.create(data.items);let draws=[],fallback=.9;
 const source={...data.monsters[id],stats:{...data.monsters[id].stats,hp:{count:1,sides:1,bonus:99},attacks:[],...extra}};
 const b=Battle.create(()=>p,[source],()=>draws.length?draws.shift():fallback,data.spells,data.enemyRules);b.start({monsterId:id});
 return {p,b,draw(values,rest=.9){draws=values;fallback=rest;}};
}
for(const id of [10,11]){const {p,b}=setup(id);p.model.members=[1];p.character(1).attributes[4]=0;b.planAll('guard');b.execute();assert.equal(p.character(1).hp,4);assert(b.state.log.some(s=>s.includes(id===10?'ハリト':'バディオス')));}
let s=setup(10);s.p.model.members=[1];s.p.character(1).attributes[4]=0;s.b.planAll('guard');s.draw([.99,0,0,0,.1,.1,.9,.99,.9]);s.b.execute();assert.equal(s.p.character(1).status,1);assert(s.b.active);
s.b.state.magic.mage=0;s.draw([0,0,0],0);s.b.execute();assert.equal(s.p.character(1).status,0); // All asleep can still wait a turn and wake.
s=setup(12);for(const c of s.p.model.roster)c.hp=c.maxHp=100;s.b.planAll('guard');s.draw([], .5);s.b.execute();assert(s.p.model.roster.every(c=>c.hp===50));assert(s.b.state.log.some(m=>m.includes('ブレス')));
s=setup(12);for(const c of s.p.model.roster){c.hp=c.maxHp=100;c.attributes[4]=18;}s.b.planAll('guard');s.b.plan(1,{type:'attack',target:0});s.draw([.99,.99,.99,.99,0,.99,0]);s.b.execute();assert.equal(s.b.state.enemy.hp,92);assert(s.p.model.roster.every(c=>c.hp===54)); // Damage uses HP at the time of breathing.
s=setup(1);s.b.planAll('guard');s.draw([],.5);s.b.execute();assert.equal(s.b.state.result,'dispersed');assert(s.p.model.roster.every(c=>c.experience===0));
s=setup(8,{mage_spell_level:0,priest_spell_level:0,status_flags_raw:2,level:100,attacks:[{count:1,sides:1,bonus:0}]});s.p.model.members=[1];s.p.character(1).attributes[4]=0;s.b.planAll('guard');s.draw([.99,0,0,.5,0,0]);s.b.execute();assert.equal(s.p.character(1).poison,1);assert.equal(s.p.character(1).hp,10);
const flagsTarget={status:0,poison:0};assert.deepEqual(Enemy.contact(7,flagsTarget,()=>0),['毒','麻痺','石化']);assert.deepEqual(flagsTarget,{status:4,poison:1});
s=setup(8,{mage_spell_level:0,priest_spell_level:0,status_flags_raw:7,level:100,attacks:[{count:1,sides:1,bonus:0}]});s.p.model.members=[1];s.b.planAll('guard');s.draw([],0);s.b.execute();assert.equal(s.p.character(1).status,0);assert.equal(s.p.character(1).poison,0);assert.equal(s.p.character(1).hp,12);
s=setup(7,{level:100,attacks:[{count:1,sides:1,bonus:0}]});s.p.model.members=[1,2];for(const c of s.p.model.roster)c.attributes[4]=0;s.b.planAll('guard');s.draw([.99,.99,0,0,.5,0,0]);s.b.execute();assert.equal(s.p.character(1).status,3);assert(s.b.active);
s.p.character(2).attributes[4]=18;s.b.plan(2,{type:'dialko',target:1});s.draw([],.9);s.b.execute();assert.equal(s.p.character(1).status,0);assert.equal(s.p.character(2).magic.dialko,1);
const d=structuredClone(data);for(const f of d.floors)for(const c of f.cells){c.edges={north:0,east:0,south:0,west:0};delete c.event;}
const game=Explorer.create(d,{autoEncounters:false}),c=game.party.character(1);c.poison=1;c.hp=2;game.move();assert.equal(c.hp,1);game.castSpell('LATUMOFIS',2,1);assert.equal(c.poison,0);game.move();assert.equal(c.hp,1);assert.equal(game.party.character(2).magic.latumofis,1);
c.status=3;game.castSpell('DIALKO',2,1);assert.equal(c.status,0);c.status=4;assert.throws(()=>game.castSpell('DIALKO',2,1));assert.equal(c.status,4);
c.status=0;c.hp=1;c.poison=1;game.move();assert.equal(c.hp,0);assert.equal(c.status,5);const save=game.snapshot();game.restore(save);assert.deepEqual(game.snapshot(),save);
const old=structuredClone(save);for(const member of old.party.roster){delete member.magic.dialko;delete member.magic.latumofis;}game.restore(old);assert.equal(game.party.character(2).magic.dialko,2);
game.entrance();game.recover();assert(game.party.model.roster.every(c=>!c.poison&&!c.status&&c.hp===c.maxHp));
console.log('Enemy actions: 18,432 spell-selection vectors + 625 sleep thresholds, B1 metadata, enemy spells/sleep/wake/breath/flee, poison/paralysis, cures, walking/death/save/migration/recovery passed');
