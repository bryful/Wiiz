/* Prototype character/roster management; creation presets are not ROM rules. */
(function(root){
  'use strict';
  const Combat=typeof module!=='undefined'&&module.exports?require('./combat-rules.js'):root.WizCombatRules;
  const CLASSES=['戦士','魔術師','僧侶','盗賊','司教','侍','君主','忍者'];
  const RACES=['人間','エルフ','ドワーフ','ノーム','ホビット'];
  const ALIGNMENTS=['善','中立','悪'];
  const clone=v=>JSON.parse(JSON.stringify(v));
  const integer=(n,a,b)=>Number.isInteger(n)&&n>=a&&n<=b;
  const signed=n=>n>=128?n-256:n;
  const HP=[12,6,8,8,8,10,10,8];
  const ATTRS=[[14,8,8,12,10,9],[8,14,8,9,11,10],[10,9,14,11,8,10],[10,10,8,10,14,12]];
  const GEAR=[[1,10,7],[5,9],[3,10,7],[2,10,7]];
  const startingMagic=classId=>({halito:[1,4,5,7].includes(classId)?2:0,dios:[2,4,6].includes(classId)?2:0,dialko:[2,4,6].includes(classId)?2:0,latumofis:[2,4,6].includes(classId)?2:0});
  function create(items, saved){
    const catalog=new Map(items.map(i=>[i.id,i]));
    let model={nextId:1,roster:[],members:[]};
    const character=id=>{const c=model.roster.find(c=>c.id===id);if(!c)throw Error('キャラクターが見つかりません');return c;};
    const item=id=>{const i=catalog.get(id);if(!i)throw Error('アイテムが見つかりません');return i;};
    function canEquip(c,i){return i.stats.kind<=4&&Boolean(i.stats.equip_mask&(1<<c.classId))&&Boolean(i.stats.alignment_raw&(1<<c.alignment));}
    function compatible(c){return !model.members.some(id=>{const other=character(id);return (c.alignment===0&&other.alignment===2)||(c.alignment===2&&other.alignment===0);});}
    function addCharacter({name,classId=0,raceId=0,alignment=1}){
      name=String(name??'').trim();
      if(!name||[...name].length>16||/[\u0000-\u001f\u007f]/.test(name))throw Error('名前は1〜16文字で入力してください');
      if(!integer(classId,0,3)||!integer(raceId,0,4)||!integer(alignment,0,2))throw Error('作成条件が不正です');
      if(model.roster.length>=20)throw Error('登録できるキャラクターは20人までです');
      if(model.roster.some(c=>c.name===name))throw Error('同じ名前が登録されています');
      const c={id:model.nextId,name,classId,raceId,alignment,level:1,experience:0,gold:0,
        hp:HP[classId],maxHp:HP[classId],status:0,poison:0,magic:startingMagic(classId),attributes:[...ATTRS[classId]],inventory:[]};
      for(const id of GEAR[classId])if(catalog.has(id))c.inventory.push({itemId:id,equipped:false,identified:true});
      for(const entry of c.inventory)entry.equipped=canEquip(c,item(entry.itemId));
      model.roster.push(c);model.nextId++;return c.id;
    }
    function join(id){
      const c=character(id);
      if(model.members.includes(id))throw Error('すでにパーティに参加しています');
      if(model.members.length>=6)throw Error('パーティは6人までです');
      if(!compatible(c))throw Error('善と悪のメンバーは同じパーティに入れません（試作ルール）');
      model.members.push(id);
    }
    function leave(id){if(!model.members.includes(id))throw Error('パーティに参加していません');model.members=model.members.filter(v=>v!==id);}
    function reorder(id,delta){const from=model.members.indexOf(id),to=from+delta;if(from<0||!integer(to,0,model.members.length-1))return;[model.members[from],model.members[to]]=[model.members[to],model.members[from]];}
    function equip(id,slot){
      const c=character(id),entry=c.inventory[slot];if(!entry)throw Error('所持枠が見つかりません');
      const i=item(entry.itemId);
      if(entry.equipped){if(i.stats.cursed_raw)throw Error('呪われた装備はここでは外せません');entry.equipped=false;return;}
      if(!canEquip(c,i))throw Error('職業・属性・種類の条件で装備できません');
      const previous=c.inventory.find(e=>e.equipped&&item(e.itemId).stats.kind===i.stats.kind);
      if(previous&&item(previous.itemId).stats.cursed_raw)throw Error('同じ部位の呪われた装備を外せません');
      if(previous)previous.equipped=false;entry.equipped=true;
    }
    function transfer(from,slot,to){
      if(from===to)throw Error('別のメンバーを選んでください');
      const a=character(from),b=character(to),entry=a.inventory[slot];
      if(!entry)throw Error('所持枠が見つかりません');
      if(entry.equipped)throw Error('渡す前に装備を外してください');
      if(b.inventory.length>=8)throw Error('受け取る側の所持品が8個あります');
      a.inventory.splice(slot,1);b.inventory.push({...entry,equipped:false});
    }
    function summary(id){
      const c=character(id);let ac=10,strength=0,attacks=1,damage={count:2,sides:2,bonus:0},criticalRaw=0;
      for(const entry of c.inventory){if(!entry.equipped)continue;const i=item(entry.itemId),s=i.stats;
        ac=signed((ac+s.ac_modifier)&255);strength=signed((strength+s.strength)&255);criticalRaw|=s.critical_raw;
        if(s.kind===0){damage={count:s.damage.count,sides:s.damage.sides,bonus:(damage.bonus+s.damage.bonus)&255};attacks=Math.max(attacks,s.minimum_attacks);}
      }
      return {ac,strength,attacks,damage,criticalRaw};
    }
    function validate(v){
      if(!v||!integer(v.nextId,1,1000000)||!Array.isArray(v.roster)||v.roster.length>20||!Array.isArray(v.members)||v.members.length>6)throw Error('パーティ記録が不正です');
      v=clone(v);
      const ids=new Set(),names=new Set();
      for(const c of v.roster){
        if(!c||!integer(c.id,1,v.nextId-1)||ids.has(c.id)||typeof c.name!=='string'||c.name!==c.name.trim()||!c.name||[...c.name].length>16||/[\u0000-\u001f\u007f]/.test(c.name)||names.has(c.name))throw Error('キャラクター記録が不正です');
        ids.add(c.id);names.add(c.name);
        for(const [key,a,b]of[['classId',0,7],['raceId',0,4],['alignment',0,2],['level',1,999],['experience',0,Number.MAX_SAFE_INTEGER],['gold',0,Number.MAX_SAFE_INTEGER],['maxHp',1,32767],['hp',0,c.maxHp],['status',0,7],['poison',0,255]])if(!integer(c[key],a,b))throw Error('能力値が不正です');
        if(c.magic===undefined)c.magic=startingMagic(c.classId);
        const maximum=startingMagic(c.classId);
        if(!c.magic||typeof c.magic!=='object'||Array.isArray(c.magic))throw Error('呪文の使用回数が不正です');
        for(const key of Object.keys(maximum)){if(c.magic[key]===undefined&&['dialko','latumofis'].includes(key))c.magic[key]=maximum[key];if(!integer(c.magic[key],0,maximum[key]))throw Error('呪文の使用回数が不正です');}
        if(!Array.isArray(c.attributes)||c.attributes.length!==6||c.attributes.some(a=>!integer(a,0,255))||!Array.isArray(c.inventory)||c.inventory.length>8)throw Error('能力値または所持品が不正です');
        const kinds=new Set();
        for(const e of c.inventory){
          if(!e||!catalog.has(e.itemId)||typeof e.equipped!=='boolean'||typeof e.identified!=='boolean')throw Error('所持品が不正です');
          if(e.equipped){const i=item(e.itemId);if(!canEquip(c,i)||kinds.has(i.stats.kind))throw Error('装備状態が不正です');kinds.add(i.stats.kind);}
        }
      }
      if(new Set(v.members).size!==v.members.length||v.members.some(id=>!ids.has(id)))throw Error('編成が不正です');
      const align=v.members.map(id=>v.roster.find(c=>c.id===id).alignment);
      if(align.includes(0)&&align.includes(2))throw Error('属性の組合せが不正です');
      return clone(v);
    }
    if(saved!==undefined)model=validate(saved);
    else for(const [name,classId]of[['レオン',0],['ミラ',2],['カイ',3],['リナ',1]])join(addCharacter({name,classId}));
    function combatSummary(id){const c=character(id),s=summary(id),base=Combat.baseStats(c.classId,c.level,c.attributes[0]);return {...s,hit:Combat.signed(base.hit+s.strength),attacks:Math.max(base.attacks,s.attacks),damage:{...s.damage,bonus:(s.damage.bonus+base.damageBonus)&255}};}
    return {get model(){return model;},character,item,canEquip,addCharacter,join,leave,reorder,equip,transfer,summary,combatSummary,
      canExplore:()=>model.members.some(id=>{const c=character(id);return c.status===0&&c.hp>0;}),
      snapshot:()=>clone(model)};
  }
  const api={create,CLASSES,RACES,ALIGNMENTS,startingMagic};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WizParty=api;
})(globalThis);
