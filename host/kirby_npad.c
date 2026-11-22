/* (inhale) Local co-op: one controller for each player (issue #16).

   The game reads Npad No.1 to No.4 and Handheld (host/nn_hid.c npad_states logs each id once), and its Play Co-op asks
   ShowControllerSupport how many players there are. Upstream's nn_hid.c gives every controller to No.1, which alone
   reads as connected, and the applet always answers one player: so every pad moved Kirby, and co-op said only one
   controller was connected.

   With the Controls tab's "One controller per player" on (HOS_OPT_PAD_PER_PLAYER), the controllers SDL has open are the
   players in the order of pad_sdl.c's slots (host/pad_sdl.c hos_sdl_pad_player): the first is No.1's, with the keyboard
   and the mouse as before, the second No.2's, and so on to No.8. That is the order they were connected in until one is
   unplugged: the players after it move up one, and a pad plugged in then takes the lowest free slot. Off, the default, everything is as upstream has it: every
   controller drives No.1. Off by default because a second device that reads as a pad (a virtual one, a Steam stand-in's
   twin, upstream #1673) would otherwise take the player's own pad to No.2 and leave No.1 to it.

   Each player's vibration goes to that player's pad when the plain motors play it; HD rumble and RenHDrum's backends
   still play every player's (host/pad_sdl.c). Motion stays the pad used last's. XInput's pads, read only when SDL has
   none, stay No.1's. */
#include <stdint.h>
#include <string.h>
#include "../gpu/vk/vk_api.h"

int rx_option(int id, int otherwise);
void hos_log(const char *fmt, ...);
int hos_sdl_pad_players(void);   /* (pad_sdl.c: the open pads that give input) */
int hos_sdl_pad_player(int player, uint64_t *buttons, int32_t stick[4]);
void hos_sdl_rumble_player(int player, float low, float high);

enum { KIRBY_NPADS = 8 };   /* (No.1 to No.8, ids 0 to 7) */

int kirby_npad_split(void) { return rx_option(HOS_OPT_PAD_PER_PLAYER, 0) != 0; }

/* how many players have a controller: 1 with the row off or no pad (No.1 is the keyboard's then), else the pads open */
int kirby_npad_players(void) {
    if (!kirby_npad_split()) return 1;
    const int n = hos_sdl_pad_players();
    return n < 1 ? 1 : n > KIRBY_NPADS ? KIRBY_NPADS : n;
}

/* the player an npad id is (0 for No.1), or -1 when nothing is connected there (Handheld 0x20 and Other 0x10 too) */
int kirby_npad_player(uint32_t id) { return id < KIRBY_NPADS && (int)id < kirby_npad_players() ? (int)id : -1; }

/* No.2 and later: that player's pad alone, through the bindings (bind: nn_hid.c bound_pad_buttons), no keyboard */
void kirby_npad_read(int player, uint64_t (*bind)(uint64_t), uint64_t *buttons, int32_t stick[4]) {
    uint64_t raw = 0;
    memset(stick, 0, 4 * sizeof *stick);
    if (hos_sdl_pad_player(player, &raw, stick)) *buttons = bind(raw);
}

/* each Npad's own sampling number, as the console counts them */
int64_t kirby_npad_sampling(int player) {
    static int64_t n[KIRBY_NPADS];
    return player >= 0 && player < KIRBY_NPADS ? ++n[player] : 0;
}

/* ShowControllerSupport's answer. arg: ControllerSupportArg (s8 player count min at 0, max at 1, single mode at 5);
   result: ControllerSupportResultInfo (s8 player count at 0, u32 selected id at 4). No dialog: the players connected,
   at most the game's max (0: four), one in single mode; the selected one No.1 */
void kirby_controller_support(const uint8_t *arg, uint8_t *result) {
    const int lo = (int8_t)arg[0], hi = (int8_t)arg[1] > 0 ? (int8_t)arg[1] : 4, single = arg[5] != 0;
    int n = single ? 1 : kirby_npad_players();
    if (n > hi) n = hi;
    memset(result, 0, 8);
    result[0] = (uint8_t)n;
    static int said;
    if (said++ < 8) hos_log("hid: controller support asked for %d to %d player%s%s: %d", lo, hi, hi == 1 ? "" : "s",
                            single ? ", single mode" : "", n);
}

/* nn_hid.c vibration_send: amp, one side's (dev 0 left, 1 right) low and high motors from the game's value, to the pad
   of the npad in handle ({u8 style, u8 npad id, u8 device, u8}) */
void kirby_npad_vibration(uint32_t handle, int dev, const float amp[2]) {
    static float of[KIRBY_NPADS][2][2];
    const int player = kirby_npad_player(handle >> 8 & 0xff);
    if (player < 0) return;
    memcpy(of[player][dev & 1], amp, sizeof of[0][0]);
    const float *l = of[player][0], *r = of[player][1];
    hos_sdl_rumble_player(player, l[0] > r[0] ? l[0] : r[0], l[1] > r[1] ? l[1] : r[1]);
}
