const fs=require('node:fs'),assert=require('node:assert/strict'),Battle=require('../web/explorer/battle.js'),Party=require('../web/explorer/party.js'),Rules=require('../web/explorer/combat-rules.js');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
for(let a=0;a<=18;a++)for(let r=0;r<10;r++){const bonus=a>=15?14-a:a>=8?0:a>=6?1:a>=4?2:3;assert.equal(Rules.playerPriority(a,r),Math.max(0,Math.min(9,r+bonus))+1);}
for(let r=0;r<256;r++)assert.equal(Rules.enemyPriority(r),(r&7)+2);
function scenario({random=.99,hp=100,damage=0,count=1,level=100}={}){
 const p=Party.create(data.items),source={...data.monsters[0],stats:{...data.monsters[0].stats,ac:0,level,hp:{count:1,sides:1,bonus:hp-1},encounter:{count:1,sides:1,bonus:count-1},attacks:damage?[{count:1,sides:1,bonus:damage-1}]:[]}},b=Battle.create(()=>p,[source],()=>random,data.spells);
 b.start({monsterId:0,group:count>1,floor:10});return {p,b};
}
let {p,b}=scenario({random:0});p.character(4).attributes[4]=18;for(const id of [1,2,3])p.character(id).attributes[4]=0;
b.planAll('guard');const before=p.snapshot();assert.equal(b.state.round,0);b.execute();assert.equal(b.state.round,1);assert.equal(b.state.lastOrder[0].name,p.character(4).name);assert.equal(b.state.lastOrder[1].name,b.state.enemy.name+'1');assert.deepEqual(p.snapshot(),before);assert.deepEqual(b.state.commands,{});
// Defence is effective for the whole turn, including attacks before the guard action.
function guarded(guard){const s=scenario({random:.45,damage:1,level:1});s.p.model.members=[1];s.p.character(1).attributes[4]=0;for(const e of s.p.character(1).inventory)e.equipped=false;s.b.plan(1,{type:guard?'guard':'attack',target:0});s.b.execute();assert(s.b.state.lastOrder[0].name.startsWith(s.b.state.enemy.name));return s.p.character(1).hp;}
assert.equal(guarded(true),12);assert.equal(guarded(false),11);
({p,b}=scenario({damage:100}));p.model.members=[4];p.character(4).attributes[4]=0;b.plan(4,{type:'halito',target:0});b.execute();assert.equal(b.state.result,'defeat');assert.equal(p.character(4).magic.halito,2);
// Earlier attacks retarget later spells, without charging spells cancelled by victory.
({p,b}=scenario({hp:4,count:2}));p.model.members=[1,4];for(const c of p.model.roster)c.attributes[4]=18;
b.plan(1,{type:'attack',target:1});b.plan(4,{type:'halito',target:1});b.execute();assert.equal(b.state.result,'victory');assert.equal(p.character(4).magic.halito,1);assert.equal(p.character(1).experience,55);
({p,b}=scenario({hp:1}));p.model.members=[1,4];for(const c of p.model.roster)c.attributes[4]=18;b.plan(1,{type:'attack',target:0});b.plan(4,{type:'halito',target:0});b.execute();assert.equal(b.state.result,'victory');assert.equal(p.character(4).magic.halito,2);
({p,b}=scenario());p.model.members=[1,2,4];p.character(1).hp=1;for(const c of p.model.roster)c.attributes[4]=18;
b.plan(1,{type:'attack',target:0});b.plan(2,{type:'dios',target:1});b.plan(4,{type:'halito',target:0});b.execute();assert.equal(p.character(1).hp,9);assert.equal(p.character(2).magic.dios,1);assert.equal(p.character(4).magic.halito,1);assert.equal(b.state.round,1);
({p,b}=scenario({random:.5}));p.model.members=[1,4];p.character(1).attributes[4]=18;p.character(4).attributes[4]=0;b.plan(1,{type:'flee'});b.plan(4,{type:'halito',target:0});b.execute();assert.equal(b.state.result,'escaped');assert.equal(p.character(4).magic.halito,2);
({p,b}=scenario({damage:1}));p.model.members=[1];p.character(1).attributes[4]=18;b.plan(1,{type:'flee'});b.execute();assert.equal(p.character(1).hp,11);assert(b.active); // One scheduled counterattack, not another round on failure.
({p,b}=scenario({damage:100,count:2}));p.model.members=[1,4];for(const c of p.model.roster)c.attributes[4]=0;b.planAll('guard');b.execute();assert.equal(p.character(4).hp,0);assert.equal(p.character(1).hp,12);assert(b.active); // Second enemy keeps its now-dead target.
({p,b}=scenario({damage:100}));p.model.members=[1,2,4];for(const c of p.model.roster)c.attributes[4]=0;b.planAll('guard');b.plan(2,{type:'dios',target:4});b.execute();assert.equal(p.character(4).hp,0);assert.equal(p.character(2).magic.dios,2);assert(b.active);
({p,b}=scenario());assert.throws(()=>b.plan(1,{type:'halito',target:0}));assert.throws(()=>b.plan(1,{type:'attack',target:99}));assert.equal(b.state.round,0);
b.plan(4,{type:'halito',target:0});p.character(4).magic.halito=0;const saved=p.snapshot();assert.throws(()=>b.execute());assert.deepEqual(p.snapshot(),saved);assert.equal(b.state.round,0);
console.log('Turns: 446 priority cases, mixed order/ties, planning, defence, dead actors/targets, automatic retarget, combined attack/heal/spell, escape cancellation and validation atomicity passed');
