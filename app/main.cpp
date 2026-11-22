#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include "dungeon.hpp"
#include "session.hpp"
#include "user_storage.hpp"
#include "save_json.hpp"
#include "spell_map_view.hpp"
#include "ui_text.hpp"
#include "item_editor.hpp"
#include "platform_text.hpp"
#include "crt_filter.hpp"
#include "gamepad_input.hpp"
#include "window_icon.hpp"
#include "picosha2.h"
#include <algorithm>
#include <cmath>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <sstream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef SDL_PLATFORM_ANDROID
#include <jni.h>
#include <atomic>
static std::atomic<bool> androidGameActive{false};
static Uint32 androidRomEvent;
extern "C" JNIEXPORT jboolean JNICALL Java_com_wiiz_app_WiizActivity_openRomPath(JNIEnv* env,jclass,jbyteArray bytes){
    if(!androidRomEvent)return false;
    const auto size=env->GetArrayLength(bytes);auto* path=static_cast<char*>(SDL_malloc(size+1));if(!path)return false;
    env->GetByteArrayRegion(bytes,0,size,reinterpret_cast<jbyte*>(path));path[size]=0;
    SDL_Event event{};event.type=androidRomEvent;event.user.data1=path;
    if(!SDL_PushEvent(&event)){SDL_free(path);return false;}return true;
}
extern "C" JNIEXPORT jboolean JNICALL Java_com_wiiz_app_WiizActivity_hasActiveGame(JNIEnv*,jclass){return androidGameActive.load();}
// Android buttons feed the same event path as desktop keys, including slot 1 shortcuts.
extern "C" JNIEXPORT void JNICALL
Java_com_wiiz_app_WiizActivity_touchKey(JNIEnv*, jclass, jint action, jboolean down) {
    static constexpr SDL_Keycode keys[] = {
        SDLK_UP, SDLK_DOWN, SDLK_LEFT, SDLK_RIGHT, SDLK_X, SDLK_Z,
        SDLK_A, SDLK_S, SDLK_Q, SDLK_F1, SDLK_F1, SDLK_M, SDLK_ESCAPE, SDLK_F6, SDLK_I
    };
    if (action < 0 || action >= int(sizeof(keys) / sizeof(keys[0]))) return;
    SDL_Event event{};
    event.type = down ? SDL_EVENT_KEY_DOWN : SDL_EVENT_KEY_UP;
    event.key.key = keys[action];
    event.key.down = down;
    event.key.mod = action == 10 ? SDL_KMOD_SHIFT : SDL_KMOD_NONE;
    SDL_PushEvent(&event);
}
#endif

