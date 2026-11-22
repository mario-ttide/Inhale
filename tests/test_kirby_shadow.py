"""Game-free test of host/kirby_shadow.c: the Shadow resolution row for this game, the console size of the shadow map in
basil/ScnCommon.bin (1400, then the handheld's 980, at 0x173ec40) raised as the file is read: 2800 at level 1, 4096 at
level 2, and left alone at level 0 or a level it does not know, for another file, a read that does not hold the pair
whole, or bytes that are not the ones known. The handheld size is never changed. The sizes in the fixture are the
game's (numbers, no game data).

And the source around it: kirby_res.c's read calls it, and the menu shows the row for this game (not one of the other
game's rows) with this game's help and hints, whose sizes are the patch's and whose memory is the map's three targets
(a D16 depth and two R16 blur targets, 6 bytes a texel).

The size is read once, so the row takes a restart in this game: the read tells the menu the level it applied
(rx_option_set 56), only where the known pair was in it, and the menu takes that as the row's start value, the row
flagged restart and compared by the size drawn (menu_shadow_res: Auto resolved). The other game's row stays live.

    python -I tests/test_kirby_shadow.py --cxx clang++
"""
import argparse
import re
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
#include <string.h>

void hos_log(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vprintf(fmt, ap); va_end(ap); printf("\n"); }
static int option = -1, asked;
int rx_option(int id, int otherwise) { asked = id; return option < 0 ? otherwise : option; }
static int told_id = -1, told = -1;   /* (what the read told the menu: rx_option_set) */
void rx_option_set(int id, int value) { told_id = id, told = value; }
static void untold(void) { told_id = -1, told = -1; }
int kirby_shadow_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, int level);
void kirby_shadow_read(const char *guest, int64_t off, uint8_t *buf, uint64_t n);

#define AT 0x173ec40
static const uint32_t game[2] = {1400, 980};
static uint8_t file[AT + 0x100];
static const char *path = "aoc1:/basil/ScnCommon.bin";

static void fresh(void) { memset(file, 0xab, sizeof file); memcpy(file + AT, game, sizeof game); }
static uint32_t at(int k) { uint32_t v; memcpy(&v, file + AT + 4 * k, 4); return v; }
static int around(void) { return file[AT - 1] == 0xab && file[AT + sizeof game] == 0xab; }
static int same(void) { return !memcmp(file + AT, game, sizeof game) && around(); }

