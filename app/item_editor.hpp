#pragma once
#include "ui_text.hpp"
#include <algorithm>
#include <stdexcept>

// Interaction model adapted from GBWiz/src/item_menu.h (MIT, bryful 2026).
// NES data, save and native recalculation remain in Session/binjnes.
class ItemEditor {
    std::vector<Session::InventoryMember> members_;
    unsigned character_[2]{0,1},row_[2]{0,0},focus_=0,action_=0;
    bool submenu_=false,deleting_=false,yes_=false;
    std::string notice_;
    static bool movable(Session::InventoryItem item){return !(item.flags&192);}
    void cycle(int delta) {
        if(members_.size()<2)return;
        unsigned next=character_[focus_];
        do {next=unsigned((int(next)+int(members_.size())+delta)%int(members_.size()));}while(members_.size()>1&&next==character_[1-focus_]);
        // Two-member parties can swap the two displayed sides.
        if(members_.size()==2)std::swap(character_[0],character_[1]);else character_[focus_]=next;
        row_[focus_]=0;submenu_=deleting_=false;
    }
    void change(Session& game,unsigned operation) {
        auto next=members_;auto& source=next[character_[focus_]];
        unsigned row=row_[focus_],other=character_[1-focus_];
        auto transfer=[&](Session::InventoryMember& from,unsigned at,Session::InventoryMember& to){
            if(to.items.size()>=8)return false;
            to.items.push_back(from.items.at(at));from.items.erase(from.items.begin()+at);return true;
        };
        if(operation==5) {
            for(unsigned m=0;m<next.size()&&source.items.size()<8;++m)if(m!=character_[focus_])
                for(unsigned i=0;i<next[m].items.size()&&source.items.size()<8;)
                    if((next[m].items[i].flags&32)&&movable(next[m].items[i]))transfer(next[m],i,source);else ++i;
        } else if(operation==6) {
            if(next.size()<2)throw std::runtime_error("No recipient.");
            for(unsigned i=0;i<source.items.size()&&next[other].items.size()<8;)
                if(movable(source.items[i]))transfer(source,i,next[other]);else ++i;
        } else {
            if(row>=source.items.size())throw std::runtime_error("Empty slot.");
            if(operation==0)game.equipItem(source,row);
            if(operation==1||operation==2){
                if(!movable(source.items[row]))throw std::runtime_error("Equipped/cursed items cannot be moved or deleted.");
                if(operation==1){if(next.size()<2)throw std::runtime_error("No recipient.");if(!transfer(source,row,next[other]))throw std::runtime_error("Recipient inventory is full.");}
                else source.items.erase(source.items.begin()+row);
            }
            if(operation==3||operation==4){
                int destination=int(row)+(operation==3?-1:1);
                if(destination<0||destination>=int(source.items.size()))return;
                std::swap(source.items[row],source.items[unsigned(destination)]);
            }
        }
        game.updateItems(members_,next);members_=std::move(next);
        if(operation==3&&row)row_[focus_]--;
        if(operation==4&&row+1<members_[character_[focus_]].items.size())row_[focus_]++;
        notice_="Saved.";
    }
    static void bitmap(SDL_Renderer* r,const uint8_t* data,unsigned width,float x,float y,float scale) {
        SDL_SetRenderDrawColor(r,240,240,240,255);std::vector<SDL_FRect> dots;
        for(unsigned py=0;py<8;++py)for(unsigned px=0;px<width;++px)if(data[py*width+px])dots.push_back({x+px*scale,y+py*scale,scale,scale});
        if(!dots.empty())SDL_RenderFillRects(r,dots.data(),int(dots.size()));
    }
public:
    void open(Session& game) {
        members_=game.openItems();character_[0]=0;character_[1]=members_.size()>1?1:0;
        row_[0]=row_[1]=focus_=action_=0;submenu_=deleting_=yes_=false;notice_.clear();
    }
    bool key(Session& game,SDL_Keycode key) {
        notice_.clear();
        if(deleting_) {
            if(key==SDLK_Z){deleting_=false;return true;}
            if(key==SDLK_LEFT||key==SDLK_RIGHT)yes_=!yes_;
            if(key==SDLK_X){if(yes_)change(game,2);deleting_=submenu_=false;}
            return true;
        }
        if(submenu_) {
            if(key==SDLK_Z){submenu_=false;return true;}
            if(key==SDLK_UP)action_=(action_+4)%5;
            if(key==SDLK_DOWN)action_=(action_+1)%5;
            if(key==SDLK_X){if(action_==2){deleting_=true;yes_=false;}else{change(game,action_);submenu_=false;}}
            return true;
        }
        if(key==SDLK_Z||key==SDLK_I)return false;
        if(key==SDLK_LEFT)focus_=0;
        if(key==SDLK_RIGHT&&members_.size()>1)focus_=1;
        if(key==SDLK_A||key==SDLK_B||key==SDLK_L)cycle(-1);
        if(key==SDLK_S||key==SDLK_N||key==SDLK_R)cycle(1);
        if(key==SDLK_UP)row_[focus_]=(row_[focus_]+9)%10;
        if(key==SDLK_DOWN)row_[focus_]=(row_[focus_]+1)%10;
        if(key==SDLK_X){if(row_[focus_]<8){if(row_[focus_]<members_[character_[focus_]].items.size()){submenu_=true;action_=0;}}else change(game,row_[focus_]==8?5:6);}
        return true;
    }
    void click(Session& game,float x,float y) {
        if(deleting_){if(y>=370&&y<450){yes_=x>=512;key(game,SDLK_X);}return;}
        if(submenu_){if(x>=270&&x<754&&y>=234&&y<534){action_=unsigned((y-234)/60);key(game,SDLK_X);}return;}
        if(x<40||x>=984)return;
        focus_=x<512?0:1;if(focus_==1&&members_.size()==1){focus_=0;return;}
        float local=x-(focus_?520.f:40.f);
        if(y>=140&&y<208){cycle(local<232?-1:1);return;}
        if(y>=226&&y<626){row_[focus_]=unsigned((y-226)/50);key(game,SDLK_X);}
        if(y>=640&&y<688){row_[focus_]=8;key(game,SDLK_X);}
        if(y>=696&&y<744){row_[focus_]=9;key(game,SDLK_X);}
    }
    void draw(SDL_Renderer* r,const Session& game) const {
        wizFrame(r,{28,54,968,744});wizText(r,&game,68,82,"PARTY ITEMS",4);
        for(unsigned side=0;side<2;++side) {
            float x=40.f+side*480;bool empty=side==1&&members_.size()<2;
            wizFrame(r,{x,136,464,608},side==focus_?4.f:2.f);
            if(empty){wizText(r,&game,x+24,164,"NO RECIPIENT",3);continue;}
            const auto& m=members_[character_[side]];auto name=game.rosterNamePixels(m.slot);
            wizText(r,&game,x+16,164,"<",3);bitmap(r,name.data(),64,x+72,160,4);wizText(r,&game,x+422,164,">",3);
            for(unsigned row=0;row<8;++row) {
                float y=238.f+row*50;
                wizText(r,&game,x+10,y,side==focus_&&row_[side]==row?">":" ",3);
                if(row>=m.items.size()){wizText(r,&game,x+48,y,"--",3);continue;}
                auto item=m.items[row];auto codes=game.itemNameCodes(item);if(codes.size()>16)codes.resize(16);
                auto pixels=game.textPixels(codes);
                wizText(r,&game,x+34,y,item.flags&128?"*":item.flags&64?"!":" ",2);
                if(!pixels.empty())bitmap(r,pixels.data(),unsigned(codes.size()*8),x+56,y,3);
            }
            wizText(r,&game,x+10,650,side==focus_&&row_[side]==8?">":" ",2);
            wizText(r,&game,x+36,650,"COLLECT UNIDENTIFIED",2);
            wizText(r,&game,x+10,706,side==focus_&&row_[side]==9?">":" ",2);
            wizText(r,&game,x+36,706,"SEND UNEQUIPPED",2);
        }
        wizText(r,&game,60,762,"SEL/STA:CHAR  A:ACTION  B:BACK",3);
        if(submenu_&&!deleting_){
            wizFrame(r,{270,218,484,326});
            const char* labels[]={"EQUIP / REMOVE","GIVE TO OTHER","DELETE","MOVE UP","MOVE DOWN"};
            for(unsigned i=0;i<5;++i)wizText(r,&game,294,248.f+float(i)*60,(action_==i?"> ":"  ")+std::string(labels[i]),3);
        }
        if(deleting_){wizFrame(r,{242,282,540,192});wizText(r,&game,280,318,"DELETE THIS ITEM?",3);wizText(r,&game,298,394,yes_?"  NO    > YES":"> NO      YES",3);}
        const auto& selected=members_[character_[focus_]].items;
        if(row_[focus_]<selected.size()) {
            auto codes=game.itemNameCodes(selected[row_[focus_]]);
            auto pixels=game.textPixels(codes);
            if(!pixels.empty())bitmap(r,pixels.data(),unsigned(codes.size()*8),60,806,2);
        } else if(!notice_.empty())wizText(r,&game,60,806,notice_,2);
    }
};
