const fs=require('node:fs'),assert=require('node:assert/strict');
const {create}=require('../web/explorer/battle.js'),Party=require('../web/explorer/party.js'),Explorer=require('../web/explorer/engine.js');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
assert.equal(data.monsters[0].id,0);assert(data.monsters[0].image.startsWith('data:image/png;base64,'));
const party=Party.create(data.items),enemy={...data.monsters[0],stats:{...data.monsters[0].stats,hp:{count:1,sides:1,bonus:0}}};
const win=create(()=>party,[enemy],()=>.99);win.start();win.attack();assert.equal(win.state.result,'victory');assert.equal(win.state.enemy.hp,0);assert.equal(party.character(1).experience,13);assert.equal(win.active,false);
win.attack();assert.equal(party.character(1).experience,13); // No duplicate reward.
const escape=create(()=>party,[enemy],()=>0);escape.start();escape.flee();assert.equal(escape.state.result,'escaped');assert.equal(party.character(1).experience,13);
const lethal={...enemy,stats:{...enemy.stats,hp:{count:1,sides:1,bonus:100},ac:-100,level:100,attacks:[{count:1,sides:1,bonus:100}]}};
const lose=create(()=>party,[lethal],()=>.99);lose.start();lose.flee();assert(lose.state.log.some(s=>s.includes('逃げられなかった')));assert.equal(party.character(4).hp,0);
for(let i=0;i<4&&lose.active;i++)lose.attack();assert.equal(lose.state.result,'defeat');assert.equal(party.canExplore(),false);assert.throws(()=>lose.start());
const game=Explorer.create(data,{rng:()=>.99});game.encounter();assert(game.battle.active);const pos=[game.state.x,game.state.y,game.state.facing,game.state.steps];
game.move();game.turn(1);game.openDoor();game.stairs();game.entrance();assert.deepEqual([game.state.x,game.state.y,game.state.facing,game.state.steps],pos);
assert.throws(()=>game.snapshot());assert.throws(()=>game.restore({}));assert.throws(()=>game.recover());
for(let i=0;i<100&&game.battle.active;i++)game.battle.attack();assert(!game.battle.active);
game.entrance();game.recover();assert(game.party.model.members.every(id=>{const c=game.party.character(id);return c.hp===c.maxHp&&c.status===0;}));
const saved=game.snapshot(),restored=Explorer.create(data);restored.restore(saved);assert.deepEqual(restored.snapshot(),saved);game.move();assert.throws(()=>game.recover());
console.log('Battle: ROM opponent/image, victory/reward once, escape/failure, damage/death/defeat, movement/save locks, base recovery and save roundtrip passed');