namespace fs = std::filesystem;
int persistenceCheck(const char* romPath,const char* folderPath);
int turboFileCheck(const char* romPath,const char* folderPath);
int rosterCheck(const char* romPath,const char* folderPath);
int creationCheck(const char* romPath,const char* folderPath);
int assistsCheck(const char* romPath,const char* folderPath);
int difficultyCheck(const char* romPath,const char* folderPath);
int storageCheck(const char* romPath,const char* folderPath);
int spellMapPrepare(const char* romPath,const char* folderPath);
enum class MenuPage {Root,States,Display,Storage,Difficulty,Roster,Identity,Items};
enum class MenuAction {Back,Resume,States,Display,Storage,Games,Folder,Exit,Crt,Speed,Format,Maker,Slot,Difficulty,Character,Amount,Experience,Gold,Spells,Assist,Roster,RosterEntry,TurboFile,BugFix,Alignment,BattleMultiplier,Race,Class,SetIdentity,Items};
constexpr const char* raceNames[]={"Human","Elf","Dwarf","Gnome","Hobbit"};
constexpr const char* classNames[]={"Fighter","Mage","Priest","Thief","Bishop","Samurai","Lord","Ninja"};
struct MenuItem {std::string label;MenuAction action;unsigned slot=0;};
static const char* crtNames[]={"OFF","Mild","Standard"};
static Uint32 folderEvent;
static void SDLCALL folderSelected(void*, const char* const* files, int) {
    SDL_Event event{}; event.type = folderEvent;
    if (!files) event.user.code = -1;
    else if (*files) event.user.data1 = SDL_strdup(*files);
    if (!SDL_PushEvent(&event)) SDL_free(event.user.data1);
}
static SDL_Keycode canonicalKey(SDL_Keycode key) {
    switch(key){case SDLK_RETURN:case SDLK_KP_ENTER:return SDLK_X;case SDLK_BACKSPACE:return SDLK_Z;
    case SDLK_SPACE:return SDLK_S;case SDLK_TAB:return SDLK_A;default:return key;}
}
static unsigned button(SDL_Keycode key) {
    key=canonicalKey(key);
    switch (key) {
    case SDLK_X: return PAD_A; case SDLK_Z: return PAD_B;
    case SDLK_A: return PAD_SELECT; case SDLK_S: return PAD_START;
    case SDLK_UP: return PAD_UP; case SDLK_DOWN: return PAD_DOWN;
    case SDLK_LEFT: return PAD_LEFT; case SDLK_RIGHT: return PAD_RIGHT;
    default: return 0;
    }
}
struct Replay { int frame; SDL_Keycode key; bool down; bool shift = false; };
static std::vector<Replay> readReplay(const fs::path& path) {
    std::ifstream script(path);
    if (!script) throw std::runtime_error("Cannot read input replay");
    std::vector<Replay> replay;
    std::string line;
    while (std::getline(script, line)) {
        if (line.empty() || line[0] == '#') continue;
        int frame; std::string key, action; std::istringstream row(line);
        if (!(row >> frame >> key >> action) || frame < 0 || (action != "down" && action != "up")) throw std::runtime_error("Invalid input replay line");
        const bool shift = key.starts_with("Shift+"); if (shift) key.erase(0,6);
        const SDL_Keycode code = SDL_GetKeyFromName(key.c_str());
        if (!code) throw std::runtime_error("Unknown replay key");
        replay.push_back({frame, code, action == "down", shift});
    }
    return replay;
}
static void text(SDL_Renderer* r, float x, float y, const std::string& s) {
    SDL_SetRenderDrawColor(r, 225, 232, 240, 255); SDL_RenderDebugText(r, x, y, s.c_str());
}
static bool screenshot(SDL_Renderer* renderer, const char* path) {
    SDL_Surface* image = SDL_RenderReadPixels(renderer, nullptr);
    bool ok = image && SDL_SaveBMP(image, path);
    SDL_DestroySurface(image); return ok;
}
static int crtCheck(const char* path,const char* output) {
    const auto entry=identifyRom(pathFromUtf8(path));const auto folder=pathFromUtf8(output);fs::create_directories(folder);
    auto game=std::make_unique<Session>(entry);
    const auto replay=readReplay("tests/replays/wiz1-dungeon.txt");unsigned held=0;
    for(int f=0;f<4300;++f){for(const auto& key:replay)if(key.frame==f){if(key.down)held|=button(key.key);else held&=~button(key.key);}game->input(held);game->frame();}
    auto filter=std::make_unique<CrtFilter>();const auto original=game->pixels;
    if(filter->render(original.data(),0)!=original.data())throw std::runtime_error("CRT OFF changed the source");
    for(unsigned mode=0;mode<3;++mode) {
        const auto* pixels=filter->render(original.data(),mode);const int width=mode?CrtFilter::width:256,height=mode?CrtFilter::height:240;
        SDL_Surface* im=SDL_CreateSurfaceFrom(width,height,SDL_PIXELFORMAT_RGBA32,const_cast<uint32_t*>(pixels),width*4);
        const auto file=folder/("crt-"+std::to_string(mode)+".bmp");const bool ok=im&&SDL_SaveBMP(im,utf8(file).c_str());SDL_DestroySurface(im);if(!ok)throw std::runtime_error(SDL_GetError());
    }
    const auto start=std::chrono::steady_clock::now();
    for(unsigned i=0;i<20;++i)filter->render(original.data(),1+i%2);
    const double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count()/20;
    if(original!=game->pixels)throw std::runtime_error("CRT changed emulator pixels");
    std::printf("CRT_OK presets=3 source_unchanged=1 off_exact=1 average_ms=%.3f\n",ms);return 0;
}
static int turboCheck(const char* path) {
        const auto entry = identifyRom(pathFromUtf8(path));
        if (!Session(entry).supportsTurbo()) throw std::runtime_error("No verified turbo profile for this ROM");
        std::vector<uint8_t> rom;
        { std::ifstream in(entry.path, std::ios::binary); rom.assign(std::istreambuf_iterator<char>(in), {}); }
        using CorePtr = std::unique_ptr<WiizCore, decltype(&wiiz_core_delete)>;
        // Advance an independent foreground core by exactly the requested number of frames.
        for (unsigned speed : {2u, 4u, 8u}) {
            Session session(entry);
            CorePtr reference(wiiz_core_new(rom.data(), rom.size()), wiiz_core_delete);
            wiiz_core_profile(reference.get(),entry.identity.scenario);
            size_t samples = 0; double energy = 0;
            std::array<uint32_t,256*240> pixels;
            for (int tick=0; tick<180; ++tick) {
                session.tick(0, speed, uint64_t(tick)*1000/60);
                for (unsigned f=0; f<speed; ++f) {
                    wiiz_core_repeat(reference.get(), 0, 0);
                    if (!wiiz_core_frame(reference.get())) throw std::runtime_error("Reference stopped");
                }
                wiiz_core_pixels(reference.get(), pixels.data());
                if (pixels != session.pixels) throw std::runtime_error("Turbo skipped or changed a game frame");
                size_t count; const float* data = session.audio(&count); samples += count;
                for (size_t n=0; n<count; ++n) { if (!std::isfinite(data[n])) throw std::runtime_error("Invalid turbo audio"); energy += data[n]*data[n]; }
            }
            if (samples < 140000 || samples > 145000 || energy < 0.01) throw std::runtime_error("Turbo music rate or command forwarding failed");
            session.reset(); session.tick(0, speed, 4000);
            std::printf("TURBO_OK speed=%u game_frames=%u music_samples=%zu energy=%.3f reset=OK\n", speed, speed*180, samples, energy);
        }
        // Compare the original driver's actual repeat-counter consumption at equal wall times.
        for (unsigned speed : {2u, 4u, 8u}) {
            Session session(entry);
            for (int f=0; f<1000; ++f) { session.input((f>=400 && f<402) || (f>=850 && f<852) ? PAD_A : 0); session.frame(); }
            const unsigned first=wiiz_core_initial_events(session.core(),1);
            for (unsigned t=0; t<120; ++t) {
                session.tick(PAD_DOWN, speed, uint64_t(t)*1000/60);
                if(t==0 && entry.identity.scenario>1 && wiiz_core_initial_events(session.core(),1)!=first+1)
                    throw std::runtime_error("Initial direction press was lost or repeated");
            }
            if(entry.identity.scenario>1 && wiiz_core_initial_events(session.core(),1)!=first+1)
                throw std::runtime_error("Held direction produced extra initial presses");
            const unsigned repeats=wiiz_core_repeat_events(session.core(), 1);
            if (repeats < 16 || repeats > 19) throw std::runtime_error("Directional repeat rate differs from wall clock: " + std::to_string(repeats));
            std::printf("REPEAT_OBSERVED speed=%u consumed=%u\n", speed, repeats);
        }
        // Exercise every mapped BGM and SE through the original sound driver, including stops.
        CorePtr music(wiiz_core_new(rom.data(), rom.size()), wiiz_core_delete);
        wiiz_core_profile(music.get(),entry.identity.scenario);
        wiiz_core_sound_player(music.get());
        for (int f=0; f<602; ++f) wiiz_core_frame(music.get());
        for (unsigned reg : (entry.identity.scenario==1?std::vector<unsigned>{0,2}:std::vector<unsigned>{0,1,3})) for (unsigned id=1; id<=(entry.identity.scenario==1?13u:reg==0?4u:(entry.identity.scenario==3 && reg==3?12u:13u)); ++id) {
            for (unsigned r=0; r<4; ++r) wiiz_core_sound_command(music.get(), r, 0);
            for (int f=0; f<60; ++f) wiiz_core_frame(music.get());
            wiiz_core_sound_command(music.get(), reg, id);
            double energy=0;
            for (int f=0; f<120; ++f) {
                if (!wiiz_core_frame(music.get())) throw std::runtime_error("Sound driver stopped");
                size_t count; const float* data=wiiz_core_audio(music.get(), &count);
                for(size_t n=0;n<count;++n) { if (!std::isfinite(data[n])) throw std::runtime_error("Invalid sound"); energy+=data[n]*data[n]; }
            }
            if (energy < 0.001) throw std::runtime_error("Missing BGM/SE " + std::to_string(reg) + ":" + std::to_string(id));
        }
        std::printf("SOUND_DRIVER_OK bgm=%u se=%u\n",entry.identity.scenario==1?13:4,entry.identity.scenario==1?13:entry.identity.scenario==2?26:25);
    return 0;
}
static int checks(int argc, char** argv) {
    const std::string mode = argv[1];
    if (argc != 3 && !(mode == "--core-check" && argc == 4) && !(mode == "--drawing-check" && argc >= 4 && argc <= 6) &&
        !(mode == "--capture" && (argc == 6 || argc == 7)))
        throw std::runtime_error("Expected ROM or folder argument");
    if (mode == "--turbo-check") {
        return turboCheck(argv[2]);
    } else if (mode == "--check") {
        auto dungeon = readDungeon(argv[2]); std::vector<uint8_t> bytes;
        for (const auto& f : dungeon.floors) {
            bytes.insert(bytes.end(), f.walls.begin(), f.walls.end());
            bytes.insert(bytes.end(), f.flags.begin(), f.flags.end());
        }
        std::printf("%zu %s\n", dungeon.floors.size(), picosha2::hash256_hex_string(bytes).c_str());
    } else if (mode == "--scan") {
        int rejected = 0; auto entries = scanRoms(pathFromUtf8(argv[2]), rejected);
        for (const auto& e : entries) std::printf("%s %s\n", e.sha.c_str(), e.title.c_str());
        std::printf("supported=%zu rejected=%d\n", entries.size(), rejected);
    } else if (mode == "--capture") {
        if (argc != 6 && argc != 7) throw std::runtime_error("--capture ROM BMP frames replay [save-copy-folder]");
        std::vector<int> captureFrames;
        std::istringstream frameList(argv[4]); std::string token;
        while (std::getline(frameList, token, ',')) {
            const int frame = std::stoi(token);
            if (frame < 1 || frame > 36000) throw std::runtime_error("Capture frame count out of range");
            captureFrames.push_back(frame);
        }
        if (captureFrames.empty()) throw std::runtime_error("No capture frames specified");
        const int limit = *std::max_element(captureFrames.begin(), captureFrames.end());
        const auto replay = readReplay(pathFromUtf8(argv[5]));
        Session session(identifyRom(pathFromUtf8(argv[2])), argc == 7 ? pathFromUtf8(argv[6]) : fs::path{},SaveFormat::Json);
        unsigned held = 0;
        for (int frame=0; frame<limit; ++frame) {
            for (const auto& input : replay) if (input.frame == frame) {
                if (input.key == SDLK_ESCAPE && input.down) { session.reset(); held = 0; }
                else if (input.down) held |= button(input.key); else held &= ~button(input.key);
            }
            session.input(held); session.frame();
            if (std::find(captureFrames.begin(), captureFrames.end(), frame+1) != captureFrames.end()) {
                auto path = pathFromUtf8(argv[3]);
                if (captureFrames.size() > 1) path = path.parent_path() / pathFromUtf8(utf8(path.stem()) + "-" + std::to_string(frame+1) + ".bmp");
                SDL_Surface* image = SDL_CreateSurfaceFrom(256, 240, SDL_PIXELFORMAT_RGBA32, session.pixels.data(), 256*sizeof(uint32_t));
                const bool ok = image && SDL_SaveBMP(image, utf8(path).c_str());
                SDL_DestroySurface(image);
                if (!ok) throw std::runtime_error(SDL_GetError());
            }
        }
        std::printf("CAPTURE_OK frames=%d no_save_write=1\n", limit);
    } else if (mode == "--drawing-check") {
        const auto entry = identifyRom(pathFromUtf8(argv[2]));
        const auto replay = argc >= 4 ? readReplay(pathFromUtf8(argv[3])) : std::vector<Replay>{};
        const int limit = argc >= 5 ? std::stoi(argv[4]) : 900;
        if (limit < 1 || limit > 36000) throw std::runtime_error("Reference frame count out of range");
        const auto saves = argc == 6 ? pathFromUtf8(argv[5]) : fs::path{};
        Session session(entry, saves,SaveFormat::Json);
        std::ifstream in(entry.path, std::ios::binary);
        std::vector<uint8_t> original((std::istreambuf_iterator<char>(in)), {});
        if (picosha2::hash256_hex_string(original) != entry.sha) throw std::runtime_error("Reference ROM hash changed");
        // Independently initialize the adopted core from the untouched on-disk ROM.
        std::unique_ptr<WiizCore, decltype(&wiiz_core_delete)> reference(wiiz_core_new(original.data(), original.size()), wiiz_core_delete);
        if (!reference) throw std::runtime_error("Reference core initialization failed");
        if (!saves.empty()) {
            std::ifstream saved(saves / (entry.sha + ".sav"), std::ios::binary);
            if (saved) {
                std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(saved)), {});
                if (bytes.size() != wiiz_core_sram_size(reference.get()) || !wiiz_core_sram_write(reference.get(), bytes.data(), bytes.size()))
                    throw std::runtime_error("Invalid reference save");
            }
        }
        std::array<uint32_t, 256*240> pixels{};
        size_t samples = 0;
        unsigned held = 0;
        for (int frame=0; frame<limit; ++frame) {
            if (argc == 3) held = frame >= 400 && frame < 402 ? PAD_A : 0;
            else for (const auto& input : replay) if (input.frame == frame) {
                if (input.key == SDLK_ESCAPE && input.down) { session.reset(); wiiz_core_reset(reference.get()); held = 0; }
                else if (input.down) held |= button(input.key); else held &= ~button(input.key);
            }
            session.input(held); wiiz_core_input(reference.get(), held);
            session.frame();
            if (!wiiz_core_frame(reference.get())) throw std::runtime_error("Reference execution stopped");
            wiiz_core_pixels(reference.get(), pixels.data());
            if (session.pixels != pixels) throw std::runtime_error("Video differs from unmodified ROM at frame " + std::to_string(frame));
            size_t a=0, b=0;
            const float* first = wiiz_core_audio(session.core(), &a);
            const float* second = wiiz_core_audio(reference.get(), &b);
            if (a != b || std::memcmp(first, second, a*sizeof(float))) throw std::runtime_error("Audio differs from unmodified ROM at frame " + std::to_string(frame));
            samples += a;
        }
        std::printf("DRAWING_OK frames=%d every_frame_pixels_equal=1 audio_samples_equal=%zu unmodified_rom=1\n", limit, samples);
    } else {
        const auto entry = identifyRom(pathFromUtf8(argv[2]));
        Session session(entry, argc == 4 ? pathFromUtf8(argv[3]) : fs::path{},SaveFormat::Json);
        double energy = 0; int audioSamples = 0;
        auto start = SDL_GetTicks();
        for (int i=0; i<600; ++i) {
            session.input(i >= 200 && i < 202 ? PAD_START : 0); session.frame();
            size_t count = 0; const float* audio = wiiz_core_audio(session.core(), &count);
            for (size_t j=0; j<count; ++j) {
                if (!std::isfinite(audio[j])) throw std::runtime_error("Non-finite audio");
                energy += double(audio[j]) * audio[j];
            }
            audioSamples += int(count);
        }
        bool varied = std::any_of(session.pixels.begin(), session.pixels.end(), [&](auto p) {return p != session.pixels[0];});
        if (!varied || energy < 0.001 || audioSamples < 400000) throw std::runtime_error("Blank video or missing audio");
        if (wiiz_core_sram_size(session.core()) != 8192) throw std::runtime_error("Unexpected battery RAM size");
        if (argc == 4) {
            session.save();
            Session restored(entry, pathFromUtf8(argv[3]),SaveFormat::Json);
            std::vector<uint8_t> before(8192), after(8192);
            const int scenario=entry.title=="Wizardry FC I"?1:entry.title=="Wizardry FC II"?2:3;
            if (!wiiz_core_sram_read(session.core(), before.data(), before.size()) ||
                !wiiz_core_sram_read(restored.core(), after.data(), after.size()) ||
                encodeBattery(before,scenario,entry.sha) != encodeBattery(after,scenario,entry.sha))
                throw std::runtime_error("Battery save roundtrip failed");
        }
        if (!wiiz_core_reset_test(session.core())) throw std::runtime_error("Reset did not preserve RAM or reach the reset vector");
        for (int i=0; i<120; ++i) session.frame();
        std::printf("CORE_OK mapper=%u frames=720 samples=%d energy=%.3f reset=preserved-and-consumed elapsed_ms=%llu\n",
            wiiz_core_mapper(session.core()), audioSamples, energy, static_cast<unsigned long long>(SDL_GetTicks()-start));
    }
    return 0;
}

