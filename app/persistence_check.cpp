// Integration checks against the adopted core, operating only in an explicit test folder.
#include "session.hpp"
#include "save_json.hpp"
#include "json.hpp"
#include "picosha2.h"
#include "item_editor.hpp"
#include <fstream>
#include <memory>
#include <stdexcept>
#include <cstdio>
#include <cstring>
#include <sstream>
#include <SDL3/SDL.h>
namespace fs=std::filesystem;
using Json=nlohmann::ordered_json;
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
int laterSpellMapPrepare(const char* romPath,const char* folderPath);
int spellMapPrepare(const char* romPath,const char* folderPath) {
    if(identifyRom(pathFromUtf8(romPath)).identity.scenario>1)return laterSpellMapPrepare(romPath,folderPath);
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);Session session(entry,folder/"saves",SaveFormat::Json);session.stateFolder(folder/"states");
    std::ifstream replay("tests/replays/wiz1-dungeon.txt");require(bool(replay),"Missing map replay");
    struct Event{int frame;unsigned key;bool down;};std::vector<Event> events;std::string line;
    while(std::getline(replay,line)){int frame;std::string key,action;std::istringstream row(line);if(!(row>>frame>>key>>action))continue;unsigned b=key=="X"?PAD_A:key=="Z"?PAD_B:key=="Down"?PAD_DOWN:0;events.push_back({frame,b,action=="down"});}
    unsigned held=0;
    for(int frame=0;frame<4300;++frame){
        if(frame==900){std::vector<uint8_t> ram(8192);wiiz_core_sram_read(session.core(),ram.data(),ram.size());auto doc=Json::parse(encodeBattery(ram,1,entry.sha));auto& c=doc["characters"][0];c["class"]=1;c["level"]=13;
            for(int n=0x29;n<0x30;++n){char k[4];std::snprintf(k,sizeof(k),"%02X",n);c["unmapped_bytes"][k]=9;}
            for(int n=0x37;n<0x3e;++n){char k[4];std::snprintf(k,sizeof(k),"%02X",n);c["unmapped_bytes"][k]=9;}
            for(int n=0x45;n<0x4c;++n){char k[4];std::snprintf(k,sizeof(k),"%02X",n);c["unmapped_bytes"][k]=255;}
            ram=decodeBattery(doc.dump(),1,entry.sha);wiiz_core_sram_write(session.core(),ram.data(),ram.size());}
        for(const auto& e:events)if(e.frame==frame){if(e.down)held|=e.key;else held&=~e.key;}session.input(held);session.frame();
    }
    session.saveState(1);
    auto press=[&](unsigned b){session.input(b);for(int f=0;f<3;++f)session.frame();session.input(0);for(int f=0;f<100;++f)session.frame();};
    press(PAD_B);press(PAD_A);press(PAD_A);session.saveState(2);press(PAD_A);session.saveState(3);
    press(PAD_A);press(PAD_A);
    require(session.spellMap().mode==1,"Actual DUMAPIC did not open the map");
    require(session.explored(1,0,0)&&!session.explored(1,1,1),"Unexplored map was disclosed");
    session.saveState(4);
    std::vector<uint8_t> ram(8192);wiiz_core_sram_read(session.core(),ram.data(),ram.size());
    require(ram[0x29]==8,"DUMAPIC did not consume exactly one original MP");
    session.mapKey(PAD_A);for(unsigned t=0;t<100;++t)session.tick(0,4,t*17);
    require(session.spellMap().mode==0,"DUMAPIC did not close");
    session.loadState(3);
    for(int level=0;level<6;++level)press(PAD_DOWN);
    press(PAD_A);press(PAD_A);require(session.spellMap().mode==2,"Actual MALOR did not open the map");session.saveState(5);
    for(unsigned speed:{1u,4u,8u}) {
        session.loadState(5);session.mapKey(PAD_B);for(unsigned t=0;t<100;++t)session.tick(0,speed,t*17);
        wiiz_core_sram_read(session.core(),ram.data(),ram.size());require(ram[0x2f]==9,"Cancel consumed MALOR MP");
        require((wiiz_core_map_position(session.core())&0xffffff)==0x010000,"Cancel moved the party");
        session.loadState(5);session.mapKey(PAD_START);require(session.spellMap().targetFloor==2,"MALOR floor selection failed");session.mapKey(PAD_SELECT);
        session.mapKey(PAD_UP);session.mapKey(PAD_A);for(unsigned t=0;t<100;++t)session.tick(0,speed,t*17);
        require((wiiz_core_map_position(session.core())&0xffffff)==0x010100,"Original MALOR did not teleport to selected tile");
        wiiz_core_sram_read(session.core(),ram.data(),ram.size());require(ram[0x2f]==8,"MALOR did not consume exactly one original MP");
        require(session.explored(1,0,1)&&!session.explored(1,1,1),"Explored-map update failed");
    }
    session.save();Session reopened(entry,folder/"saves",SaveFormat::Json);require(reopened.explored(1,0,1)&&!reopened.explored(1,1,1),"Exploration JSON roundtrip failed");
    session.loadState(5);session.mapKey(PAD_SELECT);require(session.spellMap().targetFloor==0,"Surface destination is missing");
    session.mapKey(PAD_A);for(unsigned t=0;t<100;++t)session.tick(0,4,t*17);
    require((wiiz_core_map_position(session.core())&0xffffff)==0,"Original MALOR did not return to surface");
    session.loadState(4);require(session.spellMap().mode==1&&!session.explored(1,0,1),"Map-dialog state/visited-map restoration failed");
    std::printf("SPELL_MAP_OK actual_spells=2 mp=original cancel=no_cost target=B1_E0_N1 speeds=1,4,8 explored_only=1 json_and_state=OK\n");return 0;
}
int persistenceCheck(const char* romPath,const char* folderPath) {
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);
    fs::create_directories(folder);
    const int scenario=entry.title=="Wizardry FC I"?1:entry.title=="Wizardry FC II"?2:3;
    // Lossless canonical data round-trip, plus an actual edit with no supplied checksum.
    auto session=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);
    for(int f=0;f<900;++f){session->input(f>=400&&f<402?PAD_A:0);session->frame();}
    session->save();
    std::vector<uint8_t> before(8192),after(8192);require(wiiz_core_sram_read(session->core(),before.data(),before.size()),"Cannot inspect battery RAM");
    const auto canonical=decodeBattery(encodeBattery(before,scenario,entry.sha),scenario,entry.sha);
    const auto legacyFolder=folder/"legacy";fs::create_directories(legacyFolder);
    const auto legacyPath=legacyFolder/(entry.sha+".sav");
    {std::ofstream out(legacyPath,std::ios::binary|std::ios::trunc);out.write(reinterpret_cast<const char*>(before.data()),before.size());}
    {
        auto migrated=std::make_unique<Session>(entry,legacyFolder,SaveFormat::Json);
        require(wiiz_core_sram_read(migrated->core(),after.data(),after.size())&&canonical==after,"Legacy SRAM reconstruction differed from JSON");
        migrated->save();require(fs::exists(legacyFolder/(utf8(entry.path.stem())+".json")),"Legacy save did not migrate to JSON");
        std::ifstream in(legacyPath,std::ios::binary);std::vector<uint8_t> kept(std::istreambuf_iterator<char>(in),{});
        require(kept==before,"Migration modified the original .sav");
    }
    auto document=Json::parse(encodeBattery(before,scenario,entry.sha));
    require(encodeBattery(canonical,scenario,entry.sha)==document.dump(2)+"\n","Character payload was lost on JSON round-trip");
    document["characters"][0]["level"]=17;
    const auto edited=decodeBattery(document.dump(),scenario,entry.sha);
    const size_t level=scenario==1?35:1024+33;
    require(edited[level]==0&&edited[level+1]==17,"Named JSON field did not edit character RAM");
    {std::ofstream out(folder/"saves"/(utf8(entry.path.stem())+".json"),std::ios::binary|std::ios::trunc);out<<document.dump(2);}
    {
        auto editedSession=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);
        for(int f=0;f<900;++f){editedSession->input(f>=400&&f<402?PAD_A:0);editedSession->frame();}
        require(wiiz_core_sram_read(editedSession->core(),after.data(),after.size())&&after[level]==0&&after[level+1]==17,"Original ROM rejected the checksum-free JSON edit");
        for(size_t i=0;i<20;++i){const size_t offset=scenario==1?i*256:1024+i*96;require(after[offset]==edited[offset],"JSON restart erased character registration");}
    }
    // Save all five slots with different actual game frames; overwrite and reload.
    for(unsigned slot=1;slot<=5;++slot) {
        session->tick(0,4,10000+slot*17);
        session->saveState(slot);require(session->hasState(slot),"Slot was not saved");
    }
    session->saveState(3);
    const auto captured=session->pixels;
    const auto stateFile=folder/"states"/(entry.path.stem().native()+fs::path(".stot3.state").native());
    std::vector<std::array<uint32_t,256*240>> expectedPixels;
    std::vector<std::vector<float>> expectedAudio;
    for(int t=0;t<180;++t) {
        session->tick(t>=40&&t<100?PAD_DOWN:0,4,30000+t*17);
        expectedPixels.push_back(session->pixels);size_t count;const auto* sound=session->audio(&count);
        expectedAudio.emplace_back(sound,sound+count);
    }
    session->loadState(3);require(session->pixels==captured,"Loaded screen did not match captured screen");
    // A separate fresh process-equivalent core must replay identically, including the 1x music core.
    auto restored=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);restored->loadState(3);
    size_t comparedSamples=0;
    for(int t=0;t<180;++t) {
        const unsigned held=t>=40&&t<100?PAD_DOWN:0;
        session->tick(held,4,30000+t*17);restored->tick(held,4,30000+t*17);
        require(session->pixels==restored->pixels,"Restored game diverged from captured game");
        require(session->pixels==expectedPixels[t],"Restored game differs from uninterrupted execution");
        size_t a,b;const auto* x=session->audio(&a);const auto* y=restored->audio(&b);
        require(a==b&&!std::memcmp(x,y,a*sizeof(float)),"Restored audio/resampler diverged");comparedSamples+=a;
        require(a==expectedAudio[t].size()&&!std::memcmp(x,expectedAudio[t].data(),a*sizeof(float)),"Restored audio differs from uninterrupted execution");
    }
    require(wiiz_core_sram_read(session->core(),before.data(),before.size())&&wiiz_core_sram_read(restored->core(),after.data(),after.size())&&before==after,"Restored SRAM diverged");
    // Damage rejection must leave the live game untouched.
    session->saveState(5);
    const auto intact=session->pixels;
    const auto bad=folder/"states"/(entry.path.stem().native()+fs::path(".stot5.state").native());
    {std::ifstream in(bad);in>>document;}document["game"]["bytes"].get_ref<std::string&>()[100]='x';
    {std::ofstream out(bad,std::ios::binary|std::ios::trunc);out<<document.dump();}
    bool rejected=false;try{session->loadState(5);}catch(const std::exception&){rejected=true;}
    require(rejected&&session->pixels==intact,"Damaged state changed the live session");
    document["rom_sha256"]="wrong-ROM";{std::ofstream out(bad,std::ios::binary|std::ios::trunc);out<<document.dump();}
    rejected=false;try{session->loadState(5);}catch(const std::exception&){rejected=true;}require(rejected,"Wrong-ROM state was accepted");
    rejected=false;try{session->loadState(0);}catch(const std::exception&){rejected=true;}require(rejected,"Invalid slot was accepted");
    // Keep a valid state artifact for optional manual inspection.
    session->saveState(5);
    std::printf("PERSISTENCE_OK scenario=%d json_edit=17 slots=5 pixels_equal=180 audio_equal=%zu corrupt_and_wrong_rom=rejected\n",scenario,comparedSamples);
    return 0;
}

