const fs=require('node:fs'),assert=require('node:assert/strict');
const Explorer=require('../web/explorer/engine.js'),Battle=require('../web/explorer/battle.js'),Party=require('../web/explorer/party.js'),{pick}=require('../web/explorer/encounters.js');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
assert.equal(data.encounters.table_rom_offset,0x1e27d);assert.equal(data.monsters.length,101);
const first=data.encounters.floors[0];
function sequence(values){let i=0;return ()=>values[i++%values.length];}
assert.equal(pick(first,sequence([0,0])),0);assert.equal(pick(first,sequence([.8,.99])),5);assert.equal(pick(first,sequence([.99,0])),3);
const fixture=structuredClone(data);for(const f of fixture.floors)for(const c of f.cells){c.edges={north:0,east:0,south:0,west:0};c.dark=false;delete c.event;}
let randomValue=0;const game=Explorer.create(fixture,{rng:()=>randomValue});
for(let i=0;i<5;i++){game.move();assert(!game.battle.active);}
game.move();assert(game.battle.active);assert.equal(game.state.y,6);assert.equal(game.battle.state.enemies.length,2);assert(game.battle.state.enemies.every(e=>e.id===0));
const pos=game.state.y;game.move();assert.equal(game.state.y,pos);game.battle.choose(1);assert.equal(game.battle.state.target,1);assert.throws(()=>game.battle.choose(9));
randomValue=.9;game.battle.attack();assert.equal(game.battle.state.result,'victory');assert.equal(game.party.character(1).experience,27);randomValue=0; // 2*55/4.
for(let i=0;i<5;i++){game.move();assert(!game.battle.active);}game.move();assert(game.battle.active);game.battle.flee();assert.equal(game.battle.state.result,'escaped');
game.setAutoEncounters(false);for(let i=0;i<20;i++)game.move();assert(!game.battle.active);
game.setAutoEncounters(true);game.state.floor=2;for(let i=0;i<6;i++)game.move();assert(game.battle.active);assert.equal(game.battle.state.enemy.id,7);game.battle.flee();
game.state.floor=1;game.entrance();fixture.floors[0].cells[0].edges.north=1;for(let i=0;i<20;i++){game.move();game.turn(1);game.turn(-1);}assert(!game.battle.active);assert.equal(game.state.steps,38);
const p=Party.create(data.items),b=Battle.create(()=>p,data.monsters,()=>.99,data.spells);
b.start({monsterId:0,group:true,floor:1});assert.equal(b.state.enemies.length,4);assert.throws(()=>b.choose(-1));b.choose(3);b.castSpell('HALITO',4);assert.equal(b.state.enemies[3].hp,0);assert.equal(p.character(4).magic.halito,1);assert(b.active);assert.equal(b.state.round,1);assert.notEqual(b.state.target,3);
const beforeRound=b.state.round;assert.throws(()=>b.castSpell('HALITO',1));assert.equal(b.state.round,beforeRound);
// Death retargeting, each surviving enemy counterattacks; group count is floor-capped.
const capped=Battle.create(()=>Party.create(data.items),[{...data.monsters[0],stats:{...data.monsters[0].stats,encounter:{count:20,sides:1,bonus:0}}}],()=>0);capped.start({group:true,floor:1});assert.equal(capped.state.enemies.length,5);
const camp=Explorer.create(data,{autoEncounters:false,rng:()=>.99}),fighter=camp.party.character(1),priest=camp.party.character(2);
fighter.hp=2;camp.castSpell('DIOS',2,1);assert.equal(fighter.hp,10);assert.equal(priest.magic.dios,1);camp.castSpell('DIOS',2,1);assert.equal(fighter.hp,12);assert.equal(priest.magic.dios,0);fighter.hp=1;assert.throws(()=>camp.castSpell('DIOS',2,1));assert.equal(fighter.hp,1);
camp.recover();assert.equal(priest.magic.dios,2);assert.throws(()=>camp.castSpell('DIOS',2,1));assert.equal(priest.magic.dios,2);
fighter.hp=0;fighter.status=5;assert.throws(()=>camp.castSpell('DIOS',2,1));assert.equal(priest.magic.dios,2);camp.recover();
camp.encounter();camp.castSpell('HALITO',4);assert.equal(camp.battle.state.result,'victory');assert.equal(camp.party.character(4).magic.halito,1);
const save=camp.snapshot();camp.restore(save);assert.equal(camp.party.character(4).magic.halito,1);
const old=structuredClone(save);for(const c of old.party.roster)delete c.magic;camp.restore(old);assert.equal(camp.party.character(4).magic.halito,2);
const bad=structuredClone(save);bad.party.roster[0].magic.halito=2;const before=camp.snapshot();assert.throws(()=>camp.restore(bad));assert.deepEqual(camp.snapshot(),before);
console.log('Encounters/spells: floor ranges, move-only trigger/cooldown/toggle, group targeting/rewards/cap, B2 encounters, HALITO/DIOS costs/targets/death/caps, recovery and save migration passed');
