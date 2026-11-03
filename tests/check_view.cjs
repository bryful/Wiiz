const assert=require('node:assert/strict'),{cast}=require('../web/explorer/view.js');
const {create}=require('../web/explorer/engine.js');
const data={game:'wiz1',sha256:'camera-fixture',floors:Array.from({length:10},(_,f)=>({id:f+1,cells:Array.from({length:400},(_,i)=>({x:i%20,y:Math.floor(i/20),dark:false,edges:{north:1,east:1,south:1,west:1}}))}))};
const game=create(data),dirs=game.directions;
const near=(a,b)=>assert(Math.abs(a-b)<1e-9,`${a} != ${b}`);
for(let facing=0;facing<4;facing++){
 game.state.facing=facing;
 const edges=data.floors[0].cells[0].edges;
 for(const d of dirs)edges[d]=1;
 edges[dirs[(facing+3)%4]]=2;edges[dirs[(facing+1)%4]]=2;
 const before=game.snapshot(),front=cast(game,0),left=cast(game,-.8),right=cast(game,.8);
 assert.equal(front.door,false);near(front.distance,.9);
 assert(left.door);assert(right.door);assert.equal(left.direction,(facing+3)%4);assert.equal(right.direction,(facing+1)%4);
 near(left.distance,right.distance);
 // The centre of each side door must be inside the screen, even with a front wall.
 near(cast(game,-.78125).u,.5);near(cast(game,.78125).u,.5);
 let leftPixels=0,rightPixels=0;
 for(let x=0;x<800;x+=2){const hit=cast(game,2*(x+1)/800-1);assert(Number.isFinite(hit.distance));if(hit.door){if(x<400)leftPixels+=2;else rightPixels+=2;}}
 assert(leftPixels>=240);assert(rightPixels>=240);
 assert.deepEqual(game.snapshot(),before,'Rendering must not move the player');
 // Turn toward the same physical door: it becomes the centre door.
 game.turn(1);assert(cast(game,0).door);
}
// Secret side doors still look like walls, and darkness still hides the view.
game.state.facing=0;data.floors[0].cells[0].edges.east=3;assert.equal(cast(game,.8).door,false);
game.state.secrets.add('1:0:0:1');assert(cast(game,.8).door);
data.floors[0].cells[0].edges.north=0;data.floors[0].cells[20].dark=true;assert(cast(game,0).dark);
console.log('View: both side doors visible with front wall, door centres in frame, four rotations/wrapped edges, secret/dark cells and unchanged coordinates passed');