int laterSpellMapPrepare(const char* romPath,const char* folderPath) {
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);const int scenario=entry.identity.scenario;
    Session session(entry,folder/"saves",SaveFormat::Json);session.stateFolder(folder/"states");
    auto shot=[&](const char* name){SDL_Surface* im=SDL_CreateSurfaceFrom(256,240,SDL_PIXELFORMAT_RGBA32,session.pixels.data(),1024);SDL_SaveBMP(im,utf8(folder/(std::string(name)+".bmp")).c_str());SDL_DestroySurface(im);};
    std::ifstream replay("tests/replays/wiz1-dungeon.txt");
    struct Event{int frame;unsigned key;bool down;};std::vector<Event> events;std::string line;
    while(std::getline(replay,line)){int frame;std::string key,action;std::istringstream row(line);if(!(row>>frame>>key>>action))continue;unsigned b=key=="X"?PAD_A:key=="Z"?PAD_B:key=="Down"?PAD_DOWN:0;events.push_back({frame,b,action=="down"});}
    unsigned held=0;
    for(int frame=0;frame<4300;++frame){
        if(frame==900){std::vector<uint8_t> ram(8192);wiiz_core_sram_read(session.core(),ram.data(),ram.size());auto doc=Json::parse(encodeBattery(ram,scenario,entry.sha));auto& c=doc["characters"][0];c["class"]=1;c["level"]=13;
            for(int n=0x27;n<0x35;++n){char k[4];std::snprintf(k,sizeof(k),"%02X",n);c["unmapped_bytes"][k]=0x99;}
            for(int n=0x35;n<0x43;++n){char k[4];std::snprintf(k,sizeof(k),"%02X",n);c["unmapped_bytes"][k]=255;}
            ram=decodeBattery(doc.dump(),scenario,entry.sha);wiiz_core_sram_write(session.core(),ram.data(),ram.size());}
        for(const auto& e:events)if(e.frame==frame){if(e.down)held|=e.key;else held&=~e.key;}session.input(held);session.frame();
    }
    session.saveState(1);shot("dungeon");
    auto press=[&](unsigned b){if(session.spellMap().mode)return;session.input(b);for(int f=0;f<3&&!session.spellMap().mode;++f)session.frame();session.input(0);for(int f=0;f<100&&!session.spellMap().mode;++f)session.frame();};
    press(PAD_B);shot("camp");press(PAD_A);shot("camp-a");press(PAD_A);shot("camp-aa");session.saveState(2);press(PAD_A);shot("camp-aaa");session.saveState(3);
    press(PAD_A);shot("camp-aaaa");press(PAD_A);shot("camp-aaaaa");
    require(session.spellMap().mode==1,"Later actual DUMAPIC did not open map");
    require(session.explored(1,0,0)&&!session.explored(1,1,1),"Later unexplored map disclosed");
    session.saveState(4);
    std::vector<uint8_t> ram(8192);wiiz_core_sram_read(session.core(),ram.data(),ram.size());
    require(ram[0x427]==0x89,"Later DUMAPIC did not consume exactly one MP");
    session.mapKey(PAD_A);for(unsigned t=0;t<100;++t)session.tick(0,4,t*17);
    require(session.spellMap().mode==0,"Later DUMAPIC did not close");
    session.loadState(3);press(PAD_LEFT);shot("level7");
    press(PAD_A);shot("malor-list");press(PAD_A);shot("malor");
    require(session.spellMap().mode==2,"Later actual MALOR did not open map");session.saveState(5);
    for(unsigned speed:{1u,4u,8u}) {
        session.loadState(5);session.mapKey(PAD_B);for(unsigned t=0;t<100;++t)session.tick(0,speed,t*17);
        wiiz_core_sram_read(session.core(),ram.data(),ram.size());require(ram[0x42d]==0x99,"Later MALOR cancel consumed MP");
        require((wiiz_core_map_position(session.core())&0xffffff)==0x010000,"Later MALOR cancel moved party");
        session.loadState(5);session.mapKey(PAD_START);require(session.spellMap().targetFloor==2,"Later floor select failed");session.mapKey(PAD_SELECT);
        session.mapKey(PAD_UP);session.mapKey(PAD_A);for(unsigned t=0;t<150;++t)session.tick(0,speed,t*17);

        require((wiiz_core_map_position(session.core())&0xffffff)==0x010100,"Later original MALOR wrong destination");
        wiiz_core_sram_read(session.core(),ram.data(),ram.size());require(ram[0x42d]==0x89,"Later MALOR did not consume exactly one MP");
        require(session.explored(1,0,1)&&!session.explored(1,1,1),"Later explored map update failed");
    }
    session.save();Session reopened(entry,folder/"saves",SaveFormat::Json);require(reopened.explored(1,0,1)&&!reopened.explored(1,1,1),"Later exploration JSON roundtrip failed");
    session.loadState(5);session.mapKey(PAD_SELECT);require(session.spellMap().targetFloor==0,"Later surface missing");session.mapKey(PAD_A);
    for(unsigned t=0;t<150;++t)session.tick(0,4,t*17);
    require((wiiz_core_map_position(session.core())&0xffffff)==0,"Later original MALOR surface failed");
    session.loadState(4);require(session.spellMap().mode==1&&!session.explored(1,0,1),"Later map state restore failed");
    std::printf("SPELL_MAP_OK scenario=%d actual_spells=2 mp=original cancel=no_cost target=B1_E0_N1 speeds=1,4,8 explored_only=1 json_and_state=OK\n",scenario);return 0;
}

