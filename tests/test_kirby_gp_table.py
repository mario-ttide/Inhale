"""This game's global loads search the storage buffers, not the guest page table (issues #18 and #19), game-free.

The renderer's default since the v3.1.1 sync (gpu/vk/vk_coopmat.cpp table_loads_wanted, RX_VK_GP_TABLE=1) has the
vertex, fragment and compute stages read global memory through the guest page table alone. The table covers three
windows laid out for upstream's game (gpu/vk/page_table_census.h kPageWindows: 64-72 GB, 496-512 GB, 1 TB); this game's
pools lie elsewhere (near 2 GB and 482-492 GB), so every such load read 0 and the opaque scene drew black, on every GPU
with host memory import and device addresses. host/hos_main.c sets RX_VK_GP_TABLE=0 when the player has not set it.

The check cuts the defaults host/hos_main.c sets after hos_options_choose and table_loads_wanted, runs them, and checks
the switch the renderer then takes: 0 with nothing set, the player's own value kept (1 and 2 still turn the table on).

    python -I -B tests/test_kirby_gp_table.py [--cxx c++]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    main_c = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    defaults = between(main_c, "    hos_options_choose(argc, argv);\n", "        const char *protect_hearts")
    defaults = defaults[len("    hos_options_choose(argc, argv);\n"):].rstrip()
    if not defaults.endswith("{"):
        raise SystemExit("host/hos_main.c: the defaults after hos_options_choose no longer end where the HOS_OOT_PROTECT_HEARTS "
                         "block opens")
    defaults = defaults[:-1]
    coopmat = (ROOT / "gpu/vk/vk_coopmat.cpp").read_text(encoding="utf-8")
    wanted = block(coopmat, "int table_loads_wanted(")
    return r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
''' + wanted + r'''
static void defaults() {
''' + defaults + r'''
}
static int taken(const char* preset) {
    unsetenv("RX_VK_GP_TABLE");
    if (preset) setenv("RX_VK_GP_TABLE", preset, 1);
    defaults();
    return table_loads_wanted(std::getenv("RX_VK_GP_TABLE"), true, true);   // (a GPU with host import and device addresses)
}
int main() {
    int bad = 0;
    struct { const char* preset; int want; } rows[] = {{nullptr, 0}, {"0", 0}, {"1", 1}, {"2", 2}};
    for (const auto& r : rows) {
        const int got = taken(r.preset);
        if (got != r.want) {
            std::fprintf(stderr, "FAIL: RX_VK_GP_TABLE %s: the renderer takes %d, wanted %d%s\n", r.preset ? r.preset : "unset", got,
                         r.want, r.preset ? "" : " (this game's pools are outside the page table's windows: its loads read 0)");
            bad = 1;
        }
    }
    if (!bad) std::puts("ok: RX_VK_GP_TABLE unset is 0 for this game; 0, 1 and 2 set by the player kept");
    return bad;
}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cxx", default="c++")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as d:
        src, exe = Path(d) / "t.cpp", Path(d) / "t"
        src.write_text(fixture(), encoding="utf-8")
        r = subprocess.run([a.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-o", str(exe), str(src)], capture_output=True,
                           text=True)
        if r.returncode:
            print(r.stderr)
            return 1
        return subprocess.run([str(exe)]).returncode


if __name__ == "__main__":
    sys.exit(main())