int bugFixCheck(const char*,const char*);
int initialHpCheck(const char*,const char*);
int itemsCheck(const char*,const char*);
int itemsScenesCheck(const char*,const char*);
int itemsBattleCheck(const char*,const char*);
int creationHpMenuCheck(const char*,const char*);
int main(int argc, char** argv) {
    try {
        if (argc == 4 && std::string(argv[1]) == "--items-battle-check") return itemsBattleCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--items-scenes-check") return itemsScenesCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--items-check") return itemsCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--creation-hp-check") return creationHpMenuCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--initial-hp-check") return initialHpCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--bugfix-check") return bugFixCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--turbofile-check") return turboFileCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--roster-check") return rosterCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--creation-check") return creationCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--assists-check") return assistsCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--difficulty-check") return difficultyCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--persistence-check") return persistenceCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--crt-check") return crtCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--storage-check") return storageCheck(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--map-prepare") return spellMapPrepare(argv[2],argv[3]);
        if (argc == 3 && std::string(argv[1]) == "--turbo-check") return turboCheck(argv[2]);
        if (argc > 1 && (std::string(argv[1]) == "--check" || std::string(argv[1]) == "--scan" || std::string(argv[1]) == "--core-check" || std::string(argv[1]) == "--drawing-check" || std::string(argv[1]) == "--turbo-check" || std::string(argv[1]) == "--capture"))
            return checks(argc, argv);
        const bool librarySmoke = argc > 1 && std::string(argv[1]) == "--smoke-library";
        const bool turboSmoke = argc > 1 && std::string(argv[1]) == "--smoke-turbo";
        bool smoke = turboSmoke || librarySmoke || (argc > 1 && std::string(argv[1]) == "--smoke");
        if (smoke && argc < 3) throw std::runtime_error("--smoke requires a ROM");
        const int smokeFrames = smoke && argc > 4 ? std::stoi(argv[4]) : 360;
        if (smokeFrames < 1 || smokeFrames > 36000) throw std::runtime_error("Smoke frame count out of range");
        std::vector<Replay> replay;
        if (smoke && argc > 5) replay = readReplay(pathFromUtf8(argv[5]));
        GamepadInput::configure();
        if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMEPAD)) throw std::runtime_error(SDL_GetError());
        GamepadInput gamepads;
        SDL_Window* window = nullptr; SDL_Renderer* renderer = nullptr;
        if (!SDL_CreateWindowAndRenderer("Wiiz " WIIZ_VERSION, 1024, 860, SDL_WINDOW_RESIZABLE, &window, &renderer)) throw std::runtime_error(SDL_GetError());
        setAppWindowIcon(window);
        SDL_SetRenderLogicalPresentation(renderer, 1024, 860, SDL_LOGICAL_PRESENTATION_LETTERBOX);
        FileLabelRenderer filenames(renderer);
        SDL_Texture* screen = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STREAMING, 256, 240);
        if (!screen) throw std::runtime_error(SDL_GetError());
        SDL_SetTextureScaleMode(screen, SDL_SCALEMODE_NEAREST);
        SDL_Texture* crtScreen=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGBA32,SDL_TEXTUREACCESS_STREAMING,CrtFilter::width,CrtFilter::height);
        if(!crtScreen)throw std::runtime_error(SDL_GetError());
        SDL_SetTextureScaleMode(crtScreen,SDL_SCALEMODE_LINEAR);
        auto crt=std::make_unique<CrtFilter>();
        SDL_AudioSpec spec{SDL_AUDIO_F32, 1, 48000};
        SDL_AudioStream* stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, nullptr, nullptr);
#ifdef SDL_PLATFORM_ANDROID
        // SDL opens paused: prefill roughly 50ms instead of starting with an empty queue.
        bool audioStarted = false;
