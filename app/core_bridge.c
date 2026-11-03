/* Application glue. binjnes has an optional RAM-write callback; timing/graphics are unchanged. */
#include "core_bridge.h"
#include "emulator.h"
#include "../third_party/mame-turbofile/turbofile_device.h"
#include <stdlib.h>
#include <string.h>

struct WiizCore {
    Emulator* e;
    WiizTurboFile turbofile;
    unsigned buttons;
    float audio[4096];
    size_t audio_count;
    unsigned sound_commands[3];
    int sound_role;
    unsigned repeat_events[4], initial_events[4];
    unsigned map_profile, map_events, title_ready, assists, creation_events, roster_editable;
};
int wiiz_core_prg_byte(WiizCore* core,size_t offset,unsigned value) {
    if(offset >= (size_t)core->e->ci.prg16k_banks*16384 || value>255)return 0;
    core->e->ci.prg_data[offset]=(uint8_t)value;return 1;
}
/* ROM-specific freeze targets; CPU/PPU/APU/mapper execution remains binjnes. */
static int assist_value(WiizCore* core, unsigned addr) {
    if(!core->assists || !core->title_ready || core->sound_role==2)return -1;
    const unsigned game=core->map_profile;
    if((core->assists&1) && addr>=0x6000 && addr<0x8000) {
        const unsigned offset=addr-0x6000,start=game==1?0:0x400,stride=game==1?256:96;
        if(offset>=start && offset<start+20*stride) {
            const unsigned record=(offset-start)/stride,field=(offset-start)%stride;
            if(core->e->s.c.prg_ram[start+record*stride] && field>=(game==1?0x29u:0x27u) && field<(game==1?0x45u:0x35u))return game==1?9:0x99;
        }
    }
    const unsigned light=game==1?0x27f:game==2?0x77ef:0x6d99;
    const unsigned protect=game==1?0x281:light+1,identify=game==1?0x280:light+2;
    if((core->assists&2)&&addr==light)return 255;
    if((core->assists&4)&&addr==identify)return 255;
    if((core->assists&8)&&addr==protect)return game==1?254:2;
    return -1;
}
static void put_assist(WiizCore* core,unsigned addr,unsigned value) {
    if(addr<0x800)core->e->s.c.ram[addr]=(uint8_t)value;
    else {core->e->s.c.prg_ram[addr-0x6000]=(uint8_t)value;core->e->s.m.prg_ram_updated=true;}
}
static void apply_assists(WiizCore* core) {
    if(!core->assists||!core->title_ready||core->sound_role==2)return;
    const unsigned game=core->map_profile,start=game==1?0:0x400,stride=game==1?256:96;
    if(core->assists&1)for(unsigned c=0;c<20;++c) {
        if(!core->e->s.c.prg_ram[start+c*stride])continue;
        for(unsigned f=game==1?0x29:0x27;f<(game==1?0x45u:0x35u);++f)put_assist(core,0x6000+start+c*stride+f,game==1?9:0x99);
    }
    const unsigned light=game==1?0x27f:game==2?0x77ef:0x6d99;
    const unsigned targets[]={light,game==1?0x280:light+2,game==1?0x281:light+1};
    for(unsigned i=0;i<3;++i)if(core->assists&(2u<<i))put_assist(core,targets[i],i==2?(game==1?254:2):255);
}
void wiiz_core_assists(WiizCore* core,unsigned mask,int ready) {
    core->assists=mask&63;
    /* Original tavern eligibility filter only. Keep status/location checks. */
    if(core->map_profile && core->sound_role!=2) {
        const unsigned game=core->map_profile;
        const size_t at=game==1?0x18ad5:game==2?0x1f34b:0x1f3c7;
        wiiz_core_prg_byte(core,at,(mask&32)?(game==1?0xa9:0xea):(game==1?0x25:0xd0));
        wiiz_core_prg_byte(core,at+1,(mask&32)?(game==1?0:0xea):(game==1?0x0f:0x06));
    }
    if(ready)core->title_ready=1;apply_assists(core);
}
unsigned wiiz_core_assist_mask(WiizCore* core){return core->assists;}
unsigned wiiz_core_creation_events(WiizCore* core){return core->creation_events;}
static bool sound_write(Emulator* e, uint16_t addr, uint8_t value, void* userdata) {
    WiizCore* core = userdata;
    const unsigned profile=core->map_profile ? core->map_profile : 1;
    const int forced=assist_value(core,addr);
    if(forced>=0){put_assist(core,addr,(unsigned)forced);return false;}
    const unsigned pc=e->s.c.PC.val;
    const unsigned bank=pc>=0x8000 ? (e->s.m.prg8k_bank[(pc-0x8000)/8192] & (e->ci.prg8k_banks-1)) : 0;
    /* Wiz1's original creation stores both initial HP bytes here. Clamp only
       this event, after the original RNG/math; never clamp live combat HP. */
    if(core->map_profile==1 && core->sound_role!=2 && bank/2==6 && pc==0xa294 &&
       addr>=0x6020 && addr<=0x7320 && (addr&255)==0x20 &&
       e->s.c.prg_ram[addr-0x6000+1]==0 && e->s.c.prg_ram[addr-0x6000+2]<=15) {
        put_assist(core,addr,15);
        put_assist(core,addr+2,15);
        return false;
    }
    /* The final species-base copy happens once per original bonus generation.
       Only replace the initial pool; original allocation/refunds must still run. */
    const bool creation=core->sound_role!=2 &&
        ((profile==1 && bank/2==6 && pc==0x9d93 && addr==0x254) ||
         (profile==2 && bank==14 && pc==0xdc14 && addr==0x58) ||
         (profile==3 && bank==14 && pc==0xdbe4 && addr==0x58));
    if(creation) {
        ++core->creation_events;
        if(core->assists&16) {
            unsigned points=60;
            if(profile<3) {
                unsigned base=0;
                for(unsigned i=0;i<6;++i) {
                    const unsigned at=(profile==1?0x254:0x53)+i;
                    base+=at==addr?value:e->s.c.ram[at];
                }
                points=base<=108?108-base:0;
            }
            e->s.c.ram[profile==1?0x25b:0x40]=(uint8_t)points;
        }
    }
    if(core->map_profile) {
        if(profile==1 && bank/2==6 && pc==0x800d && addr==0x600 && value==1){core->title_ready=1;core->roster_editable=1;}
        if(profile>1 && bank==4 && pc==(profile==2?0x88a2u:0x890cu) && addr==0x603 && value==1){core->title_ready=1;core->roster_editable=1;}
        if(profile==1) {
            if(addr==0x279 && pc==0xd2d9)core->map_events|=4;
            if(bank/2==2 && addr==0x0e && pc==0xa66d)core->map_events|=1;
            if(bank/2==6 && addr==0x2b && pc==0xb488)core->map_events|=2;
        } else {
            if(bank==13 && addr==0xbf && (pc&0x1fff)==(profile==2?0x00cau:0x05dcu))core->map_events|=4;
            if(bank==12 && addr==0xb1 && (pc&0x1fff)==(profile==2?0x104du:0x1035u))core->map_events|=1;
            if(bank==7 && addr==0xc2 && (pc&0x1fff)==(profile==2?0x0eb2u:0x0d82u))core->map_events|=2;
        }
    }
    if(core->map_events)core->title_ready=1;
    if(core->sound_role==1) {
        if(profile==1 && addr>=0x1d && addr<=0x20 && value==0)++core->repeat_events[addr-0x1d];
        if(profile>1 && addr>=0x10 && addr<=0x13 && value==0xf1)++core->initial_events[0x13-addr];
        if(profile>1 && addr>=0x10 && addr<=0x13 && value==(profile==2?0xfa:0xfb))++core->repeat_events[0x13-addr];
    }
    if (addr < 0x600 || addr > (profile==1?0x602:0x603)) return true;
    const bool driver = profile==1 ? pc>=0x8000 && pc<0xc000 && bank/2==2 : bank==5;
    if (driver) return true;  /* Original sound driver's own completion/stop writes. */
    if (core->sound_role == 1 && addr<=0x602) core->sound_commands[addr-0x600] = 0x100 | value;
    return core->sound_role != 2;  /* Sound-only core ignores its unrelated title-scene requests. */
}
void wiiz_core_sound_source(WiizCore* core) {
    core->sound_role = 1;
    core->e->ram_write_filter = sound_write;
    core->e->ram_write_user_data = core;
}
void wiiz_core_sound_player(WiizCore* core) {
    core->sound_role = 2;
    core->e->ram_write_filter = sound_write;
    core->e->ram_write_user_data = core;
}
unsigned wiiz_core_take_sound(WiizCore* core, unsigned reg) {
    if (reg >= 3) return 0;
    const unsigned command = core->sound_commands[reg]; core->sound_commands[reg] = 0; return command;
}
void wiiz_core_sound_command(WiizCore* core, unsigned reg, unsigned value) {
    if (reg < 4) core->e->s.c.ram[0x600+reg] = (uint8_t)value;
}
unsigned wiiz_core_current_sound(WiizCore* core, unsigned reg) {
    return reg < 4 ? core->e->s.c.ram[0x600+reg] : 0;
}
unsigned wiiz_core_repeat_events(WiizCore* core, unsigned direction) { return direction < 4 ? core->repeat_events[direction] : 0; }
unsigned wiiz_core_initial_events(WiizCore* core,unsigned direction) {return direction<4?core->initial_events[direction]:0;}
void wiiz_core_profile(WiizCore* core,unsigned scenario) {core->map_profile=scenario;core->e->ram_write_filter=sound_write;core->e->ram_write_user_data=core;}
void wiiz_core_map_profile(WiizCore* core) {wiiz_core_profile(core,1);}
unsigned wiiz_core_map_event(WiizCore* core) {unsigned result=core->map_events;core->map_events=0;return result;}
unsigned wiiz_core_map_position(WiizCore* core) {
    const uint8_t* ram=core->e->s.c.ram;
    if(core->map_profile>1)return ram[0xea]|(ram[0xeb]<<8)|(ram[0xec]<<16)|((ram[0xe9]&3)<<24);
    return ram[0x3b]|(ram[0x3c]<<8)|(ram[0x3d]<<16)|((ram[0x3e]&3)<<24);
}
void wiiz_core_map_destination(WiizCore* core,int dx,int dy,int df) {
    if(core->map_profile>1){core->e->s.c.ram[0xc0]=(uint8_t)dx;core->e->s.c.ram[0xc1]=(uint8_t)dy;core->e->s.c.ram[0xc2]=(uint8_t)(core->map_profile==3?-df:df);return;}
    core->e->s.c.ram[0x21e]=(uint8_t)dx;core->e->s.c.ram[0x21f]=(uint8_t)dy;core->e->s.c.ram[0x220]=(uint8_t)df;
}
void wiiz_core_repeat(WiizCore* core, unsigned held, unsigned repeat_due) {
    static const unsigned buttons[] = {PAD_UP, PAD_DOWN, PAD_LEFT, PAD_RIGHT};
    for (int i=0; i<4; ++i) {
        if(core->map_profile>1) {
            uint8_t* counter=&core->e->s.c.ram[0x13-i];
            if(!(held&buttons[i]))*counter=0x0e;
            else if(repeat_due&buttons[i])*counter=0xff;
            else if(*counter!=0xff && *counter!=0x0e && *counter!=0x0f)*counter=0xf4;
            continue;
        }
        uint8_t* counter = &core->e->s.c.ram[0x1d+i];
        if (!(held & buttons[i])) *counter = 0xfe;
        else if (repeat_due & buttons[i]) *counter = 0xff;
        else if (*counter != 0xff) *counter = 0xf4;
    }
}
static void input(SystemInput* out, void* userdata, bool strobe) {
    (void)strobe;
    const unsigned b = ((WiizCore*)userdata)->buttons;
    memset(out, 0, sizeof(*out));
    out->port[0].type = out->port[1].type = CONTROLLER_JOYPAD;
    JoypadInput* pad = &out->port[0].joyp;
    pad->A = !!(b & PAD_A); pad->B = !!(b & PAD_B);
    pad->select = !!(b & PAD_SELECT); pad->start = !!(b & PAD_START);
    pad->up = !!(b & PAD_UP); pad->down = !!(b & PAD_DOWN);
    pad->left = !!(b & PAD_LEFT); pad->right = !!(b & PAD_RIGHT);
}
static void expansion_write(void* data,uint8_t value){turbofile_write(&((WiizCore*)data)->turbofile,value);}
static uint8_t expansion_read(void* data,unsigned port){return turbofile_read(&((WiizCore*)data)->turbofile,port);}
void wiiz_core_turbofile_attach(WiizCore* core){core->turbofile.enabled=1;}
int wiiz_core_turbofile_read(WiizCore* core,uint8_t* data,size_t size){if(size!=8192)return 0;memcpy(data,core->turbofile.ram,size);return 1;}
int wiiz_core_turbofile_write(WiizCore* core,const uint8_t* data,size_t size){if(size!=8192)return 0;memcpy(core->turbofile.ram,data,size);return 1;}
void wiiz_core_turbofile_registers(WiizCore* core,uint8_t* out){WiizTurboFile* t=&core->turbofile;out[0]=(uint8_t)t->addr;out[1]=(uint8_t)(t->addr>>8);out[2]=t->bit;out[3]=t->latch;out[4]=t->enabled;out[5]=t->locked;}
int wiiz_core_turbofile_restore(WiizCore* core,const uint8_t* data,size_t size){
    if(size!=8198||data[8193]>31||data[8194]>7||data[8196]>1||data[8197]>1)return 0;
    WiizTurboFile* t=&core->turbofile;memcpy(t->ram,data,8192);t->addr=data[8192]|(data[8193]<<8);t->bit=data[8194];t->latch=data[8195];t->enabled=data[8196];t->locked=data[8197];return 1;
}
WiizCore* wiiz_core_new(uint8_t* rom, size_t size) {
    WiizCore* core = calloc(1, sizeof(*core));
    if (!core) return NULL;
    EmulatorInit init = {0};
    init.rom.data = rom; init.rom.size = size;
    init.audio_frequency = 48000; init.audio_frames = 512;
    init.ram_init = RAM_INIT_FCEUX;
    core->e = emulator_new(&init);
    if (!core->e) { free(core); return NULL; }
    // The hash-verified Wiz1 iNES header uses zero for unspecified PRG-RAM size.
    // Its bank-0 battery RAM is 8 KiB (ROM-specific metadata, not a mapper implementation).
    if (core->e->ci.has_bat_ram && !core->e->ci.prgram_bytes) {
        core->e->ci.prgram_bytes = 8192;
        core->e->ci.prgram8k_banks = 1;
        core->e->ci.prgram512b_banks = 16;
    }
    emulator_set_joypad_callback(core->e, input, core);
    core->e->expansion_write=expansion_write;core->e->expansion_read=expansion_read;core->e->expansion_user_data=core;
    return core;
}
void wiiz_core_delete(WiizCore* core) {
    if (!core) return;
    // The upstream destructor releases PPU storage and Emulator, but not audio data.
    free(core->e->audio_buffer.data);
    emulator_delete(core->e);
    free(core);
}
void wiiz_core_input(WiizCore* core, unsigned buttons) { core->buttons = buttons;if(buttons)core->roster_editable=0; }
unsigned wiiz_core_roster_editable(WiizCore* core){return core->roster_editable;}
unsigned wiiz_core_title_ready(WiizCore* core) {return core->title_ready;}
void wiiz_core_reset(WiizCore* core) {
    core->title_ready=0;core->roster_editable=0;
    core->buttons = 0;
    emulator_set_reset(core->e, true);
    emulator_set_reset(core->e, false);
}
int wiiz_core_frame(WiizCore* core) {
    Emulator* e = core->e;
    core->audio_count = 0;
    apply_assists(core);
    Ticks until = emulator_get_ticks(e) + e->master_ticks_per_frame * 2;
    for (;;) {
        const EmulatorEvent event = emulator_run_until(e, until);
        if (event & EMULATOR_EVENT_AUDIO_BUFFER_FULL) {
            AudioBuffer* ab = emulator_get_audio_buffer(e);
            size_t count = ab->frames;
            if (core->audio_count + count > 4096) return 0;
            memcpy(core->audio + core->audio_count, ab->data, count * sizeof(float));
            core->audio_count += count;
        }
        if (event & EMULATOR_EVENT_INVALID_OPCODE) return 0;
        if (event & EMULATOR_EVENT_NEW_FRAME) {apply_assists(core);return 1;}
        if (event & EMULATOR_EVENT_UNTIL_TICKS) return 0;
    }
}
void wiiz_core_pixels(WiizCore* core, uint32_t* rgba) { emulator_convert_frame_buffer(core->e, rgba); }
const float* wiiz_core_audio(WiizCore* core, size_t* count) { *count = core->audio_count; return core->audio; }
size_t wiiz_core_sram_size(WiizCore* core) { return core->e->ci.has_bat_ram ? core->e->ci.prgram_bytes : 0; }
int wiiz_core_sram_read(WiizCore* core, uint8_t* bytes, size_t size) {
    FileData data = {bytes, size}; return emulator_write_prg_ram(core->e, &data) == OK;
}
int wiiz_core_sram_write(WiizCore* core, uint8_t* bytes, size_t size) {
    FileData data = {bytes, size}; return emulator_read_prg_ram(core->e, &data) == OK;
}
unsigned wiiz_core_mapper(WiizCore* core) { return core->e->ci.mapper; }
/* Existing upstream S serializer + non-S presentation/resampler adapter state.
   No native pointers are written to disk. Snapshot version is ABI-specific. */
