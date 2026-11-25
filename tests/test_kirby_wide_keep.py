"""On a picture wider than 16:9 this game's pause background and its cutscene bars keep the picture's width, and its
full-screen movies their 16:9 shape, while its HUD and menus are narrowed (gpu/vk/kirby_wide.h, gpu/vk/vk_draw.cpp draw;
docs/design.md, "issue #20, ultrawide").

nx2/kirby_wide.py narrows every layout camera still at 16:9 on a picture wider than 16:9. The pause menu's background, a
blurred capture of the whole picture drawn by such a camera, then covered only the middle 16:9, and so did the black
bars of a cutscene; a full-screen movie, drawn with no layout camera, stayed stretched over the whole width. The block
of draw() that sets the dynamic state is cut out of vk_draw.cpp and compiled with the header and stand-ins, and run
once a picture (the block reads the ratio once): 32:9, 21:9, 16:9, 16:10 and 4:3. Checked at 32:9 and 21:9:

- the pause background (a 2398 x 1478 pane over the whole layout, sampling a capture of the picture's shape the GPU
  drew, into the 16:9 window texture): its viewport wider by the ratio over 16:9 about its centre, and the game's
  viewport back after the draw;
- a cutscene bar (a 1920 x 64 pane, by either of its two programs): widened the same way;
- a full-screen movie (the movie program into the window texture, sampling a 1920 x 1080 frame): its viewport narrower
  by 16:9 over the ratio about its centre, whatever pane the last layout left in the constants, and the two strips
  beside it cleared to black (Copy drew the scene target there, grey while a movie plays);
- left as the game set it: a frosted pane of the HUD (228 x 80) sampling the same capture, a HUD strip, a pane as wide
  as the layout and 975 high, a bar not centred, a bar's constants under Copy or in a target not 16:9, a hint video
  (the movie program into a 480 x 270 target of the frame's own size), Copy, the other game, a capture not drawn by
  the GPU, a texture of another shape, a target not 16:9, and a pane not centred;
- a viewport of 0 x 0 (the whole target) is widened from the target's size;
- the pane is read from guest memory only after the cheaper checks pass.

At 16:9, 16:10 and 4:3 the background, the bar and the movie are all left.

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
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
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
// (Vulkan's clear of a part of the pass's targets: what the block clears is kept)
struct VkOffset2D { int32_t x, y; };
struct VkExtent2D { uint32_t width, height; };
struct VkRect2D { VkOffset2D offset; VkExtent2D extent; };
struct VkClearRect { VkRect2D rect; uint32_t baseArrayLayer, layerCount; };
union VkClearColorValue { float float32[4]; };
union VkClearValue { VkClearColorValue color; };
struct VkClearAttachment { uint32_t aspectMask, colorAttachment; VkClearValue clearValue; };
enum { VK_IMAGE_ASPECT_COLOR_BIT = 1 };
struct Cleared { int32_t x, y; uint32_t w, h; bool black; };
static std::vector<Cleared> cleared;
static void vkCmdClearAttachments(int, uint32_t n, const VkClearAttachment* a, uint32_t rects, const VkClearRect* r) {
    for (uint32_t i = 0; i < rects; i++) {
        const float* c = a->clearValue.color.float32;
        cleared.push_back({r[i].rect.offset.x, r[i].rect.offset.y, r[i].rect.extent.width, r[i].rect.extent.height,
                           n == 1 && a->aspectMask == VK_IMAGE_ASPECT_COLOR_BIT && a->colorAttachment == 0 && c[0] == 0 &&
                               c[1] == 0 && c[2] == 0 && c[3] == 1 && r[i].baseArrayLayer == 0 && r[i].layerCount == 1});
    }
}
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
int main(int argc, char** argv) {
    picture = argc > 1 ? (float)std::atof(argv[1]) : 0.0f;   // (host->aspect_ratio: 0 at 16:9)
    const float game = 16.0f / 9.0f;
    const bool wide = picture > game * 1.01f;
    const float k = wide ? picture / game : 1.0f;   // (what a widened draw is widened by)
    const uint32_t cw = (uint32_t)(90.0f * (picture > 0.0f ? picture : game) + 0.5f);   // (the capture: 320 x 90 at 32:9)
    Texture window{2560, 1440, true}, capture{cw, 90, true}, file{cw, 90, false}, text{792, 104, true};
    Targets at;
    at.color[0] = &window, at.n = 1, at.width = 2560, at.height = 1440;
    NvnState s;
    s.viewport[0][0] = 0, s.viewport[0][1] = 0, s.viewport[0][2] = 2560, s.viewport[0][3] = 1440;
    s.ubo[0][0].addr = 0x1000, s.ubo[0][0].size = 560;
    Program p{0xc7974d16c805e580ull, false};
    const float bg[4] = {2398, 1478, -1199, 739}, frost[4] = {228, 80, -114, 40}, off[4] = {2398, 1478, -1000, 739};
    const auto run = [&](const float* pane) {
        std::memcpy(pane_mem, pane, 16);
        draw_block(s, at, p);
    };
    const auto left = [&] { return seen[0] == 0 && seen[2] == 2560; };
    const auto widened = [&] { return near(seen[0], 1280 - 1280 * k) && near(seen[2], 2560 * k); };
    sampled = {&text, &capture};
    run(bg);
    check(widened(), "the pause background's viewport wider by the ratio over 16:9 about its centre (left as it is at 16:9 or narrower)");
    check(s.viewport[0][0] == 0 && s.viewport[0][2] == 2560, "the game's viewport is back after the draw");
    run(frost);
    check(left(), "a frosted HUD pane on the same capture: left");
    run(off);
    check(left(), "a pane not centred: left");
    p.key = mkwvk::kirby_wide::kCopy;
    run(bg);
    check(left(), "Copy: left");
    p.key = 0xc7974d16c805e580ull;
    oot = 1;
    pane_reads = 0;
    run(bg);
    check(left() && pane_reads == 0, "the other game: left, its constants not read");
    oot = 0;
    sampled = {&file};
    run(bg);
    check(left(), "a texture of the picture's shape the GPU did not draw: left");
    sampled = {&text};
    run(bg);
    check(left(), "only a texture of another shape: left");
    sampled = {&capture};
    Texture square{2048, 2048, true};
    at.color[0] = &square;
    pane_reads = 0;
    run(bg);
    check(left() && pane_reads == 0, "a target not 16:9: left, the pane not read");
    at.color[0] = &window;
    s.viewport[0][2] = 0, s.viewport[0][3] = 0;
    run(bg);
    if (wide) check(widened() && near(seen[3], 1440), "a viewport of 0 x 0: widened from the target's size");
    check(s.viewport[0][2] == 0 && s.viewport[0][3] == 0, "and given back as 0 x 0");
    s.viewport[0][2] = 2560, s.viewport[0][3] = 1440;

    check(cleared.empty(), "a widened draw clears nothing");

    // A cutscene's bars: a 1920 x 64 pane drawn twice, by a program with a 1920 x 64 picture and by the plain pane
    // program with an 8 x 8 fill (textures the game uploaded: not in the list)
    const float bar[4] = {1920, 64, -960, 32}, strip[4] = {344, 48, -172, 24}, glow[4] = {1950, 975, -975, 0};
    const float bar_off[4] = {1920, 64, -900, 32};
    sampled = {};
    for (const uint64_t key : {0x4acf6657314c31dfull, 0x5cfce03bc8b25357ull}) {
        p.key = key;
        run(bar);
        check(widened(), "a cutscene bar: its viewport wider by the ratio over 16:9 about its centre (left at 16:9 or narrower)");
        check(s.viewport[0][0] == 0 && s.viewport[0][2] == 2560, "the game's viewport is back after the bar");
    }
    run(strip);
    check(left(), "a HUD strip: left");
    run(glow);
    check(left(), "a pane as wide as the layout and 975 high: left");
    run(bar_off);
    check(left(), "a bar not centred: left");
    p.key = mkwvk::kirby_wide::kCopy;
    run(bar);
    check(left(), "Copy with a bar's constants still bound: left");
    p.key = 0x5cfce03bc8b25357ull;
    Texture small{cw, 90, true};
    at.color[0] = &small;
    run(bar);
    check(left(), "a bar's constants in a target not 16:9: left");

    // A full-screen movie: the movie program draws the decoded frame (1920 x 1080 and its 960 x 540 colour plane)
    // into the 3840 x 2160 window texture; a hint video's goes into a 480 x 270 target of the frame's own size
    Texture window4k{3840, 2160, true}, y{1920, 1080, true}, uv{960, 540, true};
    Texture hint{480, 270, true}, hint_y{480, 270, true}, hint_uv{240, 135, true};
    p.key = 0x6f37d965729ec917ull;
    at.color[0] = &window4k;
    sampled = {&y, &uv};
    run(bar);   // (the constants of the last layout drawn: a bar's must not widen it)
    check(near(seen[0], 1280 - 1280 / k) && near(seen[2], 2560 / k) && seen[1] == 0 && seen[3] == 1440,
          "a full-screen movie: its viewport narrower by 16:9 over the ratio about its centre (left at 16:9 or narrower)");
    check(s.viewport[0][0] == 0 && s.viewport[0][2] == 2560, "the game's viewport is back after the movie");
    // (beside it Copy has drawn the scene target, grey while a movie plays: the two strips of the game's viewport the
    // narrowed one leaves are cleared to black; the block runs before the draw, which then covers its own columns)
    const int32_t in0 = (int32_t)std::ceil(1280 - 1280 / k), in1 = (int32_t)std::floor(1280 + 1280 / k);
    if (wide)
        check(cleared.size() == 2 && cleared[0].black && cleared[1].black && cleared[0].x == 0 && (int32_t)cleared[0].w == in0 &&
              cleared[1].x == in1 && cleared[1].x + (int32_t)cleared[1].w == 2560 && cleared[0].y == 0 && cleared[0].h == 1440 &&
              cleared[1].y == 0 && cleared[1].h == 1440, "the movie's sides: the two strips beside it cleared to black");
    else
        check(cleared.empty(), "a movie left as it is: nothing cleared");
    cleared.clear();
    s.viewport[0][2] = 0, s.viewport[0][3] = 0;
    at.width = 3840, at.height = 2160;   // (a viewport of 0 x 0 is the whole target)
    run(bar);
    if (wide)
        check(cleared.size() == 2 && cleared[0].x == 0 && (int32_t)cleared[0].w == (int32_t)std::ceil(1920 - 1920 / k) &&
              cleared[1].x + (int32_t)cleared[1].w == 3840 && cleared[1].h == 2160, "the movie's sides with a viewport of 0 x 0: of the whole target");
    cleared.clear();
    s.viewport[0][2] = 2560, s.viewport[0][3] = 1440, at.width = 2560, at.height = 1440;
    oot = 1;
    run(bar);
    check(left(), "the other game with the movie's program key: left");
    oot = 0;
    at.color[0] = &hint;
    sampled = {&hint_y, &hint_uv};
    s.viewport[0][2] = 480, s.viewport[0][3] = 270;
    run(bar);   // (a bar's constants still bound here too)
    check(seen[0] == 0 && seen[2] == 480, "a hint video (the frame into a target of its own size): left");
    check(cleared.empty(), "no draw but the narrowed movie clears anything");
    s.viewport[0][2] = 2560, s.viewport[0][3] = 1440;

    // (the factor on the header, as before)
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
    failed = []
    with tempfile.TemporaryDirectory(prefix="kirby-wide-keep-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.cpp").write_text(FIXTURE.replace("@BLOCK@", cut), encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-I", str(ROOT / "gpu/vk"),
                        str(folder / "fixture.cpp"), "-o", str(exe)], check=True, timeout=120)
        # (one run a picture: the block reads the ratio once, as draw() does; 16:9 is 0 from the host)
        for name, ratio in (("32:9", 5120 / 1440), ("21:9", 3440 / 1440), ("16:9", 0.0), ("16:10", 1.6), ("4:3", 4 / 3)):
            result = subprocess.run([str(exe), repr(ratio)], capture_output=True, text=True, timeout=30)
            print("".join(name + ": " + line + "\n" for line in result.stdout.splitlines()), end="")
            if result.returncode or "ok" not in result.stdout:
                failed.append(name)
    if failed:
        raise SystemExit("a wide picture's pause background, cutscene bar or movie is not as it should be, or another "
                         "draw is changed: " + ", ".join(failed))
    print("PASS: the pause background and the cutscene bars at the picture's width, the movie at 16:9, at 32:9 and 21:9; "
          "HUD panes, hint videos, Copy, the other game, 16:9, 16:10 and 4:3 left")


if __name__ == "__main__":
    main()