#else
        if (stream) SDL_ResumeAudioStreamDevice(stream);
#endif
#ifdef SDL_PLATFORM_ANDROID
        androidRomEvent=SDL_RegisterEvents(1);
        if(androidRomEvent==Uint32(-1))throw std::runtime_error(SDL_GetError());
#endif
        folderEvent = SDL_RegisterEvents(1);
        if (folderEvent == Uint32(-1)) throw std::runtime_error(SDL_GetError());
        char* prefString = smoke ? nullptr : SDL_GetPrefPath("Wiiz", "Wiiz");
        if (!smoke && !prefString) throw std::runtime_error(SDL_GetError());
        const fs::path prefs = smoke ? fs::current_path() / "output/native-smoke-data" : pathFromUtf8(prefString);
        if (smoke) fs::create_directories(prefs);
        SDL_free(prefString);
        // Withdrawn optimization: ignore old fast-drawing.txt, including a saved ON value.
        constexpr bool fastDrawing = false;
        unsigned speed = 4;
        if (turboSmoke && argc > 6) { speed = unsigned(std::stoi(argv[6])); if (speed != 1 && speed != 2 && speed != 4 && speed != 8) throw std::runtime_error("Invalid smoke speed"); }
        { std::ifstream in(prefs / "speed.txt"); unsigned value;
          if (!smoke && in >> value && (value == 1 || value == 2 || value == 4 || value == 8)) speed = value; }
        bool wiz1BugFix=false;
        if(!smoke){std::ifstream in(prefs/"wiz1-bug-fix.txt");int value;if(in>>value)wiz1BugFix=value==1;}
        unsigned assistMask=0;
        if(!smoke){std::ifstream in(prefs/"assists.txt");unsigned value;if(in>>value&&value<64)assistMask=value;}
        unsigned battleMultiplierSteps[2]{};
        if (!smoke) {
            std::ifstream in(prefs/"battle-multipliers.txt");
            unsigned experience, gold;
            if (in >> experience >> gold && experience <= 8 && gold <= 8) {
                battleMultiplierSteps[0] = experience;
                battleMultiplierSteps[1] = gold;
            }
        }
#ifdef SDL_PLATFORM_ANDROID
        unsigned crtMode=0; // CPU CRT reconstruction is opt-in on mobile.
#else
        unsigned crtMode=smoke?0:1;
#endif
        if(!smoke){std::ifstream in(prefs/"crt-mode.txt");unsigned value;if(in>>value && value<=2)crtMode=value;}
        SaveFormat saveFormat=SaveFormat::Sav;bool skipMaker=false;
        if(!smoke){std::ifstream in(prefs/"battery-format.txt");std::string value;if(in>>value && value=="json")saveFormat=SaveFormat::Json;
            std::ifstream boot(prefs/"skip-maker.txt");boot>>skipMaker;}
        #ifdef SDL_PLATFORM_ANDROID
        fs::path folder = prefs / "shared-rom-cache";
        fs::create_directories(folder);
#else
        fs::path folder = pathFromUtf8(SDL_GetBasePath()) / "roms";
#endif
        std::ifstream config(prefs / "rom-folder.txt", std::ios::binary);
        std::string stored; std::getline(config, stored);
        if (!stored.empty()) folder = pathFromUtf8(stored);
        else if (fs::is_directory(fs::current_path() / ".nes")) folder = fs::current_path() / ".nes";
        if (argc > 2 && std::string(argv[1]) == "--rom-dir") folder = fs::absolute(pathFromUtf8(argv[2]));
        if (librarySmoke) folder = fs::absolute(pathFromUtf8(argv[2]));
#ifdef SDL_PLATFORM_ANDROID
        folder = prefs / "shared-rom-cache";
#endif
        std::vector<RomEntry> entries;
        std::unique_ptr<Session> game;
        fs::path activeRom;
#ifdef SDL_PLATFORM_ANDROID
        // SDL queues WILL_ENTER_BACKGROUND immediately before blocking its native
        // loop. A watch saves synchronously; polling alone can be delayed until resume.
        struct BackgroundSaveWatch {
            std::unique_ptr<Session>* game;
            static bool SDLCALL callback(void* data, SDL_Event* event) {
                auto* self = static_cast<BackgroundSaveWatch*>(data);
                if (event->type == SDL_EVENT_WILL_ENTER_BACKGROUND && *self->game) {
                    try { (*self->game)->save(); userstore::flush(); }
                    catch (const std::exception& ex) { SDL_LogError(SDL_LOG_CATEGORY_APPLICATION,"Background save failed: %s",ex.what()); }
                }
                return true;
            }
            explicit BackgroundSaveWatch(std::unique_ptr<Session>* value) : game(value) { SDL_AddEventWatch(callback,this); }
            ~BackgroundSaveWatch() { SDL_RemoveEventWatch(callback,this); }
        } backgroundSaveWatch(&game);
