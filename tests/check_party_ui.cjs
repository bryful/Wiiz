const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('output/explorer/index.html','utf8'),payload=html.match(/<script id="maps" type="application\/json">([\s\S]*?)<\/script>/)[1];
assert(html.includes('href="#party-controls"'));assert(html.includes('id="party-controls"'));
const elements={},events={},storage=new Map();
const ctx=new Proxy({createLinearGradient:()=>({addColorStop(){}}),createRadialGradient:()=>({addColorStop(){}})},{get(t,k){return t[k]||(()=>{});}});
function el(id){return elements[id]??={width:800,height:500,value:'0',textContent:id==='maps'?payload:'',innerHTML:'',hidden:false,disabled:false,events:{},getContext:()=>ctx,addEventListener(k,fn){this.events[k]=fn;}};}
const context=vm.createContext({document:{getElementById:el,addEventListener(k,fn){events[k]=fn;}},localStorage:{setItem(k,v){storage.set(k,v);},getItem(k){return storage.get(k)||null;}}});
for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(m[1],context);
function click(container,action,id,slot){el(container).events.click({target:{closest:()=>({disabled:false,dataset:{action,id:String(id),slot:String(slot)}})}});}
assert.equal(el('party-count').textContent,'4 / 6 人');assert(el('party-list').innerHTML.includes('レオン'));
el('new-name').value='<勇者>';el('new-class').value='0';el('new-alignment').value='1';
el('create-character').events.submit({preventDefault(){}});assert.equal(el('character-title').textContent,'<勇者>');assert(el('party-list').innerHTML.includes('&lt;勇者&gt;'));
assert.equal(el('party-count').textContent,'5 / 6 人');assert(el('create-message').textContent.includes('参加しました'));assert.equal(el('new-name').value,'');
click('party-list','select',1);click('inventory','equip',undefined,0);assert(el('party-message').textContent.includes('装備'));
el('transfer-to').value='4';click('inventory','transfer',undefined,0);click('party-list','select',4);assert(el('inventory').innerHTML.includes('けん'));assert(el('inventory').innerHTML.includes('装備不可'));
el('save').events.click();const key=[...storage.keys()][0],save=JSON.parse(storage.get(key));assert.equal(save.version,2);assert.equal(save.party.members.length,5);
click('party-list','leave',5);assert.equal(el('party-count').textContent,'4 / 6 人');el('load').events.click();assert.equal(el('party-count').textContent,'5 / 6 人');
events.keydown({key:'ArrowUp',target:{tagName:'BODY'},preventDefault(){}});assert.equal(el('base-only').hidden,true);
assert.equal(el('party-base').hidden,false);
click('party-list','leave',5);assert(el('party-message').textContent.includes('入口か地上'));assert.equal(el('party-count').textContent,'5 / 6 人');
const before=el('position').textContent;storage.set(key,JSON.stringify({...save,floor:9,party:{...save.party,members:[999]}}));el('load').events.click();assert.equal(el('position').textContent,before);assert.equal(el('party-count').textContent,'5 / 6 人');
el('party-base').events.click();assert.equal(el('base-only').hidden,false);assert.equal(el('party-base').hidden,true);assert(el('position').textContent.includes('東0 / 北0'));
function register(name,alignment='1'){el('new-name').value=name;el('new-alignment').value=alignment;el('create-character').events.submit({preventDefault(){}});}
register('善の戦士','0');assert.equal(el('party-count').textContent,'6 / 6 人');
register('待機の戦士');assert.equal(el('party-count').textContent,'6 / 6 人');assert(el('roster-list').innerHTML.includes('待機の戦士'));assert(el('create-message').textContent.includes('6人まで'));
click('party-list','leave',1);
register('悪の戦士','2');assert.equal(el('party-count').textContent,'5 / 6 人');assert.equal(el('character-title').textContent,'悪の戦士');assert(el('create-message').textContent.includes('善と悪'));assert(el('roster-list').innerHTML.includes('悪の戦士'));
register('悪の戦士','2');assert(el('create-message').textContent.includes('同じ名前'));
el('save').events.click();const registered=JSON.parse(storage.get(key));assert.equal(registered.party.roster.length,8);assert.equal(registered.party.members.length,5);
el('load').events.click();assert(el('roster-list').innerHTML.includes('悪の戦士'));
console.log('Party UI: creation/escaped names/join/select/equip/transfer/save/load/base-only editing and corrupt-save atomicity passed');
