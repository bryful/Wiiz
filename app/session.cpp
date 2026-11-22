#include "session.hpp"
#include "user_storage.hpp"
#include "picosha2.h"
#include "save_json.hpp"
#include "json.hpp"
#include "wiz1_bugfix_data.hpp"
#include <SDL3/SDL.h>
#include <algorithm>
#include <cctype>
#include <chrono>
#include <fstream>
#include <iterator>
#include <memory>
#include <stdexcept>

namespace {
uint64_t experienceThreshold(unsigned scenario,unsigned cls,unsigned level) {
            // Cumulative thresholds from emonoya.net/faq/chara/exp_1-3.html.
            static const uint32_t thresholds[13][8]={
                {1000,1100,1050,900,1200,1250,1300,1450},
                {1724,1896,1810,1551,2105,2192,2280,2543},
                {2972,3268,3120,2674,3692,3845,4000,4461},
                {5124,5634,5379,4610,6477,6745,7017,7829},
                {8834,9713,9274,7948,11363,11833,12310,13729},
                {15231,16746,15989,13703,19935,20759,21596,24085},
                {26260,28872,27567,23625,34973,36419,37887,42254},
                {45275,49779,47529,40732,61356,63892,66468,74129},
                {78060,85825,81946,70227,107642,112091,116610,130050},
                {134586,147974,141289,121081,188845,196650,204578,228157},
                {232044,255127,243596,208760,331307,345000,358908,400275},
                {400075,439874,419993,359931,581240,605263,629663,702236},
                {289709,318529,304132,260639,438479,456601,475008,529757}};
    uint64_t target=level<=12?thresholds[level-1][cls]:
        uint64_t(thresholds[11][cls])+uint64_t(level-12)*thresholds[12][cls];
    if(scenario!=1&&level>=1012)target+=uint64_t(10000)*thresholds[12][cls];
    return target;
}
unsigned experienceLevel(unsigned scenario,unsigned cls,uint64_t value) {
    unsigned low=1,high=65535;
    while(low<high) {
        const unsigned middle=low+(high-low)/2;
        if(experienceThreshold(scenario,cls,middle)<=value)low=middle+1;else high=middle;
    }
    return low;
}
struct RosterIdentityBits {unsigned offset, shift;};
RosterIdentityBits rosterIdentityBits(unsigned scenario,Session::RosterField field) {
    const bool race=field==Session::RosterField::Race;
    // FC1–3 field layouts from bryful/Wiz (MIT), also used by save_json.cpp.
    if(scenario==1)return {race?0x0au:0x0bu,0};
    return {0x0a,race?5u:2u};
}
size_t rosterRecordOffset(unsigned scenario,unsigned slot) {
    return scenario==1?(slot-1)*256:0x400+(slot-1)*96;
}
}