#endif
        std::string status;
        int chosen = 0, menuChoice = 0, frames = 0, resets = 0;
        int stateSaves = 0, stateLoads = 0, stateErrors = 0, bonusActions = 0, rosterSwaps = 0;
        bool running = true, menu = false, pending = false, focused = true;
        bool stateLoadChoice = false;MenuPage menuPage=MenuPage::Root;
        ItemEditor itemEditor;
        auto identityField=Session::RosterField::Race;
        int identityMenuReturn=0;
        unsigned bonusSlot=1,bonusAmount=1,rosterPicked=0;
        std::array<unsigned,20> rosterOrder{};
        auto resetRosterOrder=[&]{for(unsigned i=0;i<20;++i)rosterOrder[i]=i+1;rosterPicked=0;};
        resetRosterOrder();
        const uint64_t bonusAmounts[]={1000,10000,100000,1000000};
        unsigned held = 0;std::set<SDL_Keycode> pressed, padPressed;
        auto updateHeld=[&]{held=0;for(auto key:pressed)held|=button(key);for(auto key:padPressed)held|=button(key);};
        auto silence = [&] { pressed.clear();padPressed.clear();held = 0; if (game) game->releaseInput(); if (stream) {
#ifdef SDL_PLATFORM_ANDROID
            SDL_PauseAudioStreamDevice(stream); audioStarted = false;
#endif
            SDL_ClearAudioStream(stream);
        } };
        auto scan = [&] {
            int rejected = 0; chosen = 0;
            try { entries = scanRoms(folder, rejected); status = std::to_string(entries.size()) + " supported ROM(s), " + std::to_string(rejected) + " unsupported file(s)."; }
            catch (const std::exception&) { entries.clear(); status = "ROM folder unavailable. Q: select a folder."; }
        };
        auto menuItems=[&] {
            std::vector<MenuItem> items;
            if(menuPage==MenuPage::Root) {
                if(game)items={{"Resume game",MenuAction::Resume},{"State save / load  >",MenuAction::States},
                    {"Display / speed  >",MenuAction::Display},{"Save / startup  >",MenuAction::Storage},
                    {"Game selection",MenuAction::Games},{"Select ROM folder",MenuAction::Folder},{"Exit application",MenuAction::Exit},{"Difficulty / bonuses  >",MenuAction::Difficulty},{"Roster order (title only)  >",MenuAction::Roster},{"Party items  >",MenuAction::Items}};
                else items={{"Display / speed  >",MenuAction::Display},{"Save / startup  >",MenuAction::Storage},
                    {"Select ROM folder",MenuAction::Folder},{"Rescan ROM folder",MenuAction::Games},{"Exit application",MenuAction::Exit}};
            } else {
                if(menuPage!=MenuPage::Roster)items.push_back({"< Back",MenuAction::Back});
                if(menuPage==MenuPage::States && game)for(unsigned slot=1;slot<=5;++slot)
                    items.push_back({"Slot "+std::to_string(slot)+(stateLoadChoice?"   Save  [Load]":"  [Save]  Load ")+(game->hasState(slot)?"  (saved)":"  (empty)"),MenuAction::Slot,slot});
                if(menuPage==MenuPage::Display) {
                    items.push_back({std::string("CRT: ")+crtNames[crtMode],MenuAction::Crt});
                    items.push_back({"Speed: "+std::to_string(speed)+"x / music 1x"+(game&&!game->supportsTurbo()?" (this ROM: 1x)":""),MenuAction::Speed});
                }
                if(menuPage==MenuPage::Difficulty && game) {
                    items.push_back({"Character: "+game->rosterLabel(bonusSlot),MenuAction::Character});
                    items.push_back({"Gold amount: "+std::to_string(bonusAmounts[bonusAmount]),MenuAction::Amount});
                    items.push_back({"Next level EXP (inn)",MenuAction::Experience});
                    items.push_back({"Add Gold",MenuAction::Gold});
                    items.push_back({"Spell ALL",MenuAction::Spells});
                    const char* names[]={"MP fixed at 9 (all characters)","Always LOMILWA","Always LATUMAPIC","Always MAPORFIC","Max creation bonus (species cap)","Mixed alignment at tavern"};
                    for(unsigned i=0;i<5;++i)items.push_back({std::string(names[i])+((assistMask&(1u<<i))?": ON":": OFF"),MenuAction::Assist,1u<<i});
                    if(game->supportsBugFix())items.push_back({std::string("Wiz1 bug Fix: ")+(game->bugFix()?"ON":"OFF"),MenuAction::BugFix});
                    items.push_back({std::string(names[5])+((assistMask&32)?": ON":": OFF"),MenuAction::Assist,32});
                    for(unsigned i=0;i<3;++i)items.push_back({std::string("Set alignment: ")+(i==0?"Good":i==1?"Neutral":"Evil"),MenuAction::Alignment,i});
                    if (game->supportsTurbo()) {
                        items.push_back({"Battle EXP: "+std::to_string(1u << battleMultiplierSteps[0])+"x",MenuAction::BattleMultiplier,0});
                        items.push_back({"Battle Gold: "+std::to_string(1u << battleMultiplierSteps[1])+"x",MenuAction::BattleMultiplier,1});
                    }
                    if(game->supportsRosterIdentity()) {
                        items.push_back({"Change race >",MenuAction::Race});
                        items.push_back({"Change class >",MenuAction::Class});
                    }
                }
                if(menuPage==MenuPage::Identity && game) {
                    const bool race=identityField==Session::RosterField::Race;
                    const auto* names=race?raceNames:classNames;
                    const unsigned count=race?std::size(raceNames):std::size(classNames);
                    const int current=game->rosterIdentity(bonusSlot,identityField);
                    for(unsigned i=0;i<count;++i)
                        items.push_back({std::string(names[i])+(int(i)==current?" (current)":""),MenuAction::SetIdentity,i});
                }
                if(menuPage==MenuPage::Roster && game) {
                    for(unsigned i=0;i<20;++i)items.push_back({game->rosterLabel(rosterOrder[i]),MenuAction::RosterEntry,rosterOrder[i]});
                }
                if(menuPage==MenuPage::Storage) {
                    items.push_back({std::string("Battery save: ")+(saveFormat==SaveFormat::Sav?".sav":".json"),MenuAction::Format});
                    items.push_back({std::string("Skip manufacturer screen: ")+(skipMaker?"ON":"OFF"),MenuAction::Maker});
                    if(game&&game->turboFileConnected())items.push_back({"Turbo File: connected",MenuAction::TurboFile});
                }
            }
            return items;
        };
        auto backMenu=[&]{
            if(menuPage==MenuPage::Root){menu=false;silence();return;}
            if(menuPage==MenuPage::Identity){menuPage=MenuPage::Difficulty;menuChoice=identityMenuReturn;return;}
            menuChoice=game?(menuPage==MenuPage::Roster?8:menuPage==MenuPage::Difficulty?7:menuPage==MenuPage::States?1:menuPage==MenuPage::Display?2:3):(menuPage==MenuPage::Display?0:1);
            menuPage=MenuPage::Root;
        };
        auto save = [&] {
            if (game) game->save();
        };
        auto launch = [&](const RomEntry& entry, bool persistent) {
            save();
            userstore::flush();
#ifdef SDL_PLATFORM_ANDROID
            if(!userstore::ready())throw std::runtime_error("Select Documents/Wiiz folder before starting a ROM");
            const auto saveFolder = fs::path("/wiiz-shared/Save");
#else
            const auto saveFolder = persistent ? prefs / "saves" : smoke && argc > 7 ? pathFromUtf8(argv[7]) : fs::path{};
#endif
            auto next = std::make_unique<Session>(entry, saveFolder, saveFormat, skipMaker);
#ifdef SDL_PLATFORM_ANDROID
            next->stateFolder(fs::path("/wiiz-shared/state"));
#else
            next->stateFolder((smoke && argc>7 ? pathFromUtf8(argv[7]).parent_path() : prefs) / "states");
#endif
            if(next->supportsBugFix() && wiz1BugFix)next->bugFix(true);
            next->assists(next->supportsTurbo()?assistMask:0,false);
            next->battleMultipliers(1u << battleMultiplierSteps[0], 1u << battleMultiplierSteps[1]);
            game = std::move(next); activeRom = entry.path; silence(); menu = false;
#ifdef SDL_PLATFORM_ANDROID
            androidGameActive = true;
#endif
            SDL_SetWindowTitle(window, ("Wiiz " WIIZ_VERSION " / " + entry.title + " / " + utf8(entry.path.filename())).c_str());
            status = !entry.identity.knownLayout ? "Wiz program recognized. Unverified code revision: 1x / raw battery SRAM." : stream ? "" : "Audio device unavailable; running without sound.";
        };
        scan();
        if (smoke && !librarySmoke) launch(identifyRom(pathFromUtf8(argv[2])), false);
        else if (argc == 2) launch(identifyRom(pathFromUtf8(argv[1])), true);
        double nextFrame = double(SDL_GetPerformanceCounter()) / double(SDL_GetPerformanceFrequency());
        Uint64 nextSave = SDL_GetTicks() + 2000;
        auto stateAction = [&](unsigned slot, bool load) {
            if (!game) { status = "Select a game before using state slots."; return; }
            try {
                if (load) { game->loadState(slot); silence(); ++stateLoads; if(menuPage==MenuPage::Items){menu=false;menuPage=MenuPage::Root;} }
                else { game->saveState(slot); userstore::flush(); ++stateSaves; }
                status = std::string(load ? "Loaded" : "Saved") + " state slot " + std::to_string(slot) + ".";
            } catch (const std::exception& ex) { status = ex.what(); ++stateErrors; }
        };
        while (running) {
            SDL_PumpEvents();
            gamepads.poll(focused && !pending, menu || !game);
            for (const auto& item : replay) if (item.frame == frames) {
                SDL_Event event{}; event.type = item.down ? SDL_EVENT_KEY_DOWN : SDL_EVENT_KEY_UP;
                event.key.key = item.key; event.key.down = item.down;
                event.key.mod = item.shift ? SDL_KMOD_SHIFT : SDL_KMOD_NONE;
                SDL_PushEvent(&event);
            }
            SDL_Event e;
            while (SDL_PollEvent(&e)) {
                if (e.type == SDL_EVENT_QUIT && !pending) {
                    if (game) { silence(); menu = true; menuPage=MenuPage::Root;menuChoice = 6; }
                    else running = false;
                }
#ifdef SDL_PLATFORM_ANDROID
                if (e.type == SDL_EVENT_WILL_ENTER_BACKGROUND) {
                    focused = false;
                    silence();
                    try { save(); } catch (const std::exception& ex) { status = ex.what(); }
                }
                if (e.type == SDL_EVENT_DID_ENTER_FOREGROUND) {
                    // Android may suspend/disconnect AAudio while another app owns audio.
                    // Reopen via SDL instead of trusting the old started flag/device state.
                    silence();
                    SDL_DestroyAudioStream(stream);
                    stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, nullptr, nullptr);
                    audioStarted = false;
                    if (!stream) status = SDL_GetError();
                    focused = true;
                    nextFrame = double(SDL_GetPerformanceCounter()) / double(SDL_GetPerformanceFrequency());
                }
#endif
                if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST) { focused = false; silence(); }
                if (e.type == SDL_EVENT_WINDOW_FOCUS_GAINED) { focused = true; nextFrame = double(SDL_GetPerformanceCounter()) / double(SDL_GetPerformanceFrequency()); }
                if (e.type == folderEvent) {
                    pending = false;
                    if (e.user.code == -1) status = "Folder selection failed.";
                    if (e.user.data1) {
                        const std::string path = static_cast<const char*>(e.user.data1); SDL_free(e.user.data1);
                        folder = pathFromUtf8(path); scan();
                        std::ofstream out(prefs / "rom-folder.txt", std::ios::binary | std::ios::trunc); out << path << '\n';
                        if (!out) status = "Folder selected, but its setting could not be saved.";
                    }
                }
