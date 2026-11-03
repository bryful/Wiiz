(function(root){
  'use strict';
  function pick(definition,rng=Math.random){
    const ticket=rng()*16;
    const row=definition.ranges[ticket<12?0:ticket<15?1:2];
    let base=row.base;
    for(let i=0;i<row.repeats;i++){if(Math.floor(rng()*256)>=row.threshold)break;base+=row.step;}
    return base+Math.floor(rng()*row.width);
  }
  const api={pick};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WizEncounters=api;
})(globalThis);