typedef struct {
    uint32_t magic, version, state_bytes, audio_prefix_bytes, audio_capacity, audio_position;
    uint32_t buttons, sound_role, sound_commands[3];
} WiizSnapshot;
size_t wiiz_core_state_size(WiizCore* core) {
    return sizeof(WiizSnapshot)+sizeof(S)+sizeof(FrameBuffer)+offsetof(AudioBuffer,data)+
        (core->e->audio_buffer.end-core->e->audio_buffer.data)*sizeof(float);
}
int wiiz_core_state_write(WiizCore* core, uint8_t* bytes, size_t size) {
    if (size != wiiz_core_state_size(core)) return 0;
    AudioBuffer* ab=&core->e->audio_buffer;
    WiizSnapshot header={0};
    header.magic=0x31535a57;header.version=1;header.state_bytes=sizeof(S);
    header.audio_prefix_bytes=offsetof(AudioBuffer,data);header.audio_capacity=(uint32_t)(ab->end-ab->data);
    header.audio_position=(uint32_t)(ab->position-ab->data);header.buttons=core->buttons;header.sound_role=core->sound_role;
    memcpy(header.sound_commands,core->sound_commands,sizeof(header.sound_commands));
    memset(bytes,0,size);memcpy(bytes,&header,sizeof(header));bytes+=sizeof(header);
    FileData state;emulator_init_state_file_data(&state);
    const int ok=emulator_write_state(core->e,&state)==OK;
    if(ok)memcpy(bytes,state.data,state.size);free(state.data);if(!ok)return 0;
    bytes+=sizeof(S);memcpy(bytes,core->e->frame_buffer,sizeof(FrameBuffer));bytes+=sizeof(FrameBuffer);
    memcpy(bytes,ab,offsetof(AudioBuffer,data));bytes+=offsetof(AudioBuffer,data);
    memcpy(bytes,ab->data,header.audio_position*sizeof(float));return 1;
}
int wiiz_core_state_read(WiizCore* core, const uint8_t* bytes, size_t size) {
    if (size != wiiz_core_state_size(core)) return 0;
    WiizSnapshot header;memcpy(&header,bytes,sizeof(header));bytes+=sizeof(header);
    AudioBuffer* ab=&core->e->audio_buffer;
    if(header.magic!=0x31535a57 || header.version!=1 || header.state_bytes!=sizeof(S) ||
       header.audio_prefix_bytes!=offsetof(AudioBuffer,data) || header.audio_capacity!=(uint32_t)(ab->end-ab->data) ||
       header.audio_position>header.audio_capacity || header.sound_role>2 || header.buttons>255)return 0;
    AudioBuffer prefix={0};
    memcpy(&prefix,bytes+sizeof(S)+sizeof(FrameBuffer),offsetof(AudioBuffer,data));
    if(prefix.frequency!=48000 || prefix.frames!=512 || prefix.bufferi<0 || prefix.bufferi>=128 ||
       prefix.freq_counter>=core->e->cpu_ticks_per_second)return 0;
    FileData state;emulator_init_state_file_data(&state);memcpy(state.data,bytes,sizeof(S));
    const int ok=emulator_read_state(core->e,&state)==OK;free(state.data);if(!ok)return 0;
    bytes+=sizeof(S);memcpy(core->e->frame_buffer,bytes,sizeof(FrameBuffer));bytes+=sizeof(FrameBuffer);
    memcpy(ab,bytes,offsetof(AudioBuffer,data));bytes+=offsetof(AudioBuffer,data);
    memcpy(ab->data,bytes,header.audio_capacity*sizeof(float));ab->position=ab->data+header.audio_position;
    core->buttons=header.buttons;core->audio_count=0;
    memcpy(core->sound_commands,header.sound_commands,sizeof(core->sound_commands));
    if(header.sound_role==1)wiiz_core_sound_source(core);
    else if(header.sound_role==2)wiiz_core_sound_player(core);
    return 1;
}
int wiiz_core_reset_test(WiizCore* core) {
    Emulator* e = core->e;
    e->s.c.ram[0x7ff] ^= 0x5a;
    e->s.c.prg_ram[0x1ffe] ^= 0xa5;
    uint8_t ram[sizeof(e->s.c.ram)], sram[sizeof(e->s.c.prg_ram)];
    memcpy(ram, e->s.c.ram, sizeof(ram)); memcpy(sram, e->s.c.prg_ram, sizeof(sram));
    const Ticks before = emulator_get_ticks(e);
    const uint16_t vector = e->prg_rom_map[3][0x1ffc] | ((uint16_t)e->prg_rom_map[3][0x1ffd] << 8);
    wiiz_core_reset(core);
    if (!e->s.c.req_reset || emulator_get_ticks(e) != before ||
        memcmp(ram, e->s.c.ram, sizeof(ram)) || memcmp(sram, e->s.c.prg_ram, sizeof(sram))) return 0;
    // Advance the real core until the reset request is consumed, without rebuilding it.
    for (int i=0; i<1000; ++i) {
        emulator_step(e);
        if (!e->s.c.req_reset && e->s.c.PC.val == vector) return emulator_get_ticks(e) > before &&
            e->s.c.ram[0x7ff] == ram[0x7ff] && e->s.c.prg_ram[0x1ffe] == sram[0x1ffe];
    }
    return 0;
}

