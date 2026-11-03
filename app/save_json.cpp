// Character layouts/checksum reconstruction adapted from bryful/Wiz (MIT).
// Copyright (c) 2019 bryful. See third_party/wiz-save/LICENSE and PROVENANCE.json.
#include "save_json.hpp"
#include "json.hpp"
#include <array>
#include <algorithm>
#include <stdexcept>
#include <cstdio>
using Json = nlohmann::ordered_json;
namespace {
unsigned number(const Json& value, unsigned maximum) {
    if (!value.is_number_integer() || value.get<int64_t>() < 0 || value.get<uint64_t>() > maximum)
        throw std::runtime_error("Save JSON contains an out-of-range integer");
    return value.get<unsigned>();
}
std::vector<uint8_t> bytes(const Json& value, size_t size) {
    if (!value.is_array() || value.size() != size) throw std::runtime_error("Save JSON byte-array size mismatch");
    std::vector<uint8_t> out; out.reserve(size);
    for (const auto& v : value) out.push_back(uint8_t(number(v,255)));
    return out;
}
uint16_t crc16(const uint8_t* p, size_t size) {
    // CRC16.Calc: CCITT, polynomial 0x1021, initial value 0xFFFF.
    uint16_t crc=0xffff;
    for (size_t i=0;i<size;++i) {
        crc ^= uint16_t(p[i]) << 8;
        for (int bit=0;bit<8;++bit) crc=uint16_t((crc<<1)^((crc&0x8000)?0x1021:0));
    }
    return crc;
}
struct Layout { size_t start, stride, payload; };
Layout layout(int scenario) {
    if (scenario<1 || scenario>3) throw std::runtime_error("Unknown battery layout");
    return scenario==1 ? Layout{0,256,112} : Layout{1024,96,94};
}
std::vector<std::pair<size_t,size_t>> regions(int scenario) {
    if (scenario==1) return {{0x1400,0xc00}};
    return {{0,0x400},{0xb80,0xc80},{0x1f80,0x80}};
}
std::string hexOffset(size_t offset) { char text[8]; std::snprintf(text,sizeof(text),"%02X",unsigned(offset)); return text; }
void repair(std::vector<uint8_t>& data, int scenario) {
    const auto l=layout(scenario);
    for (size_t i=0;i<20;++i) {
        auto* c=data.data()+l.start+i*l.stride;
        if (scenario==1) {
            for (size_t k=0;k<14;++k) {
                // ROM $F21C: A=8, CLC, eight ADCs. Carry feeds the next ADC;
                // the carry OUT of the final byte is discarded, not folded back.
                unsigned accumulator=8,carry=0;
                for(size_t n=0;n<8;++n){const unsigned sum=accumulator+c[k*8+n]+carry;accumulator=sum&255;carry=sum>>8;}
                c[0x70+k]=uint8_t(accumulator);
            }
            const auto crc=crc16(c,126); c[126]=uint8_t(crc>>8);c[127]=uint8_t(crc);
            for (size_t n=0;n<128;++n) { const unsigned v=c[n]^255; c[255-n]=uint8_t((v<<4)|(v>>4)); }
        } else if(c[0]) {
            const auto crc=crc16(c,94);c[94]=uint8_t(crc>>8);c[95]=uint8_t(crc);
        }
    }
    if (scenario!=1) std::copy_n(data.begin()+0x400,20*96,data.begin()+0x1800);
}
}
std::string encodeBattery(const std::vector<uint8_t>& data, int scenario, const std::string& sha) {
    if(data.size()!=8192) throw std::runtime_error("Battery RAM must be 8192 bytes");
    const auto l=layout(scenario);
    Json root={{"format","wiiz-battery"},{"version",1},{"rom_sha256",sha},{"scenario",scenario},
               {"checksum_validation",false},{"characters",Json::array()},{"memory_regions",Json::array()}};
    for(size_t i=0;i<20;++i) {
        const auto* c=data.data()+l.start+i*l.stride;
        std::vector<bool> mapped(l.payload,false);
        Json entry={{"slot",i+1}};
        auto field=[&](const char* name,size_t offset,unsigned mask=255,unsigned shift=0) {
            entry[name]=(c[offset]>>shift)&mask; mapped[offset]=true;
        };
        field("in_use",0);field("name_length",1);
        entry["name_codes"]=std::vector<uint8_t>(c+2,c+10);std::fill(mapped.begin()+2,mapped.begin()+10,true);
        field("race",10,7,scenario==1?0:5);
        field("class",scenario==1?11:10,7,scenario==1?0:2);
        field("alignment",scenario==1?12:10,3);
        if(scenario==1) entry["identity_reserved_bits"]={c[10]&248,c[11]&248,c[12]&252};
        const size_t ability=scenario==1?13:11;
        const char* names[]={"strength","intelligence","piety","vitality","agility","luck"};
        for(size_t n=0;n<6;++n) field(names[n],ability+n);
        const size_t level=scenario==1?35:33;
        entry["level"]=(unsigned(c[level])<<8)|c[level+1];mapped[level]=mapped[level+1]=true;
        field("age_raw",scenario==1?38:36);
        entry["unmapped_bytes"]=Json::object();
        for(size_t n=0;n<l.payload;++n) if(!mapped[n]) entry["unmapped_bytes"][hexOffset(n)]=c[n];
        root["characters"].push_back(std::move(entry));
    }
    for(auto [offset,size]:regions(scenario)) root["memory_regions"].push_back({{"offset",offset},{"bytes",std::vector<uint8_t>(data.begin()+offset,data.begin()+offset+size)}});
    return root.dump(2)+"\n";
}
std::vector<uint8_t> decodeBattery(const std::string& text, int scenario, const std::string& sha) {
    const auto root=Json::parse(text); const auto l=layout(scenario);
    if(root.at("format")!="wiiz-battery" || root.at("version")!=1 || root.at("rom_sha256")!=sha || root.at("scenario")!=scenario)
        throw std::runtime_error("Save JSON format/version/ROM does not match");
    const auto& chars=root.at("characters"); if(!chars.is_array()||chars.size()!=20) throw std::runtime_error("Save JSON must contain 20 character slots");
    std::vector<uint8_t> data(8192,0);
    for(size_t i=0;i<20;++i) {
        const auto& entry=chars[i]; auto* c=data.data()+l.start+i*l.stride;
        if(number(entry.at("slot"),20)!=i+1) throw std::runtime_error("Character slot order mismatch");
        std::vector<bool> mapped(l.payload,false);
        auto field=[&](const char* name,size_t offset,unsigned mask=255,unsigned shift=0) {
            c[offset]|=uint8_t(number(entry.at(name),mask)<<shift);mapped[offset]=true;
        };
        field("in_use",0);field("name_length",1);
        const auto name=bytes(entry.at("name_codes"),8);std::copy(name.begin(),name.end(),c+2);std::fill(mapped.begin()+2,mapped.begin()+10,true);
        field("race",10,7,scenario==1?0:5);field("class",scenario==1?11:10,7,scenario==1?0:2);field("alignment",scenario==1?12:10,3);
        if(scenario==1) {
            const auto extra=bytes(entry.at("identity_reserved_bits"),3);
            if((extra[0]&7)||(extra[1]&7)||(extra[2]&3)) throw std::runtime_error("Identity reserved bits overlap fields");
            for(size_t n=0;n<3;++n)c[10+n]|=extra[n];
        }
        const size_t ability=scenario==1?13:11;const char* names[]={"strength","intelligence","piety","vitality","agility","luck"};
        for(size_t n=0;n<6;++n) field(names[n],ability+n);
        const size_t level=scenario==1?35:33;const unsigned lv=number(entry.at("level"),65535);c[level]=uint8_t(lv>>8);c[level+1]=uint8_t(lv);mapped[level]=mapped[level+1]=true;
        field("age_raw",scenario==1?38:36);
        const auto& unmapped=entry.at("unmapped_bytes");size_t expected=0;
        for(size_t n=0;n<l.payload;++n)if(!mapped[n]){c[n]=uint8_t(number(unmapped.at(hexOffset(n)),255));++expected;}
        if(!unmapped.is_object()||unmapped.size()!=expected)throw std::runtime_error("Unknown or duplicate character bytes");
    }
    const auto& memory=root.at("memory_regions");const auto ranges=regions(scenario);
    if(!memory.is_array()||memory.size()!=ranges.size())throw std::runtime_error("Memory region count mismatch");
    for(size_t i=0;i<ranges.size();++i) {
        auto [offset,size]=ranges[i];if(number(memory[i].at("offset"),8191)!=offset)throw std::runtime_error("Memory region offset mismatch");
        auto part=bytes(memory[i].at("bytes"),size);std::copy(part.begin(),part.end(),data.begin()+offset);
    }
    // No input checksum is required or checked. Reconstruct original-ROM checks and mirrors.
    repair(data,scenario);
    return data;
}

