"""(inhale) Local co-op: one controller for each player, issue #16 (host/kirby_npad.c, host/nn_hid.c).

Every controller drove Npad No.1, which alone read as connected, and ShowControllerSupport answered one player: Play
Co-op said only one controller was connected. The actual GetNpadStyleSet and ShowControllerSupport of host/nn_hid.c are
compiled with host/kirby_npad.c, stand-ins for the pads of host/pad_sdl.c and for the Controls tab's row, and checked:

- the row on, two pads: No.1 and No.2 are connected (FullKey), No.3 and Handheld are not; the applet answers two
  players for a game that takes one to four, one in single mode, one for a game that takes one;
- the row on, one pad or none: one player;
- the row off (the default), two pads: one player, No.1 alone connected, as upstream has it;
- No.2's buttons are its own pad's, through the bindings, and its sticks; a third player with no pad reads nothing;
- vibration for No.2's handle goes to the second pad alone, the louder of its two sides.

python -I -B tests/test_kirby_npad.py [--cc gcc]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cc", "{cc}"]

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
typedef struct { uint64_t x[32]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))
#define G32(a) (*(uint32_t *)GP(a))
#define NPAD_NO1 0
#define STYLE_FULLKEY 1u
static void *hos_guest_range(uint64_t a, uint64_t n) { (void)n; return (void *)(uintptr_t)a; }   /* (all of it here) */

@NPAD@

/* the Controls tab's row and the pads SDL has open (host/pad_sdl.c) */
static int row_on, pads;
static uint64_t pad_raw[8];
static int32_t pad_stick[8][4];
static int rumbled = -1;
static float rumble_lo, rumble_hi;
int rx_option(int id, int otherwise) { return id == HOS_OPT_PAD_PER_PLAYER ? row_on : otherwise; }
void hos_log(const char *fmt, ...) { (void)fmt; }
int hos_sdl_pad_players(void) { return pads; }
int hos_sdl_pad_player(int player, uint64_t *buttons, int32_t stick[4]) {
    if (player < 0 || player >= pads) return 0;
    *buttons |= pad_raw[player];
    memcpy(stick, pad_stick[player], sizeof pad_stick[0]);
    return 1;
}
void hos_sdl_rumble_player(int player, float low, float high) { rumbled = player, rumble_lo = low, rumble_hi = high; }

@HLE@

static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static uint32_t style(uint32_t id) {
    Ctx c = {{0}};
    c.x[0] = (uint64_t)(uintptr_t)&id;
    imp__ZN2nn3hid15GetNpadStyleSetERKj(&c);
    return (uint32_t)c.x[0];
}
static int support(int lo, int hi, int single, uint32_t *selected) {
    uint8_t arg[0x2b8] = {0}, result[8];
    memset(result, 0xAA, sizeof result);
    arg[0] = (uint8_t)lo, arg[1] = (uint8_t)hi, arg[5] = (uint8_t)single;
    Ctx c = {{0}};
    c.x[0] = (uint64_t)(uintptr_t)result, c.x[1] = (uint64_t)(uintptr_t)arg;
    imp__ZN2nn3hid21ShowControllerSupportEPNS0_27ControllerSupportResultInfoERKNS0_20ControllerSupportArgE(&c);
    if (selected) memcpy(selected, result + 4, 4);
    return c.x[0] == 0 ? (int8_t)result[0] : -1;
}
static uint64_t bind(uint64_t raw) { return raw << 1; }   /* (a binding table: a pad input to a button) */
int main(void) {
    row_on = 1, pads = 2;
    check(style(0) == STYLE_FULLKEY && style(1) == STYLE_FULLKEY, "row on, two pads: No.1 and No.2 connected");
    check(style(2) == 0 && style(0x20) == 0 && style(0x10) == 0, "row on, two pads: No.3, Handheld and Other not");
    uint32_t selected = 99;
    check(support(1, 4, 0, &selected) == 2 && selected == 0, "row on, two pads: the applet answers two players, No.1 selected");
    check(support(1, 4, 1, NULL) == 1, "single mode: one player");
    check(support(1, 1, 0, NULL) == 1, "a game that takes one player: one");
    check(support(2, 0, 0, NULL) == 2, "a max of 0 (four): two");
    pads = 1;
    check(support(1, 4, 0, NULL) == 1 && style(1) == 0, "row on, one pad: one player");
    pads = 0;
    check(support(1, 4, 0, NULL) == 1 && style(0) == STYLE_FULLKEY, "row on, no pad: No.1 (the keyboard's)");

    row_on = 0, pads = 2;
    check(support(1, 4, 0, NULL) == 1, "row off, two pads: one player, as upstream");
    check(style(0) == STYLE_FULLKEY && style(1) == 0, "row off: No.1 alone connected");
    check(kirby_npad_player(1) == -1, "row off: no second player");

    row_on = 1, pads = 2;
    pad_raw[0] = 1, pad_raw[1] = 4;
    pad_stick[1][0] = 1234, pad_stick[1][3] = -77;
    uint64_t b = 0;
    int32_t st[4] = {9, 9, 9, 9};
    check(kirby_npad_player(1) == 1, "row on: No.2 is the second player");
    kirby_npad_read(1, bind, &b, st);
    check(b == 8 && st[0] == 1234 && st[1] == 0 && st[3] == -77, "No.2: its own pad's input through the bindings, and sticks");
    b = 0, st[0] = 5;
    kirby_npad_read(2, bind, &b, st);
    check(b == 0 && st[0] == 0, "a player with no pad reads nothing");
    check(kirby_npad_sampling(1) == 1 && kirby_npad_sampling(1) == 2 && kirby_npad_sampling(2) == 1, "each Npad its own sampling");

    const float left[2] = {0.25f, 0.5f}, right[2] = {0.75f, 0.125f};
    kirby_npad_vibration(3 | 1u << 8 | 0u << 16, 0, left);
    kirby_npad_vibration(3 | 1u << 8 | 1u << 16, 1, right);
    check(rumbled == 1 && rumble_lo == 0.75f && rumble_hi == 0.5f, "No.2's vibration: the second pad, its louder sides");
    rumbled = -1;
    kirby_npad_vibration(3 | 5u << 8, 0, left);
    check(rumbled == -1, "an npad with no pad: no vibration");
    if (!bad) puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    hid = (ROOT / "host/nn_hid.c").read_text(encoding="utf-8")
    npad = (ROOT / "host/kirby_npad.c").read_text(encoding="utf-8")
    hle = "\n".join(block(hid, marker) for marker in (
        "HLE(_ZN2nn3hid15GetNpadStyleSetERKj) {",
        "HLE(_ZN2nn3hid21ShowControllerSupportEPNS0_27ControllerSupportResultInfoERKNS0_20ControllerSupportArgE) {"))
    npad = npad.replace('#include "../gpu/vk/vk_api.h"', '#include "%s"' % (ROOT / "gpu/vk/vk_api.h").as_posix())
    fixture = HARNESS.replace("@NPAD@", npad).replace("@HLE@", hle)
    compiler = shutil.which(args.cc)
    if not compiler:
        raise SystemExit("C compiler not found: " + args.cc)
    with tempfile.TemporaryDirectory(prefix="kirby-npad-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.c").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c11", "-O1", "-Wall", "-Wno-unused-function", str(folder / "fixture.c"), "-o",
                        str(exe)], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("the controllers are not one for each player (issue #16)")
    print("PASS: one controller for each player with the row on, every one No.1's with it off")


if __name__ == "__main__":
    main()
