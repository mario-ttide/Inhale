"""This game's pause background keeps the picture's width while its HUD and menus are narrowed (gpu/vk/kirby_wide.h,
gpu/vk/vk_draw.cpp draw; docs/design.md, "issue #20, ultrawide").

nx2/kirby_wide.py narrows every layout camera still at 16:9 on a picture wider than 16:9, and the pause menu's
background, a blurred capture of the whole picture drawn by such a camera, then covered only the middle 16:9. The block
of draw() that sets the dynamic state is cut out of vk_draw.cpp and compiled with the header and stand-ins, and checked:

- the pause background (a 2398 x 1478 pane over the whole layout, sampling a 320 x 90 capture the GPU drew, into the
  16:9 window texture) at 32:9: its viewport twice as wide about its centre, and the game's viewport back after the draw;
  at 21:9 (a 215 x 90 capture) by 2.3889 / 1.7778;
- left as the game set it: a frosted pane of the HUD (228 x 80) sampling the same capture, Copy, the other game, a 16:9
  picture, a capture not drawn by the GPU, a texture of another shape, a target not 16:9, and a pane not centred;
- a viewport of 0 x 0 (the whole target) is widened from the target's size;
- the pane is read from guest memory only after the cheaper checks pass.

python -I -B tests/test_kirby_wide_keep.py [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import between   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include "kirby_wide.h"
namespace mkwvk {
static int oot = 0;   // (vk_menu.cpp's oot_game: 0 this game, 1 the other)
bool menu_oot_rows() { return oot != 0; }
struct Texture { uint32_t width = 0, height = 0; bool gpu_written = false; };
struct Targets { Texture* color[8]{}; int n = 0; uint32_t width = 0, height = 0; };
struct nvn_p_bind_buf { uint64_t addr = 0; uint32_t size = 0; };
struct NvnState { float viewport[16][4]{}; nvn_p_bind_buf ubo[6][16]{}; };
struct Program { uint64_t key = 0; bool fallback = false; };
struct Host { float (*aspect_ratio)(void); };
static float picture = 0.0f;
static float picture_ratio() { return picture; }
static Host host_v{picture_ratio};
static Host* host = &host_v;
static float pane_mem[4];
static int pane_reads;
static bool memory_read_as_submitted(uint64_t addr, void* out, uint64_t n) {
    if (addr != 0x1000 + mkwvk::kirby_wide::kPaneAt || n != 16) return false;
    pane_reads++;
    std::memcpy(out, pane_mem, 16);
    return true;
}
static std::vector<const Texture*> sampled;
static std::vector<const Texture*>& gfx_sampled() { return sampled; }
static float seen[4];   // (the viewport dynamic_state saw)
static void dynamic_state(int, const NvnState& s, const Targets&, int, bool, const Program&) { std::memcpy(seen, s.viewport[0], 16); }
#define FINE_SCOPE(x)
// (the block runs once a draw: the static ratio is read at the first, as in draw())
static void draw_block(NvnState& s, const Targets& at, const Program& p) {
    const int cmd = 0, topo = 0;
    struct { bool mesh = false; } d;
    (void)cmd, (void)topo;
@BLOCK@
}
}  // namespace mkwvk
using namespace mkwvk;
static int bad;
static void check(bool ok, const char* what) { if (!ok) { std::printf("FAIL: %s\n", what); bad = 1; } }
static bool near(float a, float b) { return a - b < 0.01f && b - a < 0.01f; }
int main() {
    picture = 5120.0f / 1440.0f;
    Texture window{2560, 1440, true}, capture{320, 90, true}, file{320, 90, false}, text{792, 104, true};
    Targets at;
    at.color[0] = &window, at.n = 1, at.width = 2560, at.height = 1440;
    NvnState s;
    s.viewport[0][0] = 0, s.viewport[0][1] = 0, s.viewport[0][2] = 2560, s.viewport[0][3] = 1440;
    s.ubo[0][0].addr = 0x1000, s.ubo[0][0].size = 560;
    Program p{0xc7974d16c805e580ull, false};
    const float bg[4] = {2398, 1478, -1199, 739}, bar[4] = {228, 80, -114, 40}, off[4] = {2398, 1478, -1000, 739};
    const auto run = [&](const float* pane) {
        std::memcpy(pane_mem, pane, 16);
        draw_block(s, at, p);
    };
    sampled = {&text, &capture};
    run(bg);
    check(near(seen[0], -1280) && near(seen[2], 5120), "32:9: the pause background's viewport twice as wide about its centre");
    check(s.viewport[0][0] == 0 && s.viewport[0][2] == 2560, "the game's viewport is back after the draw");
    run(bar);
    check(seen[0] == 0 && seen[2] == 2560, "a frosted HUD pane on the same capture: left");
    run(off);
    check(seen[0] == 0 && seen[2] == 2560, "a pane not centred: left");
    p.key = mkwvk::kirby_wide::kCopy;
    run(bg);
    check(seen[0] == 0 && seen[2] == 2560, "Copy: left");
    p.key = 0xc7974d16c805e580ull;
    oot = 1;
    pane_reads = 0;
    run(bg);
    check(seen[0] == 0 && seen[2] == 2560 && pane_reads == 0, "the other game: left, its constants not read");
    oot = 0;
    sampled = {&file};
    pane_reads = 0;
    run(bg);
    check(seen[0] == 0 && pane_reads == 0, "a texture of the picture's shape the GPU did not draw: left, the pane not read");
    sampled = {&text};
    run(bg);
    check(seen[0] == 0, "only a texture of another shape: left");
    sampled = {&capture};
    Texture square{2048, 2048, true};
    at.color[0] = &square;
    run(bg);
    check(seen[0] == 0, "a target not 16:9: left");
    at.color[0] = &window;
    s.viewport[0][2] = 0, s.viewport[0][3] = 0;
    run(bg);
    check(near(seen[0], -1280) && near(seen[2], 5120) && near(seen[3], 1440), "a viewport of 0 x 0: widened from the target's size");
    check(s.viewport[0][2] == 0 && s.viewport[0][3] == 0, "and given back as 0 x 0");
    s.viewport[0][2] = 2560, s.viewport[0][3] = 1440;
    // (a picture of another ratio: the block reads it once, as draw() does, so the factor is checked on the header)
    const mkwvk::kirby_wide::Sampled c21{215, 90, true};
    const float k21 = mkwvk::kirby_wide::keep_whole(true, 3440.0f / 1440.0f, 2560, 1440, 1, &c21, 1, bg);
    check(near(k21, (3440.0f / 1440.0f) / (16.0f / 9.0f)), "21:9: widened by the ratio over 16:9");
    check(mkwvk::kirby_wide::keep_whole(true, 16.0f / 9.0f, 2560, 1440, 1, &c21, 1, bg) == 1.0f, "a 16:9 picture: left");
    float x = 100, w = 200;
    mkwvk::kirby_wide::widen(x, w, 2.0f);
    check(near(x, 0) && near(w, 400), "widen: about the centre");
    if (!bad) std::puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    cut = between(draw, "// (inhale) this game's pause background, a capture of the whole picture",
                  "    if (trace_tex_hit && texture_frame_no() % 30 == 0) {")
    cut = cut[:cut.rindex("}")]   # (up to the scope's own closing brace, left out: the fixture's function closes)
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="kirby-wide-keep-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.cpp").write_text(FIXTURE.replace("@BLOCK@", cut), encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-I", str(ROOT / "gpu/vk"),
                        str(folder / "fixture.cpp"), "-o", str(exe)], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("this game's pause background does not keep the picture's width, or another draw is widened")
    print("PASS: the pause background at the picture's width at 32:9 and 21:9; HUD panes, Copy, the other game and 16:9 left")


if __name__ == "__main__":
    main()