int storageCheck(const char* romPath,const char* folderPath) {
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);const int scenario=entry.identity.scenario;
    if(scenario==1){std::vector<uint8_t> stress(8192,0);std::fill_n(stress.begin()+64,8,255);repairBattery(stress,1);
        require(stress[0x78]==7,"Wiz I final ADC carry was incorrectly folded");}
    const auto saves=folder/"saves";fs::create_directories(saves);
    auto path=saves/entry.path.filename();path.replace_extension(".sav");auto json=path;json.replace_extension(".json");
    auto write=[&](const fs::path& file,const std::vector<uint8_t>& data){std::ofstream out(file,std::ios::binary);out.write(reinterpret_cast<const char*>(data.data()),data.size());};
    auto bytes=[&](const fs::path& file){std::ifstream in(file,std::ios::binary);return std::vector<uint8_t>(std::istreambuf_iterator<char>(in),{});};
    auto game=std::make_unique<Session>(entry,saves,SaveFormat::Sav);
    for(int f=0;f<900;++f){game->input(f>=400&&f<402?PAD_A:0);game->frame();}game->save();game.reset();
    require(fs::file_size(path)==8192,"Standard binary SAV size/name failed");
    auto edited=bytes(path);const size_t level=scenario==1?35:1024+33;edited[level]=0;edited[level+1]=17;
    // Leave CRC and mirrored copies deliberately stale.
    write(path,edited);auto canonical=edited;repairBattery(canonical,scenario);
    game=std::make_unique<Session>(entry,saves,SaveFormat::Sav);std::vector<uint8_t> actual(8192);
    require(wiiz_core_sram_read(game->core(),actual.data(),actual.size())&&actual==canonical,"Binary save did not repair checksums/mirrors");
    for(int f=0;f<900;++f){game->input(f>=400&&f<402?PAD_A:0);game->frame();}
    wiiz_core_sram_read(game->core(),actual.data(),actual.size());require(actual[level]==0&&actual[level+1]==17,"Original ROM rejected edited binary SAV");
    for(size_t i=0;i<20;++i){const size_t offset=scenario==1?i*256:1024+i*96;require(actual[offset]==canonical[offset],"Restart erased a character registration");}
    game->saveFormat(SaveFormat::Json);require(fs::exists(json),"Live format switch to JSON failed");
    auto document=Json::parse(bytes(json));require(document["characters"][0]["level"]==17,"JSON conversion lost edit");
    document["exploration"]=std::vector<uint8_t>(scenario==1?4000:2400,0);document["exploration"][20]=1;
    const auto text=document.dump();write(json,std::vector<uint8_t>(text.begin(),text.end()));
    game.reset();game=std::make_unique<Session>(entry,saves,SaveFormat::Json);
    for(int f=0;f<900;++f){game->input(f>=400&&f<402?PAD_A:0);game->frame();}
    wiiz_core_sram_read(game->core(),actual.data(),actual.size());
    for(size_t i=0;i<20;++i){const size_t offset=scenario==1?i*256:1024+i*96;require(actual[offset]==document["characters"][i]["in_use"].get<uint8_t>(),"JSON reboot erased a registered character");}
    game->saveFormat(SaveFormat::Sav);game.reset();
    game=std::make_unique<Session>(entry,saves,SaveFormat::Sav);require(game->explored(1,0,1)&&!game->explored(1,1,1),"Binary exploration sidecar failed");game.reset();
    // Hash-name migration: preserve the source and create a ROM-name .sav from old JSON.
    const auto migration=folder/"migration";fs::create_directories(migration);const auto old=migration/(entry.sha+".json");
    write(old,std::vector<uint8_t>(text.begin(),text.end()));const auto oldBytes=bytes(old);
    game=std::make_unique<Session>(entry,migration,SaveFormat::Sav);game->save();game.reset();
    require(bytes(old)==oldBytes,"Migration changed old hash-named JSON");auto migrated=migration/entry.path.filename();migrated.replace_extension(".sav");require(fs::file_size(migrated)==8192,"Named SAV migration missing");
    // Both normal boot and skip execute the same adopted core, with no synthetic button press.
    auto normal=std::make_unique<Session>(entry);auto skip=std::make_unique<Session>(entry,fs::path{},SaveFormat::Sav,true);
    unsigned frames=0;while(!wiiz_core_title_ready(normal->core())&&frames<900){normal->frame();++frames;}
    require(frames>30&&frames<900&&wiiz_core_title_ready(skip->core()),"Manufacturer skip did not reach title");
    require(normal->pixels==skip->pixels,"Skip changed the original title screen");
    normal->reset();skip->reset();frames=0;while(!wiiz_core_title_ready(normal->core())&&frames<900){normal->frame();++frames;}
    require(wiiz_core_title_ready(skip->core())&&normal->pixels==skip->pixels,"Reset skip differs from original title");
    std::printf("STORAGE_OK scenario=%d sav=8192 filename=ROM checksum_edit=accepted format_switch=OK migration=preserved exploration=OK maker_skip=title_equal reset=OK\n",scenario);return 0;
}

