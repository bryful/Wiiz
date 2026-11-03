#pragma once
#include "session.hpp"
#include <SDL3/SDL.h>
#include <cctype>
#include <string>
#include <vector>
// Reuse the already-verified CHR font lookup used for roster names. No font asset is shipped.
inline void wizText(SDL_Renderer* r,const Session* game,float x,float y,std::string text,float scale=3.f) {
    SDL_SetRenderDrawColor(r,240,240,240,255);
    std::vector<SDL_FRect> dots;dots.reserve(text.size()*32);
    for(char c:text){
        c=char(std::toupper(static_cast<unsigned char>(c)));
        if(c==' '){x+=8*scale;continue;}
        if(game&&std::isalnum(static_cast<unsigned char>(c))){
            const auto glyph=game->fontGlyph(c);
            for(int py=0;py<8;++py)for(int px=0;px<8;++px)if(glyph[py*8+px])dots.push_back({x+px*scale,y+py*scale,scale,scale});
        }else{
            SDL_SetRenderScale(r,scale,scale);char s[]={c,0};SDL_RenderDebugText(r,x/scale,y/scale,s);SDL_SetRenderScale(r,1,1);
        }
        x+=8*scale;
    }
    if(!dots.empty())SDL_RenderFillRects(r,dots.data(),int(dots.size()));
}
inline void wizFrame(SDL_Renderer* r,SDL_FRect box,float line=4){
    SDL_SetRenderDrawColor(r,0,0,0,255);SDL_RenderFillRect(r,&box);
    SDL_SetRenderDrawColor(r,240,240,240,255);
    const SDL_FRect edges[]={{box.x,box.y,box.w,line},{box.x,box.y+box.h-line,box.w,line},{box.x,box.y,line,box.h},{box.x+box.w-line,box.y,line,box.h}};
    SDL_RenderFillRects(r,edges,4);
}
