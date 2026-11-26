"""Game-free test of host/kirby_fps.c: the Frame rate row's 30 and the Keep speed under 20 FPS row (issue #26), both
held on the game's own frame rate controller.

kirby_fps_apply, kirby_fps_keep_speed and what they call are cut from the source and run over a stand-in for the guest's
memory (the pointer to a pointer at main+0x2c39c68, then the controller: its mode at +0x60, the vsyncs a frame at +0x3c,
the step's ceiling at +0x34). No game, no game data.

  - 30: the vsyncs a frame go from the game's 1 to 2 and nothing else is written; written again when the game puts its 1
    back; 60 after that gives the 1 back, and the memory is the game's again, byte for byte;
  - 60 from the start: nothing is ever written, a 2 that is not this file's included;
  - before the game made the controller (either pointer null): nothing read past the null, nothing written;
  - a load's fixed step modes (0, 1): left; a 60 chosen during one waits for the mode to give the 1 back;
  - a controller that is not as known (another count of vsyncs, a step that cannot reach 2): left, said once;
  - another game's main: nothing read, nothing written;
  - HOS_KIRBY_FPS=30 or 60 stands over the row (option 1002, asked every call); any other value is no choice.

Keep speed under 20 FPS, the same way on the step's ceiling:

  - on: the ceiling goes from the game's 3.0 to 6.0 and nothing else is written; written again when the game puts its
    3.0 back; off after that gives the 3.0 back, and the memory is the game's again, byte for byte;
  - off from the start: nothing is ever read or written, a 6.0 that is not this file's included;
  - either pointer null, a load's modes, another game's main: left, as above;
  - another ceiling than the game's 3.0 (60.0, 4.0, 2.0): left, said once in a run, and nothing is held: off after it
    reads nothing; a 6.0 that was there before the row went on is not this file's, and off leaves it;
  - both rows on: the 30 takes hold over a ceiling of 6.0, whichever comes first, and each gives back its own alone;
  - HOS_KIRBY_KEEP_SPEED=1 or 0 stands over the row (option 1003, asked every call); any other value is no choice;
  - a present (kirby_fps_presented, cut too) asks both rows and holds both.

And the source around it: the present calls it, the renderer answers the options from the rows, the rows are this
game's and apply in play, each row is locked by its variable at a value that chooses and no other (locked_by, cut and
compiled), and the FPS counter's target (fps_cap_now, cut and compiled) is 30 with the row or the variable at 30.

    python -I tests/test_kirby_fps.py --cxx clang++
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between, block

FIXTURE = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gpu/vk/compat/inhale_env.h"

/* the guest's memory: the holder's 8 bytes in the image, and a heap for the pointer it holds and the controller */
#define HOLDER 0x82c39c68ULL
#define HEAP 0x1000200000ULL
#define PTR (HEAP + 0x40)
#define OBJ (HEAP + 0x100)
static _Alignas(8) uint8_t image[8], heap[0x200];
static int reads;
static void *gp(uint64_t a) {
    reads++;
    if (a >= HOLDER && a + 4 <= HOLDER + sizeof image) return image + (a - HOLDER);
    if (!(a >= HEAP && a + 4 <= HEAP + sizeof heap)) printf("guest address %llx\n", (unsigned long long)a), exit(2);
    return heap + (a - HEAP);
}
#define GP(a) gp(a)
#define G64(a) (*(uint64_t *)GP(a))
#define G32(a) (*(uint32_t *)GP(a))

static int logs;
void hos_log(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vprintf(fmt, ap); va_end(ap); printf("\n"); logs++; }
static int this_game = 1;
int kirby_wide_ok(void) { return this_game; }
static int row, row_speed, asked = -1;
int rx_option(int id, int otherwise) { (void)otherwise; asked = id; return id == 1003 ? row_speed : row; }
long long hos_now_ns(void) { return 0; }

/* SOURCE */

static uint8_t before[sizeof heap], image_before[sizeof image];
/* the controller as the game has it in play: the variable step mode, one vsync a frame, a step of up to 3 */
static void play(void) {
    const float top = 3.0f;
    memset(heap, 0xab, sizeof heap);
    memset(image, 0, sizeof image);
    *(uint64_t *)image = PTR;
    *(uint64_t *)(heap + 0x40) = OBJ;
    *(uint32_t *)(heap + 0x100 + 0x60) = 2;
    *(uint32_t *)(heap + 0x100 + 0x3c) = 1;
    memcpy(heap + 0x100 + 0x34, &top, 4);
    memcpy(before, heap, sizeof heap), memcpy(image_before, image, sizeof image);
}
static uint32_t *vsyncs(void) { return (uint32_t *)(heap + 0x100 + 0x3c); }
static uint32_t *mode(void) { return (uint32_t *)(heap + 0x100 + 0x60); }
/* (the holder's own bytes are never written: the heap alone may change) */
static int holder_kept(void) { return !memcmp(image_before, image, sizeof image); }
static int same(void) { return holder_kept() && !memcmp(before, heap, sizeof heap); }
/* the heap is the game's but for the vsyncs a frame, which are v */
static int only_vsyncs(uint32_t v) {
    uint8_t now[sizeof heap];
    memcpy(now, heap, sizeof heap);
    memcpy(now + 0x100 + 0x3c, before + 0x100 + 0x3c, 4);
    return holder_kept() && *vsyncs() == v && !memcmp(before, now, sizeof heap);
}
static float top(void) { float f; memcpy(&f, heap + 0x100 + 0x34, 4); return f; }
static void set_top(float f) { memcpy(heap + 0x100 + 0x34, &f, 4); }
/* the heap is the game's but for the vsyncs a frame, which are v, and the step's ceiling, which is f */
static int only(uint32_t v, float f) {
    uint8_t now[sizeof heap];
    memcpy(now, heap, sizeof heap);
    memcpy(now + 0x100 + 0x3c, before + 0x100 + 0x3c, 4);
    memcpy(now + 0x100 + 0x34, before + 0x100 + 0x34, 4);
    return holder_kept() && *vsyncs() == v && top() == f && !memcmp(before, now, sizeof heap);
}
/* the heap is the game's but for the step's ceiling, which is f */
static int only_top(float f) {
    uint32_t v;
    memcpy(&v, before + 0x100 + 0x3c, 4);
    return only(v, f);
}

int main(int argc, char **argv) {
    const char *t = argc > 1 ? argv[1] : "";
    play();
    if (!strcmp(t, "row30")) {
        kirby_fps_apply(1);
        assert(only_vsyncs(2));
        kirby_fps_apply(1);
        assert(only_vsyncs(2) && !logs);
        *vsyncs() = 1;   /* (the game comes back to the mode and writes its own) */
        kirby_fps_apply(1);
        assert(only_vsyncs(2));
        kirby_fps_apply(0);
        assert(same());
        *vsyncs() = 2;   /* (not this file's any more: 60 leaves it) */
        kirby_fps_apply(0);
        assert(only_vsyncs(2) && !logs);
        *vsyncs() = 1;
        kirby_fps_apply(1);   /* (held again, and the game then writes a count of its own: 60 leaves that too) */
        assert(only_vsyncs(2));
        *vsyncs() = 3;
        kirby_fps_apply(0);
        assert(only_vsyncs(3) && !logs);
        *vsyncs() = 1;
        kirby_fps_apply(1);   /* (and its own 1, written before the 60 is seen: left as the game's) */
        *vsyncs() = 1;
        kirby_fps_apply(0);
        kirby_fps_apply(0);
        assert(same() && !logs);
    } else if (!strcmp(t, "from60")) {
        reads = 0;
        for (int i = 0; i < 3; i++) kirby_fps_apply(0);
        assert(same() && !reads);
        *vsyncs() = 2;
        kirby_fps_apply(0);
        assert(only_vsyncs(2) && !reads && !logs);
    } else if (!strcmp(t, "unset")) {
        memset(image, 0, sizeof image), memset(image_before, 0, sizeof image);
        kirby_fps_apply(1);
        assert(same());
        *(uint64_t *)image = PTR, memcpy(image_before, image, sizeof image);
        memset(heap + 0x40, 0, 8), memset(before + 0x40, 0, 8);
        kirby_fps_apply(1);
        assert(same());
        *(uint64_t *)(heap + 0x40) = OBJ, *(uint64_t *)(before + 0x40) = OBJ;
        kirby_fps_apply(1);
        assert(only_vsyncs(2) && !logs);
    } else if (!strcmp(t, "loading")) {
        for (uint32_t m = 0; m < 2; m++) {
            *mode() = m, memcpy(before, heap, sizeof heap);
            kirby_fps_apply(1);
            assert(same());
        }
        *mode() = 2, memcpy(before, heap, sizeof heap);
        kirby_fps_apply(1);
        assert(only_vsyncs(2));
        *mode() = 0, memcpy(before + 0x100 + 0x60, mode(), 4);   /* (60 chosen during a load: the 2 waits for the mode) */
        kirby_fps_apply(0);
        assert(only_vsyncs(2));
        *mode() = 2, memcpy(before + 0x100 + 0x60, mode(), 4);
        kirby_fps_apply(0);
        assert(same() && !logs);
    } else if (!strcmp(t, "unknown")) {
        const float one = 1.0f;
        *vsyncs() = 3, memcpy(before, heap, sizeof heap);
        kirby_fps_apply(1);
        kirby_fps_apply(1);
        assert(same() && logs == 1);
        play();
        memcpy(heap + 0x100 + 0x34, &one, 4), memcpy(before, heap, sizeof heap);
        kirby_fps_apply(1);
        assert(same() && logs == 1);   /* (said once in a run) */
    } else if (!strcmp(t, "ceiling")) {   /* (a step that cannot reach 2 would halve the game's speed at two vsyncs) */
        const float low = 1.5f, two = 2.0f;
        memcpy(heap + 0x100 + 0x34, &low, 4), memcpy(before, heap, sizeof heap);
        kirby_fps_apply(1);
        assert(same() && logs == 1);
        memcpy(heap + 0x100 + 0x34, &two, 4), memcpy(before, heap, sizeof heap);
        kirby_fps_apply(1);
        assert(only_vsyncs(2));
    } else if (!strcmp(t, "other")) {
        this_game = 0, reads = 0;
        kirby_fps_apply(1);
        assert(same() && !reads && !logs);
    } else if (!strcmp(t, "want")) {   /* argv[2]: what the variable chooses, 30, 60 or 0 for the row's */
        const int env = atoi(argv[2]);
        for (row = 0; row < 2; row++) {
            asked = -1;
            assert(kirby_fps_want30() == (env == 30 || (env != 60 && row)));
            assert(asked == (env ? -1 : 1002));   /* (the row is asked each time, it changes in play; not under the variable) */
        }
        row = 0;
        assert(kirby_fps_want30() == (env == 30));
    } else if (!strcmp(t, "keep")) {
        kirby_fps_keep_speed(1);
        assert(only_top(6.0f));
        kirby_fps_keep_speed(1);
        assert(only_top(6.0f) && !logs);
        set_top(3.0f);   /* (the game comes back to the mode and writes its own) */
        kirby_fps_keep_speed(1);
        assert(only_top(6.0f));
        kirby_fps_keep_speed(0);
        assert(same());
        set_top(6.0f);   /* (not this file's any more: off leaves it) */
        kirby_fps_keep_speed(0);
        assert(only_top(6.0f) && !logs);
        set_top(3.0f);
        kirby_fps_keep_speed(1);   /* (held again, and the game then writes a ceiling of its own: off leaves that too) */
        assert(only_top(6.0f));
        set_top(4.0f);
        kirby_fps_keep_speed(0);
        assert(only_top(4.0f) && !logs);
        set_top(6.0f), reads = 0;   /* (and that off let go: a later 6.0 is not this file's, and nothing is read) */
        kirby_fps_keep_speed(0);
        assert(only_top(6.0f) && !reads);
        set_top(3.0f);
        kirby_fps_keep_speed(1);   /* (and its own 3.0, written before the off is seen: left as the game's) */
        set_top(3.0f);
        kirby_fps_keep_speed(0);
        kirby_fps_keep_speed(0);
        assert(same() && !logs);
    } else if (!strcmp(t, "keep_off")) {
        reads = 0;
        for (int i = 0; i < 3; i++) kirby_fps_keep_speed(0);
        assert(same() && !reads);
        set_top(6.0f);
        kirby_fps_keep_speed(0);
        assert(only_top(6.0f) && !reads && !logs);
    } else if (!strcmp(t, "keep_unset")) {
        memset(image, 0, sizeof image), memset(image_before, 0, sizeof image);
        kirby_fps_keep_speed(1);
        assert(same());
        *(uint64_t *)image = PTR, memcpy(image_before, image, sizeof image);
        memset(heap + 0x40, 0, 8), memset(before + 0x40, 0, 8);
        kirby_fps_keep_speed(1);
        assert(same());
        *(uint64_t *)(heap + 0x40) = OBJ, *(uint64_t *)(before + 0x40) = OBJ;
        kirby_fps_keep_speed(1);
        assert(only_top(6.0f) && !logs);
    } else if (!strcmp(t, "keep_loading")) {
        for (uint32_t m = 0; m < 4; m++) {   /* (and 3, a mode the game was not seen in) */
            if (m == 2) continue;
            *mode() = m, memcpy(before, heap, sizeof heap);
            kirby_fps_keep_speed(1);
            assert(same());
        }
        *mode() = 2, memcpy(before, heap, sizeof heap);
        kirby_fps_keep_speed(1);
        assert(only_top(6.0f));
        *mode() = 0, memcpy(before + 0x100 + 0x60, mode(), 4);   /* (off chosen during a load: the 6.0 waits for the mode) */
        kirby_fps_keep_speed(0);
        assert(only_top(6.0f));
        *mode() = 2, memcpy(before + 0x100 + 0x60, mode(), 4);
        kirby_fps_keep_speed(0);
        assert(same() && !logs);
    } else if (!strcmp(t, "keep_unknown")) {   /* (the constructor's 60.0, or any ceiling that is not the game's in play) */
        set_top(60.0f), memcpy(before, heap, sizeof heap);
        kirby_fps_keep_speed(1);
        kirby_fps_keep_speed(1);
        assert(same() && logs == 1);
        set_top(2.0f), memcpy(before, heap, sizeof heap);
        kirby_fps_keep_speed(1);
        assert(same() && logs == 1);   /* (said once in a run) */
        set_top(4.0f), memcpy(before, heap, sizeof heap);   /* (between the game's and this file's: not raised) */
        kirby_fps_keep_speed(1);
        assert(same() && logs == 1);
        set_top(6.0f), memcpy(before, heap, sizeof heap), reads = 0;
        kirby_fps_keep_speed(0);   /* (nothing was held: nothing is read, and a 6.0 is not given back) */
        assert(same() && !reads);
        set_top(3.0f);   /* (held and let go, then another ceiling again: still said once) */
        kirby_fps_keep_speed(1);
        kirby_fps_keep_speed(0);
        set_top(60.0f);
        kirby_fps_keep_speed(1);
        assert(logs == 1);
    } else if (!strcmp(t, "keep_foreign")) {   /* (a 6.0 that was there before the row went on: never this file's) */
        set_top(6.0f), memcpy(before, heap, sizeof heap);
        kirby_fps_keep_speed(1);
        kirby_fps_keep_speed(0);
        assert(same() && !logs);
    } else if (!strcmp(t, "keep_other")) {
        this_game = 0, reads = 0;
        kirby_fps_keep_speed(1);
        assert(same() && !reads && !logs);
    } else if (!strcmp(t, "both")) {   /* (the 30 takes hold over a ceiling of 6.0, whichever comes first) */
        kirby_fps_keep_speed(1), kirby_fps_apply(1);
        assert(only(2, 6.0f));
        kirby_fps_keep_speed(1), kirby_fps_apply(1);
        assert(only(2, 6.0f) && !logs);
        kirby_fps_keep_speed(0);   /* (each gives back its own alone) */
        assert(only(2, 3.0f));
        kirby_fps_apply(0);
        assert(same());
        kirby_fps_apply(1), kirby_fps_keep_speed(1);
        assert(only(2, 6.0f));
        kirby_fps_apply(0);
        assert(only(1, 6.0f));
        kirby_fps_keep_speed(0);
        assert(same() && !logs);
    } else if (!strcmp(t, "presented")) {   /* (a present asks both rows and holds what each chooses) */
        kirby_fps_presented();
        assert(same());
        row_speed = 1;
        kirby_fps_presented();
        assert(only_top(6.0f));
        row = 1;
        kirby_fps_presented();
        assert(only(2, 6.0f));
        row_speed = 0;
        kirby_fps_presented();
        assert(only(2, 3.0f));
        row = 0;
        kirby_fps_presented();
        assert(same() && !logs);
    } else if (!strcmp(t, "want_speed")) {   /* argv[2]: what the variable chooses, 1, 0 or -1 for the row's */
        const int env = atoi(argv[2]);
        for (row_speed = 0; row_speed < 2; row_speed++) {
            asked = -1;
            assert(kirby_fps_want_speed() == (env == 1 || (env < 0 && row_speed)));
            assert(asked == (env < 0 ? 1003 : -1));   /* (the row is asked each time, it changes in play; not under the variable) */
        }
    } else {
        return 3;
    }
    puts("ok");
    return 0;
}
'''

# (locked_by as kirby_env_rows.cpp has it: argv[1] the variable's name, its value from the environment)
LOCK_FIXTURE = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "gpu/vk/compat/inhale_env.h"
/* SOURCE */
int main(int, char** argv) {
    const char* text = locked_by(argv[1]);
    puts(text ? text : "free");
    return 0;
}
'''

# (fps_cap_now as vk_menu.cpp has it, over the real fps_stats.h: argv[1] the row, the variable from the environment)
MENU_FIXTURE = r'''
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include "gpu/vk/compat/inhale_env.h"
#include "gpu/vk/fps_stats.h"
using namespace mkwvk;
struct { int fps_cap = 0, kirby_fps = 0; } opts;
/* SOURCE */
int main(int, char** argv) {
    opts.kirby_fps = atoi(argv[1]);
    printf("%d\n", fps_cap_now());
    return 0;
}
'''

CASES = ["row30", "from60", "unset", "loading", "unknown", "ceiling", "other",
         "keep", "keep_off", "keep_unset", "keep_loading", "keep_unknown", "keep_foreign", "keep_other", "both",
         "presented"]
# (HOS_KIRBY_FPS, what it chooses: 30, 60, or 0 for no choice)
WANT = [(None, 0), ("30", 30), ("60", 60), ("40", 0), ("", 0), ("on", 0)]
# (HOS_KIRBY_KEEP_SPEED, what it chooses: 1, 0, or -1 for no choice)
WANT_SPEED = [(None, -1), ("1", 1), ("0", 0), ("2", -1), ("-1", -1), ("", -1), ("on", -1)]


def check_source():
    vi = block((ROOT / "host/nn_vi.c").read_text(encoding="utf-8"), "void hos_vi_native_presented(")
    assert "kirby_fps_presented();" in vi, "hos_vi_native_presented no longer calls kirby_fps_presented"
    fps = (ROOT / "host/kirby_fps.c").read_text(encoding="utf-8")
    api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
    assert "enum { HOS_OPT_KIRBY_FPS = 1002 };" in api and "enum { HOS_OPT_KIRBY_KEEP_SPEED = 1003 };" in api
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    assert "if (id == HOS_OPT_KIRBY_FPS) return opts.kirby_fps;" in replay, "the renderer no longer answers the option"
    assert "if (id == HOS_OPT_KIRBY_KEEP_SPEED) return opts.kirby_keep_speed;" in replay, \
        "the renderer no longer answers the Keep speed option"
    # (the row: this game's, in play (no restart), locked by the variable at 30 or 60 alone)
    rows = (ROOT / "gpu/vk/menu/kirby_env_rows.cpp").read_text(encoding="utf-8")
    row = between(rows, '.key = "kirby_frame_rate",', 'menu::after("kirby_dynamic_res")')
    assert ".value = &opts.kirby_fps," in row and '.choices = {"60", "30"},' in row and ".restart" not in row, row
    assert 'locked_by("HOS_KIRBY_FPS")' in row and "Applies at once." in row, row
    # (Keep speed under 20 FPS: a toggle, off unless chosen, in play, locked by the variable at 0 or 1 alone)
    row = between(rows, '.key = "kirby_keep_speed",', 'menu::after("kirby_frame_rate")')
    assert ".value = &opts.kirby_keep_speed," in row and ".kind = menu::Kind::Toggle," in row, row
    assert ".restart" not in row and ".preset_exempt = true," in row, row
    assert 'locked_by("HOS_KIRBY_KEEP_SPEED")' in row and "Applies at once." in row, row
    assert "int kirby_keep_speed = 0;" in (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8"), \
        "Keep speed under 20 FPS is off unless a player turns it on"
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    shown = block(menu, "bool kirby_row(const Row& r) {")
    assert "r.value == &opts.kirby_fps" in shown and "r.value == &opts.kirby_keep_speed" in shown, \
        "kirby_row: the Frame rate and Keep speed rows must hide while the other game runs"
    return fps, menu, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    fps, menu, rows = check_source()
    cut = "\n".join([
        between(fps, "#define KIRBY_FPS_HOLDER", "\n"),
        block(fps, "static uint64_t kirby_fps_controller(void) {"),
        block(fps, "void kirby_fps_apply(int want30) {"),
        block(fps, "int kirby_fps_want30(void) {"),
        between(fps, "#define KIRBY_FPS_TOP", "\n"),
        block(fps, "void kirby_fps_keep_speed(int want) {"),
        block(fps, "int kirby_fps_want_speed(void) {"),
        block(fps, "static void kirby_fps_log(void) {"),
        block(fps, "void kirby_fps_presented(void) {"),
    ])
    clean = {k: v for k, v in os.environ.items() if k not in ("HOS_KIRBY_FPS", "HOS_KIRBY_KEEP_SPEED", "HOS_FPS_LOG")}
    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.c"
        test.write_text(FIXTURE.replace(
            "/* SOURCE */", "enum { HOS_OPT_KIRBY_FPS = 1002, HOS_OPT_KIRBY_KEEP_SPEED = 1003 };\n" + cut),
            encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-std=c11", "-Wall", "-Werror", "-I", str(ROOT), "-x", "c", str(test), "-o", str(exe)],
                       check=True)
        for case in CASES:
            out = subprocess.run([str(exe), case], capture_output=True, text=True, env=clean)
            assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), (case, out.stdout, out.stderr)
        for value, chosen in WANT:
            env = dict(clean) if value is None else dict(clean, HOS_KIRBY_FPS=value)
            out = subprocess.run([str(exe), "want", str(chosen)], capture_output=True, text=True, env=env)
            assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), (value, out.stdout, out.stderr)
        for value, chosen in WANT_SPEED:
            env = dict(clean) if value is None else dict(clean, HOS_KIRBY_KEEP_SPEED=value)
            out = subprocess.run([str(exe), "want_speed", str(chosen)], capture_output=True, text=True, env=env)
            assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), (value, out.stdout, out.stderr)
        # (the FPS counter's target: 30 with the row or the variable at 30, the variable's 60 over the row's 30)
        test = Path(tmp) / "menu.cpp"
        test.write_text(MENU_FIXTURE.replace("/* SOURCE */", block(menu, "int fps_cap_now() {")), encoding="utf-8")
        exe = Path(tmp) / "menu"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Werror", "-I", str(ROOT), str(test), "-o", str(exe)], check=True)
        for value, row, cap in [(None, 0, 60), (None, 1, 30), ("30", 0, 30), ("60", 1, 60), ("40", 1, 30), ("40", 0, 60)]:
            env = dict(clean) if value is None else dict(clean, HOS_KIRBY_FPS=value)
            env.pop("HOS_FPS_MAX", None)
            out = subprocess.run([str(exe), str(row)], capture_output=True, text=True, env=env)
            assert out.returncode == 0 and out.stdout.strip() == str(cap), (value, row, cap, out.stdout, out.stderr)
        # (each row is locked by its variable at a value that chooses, and free at any other and without it)
        test = Path(tmp) / "lock.cpp"
        test.write_text(LOCK_FIXTURE.replace("/* SOURCE */", block(rows, "const char* locked_by(const char* name) {")),
                        encoding="utf-8")
        exe = Path(tmp) / "lock"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Werror", "-I", str(ROOT), str(test), "-o", str(exe)], check=True)
        for name, values in [("HOS_KIRBY_FPS", {None: 0, "30": 1, "60": 1, "40": 0, "0": 0, "": 0, "on": 0}),
                             ("HOS_KIRBY_KEEP_SPEED", {None: 0, "1": 1, "0": 1, "2": 0, "-1": 0, "": 0, "on": 0})]:
            for value, locked in values.items():
                env = dict(clean) if value is None else dict(clean, **{name: value})
                out = subprocess.run([str(exe), name], capture_output=True, text=True, env=env)
                said = "Set by %s (inhale_env.txt or the environment): remove that line to choose here." % name
                assert out.returncode == 0 and out.stdout.strip() == (said if locked else "free"), (name, value, out.stdout)
    print("test_kirby_fps: ok")


if __name__ == "__main__":
    main()