int difficultyCheck(const char* romPath,const char* folderPath) {
    { const auto entry=identifyRom(pathFromUtf8(romPath));
    auto tavern=std::make_unique<Session>(entry);tavern->assists(32);
    require(wiiz_core_tavern_probe(tavern->core()),"Original tavern filter mismatch");
    }
    spellMapPrepare(romPath,folderPath);
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;session.stateFolder(folder/"states");session.loadState(1);
    const int game=entry.identity.scenario;
    std::vector<uint8_t> before(8192),after(8192);wiiz_core_sram_read(session.core(),before.data(),before.size());
    const auto position=session.positionText();require(!position.empty(),"Missing position");
    session.openMap();require(session.spellMap().mode==3,"Host map did not open");
    const auto mapStart=session.spellMap();
    session.mapKey(PAD_RIGHT);session.mapKey(PAD_UP);
    require(session.spellMap().targetX==(mapStart.targetX+1)%20&&session.spellMap().targetY==(mapStart.targetY+1)%20,"Host map cursor did not move");
    session.mapKey(PAD_START);require(session.spellMap().targetFloor==mapStart.targetFloor+1,"Host map floor did not change");
    session.mapKey(PAD_SELECT);
    require(session.positionText()==position,"Host map browsing moved party");
    session.saveState(5);session.loadState(5);require(session.spellMap().mode==3,"Host map state lost");
    session.mapKey(PAD_B);require(session.spellMap().mode==0,"Host map did not close");
    wiiz_core_sram_read(session.core(),after.data(),after.size());require(before==after,"Host map changed SRAM / MP");
    session.openMap();session.mapKey(PAD_UP);session.mapKey(PAD_A);
    require(session.spellMap().mode==0,"Host map warp did not close");
    for(unsigned frame=0;frame<180;++frame)session.tick(0,1,frame*17);
    require((wiiz_core_map_position(session.core())&0xffffff)==(unsigned(mapStart.floor)<<16|unsigned((mapStart.y+1)%20)<<8|unsigned(mapStart.x)),"Host map warp destination mismatch");
    require(session.explored(mapStart.floor,mapStart.x,(mapStart.y+1)%20),"Host map warp did not record destination");
    wiiz_core_sram_read(session.core(),after.data(),after.size());
    const unsigned mapMp=game==1?0x29:0x427;
    require(std::memcmp(before.data()+mapMp,after.data()+mapMp,game==1?7:14)==0,"Host map warp consumed spell MP");
    session.loadState(1);session.openMap();session.mapKey(PAD_START);session.mapKey(PAD_UP);session.mapKey(PAD_A);
    for(unsigned frame=0;frame<180;++frame)session.tick(0,1,frame*17);
    require((wiiz_core_map_position(session.core())&0xffffff)==0x020100,"Host map cross-floor warp mismatch");
    session.loadState(1);session.openMap();session.mapKey(PAD_SELECT);session.mapKey(PAD_A);
    for(unsigned frame=0;frame<180;++frame)session.tick(0,1,frame*17);
    require((wiiz_core_map_position(session.core())&0xffffff)==0,"Host map surface warp mismatch");
    session.loadState(1);
    const unsigned start=game==1?0:0x400,gold=game==1?0x13:0x11,exp=gold+6;
    auto decimal=[&](const std::vector<uint8_t>& data,unsigned at){uint64_t value=0;for(unsigned i=0;i<6;++i)value=value*100+(data[at+i]>>4)*10+(data[at+i]&15);return value;};
    const auto oldGold=decimal(before,start+gold),oldExp=decimal(before,start+exp);
    session.rosterBonus(1,0,10000);
    wiiz_core_sram_read(session.core(),after.data(),after.size());
    auto preparedExp=decimal(after,start+exp);
    require(preparedExp>oldExp,"Experience did not advance");
    session.rosterBonus(1,0,1);wiiz_core_sram_read(session.core(),after.data(),after.size());
    require(decimal(after,start+exp)>preparedExp,"Repeated preparation did not advance");
    preparedExp=decimal(after,start+exp);
    session.rosterBonus(1,1,1000);session.rosterBonus(1,2,0);
    wiiz_core_sram_read(session.core(),after.data(),after.size());
    require(decimal(after,start+gold)==oldGold+1000,"Gold addition failed");require(decimal(after,start+exp)==preparedExp,"Experience addition failed");
    const unsigned mp=game==1?0x29:0x27,mpEnd=game==1?0x45:0x35;
    require(std::equal(before.begin()+start+mp,before.begin()+start+mpEnd,after.begin()+start+mp),"Learn spells changed MP");
    if(game==1){for(unsigned i=0;i<6;++i)require(after[start+0x45+i]==255,"Missing learned spell");require((after[start+0x4b]&3)==3,"Missing final spells");}
    else {const unsigned masks2[]={15,3,3,7,7,15,7,31,15,15,15,63,15,3};const unsigned masks3[]={15,7,7,7,15,15,7,31,31,15,31,15,15,3};const auto* masks=game==2?masks2:masks3;for(unsigned i=0;i<14;++i)require((after[start+0x35+i]&masks[i])==masks[i],"Missing learned spell");}
    for(unsigned i=0;i<120;++i)session.tick(0,1,i*17);
    std::vector<uint8_t> live(8192);wiiz_core_sram_read(session.core(),live.data(),live.size());
    require(decimal(live,start+gold)==oldGold+1000&&decimal(live,start+exp)==preparedExp,"Original idle execution overwrote bonus");
    session.rosterBonus(1,1,UINT64_MAX);wiiz_core_sram_read(session.core(),after.data(),after.size());require(decimal(after,start+gold)==999999999999ULL,"Gold cap failed");
    session.save();auto restoredOwner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& restored=*restoredOwner;std::vector<uint8_t> disk(8192);wiiz_core_sram_read(restored.core(),disk.data(),disk.size());require(after==disk,"Bonus persistence failed");
    // Run the changed roster through original boot/checksum validation.
    for(int i=0;i<900;++i){restored.input(i==400||i==401?PAD_A:0);restored.frame();}
    wiiz_core_sram_read(restored.core(),disk.data(),disk.size());require(disk[start]==after[start],"ROM rejected edited roster");
    // Exercise all class thresholds independently of the prepared dungeon save.
    const uint64_t first[]={1000,1100,1050,900,1200,1250,1300,1450};
    const uint64_t second[]={1724,1896,1810,1551,2105,2192,2280,2543};
    const uint64_t base[]={400075,439874,419993,359931,581240,605263,629663,702236};
    const uint64_t step[]={289709,318529,304132,260639,438479,456601,475008,529757};
    for(unsigned cls=0;cls<8;++cls)for(unsigned level:{1u,12u,13u,1011u,1012u,1013u}) {
        auto sample=before;auto* c=sample.data()+start;
        if(game==1)c[11]=uint8_t(cls);else c[10]=uint8_t((c[10]&0xe3)|(cls<<2));
        const unsigned at=game==1?35:33;c[at]=0;c[at+1]=1; // Stored level deliberately lags behind EXP.
        const uint64_t expected=level==1?first[cls]:base[cls]+(level-12)*step[cls]+(game!=1&&level>=1012?10000*step[cls]:0);
        uint64_t seed=expected-1;
        for(int i=5;i>=0;--i){c[exp+i]=uint8_t(((seed/10)%10)*16+seed%10);seed/=100;}
        repairBattery(sample,game);
        wiiz_core_sram_write(session.core(),sample.data(),sample.size());session.rosterBonus(1,0,999999);
        wiiz_core_sram_read(session.core(),sample.data(),sample.size());
        require(decimal(sample,start+exp)==expected,"Class/level experience threshold mismatch");
        require(session.rosterExperienceLevel(1)==level+1,"EXP estimated level mismatch");
        session.rosterBonus(1,0,0);wiiz_core_sram_read(session.core(),sample.data(),sample.size());
        const uint64_t next=level==1?second[cls]:expected+step[cls]*(game!=1&&level==1011?10001:1);
        require(decimal(sample,start+exp)==next,"Repeated EXP addition ignored current experience");
        require(session.rosterExperienceLevel(1)==level+2,"Repeated EXP estimated level mismatch");
        require(sample[start+at]==0&&sample[start+at+1]==1,"EXP addition changed level directly");
        for(unsigned alignment=0;alignment<3;++alignment) {
            const unsigned field=game==1?12:10,previous=sample[start+field];
            session.rosterBonus(1,3,alignment);wiiz_core_sram_read(session.core(),sample.data(),sample.size());
            require(sample[start+field]==((previous&0xfc)|alignment),"Alignment damaged identity bits");
        }
    }
    wiiz_core_sram_write(session.core(),after.data(),after.size());
    std::printf("DIFFICULTY_OK scenario=%d map_no_mp=1 spell_masks=1 mp_unchanged=1 bonuses=1 cap=1 restart=1\n",game);return 0;
}

int assistsCheck(const char* romPath,const char* folderPath) {
    spellMapPrepare(romPath,folderPath);
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;
    session.stateFolder(folder/"states");session.loadState(3);
    const unsigned game=entry.identity.scenario,base=game==1?0:0x400,mp=game==1?0x29:0x27;
    session.assists(15);session.saveState(2);
    require(wiiz_core_assist_probe(session.core()),"CPU RAM/SRAM freeze failed");session.loadState(2);
    auto inspect=[&]{
        std::vector<uint8_t> ram(8192);wiiz_core_sram_read(session.core(),ram.data(),ram.size());
        for(unsigned i=0;i<(game==1?28u:14u);++i)require(ram[base+mp+i]==(game==1?9:0x99),"MP did not stay at nine");
        const unsigned light=game==1?0x27f:game==2?0x77ef:0x6d99;
        require(wiiz_core_peek(session.core(),light)==255,"Light missing");
        require(wiiz_core_peek(session.core(),game==1?0x280:light+2)==255,"Identification missing");
        require(wiiz_core_peek(session.core(),game==1?0x281:light+1)==(game==1?254:2),"Protection missing");
    };
    auto press=[&](unsigned b){session.input(b);for(unsigned f=0;f<3;++f)session.frame();session.input(0);for(unsigned f=0;f<100;++f)session.frame();};
    inspect();press(PAD_A);press(PAD_A);require(session.spellMap().mode==1,"Assisted original DUMAPIC failed");inspect();
    session.mapKey(PAD_A);for(unsigned i=0;i<100;++i)session.tick(0,4,i*17);inspect();
    session.save();session.reset();for(unsigned i=0;i<900;++i){session.input(i==400||i==401?PAD_A:0);session.frame();}inspect();
    std::vector<uint8_t> ram(8192);wiiz_core_sram_read(session.core(),ram.data(),ram.size());require(ram[base]!=0,"Reset erased edited character");
    session.loadState(3);inspect();session.assists(0);press(PAD_A);press(PAD_A);require(session.spellMap().mode==1,"Disabled original cast failed");
    wiiz_core_sram_read(session.core(),ram.data(),ram.size());require(ram[base+mp]==(game==1?8:0x89),"OFF did not restore MP consumption");
    std::printf("ASSISTS_OK scenario=%u cpu_write_freeze=1 actual_cast=1 effects=1 state_reset=1 off_consumes=1\n",game);return 0;
}