#ifdef SDL_PLATFORM_ANDROID
                if (e.type == androidRomEvent || (e.type == SDL_EVENT_DROP_FILE && e.drop.data)) {
                    std::unique_ptr<char,decltype(&SDL_free)> owned(e.type==androidRomEvent?static_cast<char*>(e.user.data1):nullptr,SDL_free);
                    const fs::path source = pathFromUtf8(owned?owned.get():e.drop.data);
                    try {
                        if(!userstore::ready())throw std::runtime_error("Select Wiiz folder first");
                        const fs::path destination = source;
                        auto imported = identifyRom(destination);
                        folder = destination.parent_path();
                        scan();
                        launch(imported, true);
                    } catch (const std::exception& ex) {
                        status = std::string("ROM import failed: ") + ex.what();
                    }
                    std::error_code cleanupError;
                    // Cached ROM only; SAV/state are read/written directly through SAF.
                    continue;
                }
#endif
                if(!game && !menu && !pending && e.type==SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button==SDL_BUTTON_LEFT){
                    SDL_Event pointer=e;SDL_ConvertEventToRenderCoordinates(renderer,&pointer);
                    const int first=std::clamp(chosen-2,0,std::max(0,int(entries.size())-5));
                    const int row=int((pointer.button.y-156)/108);
                    if(pointer.button.x>=40&&pointer.button.x<984&&pointer.button.y>=156&&row>=0&&row<5&&first+row<int(entries.size())){
                        chosen=first+row;
                        try{launch(entries[chosen],!smoke);}catch(const std::exception& ex){status=ex.what();}
                    }
                    continue;
                }
                if(menu && e.type==SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button==SDL_BUTTON_LEFT){
                    SDL_Event pointer=e;SDL_ConvertEventToRenderCoordinates(renderer,&pointer);
                    if(menuPage==MenuPage::Items&&game){try{itemEditor.click(*game,pointer.button.x,pointer.button.y);}catch(const std::exception& ex){status=ex.what();}continue;}
                    const auto items=menuItems();
                    const int first=std::clamp(menuChoice-2,0,std::max(0,int(items.size())-6));
                    const int row=int((pointer.button.y-166)/88);
                    if(pointer.button.x>=40&&pointer.button.x<984&&pointer.button.y>=166&&row>=0&&row<6&&first+row<int(items.size())){
                        menuChoice=first+row;
                        SDL_Event press{};press.type=SDL_EVENT_KEY_DOWN;press.key.key=SDLK_X;press.key.down=true;SDL_PushEvent(&press);
                        press.type=SDL_EVENT_KEY_UP;press.key.down=false;SDL_PushEvent(&press);
                    }
                    continue;
                }
                if (e.type != SDL_EVENT_KEY_DOWN && e.type != SDL_EVENT_KEY_UP) continue;
                auto& sourcePressed = e.key.which == GamepadInput::keyboardId ? padPressed : pressed;
                if (e.type == SDL_EVENT_KEY_UP) { sourcePressed.erase(e.key.key);updateHeld();continue; }
                if (e.type != SDL_EVENT_KEY_DOWN || e.key.repeat || pending) continue;
                if (e.key.which == GamepadInput::keyboardId && !focused) continue;
                const auto key = canonicalKey(e.key.key);
#ifdef SDL_PLATFORM_ANDROID
                if (key == SDLK_F6) {
                    if(!game){folder=prefs/"shared-rom-cache";scan();}
                    continue;
                }
