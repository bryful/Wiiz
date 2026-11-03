#include "dungeon.hpp"
#include <SDL3/SDL.h>
#include "picosha2.h"
#include "rom_identity.hpp"
#include <algorithm>
#include <memory>
#include <stdexcept>

Dungeon readDungeon(const char* path) {
    size_t size = 0;
    std::unique_ptr<void, decltype(&SDL_free)> data(SDL_LoadFile(path, &size), SDL_free);
    if (!data) throw std::runtime_error(SDL_GetError());
    if (size > 1024 * 1024) throw std::runtime_error("ROM is too large");
    const auto* rom = static_cast<const uint8_t*>(data.get());
    const auto identity=inspectWizardry(rom,size);
    const int game=identity.scenario;
    if(!identity.knownLayout)throw std::runtime_error("Dungeon offsets are unverified for this code revision");
    auto word = [&](size_t at) -> size_t {
        if (at + 1 >= size) throw std::runtime_error("ROM pointer outside file");
        return rom[at] | (size_t(rom[at + 1]) << 8);
    };
    Dungeon result;
    result.title = "Wiiz / Wizardry FC " + std::to_string(game);
    for (int id = 1; id <= (game == 1 ? 10 : 6); ++id) {
        const size_t base = identity.prgOffset + (game == 1 ? 0x10000 : 0x12000);
        const size_t walls = base + word(base + (game == 1 ? 0x5c : 0) + id * 2) - 0x8000;
        const size_t flags = game == 1 ? base + word(base + 0x70 + id * 2) - 0x8000 : walls + 400;
        if (walls + 400 > size || flags + 400 > size) throw std::runtime_error("Invalid dungeon range");
        Floor floor;
        std::copy_n(rom + walls, 400, floor.walls.begin());
        std::copy_n(rom + flags, 400, floor.flags.begin());
        result.floors.push_back(floor);
    }
    return result;
}