static int creationCheckImpl(const char* romPath,const char* folderPath,bool hpTest) {
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);fs::create_directories(folder);
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;
    session.assists(16,false);session.stateFolder(folder/"states");
    if(hpTest && entry.identity.scenario==1)session.bugFix(true);
    auto shot=[&](const char* name){auto* raw=SDL_CreateSurfaceFrom(256,240,SDL_PIXELFORMAT_RGBA32,session.pixels.data(),1024);auto* scaled=SDL_CreateSurface(768,720,SDL_PIXELFORMAT_RGBA32);SDL_BlitSurfaceScaled(raw,nullptr,scaled,nullptr,SDL_SCALEMODE_NEAREST);SDL_SaveBMP(scaled,utf8(folder/(std::string(name)+".bmp")).c_str());SDL_DestroySurface(scaled);SDL_DestroySurface(raw);};
    auto press=[&](unsigned b){session.input(b);for(unsigned f=0;f<3;++f)session.frame();session.input(0);for(unsigned f=0;f<100;++f)session.frame();};
    for(unsigned f=0;f<900;++f){session.input(f==400||f==401?PAD_A:0);session.frame();}
    for(unsigned i=0;i<4;++i)press(PAD_DOWN);press(PAD_A);shot("edge");press(PAD_A);shot("training");press(PAD_A);
    press(PAD_A);press(PAD_START);press(PAD_A);shot("race");session.saveState(1);
    const unsigned game=entry.identity.scenario,pool=game==1?0x25b:0x40,stats=game==1?0x254:0x4d;
    const unsigned recordStart=game==1?0:0x400,stride=game==1?256:96,ability=game==1?13:11;
    std::vector<uint8_t> initial(8192);wiiz_core_sram_read(session.core(),initial.data(),initial.size());
    unsigned slot=0;while(slot<20&&initial[recordStart+slot*stride])++slot;require(slot<20,"No free test character slot");
    auto quick=[&](unsigned b){session.input(b);for(unsigned f=0;f<3;++f)session.frame();session.input(0);for(unsigned f=0;f<20;++f)session.frame();};
    // Enabling the setting on an existing allocation must not refill it.
    session.assists(0);press(PAD_A);press(PAD_A);const auto ordinary=wiiz_core_peek(session.core(),pool);
    session.assists(16);require(wiiz_core_peek(session.core(),pool)==ordinary,"Toggle refilled an existing allocation");
    for(unsigned race=0;race<5;++race) {
        session.loadState(1);for(unsigned i=0;i<race;++i)press(PAD_DOWN);press(PAD_A);press(PAD_A);
        require(wiiz_core_creation_events(session.core())==1,"Creation hook missing or repeated");
        unsigned expected=0;unsigned upper[6];
        for(unsigned stat=0;stat<6;++stat){const unsigned base=wiiz_core_peek(session.core(),stats+stat);upper[stat]=game==3?base+10:18;expected+=upper[stat]-base;}
        require(wiiz_core_peek(session.core(),pool)==expected,"Wrong initial species bonus");
        if(race==0||race==4)shot(("bonus-"+std::to_string(race)).c_str());
        for(unsigned stat=0;stat<6;++stat) {
            while(wiiz_core_peek(session.core(),stats+stat)<upper[stat]) {
                const unsigned old=wiiz_core_peek(session.core(),pool);quick(PAD_RIGHT);
                require(wiiz_core_peek(session.core(),pool)+1==old,"Allocation did not consume one point");
            }
            if(stat==0){const unsigned remaining=wiiz_core_peek(session.core(),pool);session.saveState(2);session.loadState(2);require(wiiz_core_peek(session.core(),pool)==remaining,"State refilled allocation");}
            if(stat<5)press(PAD_DOWN);
        }
        require(wiiz_core_peek(session.core(),pool)==0,"Bonus remains after reaching caps");
        quick(PAD_LEFT);require(wiiz_core_peek(session.core(),pool)==1,"Point refund failed");quick(PAD_RIGHT);require(wiiz_core_peek(session.core(),pool)==0,"Refund could not be reassigned");
        if(race==0||race==4)shot(("allocated-"+std::to_string(race)).c_str());
        press(PAD_A);
        if(hpTest && game==1)for(unsigned i=0;i<6;++i)press(PAD_DOWN);
        press(PAD_A);press(PAD_A);
        std::vector<uint8_t> saved(8192);wiiz_core_sram_read(session.core(),saved.data(),saved.size());
        require(saved[recordStart+slot*stride]!=0,"Creation did not register character");
        if(hpTest && game==1) {
            const auto base=recordStart+slot*stride;
            require((saved[base+11]&7)==6,"Lord was not selected");
            require(((unsigned(saved[base+33])<<8)|saved[base+34])>=15,"Created maximum HP below fifteen");
            require(saved[base+31]==saved[base+33]&&saved[base+32]==saved[base+34],"Initial current HP differs from maximum");
        }
        for(unsigned stat=0;stat<6;++stat)require(saved[recordStart+slot*stride+ability+stat]==upper[stat],"Registered ability differs from allocation");
        session.save();auto reopened=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);
        for(unsigned f=0;f<900;++f){reopened->input(f==400||f==401?PAD_A:0);reopened->frame();}
        std::vector<uint8_t> restored(8192);wiiz_core_sram_read(reopened->core(),restored.data(),restored.size());
        require(restored[recordStart+slot*stride]!=0,"Original ROM rejected registered character");
        if(hpTest && game==1)require(restored[recordStart+slot*stride+33]==saved[recordStart+slot*stride+33]&&restored[recordStart+slot*stride+34]==saved[recordStart+slot*stride+34],"Reload changed initial HP");
        for(unsigned stat=0;stat<6;++stat)require(restored[recordStart+slot*stride+ability+stat]==upper[stat],"Saved ability changed on restart");
    }
    std::printf("CREATION_OK scenario=%u species=5 one_shot=1 refund=1 state_no_refill=1 registered=5 restart=5\n",game);return 0;
}

int creationCheck(const char* romPath,const char* folderPath) {return creationCheckImpl(romPath,folderPath,false);}
int creationHpMenuCheck(const char* romPath,const char* folderPath) {return creationCheckImpl(romPath,folderPath,true);}

