#include "rom_identity.hpp"
#include "rom_identity_data.hpp"
#include "picosha2.h"
#include <array>
#include <stdexcept>
#include <string>
RomIdentity inspectWizardry(const uint8_t* bytes,size_t size) {
    if(size<16 || bytes[0]!='N'||bytes[1]!='E'||bytes[2]!='S'||bytes[3]!=0x1a)
        throw std::runtime_error("Not an iNES ROM");
    if((bytes[7]&12)==8)throw std::runtime_error("NES 2.0 ROM identification is not implemented");
    RomIdentity result;
    result.mapper=(bytes[6]>>4)|(bytes[7]&240);
    result.prgOffset=16+((bytes[6]&4)?512:0);result.prgBytes=size_t(bytes[4])*16384;result.chrBytes=size_t(bytes[5])*8192;
    if(result.prgBytes<32768 || result.chrBytes==0 || result.prgOffset+result.prgBytes+result.chrBytes>size)
        throw std::runtime_error("Truncated or unsupported iNES ROM");
    const uint8_t* prg=bytes+result.prgOffset;
    const size_t fixedBase=result.prgBytes-16384;
    auto hash=[&](size_t offset,size_t length){return picosha2::hash256_hex_string(prg+offset,prg+offset+length);};
    std::array<std::string,6> signatures;
    for(size_t i=0;i<6;++i)signatures[i]=hash(fixedBase+identityWindows[i],identityWindowSize);
    const IdentityFingerprint* match=nullptr;
    for(const auto& profile:identityFingerprints) {
        if(profile.mapper!=result.mapper)continue;
        unsigned votes=0;for(size_t i=0;i<6;++i)if(signatures[i]==profile.signatures[i])++votes;
        if(votes<identityMinMatches)continue;
        if(match)throw std::runtime_error("Ambiguous Wizardry program identity");
        match=&profile;
    }
    if(!match)throw std::runtime_error("Program is not a recognized Wizardry FC I/II/III family");
    result.scenario=match->scenario;
    // Tolerate code changes for ordinary emulation, but do not apply unverified RAM layouts.
    result.knownLayout=result.prgBytes==131072 && hash(fixedBase,16384)==match->fixed && hash(0x18000,16384)==match->camp;
    result.verifiedSound=result.prgBytes==131072 && hash(result.scenario==1?0x8000:0xa000,result.scenario==1?16384:8192)==match->sound;
    result.enhancedWiz1=result.scenario==1 && result.knownLayout && result.verifiedSound;
    result.enhanced=result.knownLayout && result.verifiedSound && (result.scenario==1 || hash(0xc000,16384)==match->spell);
    result.verifiedBoot=result.enhanced && hash(result.scenario==1?0x18000:0x8700,result.scenario==1?0x100:0x300)==match->boot;
    return result;
}