void repairBattery(std::vector<uint8_t>& bytes,int scenario) {
    if(bytes.size()!=8192)throw std::runtime_error("Battery RAM must be 8192 bytes");
    repair(bytes,scenario);
}

void swapRosterRecords(std::vector<uint8_t>& data,int scenario,unsigned first,unsigned second) {
    if(data.size()!=8192||first<1||first>20||second<1||second>20)throw std::runtime_error("Roster slots must be 1..20");
    const auto l=layout(scenario);if(first==second)return;
    const size_t count=scenario==1?0x1def:0xb81,list=scenario==1?0x1ddc:0xb82;
    if(data[count]>6)throw std::runtime_error("Invalid saved party size");
    // WizData.SwapChar exchanges the complete record, including unmapped fields.
    auto a=data.begin()+l.start+(first-1)*l.stride,b=data.begin()+l.start+(second-1)*l.stride;
    std::swap_ranges(a,a+l.stride,b);
    // Original tavern party references: FC-I uses record page addresses ($60..$73),
    // FC-II/III use zero-based roster indices. Keep the same people in the party.
    const unsigned x=(scenario==1?0x60:0)+first-1,y=(scenario==1?0x60:0)+second-1;
    for(unsigned i=0;i<data[count];++i) {
        auto& ref=data[list+i];if(ref==x)ref=uint8_t(y);else if(ref==y)ref=uint8_t(x);
    }
    repairBattery(data,scenario);
}
