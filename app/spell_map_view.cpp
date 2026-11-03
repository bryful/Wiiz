#include "spell_map_view.hpp"
#include "session.hpp"
#include "ui_text.hpp"
#include <SDL3/SDL.h>
#include <algorithm>
#include <string>
namespace {
void color(SDL_Renderer* r,int red,int green,int blue){SDL_SetRenderDrawColor(r,Uint8(red),Uint8(green),Uint8(blue),255);}
void stroke(SDL_Renderer* r,float x1,float y1,float x2,float y2,float width=4){
    SDL_FRect line{std::min(x1,x2)-width/2,std::min(y1,y2)-width/2,std::abs(x2-x1)+width,std::abs(y2-y1)+width};SDL_RenderFillRect(r,&line);
}
void edge(SDL_Renderer* r,float x1,float y1,float x2,float y2,unsigned value){
    if(!value)return;color(r,240,240,240);
    if(value!=2){stroke(r,x1,y1,x2,y2);return;}
    const float dx=x2-x1,dy=y2-y1;
    stroke(r,x1,y1,x1+dx*.3f,y1+dy*.3f);stroke(r,x1+dx*.7f,y1+dy*.7f,x2,y2);
    stroke(r,x1+dx*.4f,y1+dy*.4f,x1+dx*.6f,y1+dy*.6f,6);
}
}
void drawSpellMap(SDL_Renderer* r,const Session& game){
    const auto& m=game.spellMap();if(!m.mode)return;
    constexpr float left=80,top=120,cell=32;
    wizFrame(r,{28,54,968,772});
    wizText(r,&game,68,76,m.mode==3?"MAP":m.mode==1?"DUMAPIC":"MALOR",4);
    const int floor=m.mode!=2?m.floor:m.targetFloor;
    wizText(r,&game,778,128,"FLOOR",3);
    if(floor==0)wizText(r,&game,120,400,"RETURN TO CASTLE",3);
    for(int y=0;floor>0&&y<20;++y)for(int x=0;x<20;++x){
        const auto& terrain=game.dungeon().floors.at(size_t(floor-1));
        const float px=left+x*cell,py=top+(19-y)*cell;
        const bool visited=game.explored(floor,x,y);
        color(r,visited?0:96,visited?0:96,visited?0:96);
        SDL_FRect square{px+2,py+2,cell-4,cell-4};SDL_RenderFillRect(r,&square);
        // Preserve existing exploration/secret/darkness rules and ROM-derived geometry.
        if(!visited||(terrain.flags[y*20+x]&0x40))continue;
        const unsigned walls=terrain.walls[y*20+x];
        edge(r,px,py,px+cell,py,walls&3);
        edge(r,px+cell,py,px+cell,py+cell,(walls>>2)&3);
        edge(r,px,py+cell,px+cell,py+cell,(walls>>4)&3);
        edge(r,px,py,px,py+cell,(walls>>6)&3);
    }
    color(r,240,240,240);
    stroke(r,left,top,left+640,top);stroke(r,left,top+640,left+640,top+640);
    stroke(r,left,top,left,top+640);stroke(r,left+640,top,left+640,top+640);
    for(int n=0;n<20;++n){wizText(r,&game,left+n*cell+1,top+646,std::to_string(n),2);wizText(r,&game,left-40,top+(19-n)*cell+8,std::to_string(n),2);}
    for(int f=0;f<=int(game.dungeon().floors.size());++f){
        const float y=184.f+f*46;
        if(f==floor)wizText(r,&game,748,y,">",3);
        wizText(r,&game,786,y,f==0?"OUT":"B"+std::to_string(f),3);
    }
    if(floor==m.floor){
        const float cx=left+m.x*cell+cell/2,cy=top+(19-m.y)*cell+cell/2;
        const int dx[]={0,1,0,-1},dy[]={-1,0,1,0};const int h=m.heading;
        color(r,255,70,70);
        stroke(r,cx-dx[h]*8,cy-dy[h]*8,cx+dx[h]*8,cy+dy[h]*8);
        const float tipX=cx+dx[h]*10,tipY=cy+dy[h]*10;
        SDL_Vertex triangle[3]={{{tipX,tipY},{1,.27f,.27f,1},{0,0}},{{cx-dy[h]*8,cy+dx[h]*8},{1,.27f,.27f,1},{0,0}},{{cx+dy[h]*8,cy-dx[h]*8},{1,.27f,.27f,1},{0,0}}};
        SDL_RenderGeometry(r,nullptr,triangle,3,nullptr,0);
    }
    if(m.mode==2){
        if(floor>0){color(r,255,225,95);const float x=left+m.targetX*cell+5,y=top+(19-m.targetY)*cell+5;
            stroke(r,x,y,x+22,y);stroke(r,x,y+22,x+22,y+22);stroke(r,x,y,x,y+22);stroke(r,x+22,y,x+22,y+22);}
        wizText(r,&game,80,798,"ARROWS:MOVE  SELECT/START:FLOOR  A:WARP B:BACK",2);
    }else wizText(r,&game,80,798,"A / B : CLOSE",2);
}
