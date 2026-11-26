/* (inhale) A frame rate of 30 at the game's own speed, and the game's speed kept under 20 frames a second (Kirby and the
   Forgotten Land, Switch 2 Edition): docs/design.md, "issue #26, a frame rate of 30".

   The game's main loop (main+0x6537e0) paces itself with a controller of its engine's, reached through the pointer to a
   pointer at main+0x2c39c68. In play its mode (+0x60) is 2, the variable step: a frame waits for +0x3c vsyncs of the
   60 Hz clock (1 as the game sets it), and its step (+0x6c, in 60ths of a second) is the vsyncs that passed since the
   last frame began, up to +0x34 (3.0 in play). So with +0x3c at 2 the game draws 30 frames a second and each one
   advances two 60ths: half the frames, the same speed. That is the whole lever: one field, the game's own 30 path.

   The ceiling is the other lever. A frame longer than +0x34 vsyncs gets no full step, so under 20 frames a second the
   game is in slow motion. With +0x34 at 6.0 a frame of up to six vsyncs gets its step, and the game keeps its speed
   down to 10 frames a second, with steps the game's makers did not allow: so it is a choice, off unless made.

   The Graphics tab's Frame rate row (gpu/vk/menu/kirby_env_rows.cpp) chooses 60 or 30, in play; HOS_KIRBY_FPS=30 or 60
   stands over it. Its Keep speed under 20 FPS row chooses the ceiling of 6.0, in play; HOS_KIRBY_KEEP_SPEED=1 or 0
   stands over it. HOS_FPS_LOG=1 logs the presents and the game's speed every 300 presents. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"   /* (HOS_OPT_KIRBY_FPS, HOS_OPT_KIRBY_KEEP_SPEED) */
#ifndef INHALE_ENV_H
#include "../gpu/vk/compat/inhale_env.h"
#endif
#include <string.h>

int kirby_wide_ok(void);                /* kirby_wide.c: the lifted main is this game's build */
int rx_option(int id, int otherwise);   /* rx_backend.c */

#define KIRBY_FPS_HOLDER 0x82c39c68ULL

/* The controller, once the game has made it: 0 before that (the holder is in main's zeroed data), and for any other
   main. It is the main loop's own object, so it lives as long as the game runs */
static uint64_t kirby_fps_controller(void) {
    if (!kirby_wide_ok()) return 0;
    const uint64_t holder = G64(KIRBY_FPS_HOLDER);
    return holder ? G64(holder) : 0;
}

/* Holds the controller at two vsyncs a frame while want30, and gives the game's one back after. Only the state seen in
   play is touched: the variable step mode, one vsync a frame, a step that may reach 2. Anything else is left and said
   once. At 60 from the start nothing is ever written. The game writes its 1 again when it comes back to the mode (seen
   twice in a start), so this runs every present. */
void kirby_fps_apply(int want30) {
    static int held, said;
    if (!want30 && !held) return;
    const uint64_t o = kirby_fps_controller();
    if (!o || G32(o + 0x60) != 2) return;   /* (a load's fixed step modes do not read +0x3c: nothing to do there) */
    const uint32_t vsyncs = G32(o + 0x3c);
    if (!want30) {
        if (vsyncs == 2) G32(o + 0x3c) = 1;
        held = 0;
        return;
    }
    float top;
    memcpy(&top, GP(o + 0x34), 4);
    if (vsyncs == 1 && top >= 2.0f) {
        G32(o + 0x3c) = 2;
        held = 1;
    } else if (vsyncs != 2 && !said) {
        said = 1;
        hos_log("kirby fps: the controller is not as known (vsyncs a frame %u, step up to %.2f): left at the game's",
                vsyncs, top);
    }
}

/* The choice: HOS_KIRBY_FPS=30 or 60 over the menu's row (any other value is no choice) */
int kirby_fps_want30(void) {
    static int env = -1;
    if (env < 0) env = env_int("HOS_KIRBY_FPS", 0);
    return env == 30 || (env != 60 && rx_option(HOS_OPT_KIRBY_FPS, 0) != 0);
}

/* The ceiling the Keep speed row holds: six vsyncs, so 10 frames a second. 4.0 would stop at 15, above the 14.5 an Intel
   UHD 620 makes at 720 lines; 8.0 kept the speed at 9.6 too, a larger step for a frame rate nobody plays at */
#define KIRBY_FPS_TOP 6.0f

/* Holds the step's ceiling at KIRBY_FPS_TOP while want, and gives the game's 3.0 back after. Only the state seen in
   play is touched: the variable step mode and a ceiling of the game's 3.0. Any other ceiling is left and said once. Off
   from the start nothing is ever read or written. The game may write its 3.0 again, so this runs every present. */
void kirby_fps_keep_speed(int want) {
    static const float game = 3.0f, kept = KIRBY_FPS_TOP;
    static int held, said;
    if (!want && !held) return;
    const uint64_t o = kirby_fps_controller();
    if (!o || G32(o + 0x60) != 2) return;   /* (the fixed step modes do not read +0x34) */
    float top;
    memcpy(&top, GP(o + 0x34), 4);
    if (!want) {
        if (top == kept) memcpy(GP(o + 0x34), &game, 4);
        held = 0;
        return;
    }
    if (top == game) {
        memcpy(GP(o + 0x34), &kept, 4);
        held = 1;
    } else if (top != kept && !said) {
        said = 1;
        hos_log("kirby fps: the step's ceiling is not the game's 3 (%.2f): left at that", top);
    }
}

/* The choice: HOS_KIRBY_KEEP_SPEED=1 or 0 over the menu's row (any other value is no choice) */
int kirby_fps_want_speed(void) {
    static int env, read;
    if (!read) env = env_int("HOS_KIRBY_KEEP_SPEED", -1), read = 1;
    return env == 1 || (env != 0 && rx_option(HOS_OPT_KIRBY_KEEP_SPEED, 0) != 0);
}

/* HOS_FPS_LOG=1: every 300 presents, the controller's state, the presents a second and the game's speed (the steps a
   second over 60: 1.000 is the game's own speed whatever the frame rate) */
static void kirby_fps_log(void) {
    static long long n, since;
    static double steps;
    const uint64_t o = kirby_fps_controller();
    if (!o) return;
    const uint32_t mode = G32(o + 0x60);
    float step, top;
    memcpy(&step, GP(o + 0x6c), 4);
    memcpy(&top, GP(o + 0x34), 4);
    steps += mode == 2 ? step : (float)G32(o + (mode ? 0x28 : 0x14));
    const long long now = hos_now_ns();
    if (!since) since = now;
    if (++n % 300) return;
    const double s = (double)(now - since) / 1e9;
    hos_log("kirby fps: mode %u, vsyncs a frame %u, step %.3f (up to %.2f), %.1f presents a second, game speed %.3f", mode,
            G32(o + 0x3c), step, top, 300 / s, steps / 60 / s);
    since = now, steps = 0;
}

/* Once a presented frame (host/nn_vi.c hos_vi_native_presented) */
void kirby_fps_presented(void) {
    static int log = -1;
    if (log < 0) log = env_on("HOS_FPS_LOG");
    kirby_fps_keep_speed(kirby_fps_want_speed());
    kirby_fps_apply(kirby_fps_want30());
    if (log) kirby_fps_log();
}
