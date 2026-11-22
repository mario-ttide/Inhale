"""(inhale) Local co-op: each player's vibration on HD rumble and RenHDrum too, issue #16 (host/rumble_renhdrum.c,
host/pad_sdl.c, host/kirby_npad.c).

With "One controller per player" on, only the plain motors played each player's own vibration: HD rumble encoded one
shared value for every Switch pad, and RenHDrum fed every DualSense, Steam Controller, Xbox and Switch engine the value
of whichever Npad the game sent last. RenHDrum's routing (feed_to, rh_push, rh_push_player, rh_pad_player, rh_tick) and
pad_sdl.c's per-player HD values are cut out as they are and compiled with stand-ins for RenHDrum's calls. Checked:

- the row on, two Switch engines owned by players 1 and 2: player 2's value reaches its engine alone, the shared one
  neither; the cable's DualSense owned by player 1 gets player 1's values, and its triggers' copy follows them;
- the row off (no pad owned): the shared value reaches every target, as upstream has it;
- a player gone quiet silences that player's pad alone; the Test vibration row reaches every pad;
- HD rumble: player 2's value lands in player 2's slot alone, and its side bytes are made from it;
- pad_sdl.c's poll tells RenHDrum whose each pad is, and plays a VIB_HD pad's own player's bytes with the row on.

python -I -B tests/test_rumble_per_player.py [--cc gcc]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, between   # noqa: E402

RUN_ALL_ARGS = ["--cc", "{cc}"]

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "@HD_RUMBLE@"
typedef int SRWLOCK;
typedef long LONG;
#define SRWLOCK_INIT 0
#define AcquireSRWLockExclusive(l) ((void)(l))
#define ReleaseSRWLockExclusive(l) ((void)(l))
#define AcquireSRWLockShared(l) ((void)(l))
#define ReleaseSRWLockShared(l) ((void)(l))
static LONG InterlockedExchange(volatile LONG *at, LONG v) { const LONG was = *at; *at = v; return was; }
static int64_t now_ns = 1000000000LL;
static int64_t hos_now_ns(void) { return now_ns; }
static void hos_log(const char *fmt, ...) { (void)fmt; }
static float vibration_gain(int percent) { (void)percent; return 1.0f; }
typedef struct { int id; } RenHdcDualSenseDsp, RenHdcXboxRumble, RenHdcEngine, RenHdcTriTrigger;
#define RENHDRUM_DS5_EFFECTS_SIZE 64

/* RenHDrum's calls: each records what it was given, target and side, the low band's amplitude */
static int got_n;
static struct { int target, right; float amp; } got[64];
static void record(int target, bool right, float amp) { if (got_n < 64) got[got_n].target = target, got[got_n].right = right, got[got_n++].amp = amp; }
static int32_t dsp_set(RenHdcDualSenseDsp *d, bool right, float al, float fl, float ah, float fh) {
    (void)fl, (void)ah, (void)fh; record(d->id, right, al); return 0; }
static int32_t xbox_push(RenHdcXboxRumble *x, int64_t us, bool right, float al, float fl, float ah, float fh) {
    (void)us, (void)fl, (void)ah, (void)fh; record(x->id, right, al); return 0; }
static int32_t engine_push(RenHdcEngine *e, int64_t us, bool right, float al, float fl, float ah, float fh) {
    (void)us, (void)fl, (void)ah, (void)fh; record(e->id, right, al); return 0; }
static struct {
    int32_t (*dualsense_dsp_set_half_target)(RenHdcDualSenseDsp *, bool, float, float, float, float);
    int32_t (*xbox_rumble_push_half_sample)(RenHdcXboxRumble *, int64_t, bool, float, float, float, float);
    int32_t (*engine_push_half_sample)(RenHdcEngine *, int64_t, bool, float, float, float, float);
} rh = {dsp_set, xbox_push, engine_push};
static int rh_ok = 1;
static SRWLOCK lk, life;
static void recreate_bt_dsp(int percent) { (void)percent; }
static void usb_hd_set(int on) { (void)on; }

@RH_DEFINES@
@RH_STATE@
@RH_FEED@
@RH_FUNCS@

/* pad_sdl.c's HD rumble values */
#define MAX_PADS 8
@HD_STATE@
@HD_PLAYER@

static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static int reached(int target) {   /* (how many values target got since the last clear) */
    int n = 0;
    for (int i = 0; i < got_n; i++) n += got[i].target == target;
    return n;
}
static float amp_of(int target) {   /* (the last it got) */
    float a = -1.0f;
    for (int i = 0; i < got_n; i++) if (got[i].target == target) a = got[i].amp;
    return a;
}
int main(void) {
    static RenHdcEngine e0 = {10}, e1 = {11};
    static RenHdcDualSenseDsp usb = {20};
    static int pad_a, pad_b;
    pads[0].pad = &pad_a, pads[0].engine = &e0;
    pads[1].pad = &pad_b, pads[1].engine = &e1;
    usb_pad = &pad_a, usb_dsp = &usb;   /* (player 1's pad plays on both: a target each) */
    const float v[4] = {0.5f, 150.0f, 0.25f, 300.0f}, w[4] = {0.75f, 170.0f, 0.125f, 330.0f};

    /* the row off: no pad owned, the shared value everywhere */
    rh_pad_player(&pad_a, -1), rh_pad_player(&pad_b, -1);
    got_n = 0, rh_push(0, v);
    check(reached(10) == 1 && reached(11) == 1 && reached(20) == 1, "row off: the shared value reaches every target");

    /* the row on: pad A is player 1's, pad B player 2's */
    rh_pad_player(&pad_a, 0), rh_pad_player(&pad_b, 1);
    got_n = 0, rh_push(0, w);
    check(got_n == 0, "row on: the shared value reaches no player's pad");
    got_n = 0, rh_push_player(1, 1, w);
    check(reached(11) == 1 && reached(10) == 0 && reached(20) == 0 && got[0].right, "player 2's value: its engine alone");
    const uint32_t fed_before = usb_fed[1];
    got_n = 0, rh_push_player(0, 1, v);
    check(reached(10) == 1 && reached(20) == 1 && reached(11) == 0, "player 1's value: its engine and its DualSense");
    check(usb_fed[1] == fed_before + 1 && usb_last[1][0] == 0.5f && usb_last[1][1] == 150.0f && usb_last[1][3] == 300.0f,
          "the cable's triggers' copy follows player 1's value");
    got_n = 0, rh_push_player(1, 1, w);
    check(usb_fed[1] == fed_before + 1 && usb_last[1][0] == 0.5f, "player 2's value leaves player 1's triggers' copy");

    /* a player gone quiet: player 1 keeps sending, player 2 stopped */
    memset(at_of, 0, sizeof at_of), memset(quiet_of, 0, sizeof quiet_of), memset(at, 0, sizeof at);
    rh_push_player(0, 0, v), rh_push_player(1, 0, w);
    now_ns += 200000000LL, rh_push_player(0, 0, v);
    now_ns += 100000000LL;
    got_n = 0, rh_tick(now_ns, 0, 100, 100, 1);
    check(reached(11) == 1 && amp_of(11) == 0.0f && reached(10) == 0 && reached(20) == 0,
          "player 2 gone quiet: its engine silenced alone");
    got_n = 0, rh_tick(now_ns + 1, 0, 100, 100, 1);
    check(got_n == 0, "silenced once");

    /* the Test vibration row: every pad, whoever's */
    got_n = 0, rh_tick(now_ns, 1, 100, 100, 1);
    check(reached(10) == 2 && reached(11) == 2 && reached(20) == 2, "the test reaches every pad");
    got_n = 0, rh_push_player(1, 0, w);
    check(got_n == 0, "a player's value waits while the test plays");
    got_n = 0, rh_tick(now_ns, 0, 100, 100, 1);
    check(reached(10) == 2 && reached(11) == 2 && amp_of(11) == 0.0f, "the test's end silences every pad");

    /* a pad closed: no one's, the shared value again */
    rh_pad_player(&pad_b, -1);
    got_n = 0, rh_push(0, v);
    check(reached(11) == 1 && reached(10) == 0, "a pad no longer a player's: the shared value");

    /* HD rumble: player 2's slot alone */
    uint8_t idle[3][4], own[3][4], made[3][4];
    hd_sides_of(1, 100, idle);
    hos_sdl_rumble_hd_player(1, 0, v);
    check(!memcmp(hd_of[1][0], v, sizeof v) && hd_of[0][0][0] == 0.0f && hd_of[1][1][0] == 0.0f,
          "HD rumble: player 2's left side, nothing else");
    hos_sdl_rumble_hd_player(9, 0, v);   /* (no such player: nothing written) */
    hd_sides_of(1, 100, own);
    hd_sides_of(0, 100, made);
    check(memcmp(own[0], idle[0], 4) && !memcmp(made, idle, sizeof idle), "HD rumble: player 2's bytes from its value");
    if (!bad) puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    rhc = (ROOT / "host/rumble_renhdrum.c").read_text(encoding="utf-8")
    pad = (ROOT / "host/pad_sdl.c").read_text(encoding="utf-8")
    hid = (ROOT / "host/nn_hid.c").read_text(encoding="utf-8")
    funcs = "\n".join(block(rhc, marker) for marker in (
        "void rh_push(int side, const float v[4]) {", "void rh_push_player(int player, int side, const float v[4]) {",
        "void rh_pad_player(void *pad, int player) {",
        "void rh_tick(int64_t now, int test, int percent, int usb_percent, int hd) {"))
    fixture = (HARNESS.replace("@HD_RUMBLE@", (ROOT / "host/hd_rumble.h").as_posix())
               .replace("@RH_DEFINES@", between(rhc, "#define RH_STALE_NS", "#define RH_EFFECTS")
                        + "#define RH_EFFECTS RENHDRUM_DS5_EFFECTS_SIZE\n")
               .replace("@RH_STATE@", between(rhc, "static int closed;", "static int64_t now_us(void)"))
               .replace("@RH_FEED@", between(rhc, "static int64_t now_us(void)", "void rh_push(int side"))
               .replace("@RH_FUNCS@", funcs)
               .replace("@HD_STATE@", between(pad, "static SRWLOCK hd_lock", "/* (motion) the pad read"))
               .replace("@HD_PLAYER@", block(pad, "void hos_sdl_rumble_hd_player(int player, int side, const float value[4]) {")))
    # the poll: whose each pad is, before what plays it is chosen; a VIB_HD pad's own player's bytes, row on
    poll = block(pad, "static void pads_poll(void) {")
    owner = "rh_pad_player(gc, split ? count - 1 : -1);"
    own_hd = "if (pads[i].vib == VIB_HD && split && !testing) hd_sides_of(count - 1, strength, side);"
    shared_hd = "if (pads[i].vib == VIB_HD && hd_poll(i, side, now)) continue;"
    for text in (owner, own_hd, shared_hd, "rh_pad_player(pads[i].gc, -1);"):
        if poll.count(text) != 1:
            raise SystemExit("pad_sdl.c's poll: not once: " + text)
    if not poll.index(owner) < poll.index("vib_choose(i, mode, now);", poll.index("count++;")):
        raise SystemExit("pad_sdl.c's poll: whose the pad is, after its vibration is chosen")
    if not poll.index(own_hd) < poll.index(shared_hd):
        raise SystemExit("pad_sdl.c's poll: a player's HD bytes made after hd_poll sent them")
    if "kirby_npad_vibration(G32(handle), dev, amp[dev], v);" not in block(hid, "static void vibration_send(uint64_t handle, uint64_t value) {"):
        raise SystemExit("nn_hid.c's vibration_send: the value is not handed to kirby_npad_vibration")
    compiler = shutil.which(args.cc)
    if not compiler:
        raise SystemExit("C compiler not found: " + args.cc)
    with tempfile.TemporaryDirectory(prefix="rumble-per-player-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.c").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c11", "-O1", "-Wall", "-Wno-unused-function", "-Wno-unused-variable",
                        str(folder / "fixture.c"), "-o", str(exe), "-lm"], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("a player's vibration reaches another player's pad (issue #16)")
    print("PASS: each player's vibration on its own pad, on HD rumble and RenHDrum too")


if __name__ == "__main__":
    main()