unsigned wiiz_core_peek(WiizCore* core,unsigned addr) {
    if(addr>=0x8000&&addr<=0xffff)return core->e->prg_rom_map[(addr>>13)&3][addr&0x1fff];
    if(addr<0x800)return core->e->s.c.ram[addr];
    if(addr>=0x6000&&addr<0x8000)return core->e->s.c.prg_ram[addr-0x6000];
    return 0;
}
/* Test-only: execute STA via the adopted CPU to exercise RAM + SRAM interception.
   Caller restores a state afterwards; never used by the application UI. */
int wiiz_core_assist_probe(WiizCore* core) {
    const unsigned game=core->map_profile;
    const unsigned light=game==1?0x27f:game==2?0x77ef:0x6d99;
    const unsigned targets[]={game==1?0x6029:0x6427,light,game==1?0x280:light+2,game==1?0x281:light+1};
    for(unsigned i=0;i<4;++i) {
        const unsigned addr=targets[i];
        uint8_t* code=core->e->s.c.ram+0x700;
        code[0]=0xa9;code[1]=0;code[2]=0x8d;code[3]=(uint8_t)addr;code[4]=(uint8_t)(addr>>8);code[5]=0x4c;code[6]=5;code[7]=7;
        core->e->s.c.PC.val=0x700;
        for(unsigned n=0;n<1000;++n){emulator_step(core->e);if(core->e->s.c.PC.val==0x705)break;}
        if(wiiz_core_peek(core,addr)!=(unsigned)assist_value(core,addr))return 0;
    }
    return 1;
}

