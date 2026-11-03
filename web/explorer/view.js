/* Grid exploration camera: keep the current cell's side walls in view. */
(function(root){
  'use strict';
  const FOV=1.6, BACK=.4;
  function cast(game,screen){
    const s=game.state,dx=game.dx[s.facing],dy=game.dy[s.facing];
    // Eye stays inside the current tile, behind its centre. The forward boundary
    // is .9 tiles away, leaving room to see doors on both adjacent side walls.
    const px=s.x+.5-dx*BACK,py=s.y+.5-dy*BACK;
    const rx=dx+dy*screen*FOV,ry=dy-dx*screen*FOV;
    let mx=s.x,my=s.y;
    const sx=rx>=0?1:-1,sy=ry>=0?1:-1;
    const tx=rx===0?Infinity:Math.abs(1/rx),ty=ry===0?Infinity:Math.abs(1/ry);
    let ax=rx===0?Infinity:(sx>0?mx+1-px:px-mx)*tx;
    let ay=ry===0?Infinity:(sy>0?my+1-py:py-my)*ty;
    for(let i=0;i<64;i++){
      const vertical=ax<ay,distance=vertical?ax:ay;
      if(distance>12)break;
      const direction=vertical?(sx>0?1:3):(sy>0?0:2),e=game.edge(mx,my,direction);
      if(e.raw===1||e.hidden||((e.raw===2||e.raw===3)&&!e.open)){
        const v=vertical?py+ry*distance:px+rx*distance;
        return {distance,door:e.raw>=2&&!e.hidden,vertical,u:v-Math.floor(v),direction,x:mx,y:my};
      }
      if(vertical){mx+=sx;ax+=tx;}else{my+=sy;ay+=ty;}
      if(game.cell(mx,my).dark)return {distance,dark:true};
    }
    return {distance:12,dark:true};
  }
  const api={cast,FOV};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.WizView=api;
})(globalThis);
