"""Game-free test of host/kirby_res.c: the dynamic resolution's six docked frame sizes in basil/ScnCommon.bin, scaled to a
16:9 output between 2560 x 1440 and 3840 x 2160 as the file is read, and left alone for another output, another file, a
read that does not hold the whole table, or a table that is not the one known. The fixed size, every level the first
one's, and kirby_read_done's choice of it: fixed unless HOS_DYNAMIC_RES is set to a number that is not 0 (the game's
steps are off by default), and never in the handheld profile, which keeps the file as read. There HOS_SCENE_HEIGHT=<lines>
holds the scene at one 16:9 size, 360 to 1080 lines: the five sizes of the handheld set, which follows the docked table in
the file, all become it, and the docked table stays as read. A picture of its own shape
(this game's cameras at the screen's ratio, host/kirby_wide.c) gives the scene that shape, within the pixels of 3840 x 2160. The sizes in the fixture
are the game's level sizes (numbers, no game data). And nn_fs.c's read calls it before the bytes are marked written.

    python -I tests/test_kirby_res.py --cxx clang++
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block

FIXTURE = r'''
#define _POSIX_C_SOURCE 200112L   /* (setenv, unsetenv under -std=c11) */
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void hos_log(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vprintf(fmt, ap); va_end(ap); printf("\n"); }
static uint32_t out_w = 3840, out_h = 2160;
static int handheld;
uint32_t hos_output_size(int height) { return height ? out_h : out_w; }
int hos_handheld(void) { return handheld; }
/* the options file's lines the menu wrote (host/kirby_option.h): kirby_dynamic_res= and handheld_scene_size=, -1 none */
static int ini_dynres = -1, ini_scene = -1;
int hos_ini_option(const char *key, int otherwise) {
    const int v = !strcmp(key, "kirby_dynamic_res") ? ini_dynres : !strcmp(key, "handheld_scene_size") ? ini_scene : -1;
    return v >= 0 ? v : otherwise;
}
void kirby_shadow_read(const char *guest, int64_t off, uint8_t *buf, uint64_t n) { (void)guest, (void)off, (void)buf, (void)n; }
int kirby_scn_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, uint32_t out_w, uint32_t out_h, int fixed,
                    int shaped);
int kirby_scn_handheld_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, uint32_t height);
void kirby_scn_shape(uint32_t pw, uint32_t ph, uint32_t *w, uint32_t *h);
volatile uint64_t hos_wide_out;
volatile float hos_wide_ratio;
void kirby_read_done(const char *guest, int64_t off, uint8_t *buf, uint64_t n);

static const uint32_t game[18] = {0, 2560, 1440, 1, 2240, 1260, 2, 1862, 1048, 3, 1536, 864, 4, 1280, 720, 5, 854, 480};
/* the handheld set, right after the docked levels: five (width, height) */
static const uint32_t hand[10] = {1920, 1080, 1600, 900, 1120, 630, 960, 540, 640, 360};
#define HAND (0x97ca0 + sizeof game)
static uint8_t file[0x98000];
static const char *path = "aoc1:/basil/ScnCommon.bin";

static void fresh(void) {
    memset(file, 0xab, sizeof file);
    memcpy(file + 0x97ca0, game, sizeof game);
    memcpy(file + HAND, hand, sizeof hand);
}
static uint32_t at(int k) { uint32_t v; memcpy(&v, file + 0x97ca0 + 4 * k, 4); return v; }
static uint32_t hat(int k) { uint32_t v; memcpy(&v, file + HAND + 4 * k, 4); return v; }
static int hand_same(void) { return !memcmp(file + HAND, hand, sizeof hand) && file[HAND + sizeof hand] == 0xab; }
static int docked_same(void) { return !memcmp(file + 0x97ca0, game, sizeof game) && file[0x97ca0 - 1] == 0xab; }
static int same(void) { return docked_same() && hand_same(); }
static int hand_all(uint32_t w, uint32_t h) {
    for (int k = 0; k < 5; k++) if (hat(2 * k) != w || hat(2 * k + 1) != h) return 0;
    return file[HAND + sizeof hand] == 0xab;
}

int main(void) {
    /* 3840 x 2160: x1.5, each side even; the index words and the bytes around the table stay */
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3840, 2160, 0, 0) == 1);
    const uint32_t want[18] = {0, 3840, 2160, 1, 3360, 1890, 2, 2792, 1572, 3, 2304, 1296, 4, 1920, 1080, 5, 1280, 720};
    for (int k = 0; k < 18; k++) assert(at(k) == want[k]);
    assert(file[0x97ca0 - 1] == 0xab && hand_same());
    /* a read from further on that holds the table: the same */
    fresh();
    assert(kirby_scn_patch(path, 0x90000, file + 0x90000, sizeof file - 0x90000, 3840, 2160, 0, 0) == 1 && at(1) == 3840);
    /* 3200 x 1800 */
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3200, 1800, 0, 0) == 1 && at(1) == 3200 && at(2) == 1800 && at(16) == 1066);
    /* the game's 2560 x 1440, a smaller one, 21:9, 16:10, larger than 3840 x 2160, the game's own 2048 x 1152 (0 x 0): left */
    const uint32_t keep[][2] = {{2560, 1440}, {1920, 1080}, {3440, 1440}, {3840, 2400}, {5120, 2880}, {0, 0}};
    for (unsigned i = 0; i < sizeof keep / sizeof *keep; i++) {
        fresh();
        assert(kirby_scn_patch(path, 0, file, sizeof file, keep[i][0], keep[i][1], 0, 0) == 0 && same());
    }
    /* another file; a read that ends inside the table; one that starts inside it: left */
    fresh();
    assert(kirby_scn_patch("aoc1:/basil/App.bin", 0, file, sizeof file, 3840, 2160, 0, 0) == 0 && same());
    assert(kirby_scn_patch(path, 0, file, 0x97ca0 + 40, 3840, 2160, 0, 0) == 0 && same());
    assert(kirby_scn_patch(path, 0x97ca4, file + 0x97ca4, 0x100, 3840, 2160, 0, 0) == 0 && same());
    /* a table that is not the one known (another version of the file): left */
    fresh();
    file[0x97ca0 + 4 * 7] ^= 1;
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3840, 2160, 0, 0) == 0 && at(7) == (1862 ^ 1) && at(1) == 2560);
    /* fixed: every level the first one's size, at the output's or at the game's */
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3840, 2160, 1, 0) == 1);
    for (int k = 0; k < 6; k++) assert(at(3 * k) == (uint32_t)k && at(3 * k + 1) == 3840 && at(3 * k + 2) == 2160);
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 1920, 1080, 1, 0) == 1);
    for (int k = 0; k < 6; k++) assert(at(3 * k + 1) == 2560 && at(3 * k + 2) == 1440);
    assert(hand_same());
    /* the handheld set held at one height: its five sizes that 16:9 size, each side even, the docked table and the
       bytes after as read; under 360 lines 360 (the set's smallest), over 1080 lines 1080 */
    const uint32_t held[][3] = {{720, 1280, 720}, {900, 1600, 900}, {1080, 1920, 1080}, {800, 1422, 800}, {801, 1422, 800},
                                {360, 640, 360}, {630, 1120, 630}, {1, 640, 360}, {2160, 1920, 1080}};
    for (unsigned i = 0; i < sizeof held / sizeof *held; i++) {
        fresh();
        assert(kirby_scn_handheld_patch(path, 0, file, sizeof file, held[i][0]) == 1);
        assert(hand_all(held[i][1], held[i][2]) && docked_same());
    }
    fresh();
    assert(kirby_scn_handheld_patch(path, 0x90000, file + 0x90000, sizeof file - 0x90000, 720) == 1 && hand_all(1280, 720));
    /* no height (0), another file, a read without all of the set, or a set that is not the one known: left */
    fresh();
    assert(kirby_scn_handheld_patch(path, 0, file, sizeof file, 0) == 0 && same());
    assert(kirby_scn_handheld_patch("aoc1:/basil/App.bin", 0, file, sizeof file, 720) == 0 && same());
    assert(kirby_scn_handheld_patch(path, 0, file, HAND + 36, 720) == 0 && same());
    assert(kirby_scn_handheld_patch(path, HAND + 4, file + HAND + 4, 0x100, 720) == 0 && same());
    file[HAND + 4 * 3] ^= 1;
    assert(kirby_scn_handheld_patch(path, 0, file, sizeof file, 720) == 0 && hat(3) == (900 ^ 1) && hat(0) == 1920);
    /* the read's own choice (the output here is 3840 x 2160): fixed with HOS_DYNAMIC_RES unset or 0, the game's steps
       with 1 */
    unsetenv("HOS_DYNAMIC_RES");
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 6; k++) assert(at(3 * k) == (uint32_t)k && at(3 * k + 1) == 3840 && at(3 * k + 2) == 2160);
    setenv("HOS_DYNAMIC_RES", "0", 1);
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 6; k++) assert(at(3 * k + 1) == 3840 && at(3 * k + 2) == 2160);
    setenv("HOS_DYNAMIC_RES", "1", 1);
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 18; k++) assert(at(k) == want[k]);
    /* HOS_SCENE_HEIGHT is the handheld profile's: docked, the handheld set stays as read */
    setenv("HOS_SCENE_HEIGHT", "720", 1);
    unsetenv("HOS_DYNAMIC_RES");
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 6; k++) assert(at(3 * k + 1) == 3840 && at(3 * k + 2) == 2160);
    assert(hand_same());
    unsetenv("HOS_SCENE_HEIGHT");
    /* a picture of its own shape (host/kirby_wide.c): the scene takes it, at least 1440 lines, at most 3840 x 2160's pixels */
    const uint32_t shape[][4] = {{3440, 1440, 3440, 1440}, {2560, 1080, 3412, 1440}, {5120, 1440, 5120, 1440},
                                 {5120, 2160, 4434, 1870}, {6256, 1760, 5428, 1526}, {2304, 1440, 2304, 1440}};
    for (unsigned i = 0; i < sizeof shape / sizeof *shape; i++) {
        uint32_t w, h;
        kirby_scn_shape(shape[i][0], shape[i][1], &w, &h);
        if (w != shape[i][2] || h != shape[i][3]) printf("shape %ux%u: %ux%u\n", shape[i][0], shape[i][1], w, h);
        assert(w == shape[i][2] && h == shape[i][3] && (uint64_t)w * h <= 3840u * 2160u);
    }
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3440, 1440, 0, 1) == 1 && at(1) == 3440 && at(2) == 1440 && at(4) == 3010 &&
           at(5) == 1260 && at(16) == 1146 && at(17) == 480);
    /* the read's choice with that picture: fixed at its shape; at 16:9 (no ratio) the output's, as above */
    hos_wide_out = (uint64_t)1440 << 32 | 3440, hos_wide_ratio = 2.3889f;
    unsetenv("HOS_DYNAMIC_RES");
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 6; k++) assert(at(3 * k + 1) == 3440 && at(3 * k + 2) == 1440);
    /* the handheld profile (its output is 1920 x 1080): the file as read, HOS_DYNAMIC_RES unset or 0, whatever the
       picture's shape */
    handheld = 1, out_w = 1920, out_h = 1080;
    unsetenv("HOS_DYNAMIC_RES");
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    setenv("HOS_DYNAMIC_RES", "0", 1);
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    hos_wide_out = 0, hos_wide_ratio = 0.0f;
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    /* HOS_SCENE_HEIGHT=720, handheld: the handheld set 1280 x 720, the docked table as read; with the game's steps
       asked (HOS_DYNAMIC_RES=1), or the variable empty, the file as read */
    setenv("HOS_SCENE_HEIGHT", "720", 1);
    kirby_read_done(path, 0, file, sizeof file);
    assert(hand_all(1280, 720) && docked_same());
    setenv("HOS_DYNAMIC_RES", "1", 1);
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    unsetenv("HOS_DYNAMIC_RES");
    setenv("HOS_SCENE_HEIGHT", "", 1);
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    /* the menu's Handheld scene size row with the variable unset (or empty): 1 900, 2 720, 3 540, 4 360 lines; 0 or a
       hand-edited value out of range the file as read; the variable over it; the Dynamic resolution row on: as read */
    static const uint32_t row_size[][2] = {{0, 0}, {1600, 900}, {1280, 720}, {960, 540}, {640, 360}};
    for (int row = 0; row < 5; row++) {
        ini_scene = row;
        fresh();
        kirby_read_done(path, 0, file, sizeof file);
        assert(row ? hand_all(row_size[row][0], row_size[row][1]) && docked_same() : same());
    }
    unsetenv("HOS_SCENE_HEIGHT");
    ini_scene = 9;
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    ini_scene = 3;
    setenv("HOS_SCENE_HEIGHT", "720", 1);
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    assert(hand_all(1280, 720));
    unsetenv("HOS_SCENE_HEIGHT");
    ini_dynres = 1;
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    assert(same());
    setenv("HOS_DYNAMIC_RES", "0", 1);   /* (the variable over the row) */
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    assert(hand_all(960, 540));
    unsetenv("HOS_DYNAMIC_RES");
    ini_scene = -1;
    /* docked: the Dynamic resolution row on gives the game's steps, as HOS_DYNAMIC_RES=1 does; the variable at 0 over it */
    handheld = 0, out_w = 3840, out_h = 2160;
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 18; k++) assert(at(k) == want[k]);
    setenv("HOS_DYNAMIC_RES", "0", 1);
    fresh();
    kirby_read_done(path, 0, file, sizeof file);
    for (int k = 0; k < 6; k++) assert(at(3 * k + 1) == 3840 && at(3 * k + 2) == 2160);
    unsetenv("HOS_DYNAMIC_RES");
    ini_dynres = -1;
    puts("ok");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()

    # (nn_fs.c's read: the sizes rewritten in the bytes read, before they are marked written for the GPU)
    read_at = block((ROOT / "host/nn_fs.c").read_text(encoding="utf-8"), "static uint64_t read_at(")
    call, written = read_at.find("kirby_read_done(fh->path, off, (uint8_t *)GP(buf), done);"), read_at.find("HOS_WRITTEN(")
    assert 0 <= call < written, "nn_fs.c read_at: kirby_read_done must run on the bytes read, before HOS_WRITTEN"

    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.c"
        test.write_text(FIXTURE, encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-x", "c", "-std=c11", "-Wall", "-Werror", str(ROOT / "host/kirby_res.c"), str(test),
                        "-o", str(exe), "-lm"], check=True)
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        sys.stdout.write(out.stdout)
        assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), out.stderr
    print("test_kirby_res: ok")


if __name__ == "__main__":
    main()
