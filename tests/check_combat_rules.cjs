const fs=require('node:fs'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const Rules=require('../web/explorer/combat-rules.js'),Party=require('../web/explorer/party.js'),Battle=require('../web/explorer/battle.js');
const code=`import sys,json
sys.path.insert(0,'tools')
from combat_rules import base_stats,player_threshold,enemy_threshold
print(json.dumps(dict(base=[base_stats(c,l,s) for c in range(8) for l in [1,2,3,4,5,10,50,254,255,256,999] for s in range(26)],player=[player_threshold(h,a,g) for h in range(-128,128) for a in range(-99,100) for g in [1,4]],enemy=[enemy_threshold(l,a,r,p) for p in [False,True] for r in [0,1,6,10,96,127,128,255] for l in [1,5,20,25,127,255] for a in range(-99,100)])))`;
const result=spawnSync('python',['-c',code],{encoding:'utf8',maxBuffer:4*1024*1024});assert.equal(result.status,0,result.stderr);const expected=JSON.parse(result.stdout);
let index=0;for(let c=0;c<8;c++)for(const l of [1,2,3,4,5,10,50,254,255,256,999])for(let s=0;s<26;s++){const b=Rules.baseStats(c,l,s),p=expected.base[index++];assert.deepEqual(b,{hit:p.hit,attacks:p.attacks,damageBonus:p.damage_bonus});}
index=0;for(let h=-128;h<128;h++)for(let a=-99;a<100;a++)for(const g of [1,4])assert.equal(Rules.playerThreshold(h,a,g),expected.player[index++]);
index=0;for(const p of [false,true])for(const r of [0,1,6,10,96,127,128,255])for(const l of [1,5,20,25,127,255])for(let a=-99;a<100;a++)assert.equal(Rules.enemyThreshold(l,a,r,p),expected.enemy[index++]);
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const p=Party.create(data.items),fighter=p.character(1);fighter.level=25;fighter.attributes[0]=18;const combat=p.combatSummary(1);assert.equal(combat.attacks,6);assert.equal(combat.hit,Rules.signed(13+p.summary(1).strength));assert.equal(combat.damage.bonus,(p.summary(1).damage.bonus+3)&255);
fighter.level=1;fighter.attributes[0]=14;
const source={...data.monsters[0],stats:{...data.monsters[0].stats,level:1,ac:0,attacks:[{count:1,sides:1,bonus:0}]}};
let draws=[];const rng=()=>draws.shift()??0;
let b=Battle.create(()=>p,[source],rng);b.start({monsterId:0});draws=[.99,0,.45,0];b.flee();assert.equal(fighter.hp,fighter.maxHp,'Armour should prevent this roll');
for(const item of fighter.inventory)item.equipped=false;
b=Battle.create(()=>p,[source],rng);b.start({monsterId:0});draws=[.99,0,.45,0];b.flee();assert.equal(fighter.hp,fighter.maxHp-1,'Same attack should hit without armour');
// A miss must not advance the enemy damage table.
const mixed={...source,stats:{...source.stats,level:1,ac:0,attacks:[{count:1,sides:1,bonus:0},{count:1,sides:1,bonus:50}]}};
fighter.hp=fighter.maxHp;b=Battle.create(()=>p,[mixed],rng);b.start({monsterId:0});draws=[.99,0,0,.99,0];b.flee();assert.equal(fighter.hp,fighter.maxHp-1);
assert.equal(Rules.playerThreshold(20,10),1);assert.equal(Rules.playerThreshold(-100,0),20);assert.equal(Rules.playerThreshold(127,99),20); // Preserve byte overflow.
console.log('Combat: 123,280 JS/Python rule vectors, class/level/STR/equipment integration, armour affects enemy hits, and missed attacks preserve damage-table position passed');