namespace fs = std::filesystem;
fs::path pathFromUtf8(std::string_view path) {
    return fs::path(std::u8string(path.begin(), path.end()));
}
std::string utf8(const fs::path& path) {
    const auto s = path.u8string(); return {s.begin(), s.end()};
}
static std::vector<uint8_t> readBytes(const fs::path& path, size_t limit = 1024*1024) {
    return userstore::read(path,limit);
}
RomEntry identifyRom(const fs::path& path) {
    const auto bytes = readBytes(path);
    const auto sha = picosha2::hash256_hex_string(bytes);
    const auto identity=inspectWizardry(bytes.data(),bytes.size());
    const char* names[]={"","Wizardry FC I","Wizardry FC II","Wizardry FC III"};
    return {path,names[identity.scenario],sha,identity};
}
std::vector<RomEntry> scanRoms(const fs::path& folder, int& rejected) {
    rejected = 0;
    std::vector<RomEntry> entries;
    for (const auto& item : fs::directory_iterator(folder)) {
        if (!item.is_regular_file()) continue;
        auto ext = utf8(item.path().extension());
        std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c) { return char(std::tolower(c)); });
        if (ext != ".nes") continue;
        try { entries.push_back(identifyRom(item.path())); } catch (const std::exception&) { ++rejected; }
    }
    std::sort(entries.begin(), entries.end(), [](const auto& a, const auto& b) { return a.title == b.title ? a.path < b.path : a.title < b.title; });
    return entries;
}
Session::Session(const RomEntry& entry, const fs::path& saveFolder, SaveFormat format, bool skipMaker) : title(entry.title), rom_(readBytes(entry.path)), romStem_(entry.path.stem()), sha_(entry.sha) {
    saveFormat_=format;skipMaker_=skipMaker;
    const auto identity=inspectWizardry(rom_.data(),rom_.size());
    rosterFontOffset_=identity.prgOffset+identity.prgBytes+(identity.scenario==1?4:1)*4096;
    scenario_=identity.scenario;structuredSave_=identity.knownLayout;enhanced_=identity.enhanced;skipSupported_=identity.verifiedBoot;
    if (picosha2::hash256_hex_string(rom_) != entry.sha) throw std::runtime_error("ROM changed after folder scan");
    bugFixSupported_=scenario_==1 && identity.enhancedWiz1;
    for(const auto& b:wiz1FixBytes)if(identity.prgOffset+b.offset>=rom_.size() || rom_[identity.prgOffset+b.offset]!=b.original)bugFixSupported_=false;
    if(supportsTurbo()) { dungeon_=readDungeon(utf8(entry.path).c_str());explored_.resize(dungeon_.floors.size()*400,0); }
    core_ = wiiz_core_new(rom_.data(), rom_.size());
    if (!core_) throw std::runtime_error("Emulator initialization failed");
    if(supportsTurbo())wiiz_core_profile(core_,scenario_);
    try {
        if (!saveFolder.empty()) {
            userstore::mkdir(saveFolder);
            savePath_ = saveFolder / romStem_;
            savePath_ += format==SaveFormat::Sav?".sav":".json";
            mapPath_=savePath_;mapPath_.replace_extension(".map.json");
            stateFolder_ = saveFolder.parent_path() / "states";
            batterySaved_=userstore::exists(savePath_);
            fs::path source=savePath_;
            if(!batterySaved_) {
                auto alternative=savePath_;alternative.replace_extension(format==SaveFormat::Sav?".json":".sav");
                if(userstore::exists(alternative))source=alternative;
                else if(userstore::exists(saveFolder/(entry.sha+".json")))source=saveFolder/(entry.sha+".json");
                else source=saveFolder/(entry.sha+".sav");
            }
            if(userstore::exists(source)) {
                previousSave_=readBytes(source,1024*1024*4);
                // Preserve the exact on-disk input before normalization or ROM startup.
                const auto backupDir=saveFolder/"backups"/entry.path.stem();userstore::mkdir(backupDir);
                const auto stamp=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                const auto prefix=std::to_string(stamp)+"-"+std::to_string(SDL_GetPerformanceCounter())+"-";
                userstore::copy(source,backupDir/pathFromUtf8(prefix+utf8(source.filename())));
                if(userstore::exists(mapPath_))userstore::copy(mapPath_,backupDir/pathFromUtf8(prefix+utf8(mapPath_.filename())));

                if(source.extension()==".json") {
                    const auto document=nlohmann::ordered_json::parse(previousSave_.begin(),previousSave_.end());
                    if(supportsTurbo() && document.contains("exploration")) {
                        const auto& cells=document.at("exploration");
                        if(!cells.is_array()||cells.size()!=explored_.size())throw std::runtime_error("Invalid explored-map data");
                        for(size_t i=0;i<cells.size();++i) {if(!cells[i].is_number_integer() || cells[i]<0 || cells[i]>1)throw std::runtime_error("Invalid explored-map cell");explored_[i]=cells[i].get<uint8_t>();}
                    }
                    if(structuredSave_)previousSave_=decodeBattery(std::string(previousSave_.begin(),previousSave_.end()),scenario_,sha_);
                    else {
                        if(document.at("format")!="wiiz-battery-raw"||document.at("version")!=1||document.at("rom_sha256")!=sha_||document.at("scenario")!=scenario_)
                            throw std::runtime_error("Raw battery JSON format/version/ROM mismatch");
                        const auto& data=document.at("bytes");
                        if(!data.is_array()||data.size()!=wiiz_core_sram_size(core_))throw std::runtime_error("Raw battery RAM size mismatch");
                        previousSave_.clear();for(const auto& v:data){if(!v.is_number_integer()||v<0||v>255)throw std::runtime_error("Invalid raw battery byte");previousSave_.push_back(v.get<uint8_t>());}
                    }
                } else {
                    if(structuredSave_){auto original=previousSave_;repairBattery(previousSave_,scenario_);if(original!=previousSave_)batterySaved_=false;}
                    if(supportsTurbo() && userstore::exists(mapPath_)) {
                        const auto raw=readBytes(mapPath_);const auto doc=nlohmann::ordered_json::parse(raw.begin(),raw.end());
                        if(doc.at("format")!="wiiz-exploration" || doc.at("version")!=1 || doc.at("rom_sha256")!=sha_)throw std::runtime_error("Exploration file does not match ROM");
                        const auto& cells=doc.at("exploration");if(!cells.is_array()||cells.size()!=explored_.size())throw std::runtime_error("Invalid exploration size");
                        for(size_t i=0;i<cells.size();++i){if(!cells[i].is_number_integer()||cells[i]<0||cells[i]>1)throw std::runtime_error("Invalid explored cell");explored_[i]=cells[i].get<uint8_t>();}
                    }
                }
                if (previousSave_.size() != wiiz_core_sram_size(core_) || !wiiz_core_sram_write(core_, previousSave_.data(), previousSave_.size()))
                    throw std::runtime_error("Invalid battery save size. Original save was not modified.");
            }
        }
        if(structuredSave_) {
            wiiz_core_turbofile_attach(core_);previousTurboFile_.resize(8192,0);
            if(!saveFolder.empty()) {
                turboFilePath_=saveFolder.parent_path()/"turbofile.tbf";
                if(userstore::exists(turboFilePath_)) {
                    previousTurboFile_=readBytes(turboFilePath_,8192);
                    if(previousTurboFile_.size()!=8192)throw std::runtime_error("Turbo File image must be 8192 bytes");
                }
            }
            wiiz_core_turbofile_write(core_,previousTurboFile_.data(),previousTurboFile_.size());
        }
        if(skipMaker_)skipManufacturer();
    } catch (...) { wiiz_core_delete(core_); core_ = nullptr; throw; }
}
Session::~Session() { wiiz_core_delete(music_); wiiz_core_delete(core_); }
void Session::bugFix(bool enabled) {
    if(enabled==bugFix_)return;
    if(!bugFixSupported_)throw std::runtime_error("Wiz1 bug Fix is unavailable for this ROM revision");
    save();
    const size_t prgOffset=16+((rom_[6]&4)?512:0);
    // Keep ROM identity/save keys from the original file; only the private copy changes.
    for(const auto& b:wiz1FixBytes) {
        const uint8_t value=enabled?b.fixed:b.original;
        rom_[prgOffset+b.offset]=value;
        if(!wiiz_core_prg_byte(core_,b.offset,value))throw std::runtime_error("Cannot change ROM patch");
    }
    bugFix_=enabled;
    reset();
}
void Session::startMusic() {
    music_ = wiiz_core_new(rom_.data(), rom_.size());
    if (!music_) throw std::runtime_error("Music core initialization failed");
    wiiz_core_profile(music_,scenario_);
    wiiz_core_sound_player(music_);
    for (int i=0; i<600; ++i)
        if (!wiiz_core_frame(music_)) throw std::runtime_error("Music core initialization stopped");
    for (unsigned r=0; r<3; ++r) wiiz_core_sound_command(music_, r, 0);
    wiiz_core_frame(music_);
    wiiz_core_frame(music_);
    wiiz_core_sound_command(music_, 0, wiiz_core_current_sound(core_, 0));
    wiiz_core_sound_source(core_);
    for (unsigned r=0; r<3; ++r) wiiz_core_take_sound(core_, r);
}
void Session::reset() {
    if(assistMask_ && structuredSave_) {
        std::vector<uint8_t> ram(8192);
        if(!wiiz_core_sram_read(core_,ram.data(),ram.size()))throw std::runtime_error("Cannot preserve assisted roster");
        repairBattery(ram,scenario_);
        if(!wiiz_core_sram_write(core_,ram.data(),ram.size()))throw std::runtime_error("Cannot repair assisted roster");
    }
    wiiz_core_reset(core_);
    wiiz_core_delete(music_); music_ = nullptr;
    previousHeld_ = 0;
    spellMap_.mode=0;mapResume_=0;wiiz_core_map_event(core_);
    for (unsigned r=0; r<3; ++r) wiiz_core_take_sound(core_, r);
    if(skipMaker_)skipManufacturer();
}
void Session::tick(unsigned held, unsigned speed, uint64_t milliseconds) {
    speed = supportsTurbo() ? std::clamp(speed, 1u, 8u) : 1;
    if (speed > 1 && !music_) startMusic();
    if(spellMap_.mode) {
        for(unsigned i=0;i<4;++i) {
            const unsigned bit=PAD_UP<<i;
            if(!(held&bit)||!(previousHeld_&bit))repeatAt_[i]=milliseconds+200;
            else if(milliseconds>=repeatAt_[i]){mapKey(bit);repeatAt_[i]=milliseconds+100;}
        }
        previousHeld_=held;
        if(!music_)startMusic();
        if(!wiiz_core_frame(music_))throw std::runtime_error("Music core stopped");
        return;
    }
    unsigned due = 0;
    for (unsigned i=0; i<4; ++i) {
        const unsigned bit = PAD_UP << i;
        if (!(held & bit) || !(previousHeld_ & bit)) repeatAt_[i] = milliseconds + 200;
        else if (milliseconds >= repeatAt_[i]) { due |= bit; repeatAt_[i] = milliseconds + 100; }
    }
    previousHeld_ = held;
    wiiz_core_input(core_, held);
    for (unsigned i=0; i<speed; ++i) {
        if(mapResume_) {held=mapResume_>4?0:mapResume_>2?mapButton_:0;wiiz_core_input(core_,held);--mapResume_;}
        if (supportsTurbo() && music_) wiiz_core_repeat(core_, held, i == 0 ? due : 0);
        if (!wiiz_core_frame(core_)) throw std::runtime_error("Game core stopped");
        pollMap();
        if (music_ && scenario_>1) wiiz_core_sound_command(music_,3,wiiz_core_current_sound(core_,3));
        if (music_) for (unsigned r=0; r<3; ++r) {
            const unsigned command = wiiz_core_take_sound(core_, r);
            if (command & 0x100) wiiz_core_sound_command(music_, r, command & 0xff);
        }
        if(spellMap_.mode)break;
    }
    wiiz_core_pixels(core_, pixels.data());
    if (music_ && !wiiz_core_frame(music_)) throw std::runtime_error("Music core stopped");
}
const float* Session::audio(size_t* count) { return wiiz_core_audio(music_ ? music_ : core_, count); }
void Session::frame() {
    if(spellMap_.mode)return;
    if (!wiiz_core_frame(core_)) throw std::runtime_error("Emulation stopped: invalid opcode or frame timeout");
    wiiz_core_pixels(core_, pixels.data());
    pollMap();
}
bool Session::explored(int floor,int x,int y) const {
    return floor>=1&&floor<=int(dungeon_.floors.size())&&x>=0&&x<20&&y>=0&&y<20&&explored_[(floor-1)*400+y*20+x];
}
void Session::pollMap() {
    if(!supportsTurbo())return;
    const unsigned events=wiiz_core_map_event(core_),p=wiiz_core_map_position(core_);
    const int x=p&255,y=(p>>8)&255,f=(p>>16)&255;
    if(x>=20||y>=20||f<1||f>int(dungeon_.floors.size()))return;
    if(events&4) {auto& cell=explored_[(f-1)*400+y*20+x];if(!cell){cell=1;mapDirty_=true;}}
    if(events&3) {
        spellMap_={events&2?2u:1u,f,x,y,int(p>>24),f,x,y};
        auto& cell=explored_[(f-1)*400+y*20+x];if(!cell){cell=1;mapDirty_=true;}
        wiiz_core_input(core_,0);
    }
}
std::string Session::positionText() const {
    if(!enhanced_)return "";
    const unsigned p=wiiz_core_map_position(core_);
    const unsigned x=p&255,y=(p>>8)&255,f=(p>>16)&255;
    if(f==0)return "SURFACE   M: Map";
    if(x>=20||y>=20||f>dungeon_.floors.size())return "Position unavailable";
    static const char* headings[]={"N","E","S","W"};
    return "B"+std::to_string(f)+"  E:"+std::to_string(x)+"  N:"+std::to_string(y)+"  "+headings[(p>>24)&3]+"    M: Map";
}
void Session::openMap() {
    if(!enhanced_||spellMap_.mode)return;
    const unsigned p=wiiz_core_map_position(core_);
    const int x=p&255,y=(p>>8)&255,f=(p>>16)&255;
    if(x>=20||y>=20||f<1||f>int(dungeon_.floors.size()))return;
    // Mode 3 is host navigation, separate from the original MALOR spell.
    spellMap_={3,f,x,y,int((p>>24)&3),f,x,y};
    releaseInput();
}
void Session::assists(unsigned mask,bool ready) {
    if(mask>63)throw std::runtime_error("Invalid assist settings");
    if(mask && !enhanced_)throw std::runtime_error("Unverified assist layout");
    if(mask&32) {
        const size_t at=16+((rom_[6]&4)?512:0)+(scenario_==1?0x18ad5:scenario_==2?0x1f34b:0x1f3c7);
        if(rom_.at(at)!=(scenario_==1?0x25:0xd0)||rom_.at(at+1)!=(scenario_==1?0x0f:0x06))
            throw std::runtime_error("Unverified tavern alignment check");
    }
    const unsigned previous=assistMask_;
    assistMask_=mask;wiiz_core_assists(core_,mask,ready);
    if(previous && !mask) {
        std::vector<uint8_t> ram(8192);if(!wiiz_core_sram_read(core_,ram.data(),ram.size()))throw std::runtime_error("Cannot read assisted roster");
        repairBattery(ram,scenario_);if(!wiiz_core_sram_write(core_,ram.data(),ram.size()))throw std::runtime_error("Cannot repair assisted roster");
    }
}
std::string Session::rosterLabel(unsigned slot) const {
    if(!structuredSave_||slot<1||slot>20)return "Unavailable";
    std::vector<uint8_t> data(8192);if(!wiiz_core_sram_read(core_,data.data(),data.size()))return "Unavailable";
    const auto* c=data.data()+(scenario_==1?(slot-1)*256:0x400+(slot-1)*96);
    const std::string prefix="Slot "+std::to_string(slot)+": ";if(!c[0])return prefix+"(empty)";
    const unsigned level=scenario_==1?35:33;
    return prefix+"Lv "+std::to_string((unsigned(c[level])<<8)|c[level+1]);
}
unsigned Session::rosterExperienceLevel(unsigned slot) const {
    if(!structuredSave_||!enhanced_||slot<1||slot>20)return 0;
    std::array<uint8_t,8192> data{};
    if(!wiiz_core_sram_read(core_,data.data(),data.size()))return 0;
    const auto* c=data.data()+(scenario_==1?(slot-1)*256:0x400+(slot-1)*96);
    if(!c[0])return 0;
    const unsigned offset=scenario_==1?0x19:0x17;
    uint64_t value=0;
    for(unsigned i=0;i<6;++i) {
        const unsigned b=c[offset+i];if((b>>4)>9||(b&15)>9)return 0;
        value=value*100+(b>>4)*10+(b&15);
    }
    return experienceLevel(scenario_,scenario_==1?(c[11]&7):((c[10]>>2)&7),value);
}
std::array<uint8_t,64> Session::fontGlyph(char character) const {
    std::array<uint8_t,64> bitmap{};
    const unsigned c=unsigned(std::toupper(static_cast<unsigned char>(character)));
    unsigned code=c;
    if(scenario_==1){if(c>='0'&&c<='9')code=c-'0';else if(c>='A'&&c<='Z')code=c-'A'+10;else return bitmap;}
    if(rosterFontOffset_+code*16+8>rom_.size())return bitmap;
    const auto* tile=rom_.data()+rosterFontOffset_+code*16;
    for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x)bitmap[y*8+x]=(tile[y]>>(7-x))&1;
    return bitmap;
}
std::array<uint8_t,64*8> Session::rosterNamePixels(unsigned slot) const {
    std::array<uint8_t,64*8> bitmap{};
    if(!structuredSave_||slot<1||slot>20)return bitmap;
    std::array<uint8_t,8192> data{};
    if(!wiiz_core_sram_read(core_,data.data(),data.size()))return bitmap;
    const auto* c=data.data()+(scenario_==1?(slot-1)*256:0x400+(slot-1)*96);
    if(!c[0])return bitmap;
    // Original text tiles: I uses CHR 4 KiB bank 4; II/III use bank 1.
    // Reuse extract_chr.py's NES planar layout, directly from this ROM.
    // Font ink is bitplane 0; III sets bitplane 1 even on the background.
    const size_t font=rosterFontOffset_;
    if(font+4096>rom_.size())return bitmap;
    for(unsigned i=0;i<std::min(unsigned(c[1]),8u);++i) {
        const auto* tile=rom_.data()+font+unsigned(c[2+i])*16;
        for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x)
            bitmap[y*64+i*8+x]=(tile[y]>>(7-x))&1;
    }
    return bitmap;
}
bool Session::canSwapRoster() const {return enhanced_&&structuredSave_&&wiiz_core_roster_editable(core_);}
void Session::swapRoster(unsigned first,unsigned second) {reorderRoster(first,second,false);}
void Session::moveRoster(unsigned first,unsigned last) {reorderRoster(first,last,true);}
void Session::reorderRoster(unsigned first,unsigned second,bool move) {
    if(!canSwapRoster())throw std::runtime_error("Reset first; open Q at the title before pressing game buttons.");
    if(first<1||first>20||second<1||second>20)throw std::runtime_error("Roster slots must be 1..20");
    if(first==second)return;
    std::vector<uint8_t> original(8192);if(!wiiz_core_sram_read(core_,original.data(),original.size()))throw std::runtime_error("Cannot read roster");
    auto updated=original;
    if(move) {
        for(unsigned at=first;at!=second;) {const unsigned next=at<second?at+1:at-1;swapRosterRecords(updated,scenario_,at,next);at=next;}
    } else swapRosterRecords(updated,scenario_,first,second);
    commitRoster(original,updated);
    reset();skipManufacturer();
}
bool Session::supportsRosterIdentity() const {return enhanced_&&structuredSave_;}
int Session::rosterIdentity(unsigned slot, RosterField field) const {
    if(!supportsRosterIdentity()||slot<1||slot>20)return -1;
    std::array<uint8_t,8192> data{};
    if(!wiiz_core_sram_read(core_,data.data(),data.size()))return -1;
    const auto* record=data.data()+rosterRecordOffset(scenario_,slot);
    const auto [offset,shift]=rosterIdentityBits(scenario_,field);
    return record[0]?((record[offset]>>shift)&7):-1;
}
void Session::setRosterIdentity(unsigned slot, RosterField field, unsigned value) {
    if(!supportsRosterIdentity())throw std::runtime_error("Race and class editing requires a supported ROM.");
    const bool race=field==RosterField::Race;
    if(slot<1||slot>20||value>=(race?5u:8u))throw std::runtime_error("Invalid roster identity edit");
    std::vector<uint8_t> original(8192);
    if(!wiiz_core_sram_read(core_,original.data(),original.size()))throw std::runtime_error("Cannot read roster");
    const size_t start=rosterRecordOffset(scenario_,slot);
    if(!original[start])throw std::runtime_error("This roster slot is empty");
    const auto [offset,shift]=rosterIdentityBits(scenario_,field);
    const size_t index=start+offset;
    const unsigned mask=7u<<shift;
    const unsigned bits=value<<shift;
    if((original[index]&mask)==bits)return;
    auto updated=original;
    updated[index]=uint8_t((updated[index]&~mask)|bits);
    repairBattery(updated,scenario_);
    commitRoster(original,updated);
}
void Session::commitRoster(std::vector<uint8_t>& original,std::vector<uint8_t>& updated) {
    save();
    if(!savePath_.empty()) {
        const auto dir=savePath_.parent_path()/"backups"/savePath_.stem();userstore::mkdir(dir);
        const auto stamp=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
        userstore::copy(savePath_,dir/pathFromUtf8(std::to_string(stamp)+"-"+std::to_string(SDL_GetPerformanceCounter())+"-before-roster"+utf8(savePath_.extension())));
    }
    if(!wiiz_core_sram_write(core_,updated.data(),updated.size()))throw std::runtime_error("Cannot update roster");
    try {save();}catch(...){wiiz_core_sram_write(core_,original.data(),original.size());throw;}
}
void Session::battleMultipliers(unsigned experience, unsigned gold) {
    if (!enhanced_) return;
    battleExpMultiplier_ = experience;
    battleGoldMultiplier_ = gold;
    wiiz_core_battle_multipliers(core_, experience, gold);
}
void Session::rosterBonus(unsigned slot,unsigned kind,uint64_t amount) {
    if(!structuredSave_||!enhanced_)throw std::runtime_error("Unverified character layout");
    if(slot<1||slot>20||kind>3||(kind==3&&amount>2))throw std::runtime_error("Invalid roster bonus");
    std::vector<uint8_t> data(8192);
    if(!wiiz_core_sram_read(core_,data.data(),data.size()))throw std::runtime_error("Cannot read roster");
    auto* c=data.data()+(scenario_==1?(slot-1)*256:0x400+(slot-1)*96);
    if(!c[0])throw std::runtime_error("This roster slot is empty");
    // bryful/Wiz character field offsets, MIT; see third_party/wiz-save/.
    if(kind<2) {
        const unsigned offset=(scenario_==1?0x13:0x11)+(kind==0?6:0);
        uint64_t value=0;
        for(unsigned i=0;i<6;++i){const unsigned b=c[offset+i];if((b>>4)>9||(b&15)>9)throw std::runtime_error("Invalid decimal roster value");value=value*100+(b>>4)*10+(b&15);}
        if(kind==0) {
            const unsigned cls=scenario_==1?(c[11]&7):((c[10]>>2)&7);
            const unsigned level=experienceLevel(scenario_,cls,value);
            if(level==65535)throw std::runtime_error("No further experience threshold is available");
            value=experienceThreshold(scenario_,cls,level);
        } else value+=std::min<uint64_t>(amount,999999999999ULL-value);
        for(int i=5;i>=0;--i){c[offset+i]=uint8_t(((value/10)%10)*16+value%10);value/=100;}
    } else if(kind==3) {
        const unsigned at=scenario_==1?12:10;
        c[at]=uint8_t((c[at]&0xfc)|unsigned(amount));
    } else if(scenario_==1) {
        std::fill_n(c+0x45,6,uint8_t(255));c[0x4b]|=3;
    } else {
        const size_t at=(scenario_==2?0x1a9ac:0x1ae6c)+((rom_[6]&4)?512:0);
        // Existing ROM spell-level boundaries, as used by tools/item_spell_data.py.
        for(unsigned school=0;school<2;++school)for(unsigned level=0;level<7;++level) {
            const unsigned count=rom_.at(at+school*8+level+1)-rom_.at(at+school*8+level);
            if(count>8)throw std::runtime_error("Unverified spell count");
            c[0x35+school*7+level]|=uint8_t((1u<<count)-1);
        }
    }
    repairBattery(data,scenario_);
    if(!wiiz_core_sram_write(core_,data.data(),data.size()))throw std::runtime_error("Cannot update roster");
}
void Session::mapKey(unsigned button) {
    if(!spellMap_.mode)return;
    auto& m=spellMap_;
    if(m.mode==2||m.mode==3) {
        if(m.targetFloor>0) {
            if(button==PAD_UP)m.targetY=(m.targetY+1)%20;
            if(button==PAD_DOWN)m.targetY=(m.targetY+19)%20;
            if(button==PAD_LEFT)m.targetX=(m.targetX+19)%20;
            if(button==PAD_RIGHT)m.targetX=(m.targetX+1)%20;
        }
        if(button==PAD_SELECT)m.targetFloor=m.targetFloor==0?int(dungeon_.floors.size()):m.targetFloor-1;
        if(button==PAD_START)m.targetFloor=m.targetFloor==int(dungeon_.floors.size())?0:m.targetFloor+1;
        if(m.targetFloor==0)m.targetX=m.targetY=0;
    }
    if(button==PAD_A||button==PAD_B) {
        if(m.mode==3&&button==PAD_A) {
            if(!wiiz_core_map_warp(core_,m.targetFloor,m.targetX,m.targetY))throw std::runtime_error("Map movement is available in the dungeon or camp; finish battles and treasure first");
            wiiz_core_pixels(core_,pixels.data());
        }
        if(m.mode==2&&button==PAD_A)wiiz_core_map_destination(core_,m.targetX-m.x,m.targetY-m.y,m.targetFloor-m.floor);
        mapButton_=m.mode==3?0:button;mapResume_=m.mode==3?0:6;m.mode=0;previousHeld_=0;wiiz_core_input(core_,0);
    }
}
void Session::saveTurboFile() {
    if(turboFilePath_.empty())return;
    std::vector<uint8_t> bytes(8192);wiiz_core_turbofile_read(core_,bytes.data(),bytes.size());
    if(bytes==previousTurboFile_)return;
    if(userstore::exists(turboFilePath_)) {
        const auto disk=readBytes(turboFilePath_,8192);
        if(disk!=previousTurboFile_)throw std::runtime_error("Turbo File changed in another session; close other Wiiz instances.");
        const auto folder=turboFilePath_.parent_path()/"backups"/"turbofile";userstore::mkdir(folder);
        userstore::write(folder/(std::to_string(SDL_GetPerformanceCounter())+".tbf"),reinterpret_cast<const char*>(disk.data()),disk.size());
    }
    userstore::write(turboFilePath_,reinterpret_cast<const char*>(bytes.data()),bytes.size());previousTurboFile_=std::move(bytes);
}
void Session::save() {
    saveTurboFile();
    if (savePath_.empty()) return;
    std::vector<uint8_t> bytes(wiiz_core_sram_size(core_));
    if (bytes.empty()) return;
    if (!wiiz_core_sram_read(core_, bytes.data(), bytes.size())) throw std::runtime_error("Cannot read battery RAM");
    if(structuredSave_ && assistMask_)repairBattery(bytes,scenario_);
    if (batterySaved_ && bytes == previousSave_ && !mapDirty_) return;
    auto write=[&](const fs::path& path,const char* data,size_t size){
        userstore::write(path,data,size);
    };
    if(saveFormat_==SaveFormat::Sav) {
        if(supportsTurbo() && (!batterySaved_ || mapDirty_)) {
            const auto map=nlohmann::ordered_json{{"format","wiiz-exploration"},{"version",1},{"rom_sha256",sha_},{"exploration",explored_}}.dump(2)+"\n";
            write(mapPath_,map.data(),map.size());
        }
        write(savePath_,reinterpret_cast<const char*>(bytes.data()),bytes.size());
    } else {
    auto document=structuredSave_?nlohmann::ordered_json::parse(encodeBattery(bytes,scenario_,sha_)):
        nlohmann::ordered_json{{"format","wiiz-battery-raw"},{"version",1},{"rom_sha256",sha_},{"scenario",scenario_},{"checksum_validation",false},{"bytes",bytes}};
    if(supportsTurbo())document["exploration"]=explored_;
        const auto text=document.dump(2)+"\n";write(savePath_,text.data(),text.size());
    }
    batterySaved_ = true;
    mapDirty_=false;
    previousSave_ = std::move(bytes);
}

