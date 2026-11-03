/* Independent combat: ROM-derived hit arithmetic; turn order remains a prototype. */
(function(root){
  'use strict';
  const Combat=typeof module!=='undefined'&&module.exports?require('./combat-rules.js'):root.WizCombatRules;
  const Enemy=typeof module!=='undefined'&&module.exports?require('./enemy-rules.js'):root.WizEnemyRules;
  function create(getParty,monsters,rng=Math.random,spells=[],rules={}){
    let state=null;
    const die=sides=>1+Math.floor(rng()*Math.max(1,sides));
    const hit=threshold=>Math.floor(rng()*20)>=threshold;
    // JP ROM $CDB8 returns the bonus immediately when sides is zero.
    const roll=(d,signed=false)=>Math.max(1,(d.sides===0?0:Array.from({length:d.count},()=>die(d.sides)).reduce((a,b)=>a+b,0))+(signed&&d.bonus>=128?d.bonus-256:d.bonus));
    const living=()=>{const p=getParty();return p.model.members.map(id=>p.character(id)).filter(c=>c.hp>0&&c.status===0);};
    const survivors=()=>{const p=getParty();return p.model.members.map(id=>p.character(id)).filter(c=>c.hp>0&&c.status<5);};
    const defeated=()=>!survivors().some(c=>c.status<3);
    const log=text=>{state.log.unshift(text);state.log=state.log.slice(0,12);};
    const enemies=()=>state.enemies.filter(e=>e.hp>0);
    function choose(index){if(!state?.active||!Number.isInteger(index)||!state.enemies[index]?.hp)throw Error('行動可能な敵を選んでください');state.target=index;state.enemy=state.enemies[index];}
    function start(options={}){
      if(state?.active)throw Error('すでに戦闘中です');
      if(!living().length)throw Error('行動できるメンバーがいません');
      if(!monsters.length)throw Error('戦闘データがありません');
      const source=options.monsterId===undefined?monsters[Math.floor(rng()*monsters.length)]:monsters.find(m=>m.id===options.monsterId);
      if(!source)throw Error('出現する敵のデータがありません');
      const count=options.group?Math.min(Math.min((options.floor||1)+4,9),roll(source.stats.encounter)):1;
      const group=Array.from({length:count},(_,index)=>{const hp=roll(source.stats.hp);return {index,id:source.id,name:source.name_ja,hp,maxHp:hp,stats:source.stats,image:source.image};});
      state={active:true,result:null,round:0,target:0,enemies:group,enemy:group[0],magic:{mage:source.stats.mage_spell_level,priest:source.stats.priest_spell_level},commands:{},lastOrder:[],log:[`${source.name_ja}が${count}体現れた！`]};
    }
    function enemyTurn(){
      for(const enemy of enemies()){
      enemyAct(enemy);
      }
      if(defeated())finish('defeat');
    }
    function enemyAct(enemy,chosenTarget=null,defending=new Set()){
      const candidates=survivors();if(!candidates.length){finish('defeat');return;}
      const p=getParty(),target=chosenTarget||candidates[Math.floor(rng()*candidates.length)],ac=p.summary(target.id).ac;
      if(target.hp<=0||target.status>=5)return;
      let damageIndex=0;
      let hits=0;
      for(let attempt=0;attempt<enemy.stats.attacks.length;attempt++){
        if(target.hp===0)break;
        // Correct the FC indexing bug: use the defender's AC instead of unrelated RAM.
        if(hit(Combat.enemyThreshold(enemy.stats.level,enemy.stats.ac,ac,defending.has(target.id)))){hits++;const n=roll(enemy.stats.attacks[damageIndex++])*(target.status===0?1:2);target.hp=Math.max(0,target.hp-n);log(`${enemy.name} → ${target.name}に${n}ダメージ。`);if(!target.hp){target.status=5;log(`${target.name}は倒れた。`);}}
        else log(`${enemy.name}の攻撃は外れた。`);
      }
      if(hits&&target.hp>0)for(const effect of Enemy.contact(enemy.stats.status_flags_raw||0,target,rng))log(`${target.name}は${effect}になった。`);
      if(defeated())finish('defeat');
    }
    function finish(result){
      state.active=false;state.result=result;
      if(result==='victory'){
        const alive=survivors(),reward=Math.floor(state.enemies.filter(e=>!e.escaped).reduce((n,e)=>n+e.stats.experience,0)/alive.length);
        for(const c of alive)c.experience=Math.min(Number.MAX_SAFE_INTEGER,c.experience+reward);
        log(`勝利！ 生存者1人あたり経験値${reward}。`);
      }else log(result==='escaped'?'逃走に成功した。':result==='dispersed'?'敵はすべて逃げ去った。':'パーティが行動不能になった。入口に戻って「試作用の全回復」を使えます。');
    }
    function attack(){
      if(!state?.active)return;
      state.round++;
      for(const c of living()){
        attackOne(c,state.target);
        if(!state.active)return;
      }
      if(!state.enemy.hp)choose(enemies()[0].index);
      enemyTurn();
    }
    function attackOne(c,target){
        choose(state.enemies[target]?.hp?target:enemies()[0].index);
        const s=getParty().combatSummary(c.id);
        for(let i=0;i<s.attacks;i++){
          if(!state.enemy.hp)choose(enemies()[0].index);
          if(hit(Combat.playerThreshold(s.hit,state.enemy.stats.ac))){const n=roll(s.damage,true);state.enemy.hp=Math.max(0,state.enemy.hp-n);log(`${c.name} → ${state.enemy.name}${state.target+1}に${n}ダメージ。`);}
          else log(`${c.name}の攻撃は外れた。`);
          if(!enemies().length){finish('victory');return;}
        }
    }
    function flee(){if(!state?.active)return;state.round++;if(rng()<.65)finish('escaped');else{log('逃げられなかった！');enemyTurn();}}
    function castSpell(name,casterId,targetId,inTurn=false){
      const p=getParty(),spell=spells.find(s=>s.name_en===name),caster=living().find(c=>c.id===casterId),key=['HALITO','DIOS','DIALKO','LATUMOFIS'].includes(name)?name.toLowerCase():null;
      if(!spell||!key)throw Error('その呪文は未実装です');
      if(!caster||!caster.magic[key])throw Error('行動可能な術者と残り回数を確認してください');
      let target;
      if(name==='HALITO'){
        if(!state?.active)throw Error('ハリトは戦闘中に使用してください');
        if(!state.enemy.hp)throw Error('行動可能な敵を選んでください');
        target=state.enemy;
      }else{
        target=p.model.members.includes(targetId)?p.character(targetId):null;
        if(!target||target.hp===0||target.status>=5)throw Error('生存している仲間を選んでください');
        if(name==='DIOS'&&target.hp===target.maxHp)throw Error('対象のHPは満タンです');
        if(name==='DIALKO'&&!(target.status>0&&target.status<4))throw Error('治療できる睡眠・恐怖・麻痺がありません');
        if(name==='LATUMOFIS'&&!target.poison)throw Error('対象は毒を受けていません');
      }
      const amount=name==='HALITO'?roll({...spell.effect.damage,bonus:0}):name==='DIOS'?roll(spell.effect.healing):0;
      caster.magic[key]--;
      let message;
      if(name==='HALITO'){target.hp=Math.max(0,target.hp-amount);message=`${caster.name}の${spell.name_ja}：${target.name}${target.index+1}に${amount}ダメージ。`;}
      else if(name==='DIOS'){const before=target.hp;target.hp=Math.min(target.maxHp,target.hp+amount);message=`${caster.name}の${spell.name_ja}：${target.name}のHPが${target.hp-before}回復。`;}
      else{if(name==='DIALKO')target.status=0;else target.poison=0;message=`${caster.name}の${spell.name_ja}：${target.name}を治療した。`;}
      if(state?.active&&inTurn){log(message);if(!enemies().length)finish('victory');}
      else if(state?.active){
        state.round++;log(message);
        if(!enemies().length)finish('victory');
        else{if(!state.enemy.hp)choose(enemies()[0].index);enemyTurn();}
      }
      return message;
    }
    function validateCommand(id,command){
      const c=living().find(c=>c.id===id);
      if(!c||!command||!['attack','guard','flee','halito','dios','dialko','latumofis'].includes(command.type))throw Error('行動可能なメンバーの指示を選んでください');
      if(['attack','halito'].includes(command.type)&&!state.enemies[command.target]?.hp)throw Error('生きている敵を選んでください');
      if(['halito','dios','dialko','latumofis'].includes(command.type)&&(!c.magic[command.type]||!spells.some(s=>s.name_en===command.type.toUpperCase())))throw Error('呪文の残り回数を確認してください');
      if(['dios','dialko','latumofis'].includes(command.type)&&!getParty().model.members.some(id=>{const a=getParty().character(id);return id===command.target&&a.hp>0&&a.status<5;}))throw Error('生存している仲間を選んでください');
      return {type:command.type,target:command.target};
    }
    function plan(id,command){if(!state?.active)throw Error('戦闘中に指示してください');state.commands[id]=validateCommand(id,command);}
    function planAll(type){if(!state?.active)return;const commands={};for(const c of living())commands[c.id]=validateCommand(c.id,{type,target:state.enemy.hp?state.target:enemies()[0].index});state.commands=commands;}
    function enemyCommand(enemy){
      const byte=()=>Math.floor(rng()*256),scaled=n=>Math.floor(rng()*n),stats=enemy.stats;
      if(rules.spell_tables){const command=Enemy.spell(state.magic,stats.monster_type,enemies().length,byte,scaled,rules.spell_tables);if(command)return command;}
      if(stats.breath_element_raw&&byte()<153)return {type:'breath'};
      const flags=stats.status_flags_raw||0;
      if(flags&64&&enemies().length<=6&&(byte()&3)!==0)return {type:'summon'};
      if(flags&32&&enemies().reduce((n,e)=>n+e.stats.level,0)<living().reduce((n,c)=>n+c.level,0)&&byte()<166)return {type:'flee'};
      return {type:'attack'};
    }
    function hurt(target,amount,source){target.hp=Math.max(0,target.hp-amount);log(`${source} → ${target.name}に${amount}ダメージ。`);if(!target.hp){target.status=5;log(`${target.name}は倒れた。`);}}
    function specialAction(entry,defending){
      const enemy=entry.actor,command=entry.command;
      if(command.type==='attack'){enemyAct(enemy,entry.target,defending);return;}
      if(command.type==='flee'){
        enemy.escaped=true;enemy.hp=0;log(`${enemy.name}${enemy.index+1}は逃げ去った。`);
        if(!enemies().length)finish(state.enemies.some(e=>!e.escaped)?'victory':'dispersed');return;
      }
      if(command.type==='summon'){log(`${enemy.name}は仲間を呼ぼうとした（増援は未実装）。`);return;}
      if(command.type==='breath'){
        const amount=Math.floor(enemy.hp/2);log(`${enemy.name}がブレスを吐いた！`);
        for(const c of survivors())hurt(c,amount,enemy.name+'のブレス');
      }else{
        const spell=spells.find(s=>s.id===command.spellId);
        if(!spell){log(`${enemy.name}の呪文データがありません。`);return;}
        log(`${enemy.name}は${spell.name_ja}を唱えた。`);
        if(['HALITO','BADIOS'].includes(spell.name_en)){
          if(entry.target.hp>0&&entry.target.status<5)hurt(entry.target,roll({...spell.effect.damage,bonus:0}),spell.name_ja);
        }else if(spell.name_en==='KATINO'){
          for(const c of survivors())if(c.status===0){
            const resistance=0,blocked=Math.floor(rng()*256)<resistance;
            if(!blocked&&Enemy.sleepThreshold(Math.min(enemy.stats.level,255),Math.min(c.level,255))<Math.floor(rng()*100)){c.status=1;log(`${c.name}は眠ってしまった。`);}
            else log(`${c.name}は眠らなかった。`);
          }
        }else log(`${spell.name_ja}の効果は未実装です。`);
      }
      if(defeated())finish('defeat');
    }
    function execute(){
      if(!state?.active)return;
      if(defeated()){finish('defeat');return;}
      const members=living(),commands=members.map(c=>({id:c.id,...validateCommand(c.id,state.commands[c.id]||{type:'attack',target:state.enemy.hp?state.target:enemies()[0].index})}));
      const defending=new Set(commands.filter(c=>c.type==='guard').map(c=>c.id));
      const schedule=commands.map((command,index)=>({side:'party',index,command,actor:getParty().character(command.id),priority:Combat.playerPriority(getParty().character(command.id).attributes[4],Math.floor(rng()*10))}));
      const targets=survivors();
      for(const enemy of enemies())schedule.push({side:'enemy',index:6+enemy.index,actor:enemy,target:targets[Math.floor(rng()*targets.length)],priority:Combat.enemyPriority(Math.floor(rng()*256)),command:enemyCommand(enemy)});
      schedule.sort((a,b)=>a.priority-b.priority||a.index-b.index);
      state.round++;state.lastOrder=schedule.map(a=>({name:a.side==='party'?a.actor.name:`${a.actor.name}${a.actor.index+1}`,priority:a.priority}));
      log(`第${state.round}ターン開始。`);
      for(const entry of schedule){
        if(!state.active)break;
        if(entry.actor.hp<=0||(entry.side==='party'&&entry.actor.status!==0))continue;
        if(entry.side==='enemy'){specialAction(entry,defending);continue;}
        const c=entry.actor,command=entry.command;
        if(command.type==='attack')attackOne(c,command.target);
        else if(command.type==='guard')log(`${c.name}は身を守っている。`);
        else if(command.type==='flee'){if(rng()<.65)finish('escaped');else log(`${c.name}は逃げられなかった！`);}
        else{
          if(command.type==='halito')choose(state.enemies[command.target]?.hp?command.target:enemies()[0].index);
          try{castSpell(command.type.toUpperCase(),c.id,command.target,true);}catch(e){log(`${c.name}：${e.message}`);}
        }
      }
      if(state.active){
        for(const c of survivors()){
          if(c.poison)hurt(c,1,'毒');
          if(c.hp>0&&c.status===1&&rng()<.25){c.status=0;log(`${c.name}は目を覚ました。`);}
        }
        if(defeated())finish('defeat');
      }
      state.commands={};
      if(state.active&&!state.enemy.hp)choose(enemies()[0].index);
    }
    return {get state(){return state;},get active(){return Boolean(state?.active);},start,choose,attack,flee,castSpell,plan,planAll,execute};
  }
  const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WizBattle=api;
})(globalThis);
