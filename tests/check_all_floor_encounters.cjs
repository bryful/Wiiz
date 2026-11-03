const fs=require('node:fs'),assert=require('node:assert/strict'),Explorer=require('../web/explorer/engine.js'),Battle=require('../web/explorer/battle.js'),Party=require('../web/explorer/party.js'),{pick}=require('../web/explorer/encounters.js');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
assert.equal(data.monsters.length,101);assert(data.monsters.every(m=>m.image.startsWith('data:image/png;base64,')));
const game=Explorer.create(data,{rng:()=>0}),base=game.snapshot();
function walkPath(floor,x,y,remaining){
 if(!remaining)return [];
 const cell=floor.cells[y*20+x];
 for(let d=0;d<4;d++){
  const e=cell.edges[game.directions[d]];if(e===1||(e===3&&cell.dark))continue;
  const nx=(x+game.dx[d]+20)%20,ny=(y+game.dy[d]+20)%20;if(floor.cells[ny*20+nx].event)continue;
  const rest=walkPath(floor,nx,ny,remaining-1);if(rest)return [d,...rest];
 }
 return null;
}
for(const floor of data.floors){
 const definition=data.encounters.floors.find(f=>f.floor===floor.id),domain=new Set();
 for(const r of definition.ranges)for(let k=0;k<=(r.threshold?r.repeats:0);k++)for(let n=0;n<r.width;n++)domain.add(r.base+k*r.step+n);
 for(const id of domain){assert(data.monsters.some(m=>m.id===id),`B${floor.id}: missing ${id}`);}
 let seed=123+floor.id;const rng=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2**32;};
 for(let i=0;i<1000;i++)assert(domain.has(pick(definition,rng)));
 let start,route;for(const c of floor.cells){if(c.event)continue;route=walkPath(floor,c.x,c.y,6);if(route){start=c;break;}}
 assert(start,`B${floor.id}: six-step ROM route required`);
 game.restore({...base,floor:floor.id,x:start.x,y:start.y});
 for(const [i,d]of route.entries()){
  while(game.state.facing!==d)game.turn(1);
  const e=game.edge(game.state.x,game.state.y,d);if(e.raw===3)game.search();if(e.raw>=2)game.openDoor();else game.move();
  assert.equal(game.state.steps,i+1);assert.equal(game.battle.active,i===5);
 }
 const enemy=game.battle.state;assert(domain.has(enemy.enemy.id));assert(enemy.enemies.length>=1&&enemy.enemies.length<=definition.group_cap);assert.equal(game.state.floor,floor.id);
 const position=[game.state.floor,game.state.x,game.state.y];game.battle.flee();assert.equal(game.battle.state.result,'escaped');assert.deepEqual([game.state.floor,game.state.x,game.state.y],position);
 const save=game.snapshot();game.restore(save);assert.deepEqual(game.snapshot(),save);
}
// JP zero-sided encounter dice return bonus=1, not an invented d1 roll + bonus.
const special=Battle.create(()=>Party.create(data.items),data.monsters,()=>.99);
special.start({monsterId:94,group:true,floor:10});assert.equal(special.state.enemies.length,1);
console.log('All floors: complete 101-monster bundle/images, 10,000 range samples, six actual ROM moves/doors per floor, enemy domains/count caps, escape/save roundtrip and ID94 zero-side count passed');