int main(void) {
    /* High and Highest: the console size only, the bytes around stay */
    fresh();
    assert(kirby_shadow_patch(path, 0, file, sizeof file, 1) == 1 && at(0) == 2800 && at(1) == 980 && around());
    fresh();
    assert(kirby_shadow_patch(path, 0, file, sizeof file, 2) == 1 && at(0) == 4096 && at(1) == 980 && around());
    /* a read from further on that holds the pair */
    fresh();
    assert(kirby_shadow_patch(path, AT - 0x10, file + AT - 0x10, 0x20, 2) == 1 && at(0) == 4096);
    /* Game's, and a level this build does not know: left */
    const int keep[] = {0, 3, -1};
    for (unsigned i = 0; i < sizeof keep / sizeof *keep; i++) {
        fresh();
        assert(kirby_shadow_patch(path, 0, file, sizeof file, keep[i]) == 0 && same());
    }
    /* another file; a read that ends inside the pair; one that starts inside it: left */
    fresh();
    assert(kirby_shadow_patch("aoc1:/basil/App.bin", 0, file, sizeof file, 2) == 0 && same());
    assert(kirby_shadow_patch(path, 0, file, AT + 4, 2) == 0 && same());
    assert(kirby_shadow_patch(path, AT + 4, file + AT + 4, 0x10, 2) == 0 && same());
    assert(kirby_shadow_patch(NULL, 0, file, sizeof file, 2) == 0 && same());
    /* bytes that are not the ones known (another version of the file), a console size already larger among them: left */
    fresh();
    file[AT + 4] ^= 1;
    assert(kirby_shadow_patch(path, 0, file, sizeof file, 2) == 0 && at(0) == 1400 && at(1) == (980 ^ 1));
    fresh();
    const uint32_t big = 8192;
    memcpy(file + AT, &big, 4);
    assert(kirby_shadow_patch(path, 0, file, sizeof file, 1) == 0 && at(0) == 8192);
    /* the read's own choice: the row's option (56), Game's when the renderer does not answer */
    option = 1, fresh();
    kirby_shadow_read(path, 0, file, sizeof file);
    assert(asked == 56 && at(0) == 2800 && at(1) == 980);
    option = 0, fresh();
    kirby_shadow_read(path, 0, file, sizeof file);
    assert(same());
    option = -1, fresh();
    kirby_shadow_read(path, 0, file, sizeof file);
    assert(same());
    /* the level applied told to the menu (the row's start value), Game's too; nothing where the pair was not read */
    option = 2, fresh(), untold();
    kirby_shadow_read(path, 0, file, sizeof file);
    assert(told_id == 56 && told == 2 && at(0) == 4096);
    option = 0, fresh(), untold();
    kirby_shadow_read(path, AT - 0x10, file + AT - 0x10, 0x20);
    assert(told_id == 56 && told == 0 && same());
    option = 1, fresh(), untold();
    kirby_shadow_read("aoc1:/basil/App.bin", 0, file, sizeof file);
    kirby_shadow_read(path, 0, file, AT + 4);
    kirby_shadow_read(path, AT + 4, file + AT + 4, 0x10);
    assert(told_id == -1 && same());
    file[AT + 4] ^= 1;   /* (another version of the file: nothing applied, nothing told) */
    kirby_shadow_read(path, 0, file, sizeof file);
    assert(told_id == -1 && at(0) == 1400);
    puts("ok");
    return 0;
}
'''


def check_source():
    # (kirby_res.c's read hook calls it for every read)
    res = block((ROOT / "host/kirby_res.c").read_text(encoding="utf-8"), "void kirby_read_done(")
    assert "kirby_shadow_read(guest, off, buf, n);" in res, "kirby_read_done no longer calls kirby_shadow_read"
    shadow = (ROOT / "host/kirby_shadow.c").read_text(encoding="utf-8")
    assert "rx_option(HOS_OPT_SHADOW_RES, 0)" in shadow
    sizes = [int(x) for x in re.search(r"level == 1 \? (\d+) : level == 2 \? (\d+) : 0;", shadow).groups()]
    assert sizes == [2800, 4096], sizes

    # (the menu: the row is not one of the other game's, and takes this game's texts when the host says so)
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    assert "opts.shadow_res" not in block(menu, "bool is_oot_row(const Row& r) {"), \
        "is_oot_row: Shadow resolution must show for this game"
    oot_game = block(menu, "if (id == HOS_OPT_OOT_GAME) {")
    kirby_row = between(oot_game, "else if (r.value == &opts.shadow_res)", ";")
    assert "r.help = kShadowHelpKirby, r.hint = hn_shadow_res_kirby" in kirby_row, \
        "menu_option_set: the Shadow resolution row does not take this game's help and hints"
    help_kirby = between(menu, "const char* const kShadowHelpKirby =", "MODULE_HINTS(hn_shadow_res_kirby, 0,")
    # (the row takes a restart in this game only, compared by the size drawn, its start value the one the read applied)
    assert "r.restart = true" in kirby_row, \
        "menu_option_set: the Shadow resolution row does not take a restart in this game"
    # (the row is upstream's Detail module's since #1633: gpu/vk/menu/detail.cpp)
    detail = (ROOT / "gpu/vk/menu/detail.cpp").read_text(encoding="utf-8")
    row = between(detail, '.key = "shadow_resolution",', "})")
    assert row.rstrip().endswith(".hint = hn_shadow_res"), "the module's Shadow resolution must stay live (the other game's)"
    assert "if (int v; inhale_restart_value(r, &v)) return v;" in block(menu, "int row_restart_value("), \
        "row_restart_value: no longer asks inhale_restart_value"
    value = block(menu, "bool inhale_restart_value(")
    assert "if (r.value != &opts.shadow_res || !r.restart) return false;" in value and \
        "*v = menu_shadow_res();" in value, "inhale_restart_value: Shadow resolution's restart is the size drawn"
    told = block(menu, "if (id == HOS_OPT_SHADOW_RES) {")
    assert "std::lock_guard lk(menu_mu);" in told and "restart_state.restart_value(" in told, told
    assert "Applies after a restart." in help_kirby and "sun" not in help_kirby, help_kirby
    hints = between(menu, "MODULE_HINTS(hn_shadow_res_kirby, 0,", "const char* const kLaptopHelpPlain =")
    for size in [1400] + sizes:
        mb = round(size * size * 6 / 1e6)   # (D16 depth + two R16 blur targets, as the pass trace shows them)
        assert "%d pixels a side" % size in hints and "About %d MB" % mb in hints, (size, mb, hints)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.c"
        test.write_text(FIXTURE, encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-x", "c", "-std=c11", "-Wall", "-Werror", str(ROOT / "host/kirby_shadow.c"), str(test),
                        "-o", str(exe)], check=True)
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        sys.stdout.write(out.stdout)
        assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), out.stderr
    print("test_kirby_shadow: ok")


if __name__ == "__main__":
    main()