#endif
                if (key >= SDLK_F1 && key <= SDLK_F5) {
                    stateAction(unsigned(key-SDLK_F1)+1, (e.key.mod & SDL_KMOD_SHIFT)!=0);
                    continue;
                }
                if (key == SDLK_ESCAPE) {
                    if (game) {
                        try {
#ifdef SDL_PLATFORM_ANDROID
                            // The Android button means return to the title. Preserve
                            // the battery save and start the same ROM from power-on.
                            const auto entry = identifyRom(activeRom);
                            launch(entry, true);
                            status = "Battery saved; restarted the same ROM from power-on.";
#else
                            game->reset(); silence(); menu = false;
                            status = "Hardware reset signal sent to the current ROM.";
#endif
                            ++resets;
                        } catch (const std::exception& ex) { status = ex.what(); }
                    }
                    continue;
                }
                if (key == SDLK_Q) { menu = !menu; menuPage=MenuPage::Root;menuChoice = 0; stateLoadChoice = false; silence(); continue; }
                if (menu) {
                    if(menuPage==MenuPage::Items){try{if(!itemEditor.key(*game,key)){menu=false;silence();}}catch(const std::exception& ex){status=ex.what();}continue;}
                    if(key==SDLK_Z){
                        if(menuPage==MenuPage::Roster&&rosterPicked){menuChoice=int(rosterPicked)-1;resetRosterOrder();status="Move cancelled.";}
                        else backMenu();continue;
                    }
                    if(menuPage==MenuPage::Roster) {
                        if(key==SDLK_UP||key==SDLK_DOWN) {
                            const int next=std::clamp(menuChoice+(key==SDLK_UP?-1:1),0,19);
                            if(rosterPicked)std::swap(rosterOrder[menuChoice],rosterOrder[next]);
                            menuChoice=next;
                        } else if(key==SDLK_X)try {
                            if(!game->canSwapRoster())throw std::runtime_error("Reset first; open Q at the title before pressing game buttons.");
                            if(!rosterPicked){rosterPicked=rosterOrder[menuChoice];status="Up/Down: move character. X/Enter: confirm. Z: cancel.";}
                            else {
                                const unsigned target=unsigned(menuChoice)+1;
                                game->moveRoster(rosterPicked,target);if(rosterPicked!=target)++rosterSwaps;
                                bonusSlot=target;resetRosterOrder();silence();status="Roster order saved.";
                            }
                        } catch(const std::exception& ex){status=ex.what();}
                        continue;
                    }
                    auto items=menuItems();const int count=int(items.size());
                    if(key==SDLK_UP)menuChoice=(menuChoice+count-1)%count;
                    if(key==SDLK_DOWN)menuChoice=(menuChoice+1)%count;
                    const auto item=items.at(size_t(menuChoice));
                    if(item.action==MenuAction::Slot && (key==SDLK_LEFT||key==SDLK_RIGHT))stateLoadChoice=key==SDLK_RIGHT;
                    const bool adjust=(key==SDLK_LEFT||key==SDLK_RIGHT) && (item.action==MenuAction::BugFix||item.action==MenuAction::Assist||item.action==MenuAction::Character||item.action==MenuAction::Amount||item.action==MenuAction::Crt||item.action==MenuAction::Speed||item.action==MenuAction::Format||item.action==MenuAction::Maker||item.action==MenuAction::BattleMultiplier);
                    if(key==SDLK_X||adjust)try {
                        switch(item.action) {
                        case MenuAction::BugFix:{
                            game->bugFix(!game->bugFix());wiz1BugFix=game->bugFix();silence();
                            if(!smoke){std::ofstream out(prefs/"wiz1-bug-fix.txt");out<<int(wiz1BugFix)<<'\n';}
                            status="Wiz1 bug Fix changed. Game restarted with battery save preserved.";break;}
                        case MenuAction::Assist:{
                            const unsigned next=assistMask^item.slot;game->assists(next);assistMask=next;
                            if(!smoke){std::ofstream out(prefs/"assists.txt");out<<assistMask<<'\n';}
                            status=item.slot==16?((next&16)?"Maximum bonus applies to the next character you create.":"Original bonus generation applies to the next character you create."):"Assist setting changed. Learned spells and original casting restrictions still apply.";break;}
                        case MenuAction::Items:itemEditor.open(*game);menuPage=MenuPage::Items;menuChoice=0;silence();status="";break;
                        case MenuAction::Roster:menuPage=MenuPage::Roster;menuChoice=0;resetRosterOrder();status=game->canSwapRoster()?"Choose a character with Up/Down and X/Enter.":"Reset first; open Q at the title before pressing game buttons.";break;
                        case MenuAction::RosterEntry:break;
                        case MenuAction::Difficulty:menuPage=MenuPage::Difficulty;menuChoice=1;break;
                        case MenuAction::Character:bonusSlot=key==SDLK_LEFT?(bonusSlot==1?20:bonusSlot-1):(bonusSlot==20?1:bonusSlot+1);break;
                        case MenuAction::Amount:bonusAmount=(bonusAmount+(key==SDLK_LEFT?3:1))%4;break;
                        case MenuAction::BattleMultiplier:{
                            auto& step = battleMultiplierSteps[item.slot];
                            step = (step + (key == SDLK_LEFT ? 8 : 1)) % 9;
                            game->battleMultipliers(1u << battleMultiplierSteps[0], 1u << battleMultiplierSteps[1]);
                            if (!smoke) {
                                std::ofstream out(prefs/"battle-multipliers.txt");
                                out << battleMultiplierSteps[0] << ' ' << battleMultiplierSteps[1] << '\n';
                            }
                            break;}
                        case MenuAction::Alignment:
                            game->rosterBonus(bonusSlot,3,item.slot);status="Character alignment changed.";break;
                        case MenuAction::Race:case MenuAction::Class:{
                            identityField=item.action==MenuAction::Race?Session::RosterField::Race:Session::RosterField::Class;
                            const int current=game->rosterIdentity(bonusSlot,identityField);
                            if(current<0)throw std::runtime_error("This roster slot is empty.");
                            identityMenuReturn=menuChoice;
                            menuPage=MenuPage::Identity;
                            menuChoice=1+(item.action==MenuAction::Race&&current>=int(std::size(raceNames))?0:current);
                            status="Roster slot "+std::to_string(bonusSlot)+": choose a new "+(item.action==MenuAction::Race?"race.":"class.");
                            break;}
                        case MenuAction::SetIdentity:
                            game->setRosterIdentity(bonusSlot,identityField,item.slot);
                            status="Roster slot "+std::to_string(bonusSlot)+": "+item.label+".";
                            backMenu();break;
                        case MenuAction::Experience:case MenuAction::Gold:case MenuAction::Spells:
                            game->rosterBonus(bonusSlot,item.action==MenuAction::Experience?0:item.action==MenuAction::Gold?1:2,bonusAmounts[bonusAmount]);
                            ++bonusActions;status="Roster slot "+std::to_string(bonusSlot)+": "+(item.action==MenuAction::Spells?"all spells learned; MP unchanged.":item.action==MenuAction::Experience?"experience prepared; rest at the inn to level up.":"Gold added.");break;
                        case MenuAction::Back:backMenu();break;
                        case MenuAction::Resume:menu=false;silence();break;
                        case MenuAction::States:menuPage=MenuPage::States;menuChoice=1;stateLoadChoice=false;break;
                        case MenuAction::Display:menuPage=MenuPage::Display;menuChoice=1;break;
                        case MenuAction::Storage:menuPage=MenuPage::Storage;menuChoice=1;break;
                        case MenuAction::Games:save();userstore::flush();game.reset();silence();menu=false;menuPage=MenuPage::Root;scan();SDL_SetWindowTitle(window,"Wiiz " WIIZ_VERSION " / Game selection");break;
                        case MenuAction::Folder:silence();pending=true;SDL_ShowOpenFolderDialog(folderSelected,nullptr,window,utf8(folder).c_str(),false);break;
                        case MenuAction::Exit:save();userstore::flush();running=false;break;
                        case MenuAction::Slot:stateAction(item.slot,stateLoadChoice);break;
                        case MenuAction::Crt:
                            crtMode=(crtMode+(key==SDLK_LEFT?2:1))%3;
                            if(!smoke){std::ofstream out(prefs/"crt-mode.txt");out<<crtMode<<'\n';}
                            status=std::string("CRT display: ")+crtNames[crtMode]+". Game timing and audio are unchanged.";break;
                        case MenuAction::Speed:
                            speed=key==SDLK_LEFT?(speed==1?8:speed/2):(speed==8?1:speed*2);
                            if(!smoke){std::ofstream out(prefs/"speed.txt");out<<speed<<'\n';}
                            silence();status=game&&!game->supportsTurbo()?"This ROM uses 1x speed.":"Game speed changed; music and directional repeat use real time.";break;
                        case MenuAction::Format:{
                            const auto next=saveFormat==SaveFormat::Sav?SaveFormat::Json:SaveFormat::Sav;
                            if(game)game->saveFormat(next);saveFormat=next;
                            if(!smoke){std::ofstream out(prefs/"battery-format.txt");out<<(saveFormat==SaveFormat::Sav?"sav":"json")<<'\n';}
                            silence();status=saveFormat==SaveFormat::Sav?"Battery saves use .sav (checksums repaired on load).":"Battery saves use .json (checksums repaired on load).";break;}
                        case MenuAction::TurboFile:status="Original town-edge Turbo File menu. Image: "+game->turboFileLocation();break;
                        case MenuAction::Maker:
                            skipMaker=!skipMaker;if(game)game->skipMaker(skipMaker);
                            if(!smoke){std::ofstream out(prefs/"skip-maker.txt");out<<skipMaker<<'\n';}
                            silence();status="Manufacturer screen setting applies on next launch/reset.";break;
                        }
                    }catch(const std::exception& ex){status=ex.what();}
                } else if (!game) {
                    if (!entries.empty()) {
                        if (key == SDLK_UP) chosen = (chosen + int(entries.size()) - 1) % int(entries.size());
                        if (key == SDLK_DOWN) chosen = (chosen + 1) % int(entries.size());
                        if (key == SDLK_X) { try { launch(entries[chosen], !smoke); } catch (const std::exception& ex) { status = ex.what(); } }
                    }
                } else if(key==SDLK_I){try{silence();itemEditor.open(*game);menu=true;menuPage=MenuPage::Items;status="";}catch(const std::exception& ex){status=ex.what();}}
                else if(game->spellMap().mode) {
                    try{game->mapKey(key==SDLK_M&&game->spellMap().mode==3?PAD_B:button(key));status.clear();}
                    catch(const std::exception& ex){
                        status=ex.what();silence();
#ifdef SDL_PLATFORM_ANDROID
                        userstore::Bridge bridge;
                        const auto notify=bridge.env->GetMethodID(bridge.type,"showMapMoveUnavailable","()V");
                        bridge.env->CallVoidMethod(bridge.activity,notify);
#endif
                    }
                    if(game->spellMap().mode){sourcePressed.insert(e.key.key);updateHeld();}else{pressed.clear();padPressed.clear();held=0;}
                }
                else if(key==SDLK_M){silence();game->openMap();}
                else {sourcePressed.insert(e.key.key);updateHeld();}
            }
            if (!running) break;
            if (game && !menu && !pending && focused) {
                game->input(held);
                try {
                    userstore::check();
                    if (smoke && !turboSmoke) game->frame();
                    else game->tick(held, speed, turboSmoke ? uint64_t(frames)*1000/60 : SDL_GetTicks());
                    if (stream) {
                        size_t count = 0; const float* audio = game->audio(&count);
                        // Bound latency after a breakpoint/stall rather than accumulating old sound.
                        if (SDL_GetAudioStreamQueued(stream) > 48000 * int(sizeof(float)) / 5) SDL_ClearAudioStream(stream);
                        if (count && !SDL_PutAudioStreamData(stream, audio, int(count * sizeof(float)))) status = SDL_GetError();
#ifdef SDL_PLATFORM_ANDROID
                        if (!audioStarted && SDL_GetAudioStreamQueued(stream) >= 2400 * int(sizeof(float))) {
                            audioStarted = SDL_ResumeAudioStreamDevice(stream);
                            if (!audioStarted) status = SDL_GetError();
                        }
#endif
                    }
                    if (!smoke && SDL_GetTicks() >= nextSave) { save(); nextSave = SDL_GetTicks() + 2000; }
                } catch (const std::exception& ex) { status = ex.what(); silence(); menu = true; }
            }
            SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255); SDL_RenderClear(renderer);
#ifdef SDL_PLATFORM_ANDROID
            const bool androidPlay = game && !menu && !game->spellMap().mode;
            SDL_SetRenderLogicalPresentation(renderer, 1024, androidPlay ? 960 : 860, SDL_LOGICAL_PRESENTATION_LETTERBOX);
            if (!androidPlay) {
#endif
            if(game && !menu && !game->spellMap().mode) {
            text(renderer, 30, 20, "WIIZ / FC ORIGINAL DISPLAY");
            text(renderer, 30, 44, "Arrows  X/Enter:A  Z/Backspace:B  A/Tab:Select  S/Space:Start  Esc:Reset  Q:Settings");
            }
#ifdef SDL_PLATFORM_ANDROID
            }
