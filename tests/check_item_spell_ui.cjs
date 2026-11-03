// Run generated scripts offline, without bypassing browser URL restrictions.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
for(const base of ['output','output/wiz2','output/wiz3']){
 const html=fs.readFileSync(base+'/items_spells/index.html','utf8');
 const payload=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
 const data=JSON.parse(payload), elements={};
 const el=id=>elements[id]??=( {value:id==='mode'?'items':'',textContent:id==='data'?payload:'',innerHTML:'',hidden:false,events:{},addEventListener(type,fn){this.events[type]=fn;}} );
 const context=vm.createContext({document:{getElementById:el}});
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
 assert.equal((el('statusrows').innerHTML.match(/<tr>/g)||[]).length,8);
 assert(el('statusrows').innerHTML.includes('ねむっている'));
 assert.equal((el('rows').innerHTML.match(/<tr>/g)||[]).length,data.items.length);
 el('query').value='muramasa';el('query').events.input();
 assert.equal((el('rows').innerHTML.match(/<tr>/g)||[]).length,1);
 assert(el('rows').innerHTML.includes('10d5'));
 assert(el('rows').innerHTML.includes('ちから +1'));
 assert(el('rows').innerHTML.includes('使用後の変化'));
 assert(el('rows').innerHTML.includes('r &lt; 128'));
 if(data.game!=='wiz1')assert(el('rows').innerHTML.includes('r ≤ 128'));
 el('query').value='';el('mode').value='spells';el('mode').events.change();
 assert.equal((el('rows').innerHTML.match(/<tr>/g)||[]).length,data.spells.length);
 el('query').value='dios';el('query').events.input();assert(el('rows').innerHTML.includes('HP回復 1d8'));
 el('query').value='mogref';el('query').events.input();assert(el('rows').innerHTML.includes('AC -2 / 術者'));
 el('query').value='dialko';el('query').events.input();assert(el('rows').innerHTML.includes('睡眠・恐怖・麻痺を治療'));
 el('query').value='kadorto';el('query').events.input();assert(el('rows').innerHTML.includes('死亡・灰を最大HPで蘇生'));
 el('query').value='katino';el('query').events.input();assert(el('rows').innerHTML.includes('睡眠（状態コード1）'));
 el('query').value='montino';el('query').events.input();assert(el('rows').innerHTML.includes('沈黙カウンターを2〜5'));
 el('query').value='';el('query').events.input();
 el('school').value='priest';el('school').events.change();
 assert.equal((el('rows').innerHTML.match(/<tr>/g)||[]).length,29);
 el('query').value='ハリト';el('school').value='';el('query').events.input();
 assert(el('rows').innerHTML.includes('1d8'));
 el('query').value='no-such-spell';el('query').events.input();assert.equal(el('rows').innerHTML,'');
 console.log(data.game+': item/spell switching, search, priest filter, damage display and empty results passed');
}