namespace {
using Json = nlohmann::ordered_json;
std::vector<uint8_t> snapshot(WiizCore* core) {
    std::vector<uint8_t> data(wiiz_core_state_size(core));
    if(!wiiz_core_state_write(core,data.data(),data.size()))throw std::runtime_error("Core state capture failed");
    return data;
}
std::string hexBytes(const std::vector<uint8_t>& data) {
    static const char digits[]="0123456789abcdef";std::string text; text.reserve(data.size()*2);
    for(auto b:data){text+=digits[b>>4];text+=digits[b&15];}return text;
}
std::vector<uint8_t> unhex(const std::string& text, size_t size) {
    if(text.size()!=size*2)throw std::runtime_error("State payload size mismatch");
    auto digit=[](char c)->unsigned {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("Invalid state payload");};
    std::vector<uint8_t> data(size);for(size_t i=0;i<size;++i)data[i]=uint8_t(digit(text[i*2])*16+digit(text[i*2+1]));return data;
}
Json statePart(WiizCore* core) {
    const auto data=snapshot(core);
    Json part={{"bytes",hexBytes(data)},{"integrity_sha256",picosha2::hash256_hex_string(data)}};
    uint8_t regs[6];wiiz_core_turbofile_registers(core,regs);
    if(regs[4]) {
        std::vector<uint8_t> tf(8198);wiiz_core_turbofile_read(core,tf.data(),8192);std::copy(regs,regs+6,tf.begin()+8192);
        part["turbofile"]={{"bytes",hexBytes(tf)},{"integrity_sha256",picosha2::hash256_hex_string(tf)}};
    }
    return part;
}
void restorePart(WiizCore* core,const Json& part) {
    const auto data=unhex(part.at("bytes").get<std::string>(),wiiz_core_state_size(core));
    if(part.at("integrity_sha256")!=picosha2::hash256_hex_string(data))throw std::runtime_error("State payload is damaged");
    if(!wiiz_core_state_read(core,data.data(),data.size()))throw std::runtime_error("Incompatible core state");
    if(part.contains("turbofile")) {
        const auto& t=part.at("turbofile");const auto tf=unhex(t.at("bytes").get<std::string>(),8198);
        if(t.at("integrity_sha256")!=picosha2::hash256_hex_string(tf)||!wiiz_core_turbofile_restore(core,tf.data(),tf.size()))throw std::runtime_error("Invalid Turbo File state");
    }
}
}
fs::path Session::statePath(unsigned slot) const {
    if(slot<1||slot>5)throw std::runtime_error("State slot must be 1..5");
    if(stateFolder_.empty())throw std::runtime_error("State folder is unavailable");
    auto path = stateFolder_ / romStem_;
    path += ".stot" + std::to_string(slot) + ".state";
    return path;
}
fs::path Session::legacyStatePath(unsigned slot) const {
    return stateFolder_ / sha_ / ("slot" + std::to_string(slot) + ".json");
}
bool Session::hasState(unsigned slot) const {
    if(stateFolder_.empty())return false;
    try {return userstore::exists(statePath(slot)) || userstore::exists(legacyStatePath(slot));}catch(...){return false;}
}
void Session::saveState(unsigned slot) {
    const auto path=statePath(slot);userstore::mkdir(path.parent_path());
    Json doc={{"format","wiiz-state"},{"version",1},{"rom_sha256",sha_},
              {"core_revision","binjnes-e2f5871-wiiz-state1"},{"wiz1_bug_fix",bugFix_},{"assists_ready",wiiz_core_title_ready(core_)!=0},{"game",statePart(core_)},{"music",music_?statePart(music_):Json(nullptr)}};
    if(supportsTurbo()) {
        const auto& m=spellMap_;
        doc["automap"]={{"explored",explored_},{"dialog",{m.mode,m.floor,m.x,m.y,m.heading,m.targetFloor,m.targetX,m.targetY}},{"resume",mapResume_},{"button",mapButton_}};
    }
    const auto text=doc.dump(2)+"\n";
    userstore::write(path,text.data(),text.size());
}
void Session::loadState(unsigned slot) {
    const auto path = statePath(slot);
    const auto data = readBytes(userstore::exists(path) ? path : legacyStatePath(slot), 16*1024*1024);
    const auto doc=Json::parse(data.begin(),data.end());
    if(doc.at("format")!="wiiz-state"||doc.at("version")!=1||doc.at("rom_sha256")!=sha_||doc.at("core_revision")!="binjnes-e2f5871-wiiz-state1")
        throw std::runtime_error("State format/version/ROM does not match");
    using CorePtr=std::unique_ptr<WiizCore,decltype(&wiiz_core_delete)>;
    if(doc.value("wiz1_bug_fix",false)!=bugFix_)throw std::runtime_error("State Wiz1 bug Fix setting does not match; switch the setting first");
    CorePtr next(wiiz_core_new(rom_.data(),rom_.size()),wiiz_core_delete), music(nullptr,wiiz_core_delete);
    if(!next)throw std::runtime_error("Cannot initialize state core");
    wiiz_core_profile(next.get(),scenario_);
    if(structuredSave_) {
        std::vector<uint8_t> tf(8198);wiiz_core_turbofile_read(core_,tf.data(),8192);wiiz_core_turbofile_registers(core_,tf.data()+8192);
        wiiz_core_turbofile_restore(next.get(),tf.data(),tf.size());
    }
    restorePart(next.get(),doc.at("game"));
    SpellMap map;std::vector<uint8_t> explored=explored_;unsigned resume=0,button=0;
    if(supportsTurbo()) {
        wiiz_core_profile(next.get(),scenario_);
        if(doc.contains("automap")) {
            const auto& a=doc.at("automap");const auto& cells=a.at("explored");const auto& values=a.at("dialog");
            if(!cells.is_array()||cells.size()!=explored_.size()||!values.is_array()||values.size()!=8)throw std::runtime_error("Invalid state map");
            for(size_t i=0;i<cells.size();++i){if(!cells[i].is_number_integer()||cells[i]<0||cells[i]>1)throw std::runtime_error("Invalid explored state");explored[i]=cells[i].get<uint8_t>();}
            for(const auto& v:values)if(!v.is_number_integer()||v<0||v>20)throw std::runtime_error("Invalid map position");
            map={values[0].get<unsigned>(),values[1],values[2],values[3],values[4],values[5],values[6],values[7]};
            if(map.mode>3||map.floor<1||map.floor>int(dungeon_.floors.size())||map.targetFloor<0||map.targetFloor>int(dungeon_.floors.size())||map.x>=20||map.y>=20||map.targetX>=20||map.targetY>=20||map.heading>3)throw std::runtime_error("Invalid map dialog");
            resume=a.at("resume").get<unsigned>();button=a.at("button").get<unsigned>();
            if(resume>6||(button!=0&&button!=PAD_A&&button!=PAD_B))throw std::runtime_error("Invalid map resume");
        }
    }
    if(!doc.at("music").is_null()) {
        if(!supportsTurbo())throw std::runtime_error("Unexpected music core for this ROM");
        music.reset(wiiz_core_new(rom_.data(),rom_.size()));if(!music)throw std::runtime_error("Cannot initialize music state");
        wiiz_core_profile(music.get(),scenario_);
        restorePart(music.get(),doc.at("music"));
    }
    // Commit only after both snapshots have passed validation and restored successfully.
    wiiz_core_delete(core_);wiiz_core_delete(music_);core_=next.release();music_=music.release();
    wiiz_core_assists(core_,assistMask_,doc.value("assists_ready",false));
    wiiz_core_battle_multipliers(core_, battleExpMultiplier_, battleGoldMultiplier_);
    previousHeld_=0;repeatAt_.fill(0);
    spellMap_=map;explored_=std::move(explored);mapResume_=resume;mapButton_=button;mapDirty_=true;
    wiiz_core_pixels(core_,pixels.data());
}