/* Test-only: execute the original two creation HP stores with all byte values.
   A dedicated test session owns this core; do not call on a live game. */
int wiiz_core_initial_hp_probe(WiizCore* core) {
    Emulator* e=core->e;
    if(core->map_profile!=1)return 0;
    e->s.m.prg8k_bank[0]=12;e->s.m.prg8k_bank[1]=13;
    e->prg_rom_map[0]=e->ci.prg_data+0x18000;
    e->prg_rom_map[1]=e->ci.prg_data+0x1a000;
    for(unsigned slot=0;slot<20;++slot)for(unsigned hp=0;hp<256;++hp) {
        const unsigned base=slot*256;
        e->s.c.ram[0x2e]=0;e->s.c.ram[0x2f]=(uint8_t)(0x60+slot);
        e->s.c.prg_ram[base+0x1f]=0;e->s.c.prg_ram[base+0x21]=0;
        e->s.c.A=(uint8_t)hp;e->s.c.PC.val=0xa28c;
        /* Pinned binjnes emulator.c STEP_CPU_DECODE; test harness only. */
        e->s.c.step=e->s.c.next_step=781;
        e->s.c.req_nmi=e->s.c.req_reset=e->s.c.has_nmi=e->s.c.has_irq=e->s.c.has_reset=false;
        e->s.c.I=true;
        unsigned n=0;
        for(;n<1000;++n){e->s.c.req_nmi=e->s.c.has_nmi=false;emulator_step(e);if(e->s.c.PC.val==0xa296)break;}
        if(n==1000){fprintf(stderr,"HP probe timeout slot=%u hp=%u pc=%x\n",slot,hp,e->s.c.PC.val);return 0;}
        const unsigned expected=hp<=15?15:hp;
        if(e->s.c.prg_ram[base+0x20]!=expected||e->s.c.prg_ram[base+0x22]!=expected){fprintf(stderr,"HP probe slot=%u input=%u current=%u max=%u pc=%x\n",slot,hp,e->s.c.prg_ram[base+0x20],e->s.c.prg_ram[base+0x22],e->s.c.PC.val);return 0;}
    }
    /* Same SRAM fields written outside creation must retain zero (death etc). */
    uint8_t* code=e->s.c.ram+0x700;
    const uint8_t program[]={0xa9,0,0x8d,0x20,0x60,0x8d,0x22,0x60,0x4c,8,7};
    memcpy(code,program,sizeof(program));e->s.c.PC.val=0x700;
    e->s.c.step=e->s.c.next_step=781;
    for(unsigned n=0;n<1000;++n){emulator_step(e);if(e->s.c.prg_ram[0x20]==0&&e->s.c.prg_ram[0x22]==0)break;}
    return e->s.c.prg_ram[0x20]==0&&e->s.c.prg_ram[0x22]==0;
}