int rosterCheck(const char* romPath,const char* folderPath) {
    spellMapPrepare(romPath,folderPath);const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;session.stateFolder(folder/"states");session.loadState(1);
    const unsigned game=entry.identity.scenario,start=game==1?0:0x400,stride=game==1?256:96,payload=game==1?112:94,mp=game==1?0x29:0x27;
    auto ram=[&]{std::vector<uint8_t> data(8192);require(wiiz_core_sram_read(session.core(),data.data(),data.size()),"Cannot inspect roster");return data;};
    auto before=ram();bool blocked=false;try{session.swapRoster(1,2);}catch(...){blocked=true;}require(blocked&&ram()==before,"Live swap changed gameplay state");
    auto title=[&]{session.reset();session.skipManufacturer();require(session.canSwapRoster(),"Title did not enable roster editor");};
    auto press=[&](unsigned b){session.input(b);for(unsigned f=0;f<3;++f)session.frame();session.input(0);for(unsigned f=0;f<120;++f)session.frame();};
    title();before=ram();require(!session.rosterLabel(1).empty(),"Missing roster labels");
    session.swapRoster(1,2);auto after=ram();
    require(std::equal(before.begin()+start+stride,before.begin()+start+stride+payload,after.begin()+start),"First slot did not receive complete second record");
    require(std::equal(before.begin()+start,before.begin()+start+payload,after.begin()+start+stride),"Second slot did not receive complete first record");
    for(unsigned i=2;i<20;++i)require(std::equal(before.begin()+start+i*stride,before.begin()+start+i*stride+payload,after.begin()+start+i*stride),"Other character changed");
    require(session.canSwapRoster(),"Swap did not return to editable title");
    auto shot=[&](const char* name){auto* raw=SDL_CreateSurfaceFrom(256,240,SDL_PIXELFORMAT_RGBA32,session.pixels.data(),1024);auto* scaled=SDL_CreateSurface(768,720,SDL_PIXELFORMAT_RGBA32);SDL_BlitSurfaceScaled(raw,nullptr,scaled,nullptr,SDL_SCALEMODE_NEAREST);SDL_SaveBMP(scaled,utf8(folder/(std::string(name)+".bmp")).c_str());SDL_DestroySurface(scaled);SDL_DestroySurface(raw);};
    session.saveState(3);
    // Resume the original maze party, now containing the same mage at slot 2.
    press(PAD_A);shot("castle");for(unsigned i=0;i<4;++i)press(PAD_DOWN);press(PAD_A);shot("edge");press(PAD_DOWN);press(PAD_DOWN);press(PAD_A);shot("resume");press(PAD_A);shot("explore");
    for(unsigned i=0;i<5;++i)press(PAD_A);
    shot("cast");require(session.spellMap().mode==1,"Resumed party no longer contains original spellcaster");
    after=ram();require(after[start+stride+mp]==(game==1?8:0x89),"Original party identity/MP was not preserved");
    session.mapKey(PAD_A);title();before=ram();session.swapRoster(2,20);after=ram();
    require(std::equal(before.begin()+start+stride,before.begin()+start+stride+payload,after.begin()+start+19*stride),"Move to empty slot lost character fields");
    require(after[start+stride]==0&&after[start+19*stride]!=0,"Empty slot exchange failed");
    session.swapRoster(20,2);after=ram();require(std::equal(before.begin()+start+stride,before.begin()+start+stride+payload,after.begin()+start+stride),"Reverse swap lost fields");
    session.swapRoster(2,2);bool invalid=false;try{session.swapRoster(0,1);}catch(...){invalid=true;}require(invalid,"Out-of-range slot accepted");
    auto reopened=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);for(unsigned f=0;f<900;++f){reopened->input(f==400||f==401?PAD_A:0);reopened->frame();}
    std::vector<uint8_t> saved(8192);wiiz_core_sram_read(reopened->core(),saved.data(),saved.size());require(std::equal(after.begin()+start+stride,after.begin()+start+stride+payload,saved.begin()+start+stride),"Restart rejected swapped record");
    const auto backup=folder/"saves"/"backups"/entry.path.stem();bool found=false;for(const auto& f:fs::directory_iterator(backup))if(utf8(f.path().filename()).find("before-roster")!=std::string::npos)found=true;require(found,"Pre-swap backup missing");
    title();before=ram();session.moveRoster(1,20);after=ram();
    for(unsigned i=0;i<20;++i) {
        const unsigned source=i==19?0:i+1;
        require(std::equal(before.begin()+start+source*stride,before.begin()+start+source*stride+payload,after.begin()+start+i*stride),"Insertion changed character fields/order");
    }
    const unsigned partyCount=game==1?0x1def:0xb81,partyList=game==1?0x1ddc:0xb82,refBase=game==1?0x60:0;
    for(unsigned i=0;i<before[partyCount];++i) {
        const unsigned old=before[partyList+i]-refBase;
        require(after[partyList+i]==refBase+(old==0?19:old-1),"Insertion changed party identity");
    }
    session.moveRoster(20,1);after=ram();
    for(unsigned i=0;i<20;++i)require(std::equal(before.begin()+start+i*stride,before.begin()+start+i*stride+payload,after.begin()+start+i*stride),"Reverse insertion lost records");
    using Field=Session::RosterField;
    auto rejectIdentity=[&](unsigned slot,Field field,unsigned value,const char* reason) {
        const auto original=ram();
        bool rejected=false;
        try{session.setRosterIdentity(slot,field,value);}catch(const std::runtime_error&){rejected=true;}
        require(rejected&&ram()==original,reason);
    };
    {
        rejectIdentity(20,Field::Race,4,"Empty slot accepted an identity edit");
        rejectIdentity(1,Field::Race,5,"Out-of-range race accepted");
        rejectIdentity(1,Field::Class,8,"Out-of-range class accepted");
        press(PAD_A);
        for(unsigned i=0;i<4;++i)press(PAD_DOWN);
        press(PAD_A);press(PAD_A);shot("training-identity");
        require(!session.canSwapRoster(),"Training route did not leave title");
        session.rosterBonus(1,3,2);
        after=ram();
        auto expected=after;
        const unsigned race=game==1?((after[start+10]&7)+1)%5:((after[start+10]>>5)+1)%5;
        const unsigned job=game==1?((after[start+11]&7)+1)%8:(((after[start+10]>>2)&7)+1)%8;
        if(game==1) {
            expected[start+10]=uint8_t((after[start+10]&0xf8)|race);
            expected[start+11]=uint8_t((after[start+11]&0xf8)|job);
        } else {
            expected[start+10]=uint8_t((race<<5)|(job<<2)|2);
        }
        auto facilityScreen=std::make_unique<decltype(session.pixels)>(session.pixels);
        session.setRosterIdentity(1,Field::Race,race);
        require(session.pixels==*facilityScreen&&!session.canSwapRoster(),"Identity edit interrupted training");
        press(PAD_B);
        require(session.rosterIdentity(1,Field::Race)==int(race),"Leaving training lost edited race");

        title();press(PAD_A);press(PAD_A);shot("tavern-identity");
        require(!session.canSwapRoster(),"Tavern route did not leave title");
        *facilityScreen=session.pixels;
        session.setRosterIdentity(1,Field::Class,job);
        require(session.pixels==*facilityScreen&&!session.canSwapRoster(),"Identity edit interrupted tavern");
        press(PAD_B);
        after=ram();
        for(unsigned i=0;i<20;++i)
            require(std::equal(expected.begin()+start+i*stride,expected.begin()+start+i*stride+payload,after.begin()+start+i*stride),"Identity edit changed unrelated character data");
        require(session.rosterIdentity(1,Field::Race)==int(race)&&session.rosterIdentity(1,Field::Class)==int(job),"Leaving tavern lost edited identity");
        auto edited=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);
        edited->skipManufacturer();
        require(edited->rosterIdentity(1,Field::Race)==int(race)&&edited->rosterIdentity(1,Field::Class)==int(job),"ROM restart lost edited identity");
    }
    std::printf("ROSTER_OK scenario=%u complete_records=1 resumed_original_mage=1 empty_slot=1 reverse=1 restart=1 backup=1 live_reorder_rejected=1 insertion_20=1 reverse_insertion=1 party_remap=1 facility_identity_edit=1\n",game);return 0;
}

int turboFileCheck(const char* romPath,const char* folderPath) {
    const auto entry=identifyRom(pathFromUtf8(romPath));const auto folder=pathFromUtf8(folderPath);fs::create_directories(folder);
    Session session(entry,folder/"saves",SaveFormat::Sav);session.stateFolder(folder/"states");
    auto shot=[&](unsigned n){auto* raw=SDL_CreateSurfaceFrom(256,240,SDL_PIXELFORMAT_RGBA32,session.pixels.data(),1024);auto* scaled=SDL_CreateSurface(768,720,SDL_PIXELFORMAT_RGBA32);SDL_BlitSurfaceScaled(raw,nullptr,scaled,nullptr,SDL_SCALEMODE_NEAREST);SDL_SaveBMP(scaled,utf8(folder/("step-"+std::to_string(n)+".bmp")).c_str());SDL_DestroySurface(scaled);SDL_DestroySurface(raw);};
    for(unsigned f=0;f<900;++f){session.input(f==400||f==401?PAD_A:0);session.frame();}
    shot(0);std::ifstream in(folder/"keys.txt");std::string keys;in>>keys;if(keys.empty())keys="DDDDADDDA";
    unsigned n=0;std::vector<uint8_t> expectedTf;
    for(char k:keys) {
        if(k=='S'){
            expectedTf.resize(8198);wiiz_core_turbofile_read(session.core(),expectedTf.data(),8192);wiiz_core_turbofile_registers(session.core(),expectedTf.data()+8192);
            session.saveState(1);continue;
        }
        if(k=='L'){
            session.loadState(1);
            if(!expectedTf.empty()){
                std::vector<uint8_t> actual(8198);wiiz_core_turbofile_read(session.core(),actual.data(),8192);wiiz_core_turbofile_registers(session.core(),actual.data()+8192);
                require(actual==expectedTf,"Turbo File RAM/serial registers did not roll back with state");
            }
            continue;
        }
        unsigned b=k=='A'?PAD_A:k=='B'?PAD_B:k=='U'?PAD_UP:k=='D'?PAD_DOWN:k=='R'?PAD_RIGHT:k=='T'?PAD_START:0;
        session.input(b);for(unsigned f=0;f<3;++f)session.frame();session.input(0);for(unsigned f=0;f<180;++f)session.frame();shot(++n);
    }
    std::vector<uint8_t> tf(8192);wiiz_core_turbofile_read(session.core(),tf.data(),tf.size());
    session.save();std::ofstream out(folder/"observed.tbf",std::ios::binary);out.write(reinterpret_cast<const char*>(tf.data()),tf.size());
    unsigned used=0;for(auto v:tf)used+=v!=0;
    std::printf("TURBOFILE_PROBE scenario=%u nonzero=%u steps=%u\n",entry.identity.scenario,used,n);return 0;
}

