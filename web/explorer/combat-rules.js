(function(root){
  'use strict';
  const signed=n=>((n&255)>=128?(n&255)-256:n&255);
  function baseStats(classId,level,strength){
    level=Math.min(level,255);
    const hit=[0,2,5,6,7].includes(classId)?Math.floor(level/3)+2:Math.floor(level/5);
    const bonus=strength>=16?strength-15:strength<6?strength-6:0;
    return {hit:signed(hit+bonus),attacks:[0,5,6,7].includes(classId)?Math.min(10,Math.floor(level/5)+(classId===7?2:1)):1,damageBonus:Math.max(0,strength-15)};
  }
  function playerThreshold(hit,ac,group=1){return Math.min(19,Math.max(0,signed(19+group-ac-hit)))+1;}
  function enemyThreshold(level,attackerAC,referencedAC,parry=false){
    const a=(19+(parry?2:0)-referencedAC-level)&255,b=(a-attackerAC)&255;
    return (b>=128?(b>=220||a>=128?0:19):Math.min(b,19))+1;
  }
  function playerPriority(agility,roll){const a=Math.min(18,Math.max(0,agility)),bonus=a>=15?14-a:a>=8?0:a>=6?1:a>=4?2:3;return Math.max(0,Math.min(9,roll+bonus))+1;}
  function enemyPriority(roll){return (roll&7)+2;}
  const api={signed,baseStats,playerThreshold,enemyThreshold,playerPriority,enemyPriority};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WizCombatRules=api;
})(globalThis);
