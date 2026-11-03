const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('output/explorer/index.html','utf8');
assert(!html.includes('__MAPS__')&&!html.includes('__ENGINE__')&&!html.includes('__UI__'));
assert(!/<script[^>]+src=|fetch\(/.test(html),'Must work without external script or fetch');
const payload=html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1],data=JSON.parse(payload);
const events={},elements={},storage=new Map();let drawCalls=0;
const gradient=()=>({addColorStop(){}});
const ctx=new Proxy({createLinearGradient:gradient,createRadialGradient:gradient},{get(t,k){return k in t?t[k]:(...args)=>{for(const v of args)if(typeof v==='number')assert(Number.isFinite(v));drawCalls++;};}});
let mapMarker;
const mapCtx=new Proxy(ctx,{get(t,k){return k==='moveTo'?(...args)=>{mapMarker=args;t.moveTo(...args);}:t[k];}});
function el(id){return elements[id]??={width:id==='map'?320:800,height:id==='map'?320:500,textContent:id==='maps'?payload:'',innerHTML:'',hidden:false,disabled:false,events:{},getContext:()=>id==='map'?mapCtx:ctx,addEventListener(k,fn){this.events[k]=fn;}};}
const localStorage={setItem(k,v){storage.set(k,v);},getItem(k){return storage.get(k)||null;}};
const math=Object.create(Math);math.random=()=>.99;
const context=vm.createContext({Math:math,document:{getElementById:el,addEventListener(k,fn){events[k]=fn;}},localStorage});
for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(match[1],context);
assert(el('position').textContent.includes('東0 / 北0'));assert(drawCalls>1000);
function key(key,tagName='BODY',id='',code=''){let prevented=false;events.keydown({key,code,target:{tagName,id},preventDefault(){prevented=true;}});if(!prevented&&tagName==='BUTTON'&&[' ','Enter'].includes(key))el(id).events.click?.();return prevented;}
assert(key('ArrowUp'));assert(el('position').textContent.includes('東0 / 北1'));
assert(!key('ArrowUp','INPUT'));assert(el('position').textContent.includes('北1'));
key('ArrowRight');assert(el('compass').textContent.includes('EAST'));
// A focused entrance button must not receive the browser's native Space/Enter click.
const before=el('position').textContent;
assert(key(' ','BUTTON','entrance','Space'));assert.equal(el('position').textContent,before);
assert(key('Enter','BUTTON','entrance','Enter'));assert.equal(el('position').textContent,before);
assert(key('あ','BUTTON','entrance','KeyA'));assert(el('compass').textContent.includes('NORTH'));
assert(key('D','BUTTON','entrance','KeyD'));assert(el('compass').textContent.includes('EAST'));
for(const letter of 'bceghijklmnopqrtuvxyz'){
 assert(!key(letter,'BUTTON','entrance',`Key${letter.toUpperCase()}`));assert.equal(el('position').textContent,before);
}
assert(key('f','BUTTON','entrance','KeyF'));assert.equal(el('position').textContent,before);
assert(!key('w','INPUT','','KeyW'));assert.equal(el('position').textContent,before);
assert(key('s','BUTTON','entrance','KeyS'));assert(key('W','BUTTON','entrance','KeyW'));assert.equal(el('position').textContent,before);
el('save').events.click();el('entrance').events.click();el('load').events.click();assert(el('position').textContent.includes('北1'));
const storageKey=[...storage.keys()][0],save=JSON.parse(storage.get(storageKey));
// Door action updates the actual save position, displayed position and map marker together.
const doorCell=data.floors[0].cells.find(c=>c.edges.north===2 && !data.floors[0].cells[((c.y+1)%20)*20+c.x].event);
assert(doorCell);
const doorSave={...save,floor:1,x:doorCell.x,y:doorCell.y,facing:0};
for(const activate of [()=>el('door').events.click(),()=>key(' ','BUTTON','door','Space')]){
 storage.set(storageKey,JSON.stringify(doorSave));el('load').events.click();activate();el('save').events.click();
 const after=JSON.parse(storage.get(storageKey)),y=(doorCell.y+1)%20;
 assert.equal(after.x,doorCell.x);assert.equal(after.y,y);assert.equal(after.steps,save.steps+1);assert(after.visited.includes(`1:${after.x}:${y}`));
 assert(el('position').textContent.includes(`東${after.x} / 北${y}`));
 assert.deepEqual(mapMarker,[20+(after.x+.5)*14,20+(19.5-y)*14-6]);
}
storage.set(storageKey,JSON.stringify(save));el('load').events.click();
storage.set(storageKey,JSON.stringify({...save,x:21}));el('load').events.click();assert(el('position').textContent.includes('北1'));assert(el('save-status').textContent.includes('読み込めません'));
for(const floor of data.floors){
 for(const c of [floor.cells[0],floor.cells.find(c=>c.dark),floor.cells.find(c=>c.edges.north===2)].filter(Boolean)){
  storage.set(storageKey,JSON.stringify({...save,floor:floor.id,x:c.x,y:c.y,visited:[`${floor.id}:${c.x}:${c.y}`]}));el('load').events.click();
  assert(el('position').textContent.includes(`B${floor.id}F`));
 }
}
el('entrance').events.click();el('stairs').events.click();assert.equal(el('outside').hidden,false);assert.equal(el('forward').disabled,true);el('enter').events.click();assert.equal(el('outside').hidden,true);
vm.runInContext('Math.random=()=>0.99',context);
el('battle-start').events.click();assert.equal(el('battle-panel').hidden,false);assert.equal(el('forward').disabled,true);assert.equal(el('save').disabled,true);assert.equal(el('battle-attack').disabled,false);
const battlePosition=el('position').textContent;key('ArrowUp');assert.equal(el('position').textContent,battlePosition);
el('battle-attack').events.click();el('turn-execute').events.click();assert(el('battle-log').textContent.includes('勝利'));assert.equal(el('save').disabled,false);assert.equal(el('battle-attack').disabled,true);
el('recover').events.click();assert(el('log').innerHTML.includes('全回復'));
localStorage.setItem=()=>{throw Error('Denied');};el('save').events.click();assert(el('save-status').textContent.includes('保存できません'));
console.log(`Explorer UI: bundled scripts, keyboard/buttons, all 10 floors, dark/door rendering, save/load/error paths and return/re-entry passed (${drawCalls} finite draw calls)`);
