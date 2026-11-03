const assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process');
const Party=require('../web/explorer/party.js'),Explorer=require('../web/explorer/engine.js');
const html=fs.readFileSync('output/explorer/index.html','utf8');
const data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const p=Party.create(data.items);
assert.equal(p.model.roster.length,4);assert.equal(p.model.members.length,4);
const fighter=p.character(1),mage=p.character(4);
assert.equal(p.summary(1).ac,6);assert.equal(p.summary(4).ac,9);
p.equip(1,0);assert.equal(fighter.inventory[0].equipped,false);p.transfer(1,0,4);
assert.equal(mage.inventory.length,3);assert.throws(()=>p.equip(4,2)); // Mage cannot use a long sword.
assert.throws(()=>p.transfer(1,0,4)); // Still equipped armor.
const extra=p.addCharacter({name:'テスト',classId:3,raceId:4,alignment:1});p.join(extra);
const sixth=p.addCharacter({name:'六人目'});p.join(sixth);
const seventh=p.addCharacter({name:'七人目'});assert.throws(()=>p.join(seventh));
p.reorder(extra,-1);assert.equal(p.model.members[3],extra);
p.leave(extra);p.join(seventh);assert(!p.model.members.includes(extra));
assert.throws(()=>p.addCharacter({name:'レオン'}));assert.throws(()=>p.addCharacter({name:'x'.repeat(17)}));
const align=Party.create(data.items);const good=align.addCharacter({name:'善',alignment:0}),evil=align.addCharacter({name:'悪',alignment:2});align.join(good);assert.throws(()=>align.join(evil));
const saved=p.snapshot();assert.deepEqual(Party.create(data.items,saved).snapshot(),saved);
const full=Party.create(data.items).snapshot();full.roster[0].inventory=[{itemId:1,equipped:false,identified:true}];full.roster[1].inventory=Array.from({length:8},()=>({itemId:5,equipped:false,identified:true}));
const capacity=Party.create(data.items,full),beforeFull=capacity.snapshot();assert.throws(()=>capacity.transfer(1,0,2));assert.deepEqual(capacity.snapshot(),beforeFull);
const curse=data.items.find(i=>i.stats.cursed_raw&&i.stats.kind<=4&&i.stats.equip_mask&&i.stats.alignment_raw);
assert(curse);const cursed=Party.create(data.items).snapshot(),victim=cursed.roster[0];
victim.classId=[0,1,2,3,4,5,6,7].find(c=>curse.stats.equip_mask&(1<<c));victim.alignment=[0,1,2].find(a=>curse.stats.alignment_raw&(1<<a));victim.inventory=[{itemId:curse.id,equipped:true,identified:true}];cursed.members=[1];
const locked=Party.create(data.items,cursed),lockedSave=locked.snapshot();assert.throws(()=>locked.equip(1,0));assert.deepEqual(locked.snapshot(),lockedSave);
for(const mutate of [s=>s.members.push(s.members[0]),s=>s.roster[0].hp=999,s=>s.roster[0].inventory.push({itemId:999,equipped:false,identified:true}),s=>s.roster[0].inventory[0].equipped='yes',s=>s.roster[0].attributes=[1],s=>s.nextId=1]){
 const bad=JSON.parse(JSON.stringify(saved));mutate(bad);assert.throws(()=>Party.create(data.items,bad));
}
const game=Explorer.create(data);game.move();const original=game.snapshot();
const bad=JSON.parse(JSON.stringify(original));bad.x=10;bad.party.members=[999];assert.throws(()=>game.restore(bad));assert.deepEqual(game.snapshot(),original);
const id=game.party.addCharacter({name:'旧形式のあと'});const before=game.party.snapshot();
const legacy={...original,version:1};delete legacy.party;game.restore(legacy);assert.deepEqual(game.party.snapshot(),before);assert(game.party.character(id));
for(const id of [...game.party.model.members])game.party.leave(id);const steps=game.state.steps;game.move();assert.equal(game.state.steps,steps);

// Compare the JS W1 equipment summary against the already CPU-verified Python
// kernel on real ROM items. This catches sign, dice ordering and class-mask bugs.
const program=`import sys,json\nsys.path.insert(0,'tools')\nfrom game_rules import equipment_contribution\nitems=json.load(sys.stdin)\nresult=[]\nfor item in items:\n s=dict(strength=0,attacks=1,ac=10,critical_raw=0,damage=dict(count=2,sides=2,bonus=0))\n result.append(equipment_contribution('wiz1',s,item))\nprint(json.dumps(result))`;
const expected=JSON.parse(cp.execFileSync('python',['-c',program],{input:JSON.stringify(data.items),encoding:'utf8'}));
let count=0;
for(const item of data.items){
 if(item.stats.kind>4)continue;
 const classes=[0,1,2,3,4,5,6,7].filter(c=>item.stats.equip_mask&(1<<c));
 const alignments=[0,1,2].filter(a=>item.stats.alignment_raw&(1<<a));
 if(!classes.length||!alignments.length)continue;
 const seed=Party.create(data.items).snapshot(),c=seed.roster[0];
 c.classId=classes[0];c.alignment=alignments[0];c.inventory=[{itemId:item.id,equipped:true,identified:true}];seed.members=[c.id];
 const summary=Party.create(data.items,seed).summary(c.id),r=expected[item.id];
 assert.deepEqual(summary,{ac:r.ac,strength:r.strength,attacks:r.attacks,damage:r.damage,criticalRaw:r.critical_raw});count++;
}
console.log(`Party: creation/6 slots/order/transfer/equipment/atomic saves/legacy migration passed; ${count} ROM equipment summaries matched Python kernels`);
