(function(root){
  'use strict';
  function spell(magic,type,count,byte,scaled,tables){
    let school=null;
    if(magic.mage&&(type===1||(byte()&3)!==0))school='mage';
    else if(magic.priest&&(type===2||(byte()&3)!==0))school='priest';
    if(!school)return null;
    let maximum=magic[school];if(scaled(count+2)===1)maximum--;
    if(!maximum){magic[school]=1;return null;}
    magic[school]=maximum;
    let level=maximum;while(byte()>=179){level--;if(!level){level=1;break;}}
    const index=level*2+(byte()<85?0:1),code=tables?.[school]?.[index];
    return code?{type:'spell',spellId:code/2-1}:null;
  }
  function sleepThreshold(caster,target){
    const difference=(target-caster)&255;
    if(target<caster){const v=(difference*5)&255;let t=v>=128?(v+50)&255:5;return v>=128&&t>=128?5:t;}
    const total=difference*5;return difference*4>255||total>255||total+50>255?200:total+50;
  }
  function contact(flags,target,random){
    const applied=[];
    // Flags and effects come from ROM. Until luck/resistance rebuild is connected,
    // use an explicit prototype 25% check for each supported additional effect.
    if(flags&2&&random()<.25){target.poison=1;applied.push('毒');}
    if(flags&4&&target.status<3&&random()<.25){target.status=3;applied.push('麻痺');}
    if(flags&1&&target.status<4&&random()<.25){target.status=4;applied.push('石化');}
    return applied;
  }
  const api={spell,sleepThreshold,contact};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WizEnemyRules=api;
})(globalThis);