void Session::saveFormat(SaveFormat format) {
    if(format==saveFormat_)return;
    if(savePath_.empty()){saveFormat_=format;return;}
    save();const auto old=savePath_;const auto saved=batterySaved_;const auto previous=saveFormat_;
    saveFormat_=format;savePath_.replace_extension(format==SaveFormat::Sav?".sav":".json");batterySaved_=false;
    try {save();}catch(...){savePath_=old;saveFormat_=previous;batterySaved_=saved;throw;}
}
void Session::skipManufacturer() {
    if(!skipSupported_)return;
    input(0);
    for(unsigned i=0;i<900&&!wiiz_core_title_ready(core_);++i)
        if(!wiiz_core_frame(core_))throw std::runtime_error("Startup stopped");
    wiiz_core_pixels(core_,pixels.data());previousHeld_=0;
}

namespace {
size_t inventoryOffset(unsigned scenario,unsigned slot) {
    return scenario==1?(slot-1)*256:0x400+(slot-1)*96;
}
unsigned inventoryCountOffset(unsigned scenario){return scenario==1?0x5c:0x53;}
unsigned inventoryFlagsOffset(unsigned scenario){return scenario==1?0x4c:0x43;}
unsigned inventoryLimit(unsigned scenario){return scenario==1?101:scenario==2?110:138;}
}
std::vector<Session::InventoryMember> Session::openItems() {
    if(!enhanced_||!structuredSave_)throw std::runtime_error("Item editor requires a verified ROM.");
    const size_t trainer=(rom_[6]&4)?512:0;
    auto signature=[&](size_t at,std::initializer_list<uint8_t> bytes){return at+trainer+bytes.size()<=rom_.size()&&std::equal(bytes.begin(),bytes.end(),rom_.begin()+at+trainer);};
    if((scenario_==1&&!signature(0x1ae7f,{0xa6,0x4e,0xbd,0xdc,0x7d}))||
       (scenario_==2&&(!signature(0x1bdfd,{0xa6,0x0b,0xa0,0x22})||!signature(0x1d06a,{0xa9,0x0a,0x85,0x02})))||
       (scenario_==3&&(!signature(0x19e4d,{0xa6,0x0b,0xa0,0x22})||!signature(0x1d06c,{0xa9,0x0a,0x85,0x02}))))
        throw std::runtime_error("Unverified equipment routines in this ROM.");
    if(!wiiz_core_items_pause(core_))throw std::runtime_error("Items are unavailable during battle or an unfinished inventory transfer.");
    releaseInput();wiiz_core_pixels(core_,pixels.data());
    std::array<uint8_t,8192> ram{};
    if(!wiiz_core_sram_read(core_,ram.data(),ram.size()))throw std::runtime_error("Cannot read inventory");
    unsigned count=ram[scenario_==1?0x1def:0xb81],list=scenario_==1?0x1ddc:0xb82;
    if(!count||count>6)throw std::runtime_error("A party of 1..6 is required.");
    std::vector<InventoryMember> result;
    for(unsigned n=0;n<count;++n) {
        unsigned ref=ram[list+n];
        if(scenario_==1){if(ref<0x60)throw std::runtime_error("Invalid party reference");ref-=0x60;}
        if(ref>=20||std::any_of(result.begin(),result.end(),[&](const auto& m){return m.slot==ref+1;}))throw std::runtime_error("Invalid party reference");
        const auto* c=ram.data()+inventoryOffset(scenario_,ref+1);
        unsigned size=c[inventoryCountOffset(scenario_)],flags=inventoryFlagsOffset(scenario_);
        if(!c[0]||size>8)throw std::runtime_error("Invalid inventory record");
        InventoryMember member{ref+1,{}};
        for(unsigned i=0;i<size;++i){if(c[flags+8+i]>=inventoryLimit(scenario_))throw std::runtime_error("Unverified item ID");member.items.push_back({c[flags+8+i],c[flags+i]});}
        result.push_back(std::move(member));
    }
    return result;
}
std::vector<uint8_t> Session::itemNameCodes(InventoryItem item) const {
    if(item.id>=inventoryLimit(scenario_))return {};
    const size_t trainer=(rom_[6]&4)?512:0;
    auto byte=[&](size_t at){return rom_.at(at+trainer);};
    auto word=[&](size_t at){return unsigned(byte(at))|(unsigned(byte(at+1))<<8);};
    bool unknown=(item.flags&32)!=0;std::vector<uint8_t> result;
    if(scenario_==1) {
        unsigned ptr=word((unknown?0xb010:0xb0da)+item.id*2);
        if(ptr<0x8000||ptr>=0xc000)throw std::runtime_error("Unverified item name pointer");
        size_t at=0x8010+ptr-0x8000;
        for(unsigned i=0;i<48;++i){auto b=byte(at+i);if(b==255)return result;result.push_back(b);}
    } else if(scenario_==2) {
        unsigned ptr=word(0x10010+item.id*2);
        if(ptr<0x8000||ptr>=0xc000)throw std::runtime_error("Unverified item pointer");
        size_t at=0x10010+ptr-0x8000;
        if(unknown){ptr=word(at+32);if(ptr<0x8000||ptr>=0xc000)throw std::runtime_error("Unverified item name pointer");at=0x10010+ptr-0x8000;}
        for(unsigned i=0;i<16;++i){auto b=byte(at+16+i);if(!b)break;result.push_back(b);}return result;
    } else {
        unsigned ptr=word(0x10010+item.id*31+(unknown?2:0));
        if(ptr<0x8000||ptr>=0xc000)throw std::runtime_error("Unverified item name pointer");
        size_t at=0x10010+ptr-0x8000;
        for(unsigned i=0;i<96;++i){if(!byte(at+i)){at+=i+1;break;}if(i==95)throw std::runtime_error("Unterminated item name");}
        for(unsigned i=0;i<48;++i){auto b=byte(at+i);if(!b)return result;result.push_back(b);}
    }
    throw std::runtime_error("Unterminated item name");
}
std::vector<uint8_t> Session::textPixels(const std::vector<uint8_t>& codes) const {
    std::vector<uint8_t> bitmap(codes.size()*64);
    for(size_t i=0;i<codes.size();++i) {
        size_t at=rosterFontOffset_+codes[i]*16;
        if(at+8>rom_.size())throw std::runtime_error("Invalid font glyph");
        for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x)bitmap[y*codes.size()*8+i*8+x]=(rom_[at+y]>>(7-x))&1;
    }
    return bitmap;
}
void Session::equipItem(InventoryMember& member,unsigned index) const {
    if(index>=member.items.size())throw std::runtime_error("Empty inventory slot");
    auto& selected=member.items[index];
    if(selected.flags&64)throw std::runtime_error("Cursed equipment cannot be changed.");
    if(selected.flags&128){selected.flags&=127;return;}
    if(selected.flags&32)throw std::runtime_error("Identify this item first.");
    std::array<uint8_t,8192> ram{};
    if(!wiiz_core_sram_read(core_,ram.data(),ram.size()))throw std::runtime_error("Cannot read character");
    const auto* c=ram.data()+inventoryOffset(scenario_,member.slot);
    unsigned cls=scenario_==1?(c[11]&7):((c[10]>>2)&7),align=c[scenario_==1?12:10]&3;
    size_t trainer=(rom_[6]&4)?512:0;
    auto stats=[&](unsigned id) {
        size_t at;
        if(scenario_==1)at=0x10110+id*64+34;
        else if(scenario_==2){size_t p=0x10010+id*2+trainer;unsigned ptr=rom_.at(p)|(unsigned(rom_.at(p+1))<<8);if(ptr<0x8000||ptr>=0xc000)throw std::runtime_error("Invalid item pointer");at=0x10010+ptr-0x8000+34;}
        else at=0x10010+id*31+4;
        return at+trainer;
    };
    size_t at=stats(selected.id);unsigned kind=rom_.at(at);
    if(kind>5||!(rom_.at(at+(scenario_==1?14:13))&(1u<<cls)))throw std::runtime_error("This character cannot equip this item.");
    for(unsigned i=0;i<member.items.size();++i)if(i!=index&&(member.items[i].flags&128)&&rom_.at(stats(member.items[i].id))==kind) {
        if(member.items[i].flags&64)throw std::runtime_error("Remove curse before replacing equipment.");
    }
    for(unsigned i=0;i<member.items.size();++i)if(i!=index&&(member.items[i].flags&128)&&rom_.at(stats(member.items[i].id))==kind)member.items[i].flags&=127;
    bool aligned=scenario_==1?(rom_.at(at+1)&(1u<<align))!=0:(rom_.at(at+1)>=128||rom_.at(at+1)==align);
    selected.flags|=uint8_t(128|((rom_.at(at+2)||!aligned)?64:0));
}
void Session::updateItems(const std::vector<InventoryMember>& before,const std::vector<InventoryMember>& after) {
    if(!enhanced_||!structuredSave_||before.empty()||before.size()>6||before.size()!=after.size())throw std::runtime_error("Invalid inventory update");
    if(before==after)return;
    std::vector<uint8_t> original(8192);
    if(!wiiz_core_sram_read(core_,original.data(),original.size()))throw std::runtime_error("Cannot read inventory");
    const bool liveStats=wiiz_core_items_stats_live(core_)!=0;
    auto updated=original;unsigned countAt=scenario_==1?0x1def:0xb81,list=scenario_==1?0x1ddc:0xb82;
    if(original[countAt]!=before.size())throw std::runtime_error("Party changed; reopen Items.");
    for(unsigned n=0;n<before.size();++n) {
        const auto& a=before[n];const auto& b=after[n];
        if(a.slot<1||a.slot>20||a.slot!=b.slot||b.items.size()>8||original[list+n]!=(scenario_==1?0x60:0)+a.slot-1)throw std::runtime_error("Party changed; reopen Items.");
        unsigned base=unsigned(inventoryOffset(scenario_,a.slot)),flags=inventoryFlagsOffset(scenario_);
        if(original[base+inventoryCountOffset(scenario_)]!=a.items.size())throw std::runtime_error("Inventory changed; reopen Items.");
        for(unsigned i=0;i<a.items.size();++i)if(original[base+flags+i]!=a.items[i].flags||original[base+flags+8+i]!=a.items[i].id)throw std::runtime_error("Inventory changed; reopen Items.");
        if(a==b)continue;
        updated[base+inventoryCountOffset(scenario_)]=uint8_t(b.items.size());
        for(unsigned i=0;i<8;++i){if(i<b.items.size()&&b.items[i].id>=inventoryLimit(scenario_))throw std::runtime_error("Invalid item ID");updated[base+flags+i]=i<b.items.size()?b.items[i].flags:0;updated[base+flags+8+i]=i<b.items.size()?b.items[i].id:255;}
    }
    if(updated==original)return;
    std::vector<uint8_t> state(wiiz_core_state_size(core_));
    if(!wiiz_core_state_write(core_,state.data(),state.size()))throw std::runtime_error("Cannot snapshot inventory");
    std::unique_ptr<WiizCore,decltype(&wiiz_core_delete)> clone(wiiz_core_new(rom_.data(),rom_.size()),wiiz_core_delete);
    if(!clone||!wiiz_core_state_read(clone.get(),state.data(),state.size()))throw std::runtime_error("Cannot clone NES core");
    wiiz_core_profile(clone.get(),scenario_);
    if(!wiiz_core_sram_write(clone.get(),updated.data(),updated.size()))throw std::runtime_error("Cannot prepare inventory");
    for(unsigned n=0;n<after.size();++n)if(!wiiz_core_items_recalculate(clone.get(),n))throw std::runtime_error("Original equipment recalculation failed; no changes saved.");
    std::vector<uint8_t> computed(8192);
    if(!wiiz_core_sram_read(clone.get(),computed.data(),computed.size()))throw std::runtime_error("Cannot read recalculated inventory");
    for(const auto& member:after) {
        auto base=inventoryOffset(scenario_,member.slot);
        updated[base+(scenario_==1?0x28:0x26)]=computed[base+(scenario_==1?0x28:0x26)];
        if(scenario_!=1)updated[base+0x59]=computed[base+0x59];
    }
    if(scenario_==1&&liveStats) {
        for(unsigned at:{0x1ad6u,0x1adcu,0x1ae2u,0x1b0cu,0x1b36u,0x1b60u,0x1b8au,0x1d82u,0x1d88u,0x1d8eu,0x1db2u,0x1db8u,0x1dd0u})
            std::copy_n(computed.begin()+at,6,updated.begin()+at);
    }
    repairBattery(updated,scenario_);
    try {
        commitRoster(original,updated);
        if(!wiiz_core_items_sync(core_,original.data(),updated.data(),updated.size()))throw std::runtime_error("Cannot synchronize original item menu");
        if(liveStats&&!wiiz_core_items_merge(core_,clone.get()))throw std::runtime_error("Cannot apply derived equipment stats");
    } catch(...) {wiiz_core_state_read(core_,state.data(),state.size());previousSave_.clear();batterySaved_=false;throw;}
}
