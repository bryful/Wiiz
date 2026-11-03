#include "../app/gamepad_input.hpp"
#include <SDL3/SDL_hidapi.h>
#include <cstdio>
#include <stdexcept>
#include "../third_party/sdl3/wiiz_spi_reply.h"

static void require(bool ok) { if (!ok) throw std::runtime_error(SDL_GetError()); }
int main(int argc, char** argv) {
    try {
        require(wiizSwitchSPIReplyMatches(0x603d, 18, 0x603d, 18, 45));
        require(wiizSwitchSPIReplyMatches(0x603d, 18, 0x603d, 25, 45));
        require(wiizSwitchSPIReplyMatches(0x8010, 22, 0x8010, 24, 45));
        require(!wiizSwitchSPIReplyMatches(0x603d, 18, 0x8010, 25, 45));
        require(!wiizSwitchSPIReplyMatches(0x603d, 18, 0x603d, 17, 45));
        require(!wiizSwitchSPIReplyMatches(0x603d, 18, 0x603d, 25, 24));
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        GamepadInput::configure();
        if (argc > 1 && std::string(argv[1]) == "--monitor-hidapi") SDL_SetHint(SDL_HINT_JOYSTICK_HIDAPI_SWITCH, "1");
        if (argc > 1) SDL_SetLogPriority(SDL_LOG_CATEGORY_INPUT, SDL_LOG_PRIORITY_DEBUG);
        require(SDL_Init(SDL_INIT_GAMEPAD | SDL_INIT_EVENTS));
        if (argc > 1) {
            require(SDL_InitSubSystem(SDL_INIT_VIDEO));
            require(SDL_CreateWindow("Wiiz input diagnostic", 320, 200, SDL_WINDOW_HIDDEN) != nullptr);
        }
        if (argc > 1 && std::string(argv[1]).starts_with("--monitor")) {
            GamepadInput input; int buttons = 0, axes = 0, actions = 0;
            const auto until = SDL_GetTicks() + (argc > 2 ? std::stoul(argv[2]) : 45000);
            while (SDL_GetTicks() < until) {
                SDL_PumpEvents(); input.poll(true, false);
                SDL_Event e;
                while (SDL_PollEvent(&e)) {
                    if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN || e.type == SDL_EVENT_GAMEPAD_BUTTON_UP) {
                        ++buttons; std::printf("PAD button=%d down=%d\n", e.gbutton.button, e.gbutton.down);
                    }
                    if (e.type == SDL_EVENT_GAMEPAD_AXIS_MOTION) ++axes;
                    if (e.type == SDL_EVENT_KEY_DOWN && e.key.which == GamepadInput::keyboardId) {
                        ++actions; std::printf("ACTION %s\n", SDL_GetKeyName(e.key.key));
                    }
                }
                SDL_Delay(16);
            }
            std::printf("MONITOR buttons=%d axes=%d actions=%d\n", buttons, axes, actions);
            input.close(); SDL_Quit(); return 0;
        }
        if (argc > 1 && std::string(argv[1]) == "--devices") {
            auto* devices = SDL_hid_enumerate(0x057e, 0);
            for (auto* d = devices; d; d = d->next) {
                std::printf("HID vendor=%04x product=%04x path=%s\n", d->vendor_id, d->product_id, d->path);
                auto* hid = SDL_hid_open_path(d->path);
                if (hid) {
                    unsigned char report[128]{};
                    const int size = SDL_hid_read_timeout(hid, report, sizeof(report), 100);
                    std::printf("HID open=OK report_bytes=%d report_id=%02x error=%s\n", size, report[0], SDL_GetError());
                    SDL_hid_close(hid);
                } else std::printf("HID open=FAILED error=%s\n", SDL_GetError());
            }
            SDL_hid_free_enumeration(devices);
            GamepadInput input;
            const auto until = SDL_GetTicks() + 3000;
            while (SDL_GetTicks() < until) { SDL_PumpEvents(); input.poll(true, false); SDL_Delay(16); }
            int count = 0; auto* ids = SDL_GetJoysticks(&count);
            std::printf("SDL joysticks=%d\n", count);
            for (int i = 0; i < count; ++i) {
                std::printf("id=%u name=%s gamepad=%d vendor=%04x product=%04x path=%s\n", ids[i],
                    SDL_GetJoystickNameForID(ids[i]), int(SDL_IsGamepad(ids[i])), SDL_GetJoystickVendorForID(ids[i]),
                    SDL_GetJoystickProductForID(ids[i]), SDL_GetJoystickPathForID(ids[i]));
            }
            SDL_free(ids); input.close(); SDL_Quit(); return 0;
        }
        {
            GamepadInput input;
            SDL_VirtualJoystickDesc desc{}; SDL_INIT_INTERFACE(&desc);
            desc.type = SDL_JOYSTICK_TYPE_GAMEPAD; desc.naxes = SDL_GAMEPAD_AXIS_COUNT;
            desc.nbuttons = 15; desc.name = "Wiiz virtual input verification";
            const auto id = SDL_AttachVirtualJoystick(&desc); require(id != 0);
            auto* joystick = SDL_OpenJoystick(id); require(joystick != nullptr);
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, -32768));
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER, -32768));
            auto pump = [&] { SDL_PumpEvents(); input.poll(true, false); };
            auto expect = [&](SDL_Keycode key, bool down, bool shift = false) {
                SDL_Event e; int found = 0;
                while (SDL_PollEvent(&e)) if ((e.type == SDL_EVENT_KEY_DOWN || e.type == SDL_EVENT_KEY_UP) && e.key.which == GamepadInput::keyboardId) {
                    require(e.key.key == key && e.key.down == down && bool(e.key.mod & SDL_KMOD_SHIFT) == shift); ++found;
                }
                require(found == 1);
            };
            pump(); SDL_FlushEvents(SDL_EVENT_FIRST, SDL_EVENT_LAST);
            const int buttons[] = {11,12,13,14,1,0,2,3,7,10,8};
            const SDL_Keycode keys[] = {SDLK_UP,SDLK_DOWN,SDLK_LEFT,SDLK_RIGHT,SDLK_X,SDLK_Z,SDLK_A,SDLK_S,SDLK_Q,SDLK_M,SDLK_F1};
            for (int i = 0; i < 11; ++i) {
                require(SDL_SetJoystickVirtualButton(joystick, buttons[i], true)); pump(); expect(keys[i], true, i == 10);
                require(SDL_SetJoystickVirtualButton(joystick, buttons[i], false)); pump(); expect(keys[i], false, i == 10);
            }
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, 32767)); pump(); expect(SDLK_F1, true);
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFT_TRIGGER, -32768)); pump(); expect(SDLK_F1, false);
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTX, 20000)); pump(); expect(SDLK_RIGHT, true);
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTX, 14000)); pump();
            SDL_Event e; while (SDL_PollEvent(&e)) require(e.type != SDL_EVENT_KEY_UP);
            require(SDL_SetJoystickVirtualAxis(joystick, SDL_GAMEPAD_AXIS_LEFTX, 0)); pump(); expect(SDLK_RIGHT, false);
            require(SDL_SetJoystickVirtualButton(joystick, 12, true)); pump(); expect(SDLK_DOWN, true);
            SDL_Delay(360); SDL_PumpEvents(); input.poll(true, true); expect(SDLK_DOWN, true);
            require(SDL_SetJoystickVirtualButton(joystick, 12, false)); pump(); expect(SDLK_DOWN, false);
            require(SDL_SetJoystickVirtualButton(joystick, 1, true)); SDL_PumpEvents(); input.poll(false, false);
            while (SDL_PollEvent(&e)) require(e.type != SDL_EVENT_KEY_DOWN);
            require(SDL_SetJoystickVirtualButton(joystick, 1, false)); pump(); expect(SDLK_X, false);
            require(SDL_SetJoystickVirtualButton(joystick, 1, true)); pump(); expect(SDLK_X, true);
            require(SDL_DetachVirtualJoystick(id)); pump(); expect(SDLK_X, false);
            SDL_CloseJoystick(joystick);
            const auto reconnected = SDL_AttachVirtualJoystick(&desc); require(reconnected != 0);
            joystick = SDL_OpenJoystick(reconnected); require(joystick != nullptr); pump();
            SDL_FlushEvents(SDL_EVENT_FIRST, SDL_EVENT_LAST);
            require(SDL_SetJoystickVirtualButton(joystick, 1, true)); pump(); expect(SDLK_X, true);
            require(SDL_DetachVirtualJoystick(reconnected)); pump(); expect(SDLK_X, false);
            SDL_CloseJoystick(joystick);
            const std::string androidMapping = "00000000000000000000000000000000,Android Pro,a:b0,b:b1,x:b2,y:b3,sdk>=:29,";
            const auto corrected = androidProMapping(androidMapping, 0x057e, 0x2009, true);
            require(corrected != androidMapping);
            require(androidProMapping(corrected, 0x057e, 0x2009, true) == corrected);
            require(androidProMapping(androidMapping, 0x057e, 0x2009, false) == androidMapping);
            require(androidProMapping(androidMapping, 0x045e, 0x2009, true) == androidMapping);
            const auto pro = SDL_AttachVirtualJoystick(&desc); require(pro != 0);
            joystick = SDL_OpenJoystick(pro); require(joystick != nullptr);
            require(SDL_SetGamepadMapping(pro, corrected.c_str())); pump();
            SDL_FlushEvents(SDL_EVENT_FIRST, SDL_EVENT_LAST);
            const SDL_Keycode proKeys[] = {SDLK_X, SDLK_Z, SDLK_S, SDLK_A};
            for (int i = 0; i < 4; ++i) {
                require(SDL_SetJoystickVirtualButton(joystick, i, true)); pump(); expect(proKeys[i], true);
                require(SDL_SetJoystickVirtualButton(joystick, i, false)); pump(); expect(proKeys[i], false);
            }
            require(SDL_DetachVirtualJoystick(pro)); pump(); SDL_CloseJoystick(joystick);
        }
        SDL_Quit(); std::puts("GAMEPAD_OK fixed positions, shortcuts, hysteresis, repeat, focus suppression, reconnect"); return 0;
    } catch (const std::exception& ex) { std::fprintf(stderr, "GAMEPAD_FAILED: %s\n", ex.what()); SDL_Quit(); return 1; }
}
