#pragma once
#include "core_bridge.h"
#include "dungeon.hpp"
#include "rom_identity.hpp"
#include <array>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct RomEntry {
    std::filesystem::path path;
    std::string title, sha;
    RomIdentity identity;
};
struct SpellMap { unsigned mode=0; int floor=1,x=0,y=0,heading=0,targetFloor=1,targetX=0,targetY=0; };
std::string utf8(const std::filesystem::path& path);
std::filesystem::path pathFromUtf8(std::string_view path);
RomEntry identifyRom(const std::filesystem::path& path);
std::vector<RomEntry> scanRoms(const std::filesystem::path& folder, int& rejected);

enum class SaveFormat { Sav, Json };
class Session {
public:
    explicit Session(const RomEntry& entry, const std::filesystem::path& saveFolder = {}, SaveFormat format = SaveFormat::Sav, bool skipMaker = false);
    ~Session();
    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;
    void frame();
    void input(unsigned buttons) { wiiz_core_input(core_, buttons); }
    void reset();
    void tick(unsigned held, unsigned speed, uint64_t milliseconds);
    const float* audio(size_t* count);
    void releaseInput() { previousHeld_ = 0; input(0); }
    bool supportsTurbo() const { return enhanced_; }
    void battleMultipliers(unsigned experience, unsigned gold);
    bool supportsBugFix() const { return bugFixSupported_; }
    bool bugFix() const { return bugFix_; }
    void bugFix(bool enabled);
    bool turboFileConnected() const { return structuredSave_; }
    std::string turboFileLocation() const { return utf8(turboFilePath_); }
    void save();
    void saveFormat(SaveFormat format);
    void skipMaker(bool enabled) { skipMaker_=enabled; }
    void skipManufacturer();
    void stateFolder(const std::filesystem::path& folder) { stateFolder_ = folder; }
    void saveState(unsigned slot);
    void loadState(unsigned slot);
    bool hasState(unsigned slot) const;
    const SpellMap& spellMap() const { return spellMap_; }
    const Dungeon& dungeon() const { return dungeon_; }
    bool explored(int floor,int x,int y) const;
    void mapKey(unsigned button);
    void openMap();
    std::string positionText() const;
    void assists(unsigned mask, bool ready=true);
    unsigned assists() const { return assistMask_; }
    std::string rosterLabel(unsigned slot) const;
    unsigned rosterExperienceLevel(unsigned slot) const;
    std::array<uint8_t,64> fontGlyph(char character) const;
    std::array<uint8_t, 64*8> rosterNamePixels(unsigned slot) const;
    bool canSwapRoster() const;
    void swapRoster(unsigned first, unsigned second);
    void moveRoster(unsigned first, unsigned last);
    enum class RosterField { Race, Class };
    bool supportsRosterIdentity() const;
    int rosterIdentity(unsigned slot, RosterField field) const;
    void setRosterIdentity(unsigned slot, RosterField field, unsigned value);
    void rosterBonus(unsigned slot, unsigned kind, uint64_t amount);
    struct InventoryItem { uint8_t id=255, flags=0; bool operator==(const InventoryItem&) const = default; };
    struct InventoryMember { unsigned slot=0; std::vector<InventoryItem> items; bool operator==(const InventoryMember&) const = default; };
    std::vector<InventoryMember> openItems();
    void updateItems(const std::vector<InventoryMember>& before,const std::vector<InventoryMember>& after);
    void equipItem(InventoryMember& member,unsigned index) const;
    std::vector<uint8_t> itemNameCodes(InventoryItem item) const;
    std::vector<uint8_t> textPixels(const std::vector<uint8_t>& codes) const;
    WiizCore* core() { return core_; }
    std::array<uint32_t, 256 * 240> pixels{};
    std::string title;
private:
    std::vector<uint8_t> rom_, previousSave_;
    WiizCore* core_ = nullptr;
    WiizCore* music_ = nullptr;
    unsigned assistMask_ = 0;
    unsigned previousHeld_ = 0;
    std::array<uint64_t, 4> repeatAt_{};
    void startMusic();
    std::filesystem::path savePath_;
    std::filesystem::path stateFolder_;
    std::filesystem::path romStem_;
    std::string sha_;
    int scenario_ = 0;
    size_t rosterFontOffset_ = 0;
    bool structuredSave_ = false, enhanced_ = false;
    unsigned battleExpMultiplier_ = 1, battleGoldMultiplier_ = 1;
    bool bugFixSupported_ = false, bugFix_ = false;
    bool batterySaved_ = false, skipMaker_ = false, skipSupported_ = false;
    SaveFormat saveFormat_ = SaveFormat::Sav;
    std::filesystem::path mapPath_;
    Dungeon dungeon_;
    SpellMap spellMap_;
    std::vector<uint8_t> explored_;
    bool mapDirty_ = false;
    unsigned mapResume_ = 0, mapButton_ = 0;
    void pollMap();
    void saveTurboFile();
    std::filesystem::path turboFilePath_;
    std::vector<uint8_t> previousTurboFile_;
    void reorderRoster(unsigned first, unsigned last, bool move);
    void commitRoster(std::vector<uint8_t>& original, std::vector<uint8_t>& updated);
    std::filesystem::path statePath(unsigned slot) const;
    std::filesystem::path legacyStatePath(unsigned slot) const;
};
