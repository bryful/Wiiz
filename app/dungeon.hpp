#pragma once
#include <array>
#include <cstdint>
#include <string>
#include <vector>

struct Floor {
    std::array<uint8_t, 400> walls{}, flags{};
};
struct Dungeon {
    std::string title;
    std::vector<Floor> floors;
};
// ROM-specific extraction only; CPU/APU/PPU emulation is not implemented here.
Dungeon readDungeon(const char* path);