#endif
            if (game) {
                SDL_Texture* display=screen;
                if(crtMode){SDL_UpdateTexture(crtScreen,nullptr,crt->render(game->pixels.data(),crtMode),CrtFilter::width*sizeof(uint32_t));display=crtScreen;}
                else SDL_UpdateTexture(screen,nullptr,game->pixels.data(),256*sizeof(uint32_t));
                SDL_FRect area{128,90,768,720};
#ifdef SDL_PLATFORM_ANDROID
                if (androidPlay) area = {0,0,1024,960};
#endif
                SDL_RenderTexture(renderer,display,nullptr,&area);
                drawSpellMap(renderer,*game);
#ifdef SDL_PLATFORM_ANDROID
                if (!androidPlay)
#endif
                if(!game->spellMap().mode)text(renderer,128,72,game->positionText());
            } else {
                wizFrame(renderer,{28,54,968,744});
                wizText(renderer,nullptr,68,82,"SELECT ROM",4);
                if(!entries.empty())wizText(renderer,nullptr,770,90,std::to_string(chosen+1)+"/"+std::to_string(entries.size()),3);
                const int first=std::clamp(chosen-2,0,std::max(0,int(entries.size())-5));
                for(int i=first;i<int(entries.size())&&i<first+5;++i){
                    const float y=156.f+(i-first)*108;
                    wizText(renderer,nullptr,56,y+40,i==chosen?">":" ",4);
                    wizText(renderer,nullptr,108,y,entries[i].title,2);
                    filenames.draw(108,y+28,utf8(entries[i].path.filename()),40,840);
                }
                if(entries.empty()){
                    wizText(renderer,nullptr,88,208,"NO ROMS",4);
#ifdef SDL_PLATFORM_ANDROID
                    filenames.draw(88,278,"「ファイル」からROMを取り込んでください",36,850);
#else
                    filenames.draw(88,278,"QメニューからROMフォルダーを選択してください",36,850);
#endif
                }
                wizText(renderer,nullptr,70,716,"UP/DOWN  A:PLAY",3);
                wizText(renderer,nullptr,70,756,"TAP A FILENAME TO PLAY",3);

            }
            if(menu && menuPage==MenuPage::Items && game)itemEditor.draw(renderer,*game);
            if(menu && menuPage!=MenuPage::Items) {
                const auto items=menuItems();
                constexpr int visible=6;constexpr float rowHeight=88, rowTop=166;
                const int first=std::clamp(menuChoice-2,0,std::max(0,int(items.size())-visible));
                wizFrame(renderer,{28,54,968,744});
                const char* heading=menuPage==MenuPage::Root?"OPTIONS":menuPage==MenuPage::States?"STATE SAVE / LOAD":menuPage==MenuPage::Display?"DISPLAY / SPEED":menuPage==MenuPage::Roster?"ROSTER":menuPage==MenuPage::Difficulty?"DIFFICULTY":menuPage==MenuPage::Identity?(identityField==Session::RosterField::Race?"CHANGE RACE":"CHANGE CLASS"):"SAVE / STARTUP";
                wizText(renderer,game.get(),68,82,heading,4);
                wizText(renderer,game.get(),770,90,std::to_string(menuChoice+1)+"/"+std::to_string(items.size()),3);
                auto shortLabel=[](std::string s){
                    if(s=="Difficulty / bonuses  >")return std::string("Difficulty >");
                    if(s=="Roster order (title only)  >")return std::string("Roster order >");
                    if(s=="Game selection / rescan")return std::string("Game selection");
                    if(s=="Select ROM folder")return std::string("ROM folder");
                    if(s=="Rescan ROM folder")return std::string("Rescan ROMs");
                    if(s.rfind("Skip manufacturer screen: ",0)==0)s="Skip logo"+s.substr(s.rfind(':'));
                    if(s.rfind("MP fixed at 9 (all characters)",0)==0)s="MP FIXED AT 9"+s.substr(s.rfind(':'));
                    if(s.rfind("Max creation bonus (species cap)",0)==0)s="MAX CREATION BONUS"+s.substr(s.rfind(':'));
                    if(s.rfind("Mixed alignment at tavern",0)==0)s="MIXED PARTY"+s.substr(s.rfind(':'));
                    if(s.size()>25)s=s.substr(0,22)+"...";
                    return s;
                };
                for(int i=first;i<int(items.size())&&i<first+visible;++i){
                    const float y=rowTop+(i-first)*rowHeight;
                    wizText(renderer,game.get(),56,y+16,i==menuChoice?(rosterPicked&&menuPage==MenuPage::Roster?"*":">"):" ",4);
                    const auto label=items[i].action==MenuAction::Character?"Character "+std::to_string(bonusSlot):shortLabel(items[i].label);
                    wizText(renderer,game.get(),100,y+16,label,4);
                    if(game&&items[i].action==MenuAction::Experience) {
                        const unsigned level=game->rosterExperienceLevel(bonusSlot);
                        wizText(renderer,game.get(),100,y+52,"EXP EST. LV: "+(level?std::to_string(level):std::string("--")),3);
                    }
                    if(game&&(items[i].action==MenuAction::Character||items[i].action==MenuAction::RosterEntry)){
                        const auto name=game->rosterNamePixels(items[i].action==MenuAction::RosterEntry?items[i].slot:bonusSlot);
                        SDL_SetRenderDrawColor(renderer,240,240,240,255);
                        std::vector<SDL_FRect> pixels;
                        for(unsigned py=0;py<8;++py)for(unsigned px=0;px<64;++px)if(name[py*64+px])pixels.push_back({640.f+px*4,y+16+py*4,4,4});
                        if(!pixels.empty())SDL_RenderFillRects(renderer,pixels.data(),int(pixels.size()));
                    }
                }
                wizText(renderer,game.get(),70,716,gamepads.navigationHint(),3);
                wizText(renderer,game.get(),70,756,"LEFT/RIGHT:CHANGE",3);
            }

#ifdef SDL_PLATFORM_ANDROID
            const float statusY = androidPlay ? 940.f : 830.f;
#else
            const float statusY = 830.f;
#endif
            text(renderer, 30, statusY, status.size() > 120 ? status.substr(0, 117) + "..." : status);
            if (smoke && frames == smokeFrames - 1 && argc > 3 && !screenshot(renderer, argv[3])) throw std::runtime_error(SDL_GetError());
            SDL_RenderPresent(renderer);
            if (smoke && ++frames >= smokeFrames) running = false;
            if (!smoke) {
                nextFrame += 1.0 / 60.0988;
                double now = double(SDL_GetPerformanceCounter()) / double(SDL_GetPerformanceFrequency());
                if (nextFrame > now) SDL_DelayNS(Uint64((nextFrame-now)*1e9));
                else if (now-nextFrame > 0.1) nextFrame = now;
            }
        }
#ifdef SDL_PLATFORM_ANDROID
        androidGameActive = false;
#endif
        if (!smoke) { save(); userstore::flush(); }
        else std::printf("SMOKE_OK game=%s menu=%d resets=%d frames=%d fast_drawing=%d speed=%u state_saves=%d state_loads=%d state_errors=%d held=%u save_format=%s skip_maker=%d title_ready=%u crt=%u menu_page=%u bonus_actions=%d assist_mask=%u roster_swaps=%d wiz1_bug_fix=%d\n", game ? game->title.c_str() : "none", int(menu), resets, frames, int(fastDrawing), turboSmoke && game && game->supportsTurbo() ? speed : 1, stateSaves,stateLoads,stateErrors,held,saveFormat==SaveFormat::Sav?"sav":"json",int(skipMaker),game?wiiz_core_title_ready(game->core()):0,crtMode,unsigned(menuPage),bonusActions,game?game->assists():0,rosterSwaps,game?int(game->bugFix()):0);
        game.reset(); SDL_DestroyAudioStream(stream); SDL_DestroyTexture(crtScreen);SDL_DestroyTexture(screen);
        filenames.clear();
        SDL_DestroyRenderer(renderer); SDL_DestroyWindow(window); gamepads.close(); SDL_Quit(); return 0;
    } catch (const std::exception& ex) { std::fprintf(stderr, "%s\n", ex.what()); SDL_Quit(); return 1; }
}

