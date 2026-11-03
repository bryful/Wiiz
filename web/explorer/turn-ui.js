(function(root){
  'use strict';
  const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function create(game,onChange){
    const $=id=>document.getElementById(id);
    function render(){
      const b=game.battle.state,active=game.battle.active;
      $('turn-execute').disabled=!active;
      $('turn-commands').innerHTML=!active?'':game.party.model.members.map(id=>{
        const c=game.party.character(id);
        if(!c.hp||c.status!==0)return `<div class="turn-row">${esc(c.name)} · 行動できません</div>`;
        const command=b.commands[id]||{type:'attack',target:b.target};
        const options=[['attack','攻撃',true],['guard','防御',true],['flee','逃走',true],...Object.entries({halito:'ハリト',dios:'ディオス',dialko:'ディアルコ',latumofis:'ラツモフィス'}).map(([key,name])=>[key,`${name}（残り${c.magic[key]}回）`,c.magic[key]>0])];
        const targets=['dios','dialko','latumofis'].includes(command.type)?game.party.model.members.map(id=>game.party.character(id)).filter(c=>c.hp>0&&c.status<5).map(c=>[c.id,`${c.name} HP ${c.hp}/${c.maxHp}`]):b.enemies.filter(e=>e.hp>0).map(e=>[e.index,`${e.index+1}. ${e.name} HP ${e.hp}/${e.maxHp}`]);
        return `<div class="turn-row"><strong>${esc(c.name)}</strong><label>行動<select aria-label="${esc(c.name)}の行動" data-member="${id}" data-field="action">${options.map(([value,label,enabled])=>`<option value="${value}" ${command.type===value?'selected':''} ${enabled?'':'disabled'}>${label}</option>`).join('')}</select></label><label ${['guard','flee'].includes(command.type)?'hidden':''}>対象<select aria-label="${esc(c.name)}の対象" data-member="${id}" data-field="target">${targets.map(([value,label])=>`<option value="${value}" ${command.target===value?'selected':''}>${esc(label)}</option>`).join('')}</select></label></div>`;
      }).join('');
      $('battle-order').textContent=b?.lastOrder.length?`前ターンの予定順（倒れた者は行動しません）：${b.lastOrder.map(a=>`${a.name}［${a.priority}］`).join(' → ')}`:'';
    }
    $('turn-commands').addEventListener('change',e=>{
      const select=e.target.closest('select[data-member]');if(!select)return;
      try{
        const b=game.battle.state,id=Number(select.dataset.member),old=b.commands[id]||{type:'attack',target:b.target};
        let command;
        if(select.dataset.field==='target')command={...old,target:Number(select.value)};
        else{const type=select.value;command={type,target:['dios','dialko','latumofis'].includes(type)?id:b.enemies.find(e=>e.hp>0)?.index};}
        game.battle.plan(id,command);$('turn-message').textContent='指示を更新しました。「ターン実行」で進めます。';onChange();
      }catch(e){$('turn-message').textContent=e.message;}
    });
    return {render};
  }
  root.WizTurnUI={create};
})(globalThis);
