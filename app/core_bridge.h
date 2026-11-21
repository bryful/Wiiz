#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct WiizCore WiizCore;
enum { PAD_A=1, PAD_B=2, PAD_SELECT=4, PAD_START=8, PAD_UP=16, PAD_DOWN=32, PAD_LEFT=64, PAD_RIGHT=128 };
WiizCore* wiiz_core_new(uint8_t* rom, size_t size);
void wiiz_core_delete(WiizCore*);
void wiiz_core_turbofile_attach(WiizCore*);
int wiiz_core_turbofile_read(WiizCore*,uint8_t*,size_t);
int wiiz_core_turbofile_write(WiizCore*,const uint8_t*,size_t);
void wiiz_core_turbofile_registers(WiizCore*,uint8_t*);
int wiiz_core_turbofile_restore(WiizCore*,const uint8_t*,size_t);
void wiiz_core_input(WiizCore*, unsigned buttons);
void wiiz_core_reset(WiizCore*);
unsigned wiiz_core_title_ready(WiizCore*);
unsigned wiiz_core_roster_editable(WiizCore*);
unsigned wiiz_core_items_battle(WiizCore*);
int wiiz_core_items_battle_check(WiizCore*);
int wiiz_core_items_pause(WiizCore*);
int wiiz_core_items_recalculate(WiizCore*, unsigned party_index);
unsigned wiiz_core_items_stats_live(WiizCore*);
int wiiz_core_items_merge(WiizCore*, WiizCore*);
int wiiz_core_items_sync(WiizCore*,const uint8_t*,const uint8_t*,size_t);
int wiiz_core_frame(WiizCore*);
void wiiz_core_pixels(WiizCore*, uint32_t* rgba);
const float* wiiz_core_audio(WiizCore*, size_t* count);
size_t wiiz_core_sram_size(WiizCore*);
int wiiz_core_sram_read(WiizCore*, uint8_t* bytes, size_t size);
int wiiz_core_sram_write(WiizCore*, uint8_t* bytes, size_t size);
int wiiz_core_reset_test(WiizCore*);
unsigned wiiz_core_mapper(WiizCore*);
void wiiz_core_sound_source(WiizCore*);
void wiiz_core_sound_player(WiizCore*);
unsigned wiiz_core_take_sound(WiizCore*, unsigned reg);
void wiiz_core_sound_command(WiizCore*, unsigned reg, unsigned value);
unsigned wiiz_core_current_sound(WiizCore*, unsigned reg);
unsigned wiiz_core_repeat_events(WiizCore*, unsigned direction);
unsigned wiiz_core_initial_events(WiizCore*, unsigned direction);
void wiiz_core_repeat(WiizCore*, unsigned held, unsigned repeat_due);
size_t wiiz_core_state_size(WiizCore*);
int wiiz_core_state_write(WiizCore*, uint8_t*, size_t);
int wiiz_core_state_read(WiizCore*, const uint8_t*, size_t);
void wiiz_core_map_profile(WiizCore*);
void wiiz_core_assists(WiizCore*, unsigned mask, int ready);
void wiiz_core_battle_multipliers(WiizCore*, unsigned experience, unsigned gold);
unsigned wiiz_core_assist_mask(WiizCore*);
unsigned wiiz_core_creation_events(WiizCore*);
unsigned wiiz_core_peek(WiizCore*, unsigned addr);
int wiiz_core_prg_byte(WiizCore*, size_t offset, unsigned value);
int wiiz_core_assist_probe(WiizCore*);
int wiiz_core_tavern_probe(WiizCore*);
int wiiz_core_initial_hp_probe(WiizCore*);
void wiiz_core_profile(WiizCore*, unsigned scenario);
unsigned wiiz_core_map_event(WiizCore*);
unsigned wiiz_core_map_position(WiizCore*);
void wiiz_core_map_destination(WiizCore*, int dx, int dy, int df);
int wiiz_core_map_warp(WiizCore*, unsigned floor, unsigned x, unsigned y);
#ifdef __cplusplus
}
#endif