int initialHpCheck(const char* romPath,const char* folderPath) {
    const auto entry=identifyRom(pathFromUtf8(romPath));
    Session session(entry,pathFromUtf8(folderPath)/"saves");
    require(session.supportsTurbo()&&entry.identity.scenario==1,"Verified Wiz1 required");
    session.skipManufacturer();
    require(wiiz_core_initial_hp_probe(session.core())!=0,"Initial HP floor failed");
    std::puts("INITIAL_HP_OK 20 slots x 256 values, original CPU stores, outside creation unchanged");
    return 0;
}
int bugFixCheck(const char* romPath,const char* folderPath) {
    const auto entry=identifyRom(pathFromUtf8(romPath));
    Session session(entry,pathFromUtf8(folderPath)/"saves");
    session.stateFolder(pathFromUtf8(folderPath)/"states");
    require(!session.bugFix(),"Default must be OFF");
    if(entry.identity.scenario!=1) {
        require(!session.supportsBugFix(),"Non-Wiz1 patch offered");
        bool rejected=false;try{session.bugFix(true);}catch(...){rejected=true;}
        require(rejected,"Non-Wiz1 patch accepted");
        std::puts("BUGFIX_OK unsupported scenario rejected");return 0;
    }
    require(session.supportsBugFix(),"Known Wiz1 unsupported");
    session.skipManufacturer();
    session.saveState(1);
    std::vector<uint8_t> before(8192),after(8192);
    wiiz_core_sram_read(session.core(),before.data(),before.size());
    session.bugFix(true);
    require(session.bugFix(),"ON failed");
    require(wiiz_core_peek(session.core(),0xf9e9)==0x7c,"Patched AC instruction missing");
    wiiz_core_sram_read(session.core(),after.data(),after.size());
    require(before==after,"Toggle damaged battery RAM");
    bool rejected=false;try{session.loadState(1);}catch(...){rejected=true;}
    require(rejected,"Mismatched patch state accepted");
    session.saveState(2);session.loadState(2);
    require(wiiz_core_peek(session.core(),0xf9e9)==0x7c,"State lost patch");
    for(unsigned i=0;i<120;++i)session.tick(0,4,i*17);
    session.bugFix(false);
    require(wiiz_core_peek(session.core(),0xf9e9)==0x7d,"OFF failed to restore original");
    session.loadState(1);
    session.bugFix(true);session.bugFix(false);
    require(identifyRom(pathFromUtf8(romPath)).sha==entry.sha,"Source ROM modified");
    std::puts("BUGFIX_OK toggle SRAM state music original-ROM");return 0;
}

int itemsCheck(const char* romPath,const char* folderPath) {
    auto entry=identifyRom(pathFromUtf8(romPath));auto folder=pathFromUtf8(folderPath);
    if(!fs::exists(folder/"states"/(utf8(entry.path.stem())+".stot1.state")))spellMapPrepare(romPath,folderPath);
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;session.stateFolder(folder/"states");session.loadState(1);
    auto members=session.openItems();require(!members.empty(),"Missing party inventory");
    const unsigned game=entry.identity.scenario;
    std::vector<uint8_t> seed(8192);wiiz_core_sram_read(session.core(),seed.data(),seed.size());
    const unsigned flags=game==1?0x4c:0x43,count=game==1?0x5c:0x53;
    auto offset=[&](unsigned slot){return game==1?(slot-1)*256:0x400+(slot-1)*96;};
    unsigned base=offset(members[0].slot);
    // Explicit test-only inventory, with an identified weapon and unknown item.
    const uint8_t weapon=game==2?13:1;
    seed[base+count]=2;seed[base+flags]=0;seed[base+flags+1]=32;seed[base+flags+8]=weapon;seed[base+flags+9]=2;
    for(unsigned i=2;i<8;++i){seed[base+flags+i]=0;seed[base+flags+8+i]=255;}
    // Select an ordinary fighter so that the original equip check is applicable.
    if(game==1)seed[base+11]=0;else seed[base+10]&=0xe3;
    repairBattery(seed,game);wiiz_core_sram_write(session.core(),seed.data(),seed.size());
    members=session.openItems();auto after=members;
    require(!session.itemNameCodes(members[0].items[0]).empty(),"Missing Japanese item name");
    session.equipItem(after[0],0);require(after[0].items[0].flags&128,"Equip did not set native flag");
    session.updateItems(members,after);members=after;
    std::vector<uint8_t> current(8192);wiiz_core_sram_read(session.core(),current.data(),current.size());
    require(current[base+flags]&128,"Equipped flag not committed");
    // II/III do not load combat arrays in town/the maze; verify the original
    // calculation on a disposable core rather than requiring live scratch RAM.
    auto calculation=std::make_unique<Session>(entry);
    std::vector<uint8_t> inventoryState(wiiz_core_state_size(session.core()));
    require(wiiz_core_state_write(session.core(),inventoryState.data(),inventoryState.size())&&wiiz_core_state_read(calculation->core(),inventoryState.data(),inventoryState.size()),"Cannot prepare original damage check");
    require(wiiz_core_items_recalculate(calculation->core(),0)!=0,"Native damage calculation failed");
    require(wiiz_core_peek(calculation->core(),game==1?0x7d82:game==2?0x53e:0x55e)==1&&wiiz_core_peek(calculation->core(),game==1?0x7d88:game==2?0x544:0x564)==(game==2?6u:8u),"Native weapon damage was not applied");
    // Recalculation must leave HP, identity, spells and all other roster slots alone.
    for(unsigned slot=1;slot<=20;++slot)for(unsigned i=0;i<(game==1?112u:94u);++i) {
        bool permitted=slot==members[0].slot&&(i==flags||i==count||(i>=flags&&i<flags+16)||i==(game==1?0x28u:0x26u)||(game!=1&&i==0x59));
        require(permitted||current[offset(slot)+i]==seed[offset(slot)+i],"Item update modified unrelated character data");
    }
    after=members;session.equipItem(after[0],0);require(!(after[0].items[0].flags&128),"Remove failed");session.updateItems(members,after);members=after;
    after=members;std::swap(after[0].items[0],after[0].items[1]);session.updateItems(members,after);members=after;
    require(members[0].items[0].flags==32,"Reorder lost unidentified flag");
    after=members;after[0].items.erase(after[0].items.begin());session.updateItems(members,after);
    bool rejected=false;try{session.updateItems(members,after);}catch(...){rejected=true;}require(rejected,"Stale inventory accepted");
    session.save();auto reopened=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);
    std::vector<uint8_t> loaded(8192);wiiz_core_sram_read(reopened->core(),loaded.data(),loaded.size());
    require(loaded[base+count]==1&&loaded[base+flags+8]==weapon,"Saved inventory did not survive reload");
    for(unsigned f=0;f<120;++f){session.input(0);session.frame();}
    auto resumed=session.openItems();require(resumed[0].items.size()==1&&resumed[0].items[0].id==weapon,"Original game overwrote edited inventory");
    // Two-member fixture exercises GBWiz's transfer/bulk interaction on the NES backend.
    wiiz_core_sram_read(session.core(),seed.data(),seed.size());
    unsigned partner=offset(20),stride=game==1?256:96;
    std::copy_n(seed.begin()+base,stride,seed.begin()+partner);
    seed[game==1?0x1def:0xb81]=2;seed[(game==1?0x1ddc:0xb82)+1]=game==1?0x73:19;
    seed[partner+count]=2;seed[partner+flags]=32;seed[partner+flags+8]=2;
    seed[partner+flags+1]=64;seed[partner+flags+9]=weapon;
    repairBattery(seed,game);wiiz_core_sram_write(session.core(),seed.data(),seed.size());
    ItemEditor editor;editor.open(session);
    for(unsigned i=0;i<8;++i)editor.key(session,SDLK_DOWN);editor.key(session,SDLK_X);
    auto bulk=session.openItems();require(bulk[0].items.size()==2&&bulk[1].items.size()==1&&bulk[0].items[1].flags==32&&bulk[1].items[0].flags==64,"Collect failed or moved cursed item");
    editor.key(session,SDLK_DOWN);editor.key(session,SDLK_X);
    bulk=session.openItems();require(bulk[0].items.empty()&&bulk[1].items.size()==3&&bulk[1].items[2].flags==32,"Bulk send lost flags");
    editor.key(session,SDLK_RIGHT);editor.key(session,SDLK_X);editor.key(session,SDLK_DOWN);editor.key(session,SDLK_DOWN);editor.key(session,SDLK_X);editor.key(session,SDLK_X);
    require(session.openItems()==bulk,"Default delete confirmation changed inventory");
    // Move the ordinary weapon back using the single-item submenu.
    editor.key(session,SDLK_DOWN);editor.key(session,SDLK_X);editor.key(session,SDLK_DOWN);editor.key(session,SDLK_X);
    bulk=session.openItems();require(bulk[0].items.size()==1&&bulk[1].items.size()==2,"Individual transfer failed");
    editor.key(session,SDLK_UP);editor.key(session,SDLK_X);editor.key(session,SDLK_DOWN);editor.key(session,SDLK_DOWN);editor.key(session,SDLK_X);editor.key(session,SDLK_RIGHT);
    rejected=false;try{editor.key(session,SDLK_X);}catch(...){rejected=true;}
    require(rejected&&session.openItems()==bulk,"Cursed item deletion accepted");
    session.saveState(2);
    session.reset();session.skipManufacturer();
    wiiz_core_sram_read(session.core(),seed.data(),seed.size());seed[game==1?0x1def:0xb81]=0;wiiz_core_sram_write(session.core(),seed.data(),seed.size());
    rejected=false;try{session.openItems();}catch(...){rejected=true;}require(rejected,"No-party state accepted item editor");
    std::printf("ITEMS_OK scenario=%u original_recalc=1 equip=1 remove=1 flags=1 reorder=1 delete=1 stale_rejected=1 unrelated_records=preserved save_reload=1 resume=1 transfer=1 bulk=1 curse_guard=1 delete_default_no=1 party_only=1 no_party_rejected=1\n",game);return 0;
}


