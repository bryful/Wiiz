const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {create} = require('../web/explorer/engine.js');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../output/dungeons/maps.json'), 'utf8'));
const game = create(data);
assert.deepEqual([game.state.x, game.state.y, game.state.facing], [0, 0, 0]);
game.move(true); assert.equal(game.state.steps, 0); // South wall at entry.
game.move(); assert.deepEqual([game.state.x, game.state.y], [0, 1]);
game.turn(-1); assert.equal(game.state.facing, 3); game.turn(1);

// Walk actual ROM data from entry to B1's down stairs; no state teleporting.
game.entrance();
const floor = data.floors[0], queue = [{x:0,y:0,path:[]}], seen = new Set(['0,0']);
let route;
while(queue.length){
 const here=queue.shift();if(here.x===0&&here.y===10){route=here.path;break;}
 const c=floor.cells[here.y*20+here.x];
 for(let d=0;d<4;d++){
  const e=c.edges[game.directions[d]];if(e===1||(e===3&&c.dark))continue;
  const x=(here.x+game.dx[d]+20)%20,y=(here.y+game.dy[d]+20)%20,key=`${x},${y}`;
  if(seen.has(key)||floor.cells[y*20+x].event?.kind==='teleport')continue;
  seen.add(key);queue.push({x,y,path:[...here.path,d]});
 }
}
assert(route,'Actual map must have a walkable route to the down stairs');
for(const d of route){
 while(game.state.facing!==d)game.turn(1);
 const e=game.edge(game.state.x,game.state.y,d);
 if(e.raw===3)game.search();if(e.raw>=2)game.openDoor();else game.move();
}
assert.deepEqual([game.state.floor,game.state.x,game.state.y],[1,0,10]);
game.stairs();assert.deepEqual([game.state.floor,game.state.x,game.state.y],[2,12,7]);
game.stairs();assert.deepEqual([game.state.floor,game.state.x,game.state.y],[1,0,10]);
const saved=game.snapshot();game.entrance();game.restore(JSON.stringify(saved));
assert.deepEqual(game.snapshot(),saved);
for(const bad of [{...saved,x:20},{...saved,facing:-1},{...saved,sha256:'wrong'},{...saved,visited:['1:999:0']},{...saved,secrets:['1:0:0:0']},{...saved,steps:Infinity}]){
 const before=game.snapshot();assert.throws(()=>game.restore(bad));assert.deepEqual(game.snapshot(),before);
}
game.entrance();game.stairs();assert.equal(game.state.phase,'outside');game.move();assert.equal(game.state.phase,'outside');game.entrance();assert.equal(game.state.phase,'exploring');

// Synthetic edge/event fixtures cover mechanics absent from the entry route.
function fixture(){const d=JSON.parse(JSON.stringify(data));for(const f of d.floors)for(const c of f.cells){c.edges={north:0,east:0,south:0,west:0};c.dark=false;delete c.event;}return d;}
const f=fixture();f.floors[0].cells[0].edges.north=2;
const doors=create(f);doors.move();assert.equal(doors.state.y,0);doors.openDoor();assert.equal(doors.state.y,1);assert.equal(doors.state.steps,1);assert(doors.state.visited.has('1:0:1'));assert.equal(doors.state.opened.size,0);
// Opposite side need not agree: returning follows current cell's edge.
doors.move(true);assert.equal(doors.state.y,0);
f.floors[0].cells[0].edges.north=3;
const secret=create(f);secret.move();assert.equal(secret.state.y,0);secret.openDoor();assert.equal(secret.state.opened.size,0);secret.search();secret.openDoor();assert.equal(secret.state.y,1);assert.equal(secret.state.steps,1);
const wrapped=create(fixture());wrapped.move(true);assert.equal(wrapped.state.y,19);wrapped.turn(-1);wrapped.move();assert.equal(wrapped.state.x,19);
const t=fixture();t.floors[0].cells[20].event={kind:'teleport',destination:{floor:2,x:3,y:4}};
const teleport=create(t);teleport.move();assert.deepEqual([teleport.state.floor,teleport.state.x,teleport.state.y],[2,3,4]);
t.floors[0].cells[0].edges.north=2;
const doorTeleport=create(t);doorTeleport.openDoor();assert.deepEqual([doorTeleport.state.floor,doorTeleport.state.x,doorTeleport.state.y],[2,3,4]);assert.equal(doorTeleport.state.steps,1);assert(doorTeleport.state.visited.has('2:3:4'));
t.floors[0].cells[0].edges.north=0;
t.floors[1].cells[83].event={kind:'teleport',destination:{floor:1,x:0,y:1}};
const cycle=create(t);cycle.move();assert(cycle.state.log[0].includes('循環'));assert(cycle.state.visited.size<=3);
const dark=fixture();dark.floors[0].cells[0].dark=true;dark.floors[0].cells[0].edges.north=3;
const darkness=create(dark);darkness.search();assert.equal(darkness.state.secrets.size,0);
console.log(`Explorer engine: actual ${route.length}-step ROM route, two-way stairs, source edges, doors/secrets, wrapping, teleport cycle and atomic save validation passed`);
