const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('output/explorer/index.html','utf8'),data=JSON.parse(html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1]);
for(const f of data.floors)for(const c of f.cells){c.edges={north:0,east:0,south:0,west:0};delete c.event;c.dark=false;}
data.monsters[0].stats.level=100; // Force counterattack damage so healing can be exercised.
const elements={},events={},storage=new Map();let scrolls=0;
const ctx=new Proxy({createLinearGradient:()=>({addColorStop(){}}),createRadialGradient:()=>({addColorStop(){}})},{get(t,k){return t[k]||(()=>{});}});
function el(id){return elements[id]??={width:800,height:500,value:'',textContent:id==='maps'?JSON.stringify(data):'',innerHTML:'',hidden:false,disabled:false,events:{},scrollIntoView(){scrolls++;},getContext:()=>ctx,addEventListener(k,fn){this.events[k]=fn;}};}
let randomValue=0;const math=Object.create(Math);math.random=()=>randomValue;
const context=vm.createContext({Math:math,document:{getElementById:el,addEventListener(k,fn){events[k]=fn;}},localStorage:{setItem(k,v){storage.set(k,v);},getItem(k){return storage.get(k)||null;}}});
for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(m[1],context);
function walk(){events.keydown({key:'ArrowUp',code:'ArrowUp',target:{tagName:'BODY'},preventDefault(){}});}
for(let i=0;i<6;i++)walk();assert.equal(el('battle-panel').hidden,false);assert.equal(scrolls,1);assert(el('battle-enemy').textContent.includes('2/2体'));assert.equal(el('save').disabled,true);
el('battle-target').value='1';el('battle-target').events.change();assert.equal(el('battle-target').value,'1');
randomValue=.5;
// Queue a spell with the others guarding; editing commands must not consume resources.
function guardAll(){for(const member of ['1','2','3','4'])el('turn-commands').events.change({target:{closest:()=>({dataset:{member,field:'action'},value:'guard'})}});}
guardAll();
el('cast-halito').events.click();assert(el('spell-message').textContent.includes('指示'));assert(el('halito-caster').innerHTML.includes('残り2回'));
el('turn-execute').events.click();assert(el('halito-caster').innerHTML.includes('残り1回'));
guardAll();el('heal-target').value='3';el('cast-dios').events.click();assert(el('spell-message').textContent.includes('指示'));el('turn-execute').events.click();assert(el('dios-caster').innerHTML.includes('残り1回'));
for(let i=0;i<10&&!el('battle-attack').disabled;i++){el('battle-attack').events.click();el('turn-execute').events.click();}assert(el('battle-log').textContent.includes('勝利'));assert.equal(el('save').disabled,false);
el('save').events.click();const key=[...storage.keys()][0],saved=JSON.parse(storage.get(key));assert.equal(saved.party.roster[3].magic.halito,1);assert.equal(saved.party.roster[1].magic.dios,1);assert.equal(saved.party.roster[0].experience,27);
el('load').events.click();assert(el('halito-caster').innerHTML.includes('残り1回'));
el('entrance').events.click();el('recover').events.click();assert(el('halito-caster').innerHTML.includes('残り2回'));
el('auto-encounters').checked=false;el('auto-encounters').events.change();for(let i=0;i<12;i++)walk();assert.equal(scrolls,1);assert.equal(el('forward').disabled,false);
el('auto-encounters').checked=true;el('auto-encounters').events.change();
randomValue=0;
for(const floor of data.floors){
 storage.set(key,JSON.stringify({...saved,floor:floor.id,x:0,y:0}));el('load').events.click();assert(el('encounter-status').textContent.includes(`B${floor.id}F`));
 for(let i=0;i<6;i++)walk();
 const row=data.encounters.floors[floor.id-1].ranges[0],id=row.base+row.step*(row.threshold?row.repeats:0),opponent=data.monsters.find(m=>m.id===id);
 assert(el('battle-enemy').textContent.includes(opponent.name_ja));assert.equal(el('battle-image').src,opponent.image);assert.equal(el('battle-attack').disabled,false);
 el('battle-flee').events.click();el('turn-execute').events.click();assert(el('battle-log').textContent.includes('逃走に成功'));assert.equal(el('forward').disabled,false);
}
assert.equal(scrolls,11);
const afflicted=structuredClone(saved);afflicted.floor=1;afflicted.x=0;afflicted.y=0;afflicted.party.roster[0].status=3;afflicted.party.roster[0].poison=1;
storage.set(key,JSON.stringify(afflicted));el('load').events.click();assert(el('party-list').innerHTML.includes('麻痺'));assert(el('party-list').innerHTML.includes('毒'));
el('support-spell').value='DIALKO';el('support-spell').events.change();el('heal-target').value='1';el('cast-dios').events.click();assert(el('spell-message').textContent.includes('治療'));assert(!el('party-list').innerHTML.includes('麻痺'));assert(el('party-list').innerHTML.includes('毒'));
el('support-spell').value='LATUMOFIS';el('support-spell').events.change();el('heal-target').value='1';el('cast-dios').events.click();assert(!el('party-list').innerHTML.includes('毒'));
el('save').events.click();const cured=JSON.parse(storage.get(key));assert.equal(cured.party.roster[0].status,0);assert.equal(cured.party.roster[0].poison,0);assert.equal(cured.party.roster[1].magic.dialko,1);assert.equal(cured.party.roster[1].magic.latumofis,1);
el('battle-start').events.click();assert(el('turn-commands').innerHTML.includes('ディアルコ'));assert(el('turn-commands').innerHTML.includes('ラツモフィス'));
console.log('Encounter UI: walking starts group/scroll/locks, target selection, HALITO/DIOS, victory, resource save/load/recovery and encounter toggle passed');
