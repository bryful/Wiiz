#pragma once
#include <cstddef>
#include <cstdint>
struct RomIdentity {
    int scenario=0, mapper=0;
    size_t prgOffset=0, prgBytes=0, chrBytes=0;
    bool knownLayout=false, enhancedWiz1=false, verifiedSound=false, enhanced=false, verifiedBoot=false;
};
// Identify program structure, independently of filename, default characters and graphics.
RomIdentity inspectWizardry(const uint8_t* bytes, size_t size);
