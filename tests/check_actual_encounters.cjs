const fs=require('node:fs'),assert=require('node:assert/strict'),{create}=require('../web/explorer/engine.js');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const game=create(data,{rng:()=>0}),queue=[{x:0,y:0,path:[]}],seen=new Set(['0,0']);let route;
while(queue.length){const p=queue.shift();if(p.x===0&&p.y===10){route=p.path;break;}const c=data.floors[0].cells[p.y*20+p.x];for(let d=0;d<4;d++){
 const edge=c.edges[game.directions[d]];if(edge===1||(edge===3&&c.dark))continue;
 const x=(p.x+game.dx[d]+20)%20,y=(p.y+game.dy[d]+20)%20,k=`${x},${y}`;
 if(seen.has(k)||data.floors[0].cells[y*20+x].event?.kind==='teleport')continue;
 seen.add(k);queue.push({x,y,path:[...p.path,d]});
}}
assert(route);let battles=0;
for(const d of route){while(game.state.facing!==d)game.turn(1);const edge=game.edge(game.state.x,game.state.y,d);if(edge.raw===3)game.search();if(edge.raw>=2)game.openDoor();else game.move();
 if(game.battle.active){battles++;assert(game.encounterStatus().includes('戦闘中'));game.battle.flee();}
}
assert(battles>=2);assert.equal(game.state.steps,route.length);assert.deepEqual([game.state.x,game.state.y],[0,10]);game.stairs();assert.equal(game.state.floor,2);assert(!game.encounterStatus().includes('未対応'));assert(game.encounterStatus().includes('イベント'));
game.setAutoEncounters(false);assert(game.encounterStatus().includes('OFF'));game.setAutoEncounters(true);game.entrance();assert(game.encounterStatus().includes('イベント'));
console.log(`Actual ROM B1 route: ${route.length} successful moves including doors, ${battles} encounters, B2/off/event status passed`);