int itemsBattleCheck(const char* romPath,const char* folderPath) {
    auto entry=identifyRom(pathFromUtf8(romPath));auto folder=pathFromUtf8(folderPath);
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;session.stateFolder(folder/"states");session.loadState(1);
    require(wiiz_core_items_battle_check(session.core())!=0,"Original encounter entry failed");
    bool rejected=false;try{session.openItems();}catch(...){rejected=true;}require(rejected,"Battle entry accepted item editor");
    for(unsigned i=0;i<20;++i)session.frame();
    auto* image=SDL_CreateSurfaceFrom(256,240,SDL_PIXELFORMAT_RGBA32,session.pixels.data(),1024);SDL_SaveBMP(image,utf8(folder/"scene-battle.bmp").c_str());SDL_DestroySurface(image);
    std::vector<uint8_t> before(8192),after(8192);wiiz_core_sram_read(session.core(),before.data(),before.size());
    rejected=false;try{session.openItems();}catch(...){rejected=true;}wiiz_core_sram_read(session.core(),after.data(),after.size());
    require(rejected&&before==after,"Battle inventory editor was not rejected");
    session.saveState(5);session.loadState(5);rejected=false;try{session.openItems();}catch(...){rejected=true;}
    require(rejected,"Restored battle state accepted item editor");
    std::printf("ITEM_BATTLE_OK scenario=%u entry=original scene_rejected=1 state_restore_rejected=1\n",entry.identity.scenario);return 0;
}

int itemsScenesCheck(const char* romPath,const char* folderPath) {
    auto entry=identifyRom(pathFromUtf8(romPath));auto folder=pathFromUtf8(folderPath);unsigned game=entry.identity.scenario;
    auto owner=std::make_unique<Session>(entry,folder/"saves",SaveFormat::Json);auto& session=*owner;session.stateFolder(folder/"states");
    auto press=[](Session& play,unsigned b){play.input(b);for(unsigned i=0;i<8;++i)play.frame();play.input(0);for(unsigned i=0;i<120;++i)play.frame();};
    auto shot=[&](Session& play,const std::string& name){auto* image=SDL_CreateSurfaceFrom(256,240,SDL_PIXELFORMAT_RGBA32,play.pixels.data(),1024);SDL_SaveBMP(image,utf8(folder/("scene-"+name+".bmp")).c_str());SDL_DestroySurface(image);};
    auto read=[](Session& play){std::vector<uint8_t> ram(8192);require(wiiz_core_sram_read(play.core(),ram.data(),ram.size()),"Scene inventory read failed");return ram;};
    unsigned count=game==1?0x5c:0x53,flags=game==1?0x4c:0x43;
    auto offset=[&](unsigned slot){return game==1?(slot-1)*256:0x400+(slot-1)*96;};
    auto seed=[&](Session& play){auto members=play.openItems();auto ram=read(play);unsigned at=offset(members[0].slot);ram[at+count]=2;
        for(unsigned i=0;i<8;++i){ram[at+flags+i]=i==1?32:0;ram[at+flags+8+i]=i<2?(game==2?13:1)+i:255;}
        repairBattery(ram,game);wiiz_core_sram_write(play.core(),ram.data(),ram.size());};
    unsigned scenes=0;
    auto check=[&](Session& play,const std::string& name) {
        shot(play,name);auto before=play.openItems();require(before[0].items.size()==2,"Scene lost inventory before edit");
        auto screen=std::make_unique<decltype(play.pixels)>(play.pixels);auto after=before;std::swap(after[0].items[0],after[0].items[1]);
        play.updateItems(before,after);require(play.pixels==*screen,"Item edit changed original scene");
        for(unsigned i=0;i<120;++i)play.frame();auto resumed=play.openItems();
        require(resumed==after,"Native scene overwrote edited inventory");
        std::printf("ITEM_SCENE_OK %s count=%zu\n",name.c_str(),resumed.size());std::fflush(stdout);++scenes;
    };
    for(const auto& route:std::vector<std::pair<std::string,std::vector<unsigned>>>{{"dungeon",{}},{"camp",{PAD_B}},{"camp-person",{PAD_B,PAD_A}},{"camp-detail",{PAD_B,PAD_A,PAD_DOWN,PAD_A}}}) {
        session.loadState(1);seed(session);for(unsigned key:route.second)press(session,key);check(session,route.first);session.saveState(3);
    }
    std::ifstream replay("tests/replays/wiz1-dungeon.txt");require(bool(replay),"Missing party replay");
    struct Event {unsigned frame,key;bool down;};std::vector<Event> events;std::string line;
    while(std::getline(replay,line)){unsigned frame;std::string key,action;std::istringstream row(line);if(!(row>>frame>>key>>action))continue;unsigned b=key=="X"?PAD_A:key=="Z"?PAD_B:PAD_DOWN;events.push_back({frame,b,action=="down"});}
    auto townSession=[&](bool inspect) {
        auto next=std::make_unique<Session>(entry,folder/("town-saves-"+std::to_string(SDL_GetPerformanceCounter())),SaveFormat::Json);
        next->stateFolder(folder/"states");unsigned held=0;
        for(unsigned frame=0;frame<2251;++frame) {
            for(const auto& e:events)if(e.frame==frame){if(e.down)held|=e.key;else held&=~e.key;}
            next->input(held);next->frame();
            if(frame==1700){seed(*next);if(inspect)check(*next,"tavern-roster");}
            if(inspect&&frame==1950)check(*next,"tavern");
        }
        return next;
    };
    {auto town=townSession(true);check(*town,"castle");town->saveState(4);}
    for(unsigned facility=1;facility<=3;++facility) {
        auto town=townSession(false);
        for(unsigned n=0;n<facility;++n)press(*town,PAD_DOWN);press(*town,PAD_A);
        std::string name=facility==1?"inn":facility==2?"shop":"temple";check(*town,name);
        if(facility<3){press(*town,PAD_A);check(*town,name+"-person");}
        if(facility==2){press(*town,PAD_DOWN);press(*town,PAD_A);check(*town,"shop-inventory");}
        press(*town,PAD_B);require(!town->openItems().empty(),"Leaving facility lost party inventory");
    }
    {auto town=townSession(false);for(unsigned n=0;n<4;++n)press(*town,PAD_DOWN);press(*town,PAD_A);check(*town,"town-edge");
        for(unsigned n=0;n<4;++n)press(*town,PAD_DOWN);press(*town,PAD_A);shot(*town,"training");
        if(read(*town)[game==1?0x1def:0xb81])check(*town,"training");
        else {bool denied=false;try{town->openItems();}catch(...){denied=true;}require(denied,"Native training disband accepted an empty party");std::puts("ITEM_SCENE_OK training original_party_disband=1 no_party_rejected=1");}}
    itemsBattleCheck(romPath,folderPath);
    std::printf("ITEM_SCENES_OK scenario=%u scenes=%u battle_rejected=1 battle_state_restore=1\n",game,scenes);return 0;
}
