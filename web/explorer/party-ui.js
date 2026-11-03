(function(root){
  'use strict';
  const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function create(game,onChange){
    const $=id=>document.getElementById(id);let selected=game.party.model.members[0];
    const atBase=()=>!game.battle.active&&(game.state.phase==='outside'||(game.state.floor===1&&game.state.x===0&&game.state.y===0));
    function operation(fn,feedback='party-message'){
      const notify=message=>{$('party-message').textContent=message;$(feedback).textContent=message;};
      try{const message=fn();notify(message||'更新しました。');onChange();}catch(e){notify(e.message);}
    }
    function render(){
      const p=game.party,m=p.model,base=atBase();
      if(!m.roster.some(c=>c.id===selected)||(!base&&!m.members.includes(selected)))selected=m.members[0]??(base?m.roster[0]?.id:undefined);
      $('party-count').textContent=`${m.members.length} / 6 人`;
      $('party-list').innerHTML=m.members.length?m.members.map((id,index)=>{const c=p.character(id),s=p.summary(id);return `<div class="member ${id===selected?'selected':''}"><button data-action="select" data-id="${id}" class="member-name">${index+1}. ${esc(c.name)} <small>${WizParty.CLASSES[c.classId]}</small></button><span>HP ${c.hp}/${c.maxHp} · AC ${s.ac}${c.status?` · ${["正常","睡眠","恐怖","麻痺","石化","死亡","灰","喪失"][c.status]}`:""}${c.poison?" · 毒":""}</span><div class="member-actions"><button data-action="up" data-id="${id}" ${index===0?'disabled':''} aria-label="${esc(c.name)}を前へ">↑</button><button data-action="down" data-id="${id}" ${index===m.members.length-1?'disabled':''} aria-label="${esc(c.name)}を後ろへ">↓</button><button data-action="leave" data-id="${id}" ${!base?'disabled':''}>待機</button></div></div>`;}).join(''):'<p>メンバーがいません。入口で登録キャラクターを参加させてください。</p>';
      $('base-only').hidden=!base;
      $('party-base').hidden=base||game.battle.active;
      $('base-hint').textContent=base?'入口・地上でキャラクターの作成と編成ができます。':'作成・参加・待機は入口か地上で行えます。並び順と装備は変更できます。';
      $('roster-list').innerHTML=m.roster.filter(c=>!m.members.includes(c.id)).map(c=>`<div class="roster-row"><button data-action="select" data-id="${c.id}">${esc(c.name)} · ${WizParty.CLASSES[c.classId]}</button><button data-action="join" data-id="${c.id}" ${m.members.length>=6?'disabled':''}>参加</button></div>`).join('')||'<p>待機中のキャラクターはいません。</p>';
      const c=m.roster.find(c=>c.id===selected);$('character-panel').hidden=!c;if(!c)return;
      const s=p.summary(c.id),combat=p.combatSummary(c.id),status=['正常','睡眠','恐怖','麻痺','石化','死亡','灰','喪失'][c.status];
      $('character-title').textContent=c.name;
      $('character-info').textContent=`${WizParty.RACES[c.raceId]} / ${WizParty.ALIGNMENTS[c.alignment]} / ${WizParty.CLASSES[c.classId]} Lv.${c.level} · ${status}${c.poison?'・毒':''}`;
      $('character-stats').innerHTML=`<span>HP <b>${c.hp} / ${c.maxHp}</b></span><span>暫定AC <b>${s.ac}</b></span><span>装備命中補正 <b>${s.strength}</b></span><span>通常攻撃 <b>${combat.attacks}回 / ${combat.damage.count}d${combat.damage.sides}${combat.damage.bonus?'+'+combat.damage.bonus:''}</b></span><span>経験値 <b>${c.experience}</b></span><span>所持金 <b>${c.gold} G</b></span>`;
      $('attributes').textContent=['力','知恵','信仰心','生命力','素早さ','運'].map((n,i)=>`${n} ${c.attributes[i]}`).join('　');
      $('character-combat').textContent=`通常攻撃：命中力 ${combat.hit} · ${combat.attacks}回 · ${combat.damage.count}d${combat.damage.sides}${combat.damage.bonus?'+'+combat.damage.bonus:''}`;
      $('inventory-count').textContent=`${c.inventory.length} / 8 個`;
      const recipients=m.members.filter(id=>id!==c.id);
      const old=$('transfer-to').value;
      $('transfer-to').innerHTML=recipients.map(id=>`<option value="${id}">${esc(p.character(id).name)}</option>`).join('');
      $('transfer-to').value=recipients.includes(Number(old))?old:String(recipients[0]??'');
      $('inventory').innerHTML=c.inventory.map((entry,slot)=>{const i=p.item(entry.itemId),s=i.stats,can=p.canEquip(c,i);return `<div class="inventory-row"><div><strong>${esc(i.name_ja)}</strong><small>${entry.equipped?'装備中 · ':''}${s.cursed_raw?'呪いあり · ':''}${s.ac_modifier?'AC '+s.ac_modifier+' · ':''}${s.damage.count&&s.damage.sides?s.damage.count+'d'+s.damage.sides+(s.damage.bonus?'+'+s.damage.bonus:''):''}</small></div><button data-action="equip" data-slot="${slot}" ${!entry.equipped&&!can?'disabled':''}>${entry.equipped?'外す':can?'装備':'装備不可'}</button><button data-action="transfer" data-slot="${slot}" ${entry.equipped||!recipients.length?'disabled':''}>渡す</button></div>`;}).join('')||'<p>所持品はありません。</p>';
    }
    function handle(e){const b=e.target.closest('button[data-action]');if(!b||b.disabled)return;const action=b.dataset.action,id=Number(b.dataset.id),slot=Number(b.dataset.slot);
      operation(()=>{const p=game.party;
        if(game.battle.active)throw Error('戦闘を終えてからキャラクターを操作してください');
        if(action==='select'){selected=id;return 'キャラクターを選択しました。';}
        if(['join','leave'].includes(action)&&!atBase())throw Error('入口か地上で編成してください');
        if(action==='join'){p.join(id);selected=id;return 'パーティに参加しました。';}
        if(action==='leave'){p.leave(id);return '登録名簿で待機します。';}
        if(action==='up'||action==='down'){p.reorder(id,action==='up'?-1:1);return '並び順を変えました。';}
        if(action==='equip'){p.equip(selected,slot);return '装備を変更しました。';}
        if(action==='transfer'){p.transfer(selected,slot,Number($('transfer-to').value));return 'アイテムを渡しました。';}
      });
    }
    for(const id of ['party-list','roster-list','inventory'])$(id).addEventListener('click',handle);
    $('party-base').addEventListener('click',()=>operation(()=>{if(game.battle.active)throw Error('戦闘を終えてから入口へ戻ってください');game.entrance();return '入口へ戻りました。キャラクターの作成・参加・待機ができます。';}));
    $('create-character').addEventListener('submit',e=>{e.preventDefault();operation(()=>{
      if(!atBase())throw Error('入口か地上で作成してください');
      selected=game.party.addCharacter({name:$('new-name').value,classId:Number($('new-class').value),raceId:Number($('new-race').value),alignment:Number($('new-alignment').value)});
      const name=game.party.character(selected).name;
      $('new-name').value='';
      try{game.party.join(selected);return `${name}を登録し、パーティに参加しました。記録を保存すると次回も使えます。`;}
      catch(e){return `${name}を名簿に登録しました。現在は待機中です：${e.message}。編成後に「参加」を押してください。`;}
    },'create-message');});
    return {render};
  }
  root.WizPartyUI={create};
})(globalThis);