/* Test only: original tavern alignment filter, all candidate/party pairs.
   The caller discards this dedicated core after the probe. */
int wiiz_core_tavern_probe(WiizCore* core) {
    Emulator* e=core->e;
    const unsigned game=core->map_profile;
    if(!game)return 0;
    if(game==1) {
        e->s.m.prg8k_bank[0]=12;e->s.m.prg8k_bank[1]=13;
        e->prg_rom_map[0]=e->ci.prg_data+0x18000;
        e->prg_rom_map[1]=e->ci.prg_data+0x1a000;
    } else {
        e->s.m.prg8k_bank[3]=15;e->prg_rom_map[3]=e->ci.prg_data+0x1e000;
    }
    for(unsigned enabled=0;enabled<2;++enabled)for(unsigned party=0;party<3;++party)for(unsigned candidate=0;candidate<3;++candidate) {
        wiiz_core_assists(core,enabled?32:0,1);
        if(game==1) {
            e->s.c.ram[0x2e]=0;e->s.c.ram[0x2f]=0x60;
            e->s.c.prg_ram[12]=(uint8_t)candidate;
            e->s.c.ram[0x0f]=party==0?1:party==2?4:0;
            const uint8_t call[]={0x20,0xcd,0x8a,0x4c,3,7};
            memcpy(e->s.c.ram+0x700,call,sizeof(call));
        } else {
            e->s.c.ram[0x0e]=0;e->s.c.ram[0x0f]=0x64;
            e->s.c.prg_ram[0x40a]=(uint8_t)candidate;
            for(unsigned i=0;i<3;++i)e->s.c.ram[0x3a+i]=(i+party==2 && i!=1);
        }
        const unsigned start=game==1?0x700:game==2?0xf341:0xf3bd;
        const unsigned accept=game==1?0x703:game==2?0xf34d:0xf3c9;
        const unsigned reject=game==1?0:game==2?0xf353:0xf3cf;
        e->s.c.PC.val=(uint16_t)start;e->s.c.step=e->s.c.next_step=781;
        e->s.c.req_nmi=e->s.c.req_reset=e->s.c.has_nmi=e->s.c.has_irq=e->s.c.has_reset=false;e->s.c.I=true;
        unsigned n=0;
        for(;n<1000;++n){e->s.c.req_nmi=e->s.c.has_nmi=false;emulator_step(e);if(e->s.c.step==782 && (e->s.c.PC.val==accept||(reject&&e->s.c.PC.val==reject)))break;}
        if(n==1000)return 0;
        const bool allowed=game==1?e->s.c.A==0:e->s.c.PC.val==accept;
        if(allowed!=(enabled||party==1||candidate==1||party==candidate)) {
            fprintf(stderr,"Tavern filter game=%u enabled=%u party=%u candidate=%u A=%u PC=%x\n",game,enabled,party,candidate,e->s.c.A,e->s.c.PC.val);return 0;
        }
    }
    return 1;
}
