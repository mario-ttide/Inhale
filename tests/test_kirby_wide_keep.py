"""On a picture wider than 16:9 this game's pause background and its cutscene bars keep the picture's width, its
full-screen movies their 16:9 shape, and a wipe's cover, the loading screen and the stage panel's picture reach the
picture's edges, while its HUD and menus are narrowed (gpu/vk/kirby_wide.h, gpu/vk/vk_draw.cpp draw; docs/design.md,
"issue #20, ultrawide"). On a picture narrower than 16:9 the same along y (docs/design.md, "16:10 and 4:3: the HUD and
menus at their own shape", issue #25).

nx2/kirby_wide.py narrows every layout camera still at 16:9 on a picture wider than 16:9. The pause menu's background, a
blurred capture of the whole picture drawn by such a camera, then covered only the middle 16:9, and so did the black
bars of a cutscene; a full-screen movie, drawn with no layout camera, stayed stretched over the whole width. The block
of draw() that sets the dynamic state is cut out of vk_draw.cpp and compiled with the header and stand-ins, and run
once a picture (the block reads the ratio once): 32:9, 21:9, 16:9, 16:10 and 4:3. Checked at 32:9 and 21:9 (at 16:10
and 4:3: below):

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

The wipes, the loading screen and the stage panel (draws measured on a walk into a stage and out of it), into the
3840 x 2160 window texture of which 2560 x 1440 is shown, by a layout's program (its vertex stage reads its constants
up to the pane) under a narrowed camera:

- a pane over the whole layout (the loading screen's fill, a wipe's cover with the star's hole, a cover that shows a
  layer, the stage panel's picture, a 480 x 270 pane scaled by 4): the block calls draw() twice before the draw itself,
  once a side strip. Each strip's scissor is the strip to the pixel, its viewport is within the device's limit and
  puts the pane's outer edge on the picture's edge, and the strip shows a tenth of the layout at most; the draw itself
  has the game's viewport and scissor, and both are given back. A nested draw applies nothing: no deeper level;
- a pane in one corner of the screen (the loading screen's two blots): no strip, its viewport moved aside so that the
  pane's outer edge is on the picture's edge, its width the game's (a strip would smear the blot along the side);
- none for a mesh, indirect or occlusion-query draw or with a copy of the target open; with a viewport limit of 4096
  the whole pane is widened instead (a corner's pane is moved all the same);
- a wipe's layer, a 2560 x 1440 target that is not the last present's: each of its draws widened by the ratio over
  16:9 about its centre, the fill too; a pane in one corner is put off the target (not drawn). Left: a camera of the target's own, a blur with the last layout's constants
  still bound, the window texture, any target before the first present;
- left: a pane larger than the layout, a star outline, a HUD pane, a button that slides over the right edge, the pause
  menu's glow on the edge, a turned pane in a corner, a whole pane moved aside, a program that reads no layout
  constants, a camera not narrowed, the other game;
- the stage's name on the loading screen (a 1920 x 120 pane of text the GPU drew, a bar's shape): left.

At 16:10 and 4:3 nx2/kirby_wide.py lowers every layout camera still at 16:9 (its second row by the ratio over 16:9), so
the layouts keep their shape at the picture's whole width and end short of its top and bottom. The same draws, along y:

- the pause background and a cutscene bar: the viewport higher by 16:9 over the ratio about its centre (the bar is
  back at the picture's top or bottom edge);
- a full-screen movie: its viewport lower by the ratio over 16:9 about its centre, the strips above and below it
  cleared to black;
- a pane over the whole layout: a strip above and one below, each a draw of the block's own with the strip's rows as
  its scissor and a viewport as high as the device allows (the limit along y), the pane's outer edge on the picture's;
  with a height limit under twice the viewport (2048 for its 1440 rows) the pane is heightened instead;
- a pane in one corner: moved up or down by half of what the lowering leaves (the layout's +y is the higher row: the
  viewport is not turned over under this game's lower-left window origin), its height the game's; off the target in a
  layer;
- a wipe's layer: each of its draws heightened;
- left: the same list, and a pane that slides in over the top edge, a whole pane moved up.

At 16:9 all of these are left.

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
#include "kirby_upscale.h"   // (the last present's texture size: what tells the window texture from a layer's target)
#include "kirby_wide.h"
namespace mkwvk {
static int oot = 0;   // (vk_menu.cpp's oot_game: 0 this game, 1 the other)
bool menu_oot_rows() { return oot != 0; }
struct Texture { uint32_t width = 0, height = 0; bool gpu_written = false; };
struct Targets { Texture* color[8]{}; int n = 0; uint32_t width = 0, height = 0; };
struct nvn_p_bind_buf { uint64_t addr = 0; uint32_t size = 0; };
struct NvnState { float viewport[16][4]{}; nvn_p_bind_buf ubo[6][16]{}; int32_t scissor[4]{}; };
// (a program's stages: what its vertex stage (0) reads of its constant buffers, c3 the layouts')
struct Stage { int nvn_stage = 0; struct { uint32_t constant_buffer_used_sizes[8]{}; } info; };
struct Program { uint64_t key = 0; bool fallback = false; std::vector<Stage> stages; };
struct DrawArgs { bool mesh = false; uint64_t indirect = 0; void* occ_pool = nullptr; };
static struct { struct { struct { uint32_t maxViewportDimensions[2] = {16384, 16384}; } limits; } props; } dev;
struct Host { float (*aspect_ratio)(void); };
static float picture = 0.0f;
static float picture_ratio() { return picture; }
static Host host_v{picture_ratio};
static Host* host = &host_v;
// (a layout's vertex constants: the camera's m00 at +0 and m11 at +20, the pane's matrix at +64 (three rows of four),
// the pane at +528)
static float c3_mem[140];
static float* const pane_mem = c3_mem + mkwvk::kirby_wide::kPaneAt / 4;
static int pane_reads;   // (every read of the constants)
static bool memory_read_as_submitted(uint64_t addr, void* out, uint64_t n) {
    if (addr < 0x1000 || addr + n > 0x1000 + sizeof c3_mem) return false;
    pane_reads++;
    std::memcpy(out, (const char*)c3_mem + (addr - 0x1000), n);
    return true;
}
static std::vector<const Texture*> sampled;
static std::vector<const Texture*>& gfx_sampled() { return sampled; }
static float seen[4];   // (the viewport dynamic_state saw for the draw itself)
static int32_t seen_sc[4];
// (a draw of draw()'s own, for a side strip: its viewport, its scissor and how deep it is nested; before == true when
// the draw itself had not set its state yet)
struct Nested { float vp[4]; int32_t sc[4]; int depth; bool before; };
static std::vector<Nested> nested;
static int depth;
static bool main_set;
static void dynamic_state(int, const NvnState& s, const Targets&, int, bool, const Program&) {
    if (depth) {
        Nested n{};
        std::memcpy(n.vp, s.viewport[0], 16), std::memcpy(n.sc, s.scissor, 16), n.depth = depth, n.before = !main_set;
        nested.push_back(n);
        return;
    }
    std::memcpy(seen, s.viewport[0], 16), std::memcpy(seen_sc, s.scissor, 16), main_set = true;
}
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
static bool feedback_open;   // (the draw goes into a copy of its target: vk_feedback.h)
static const Targets* draw_at;
static const Program* draw_p;
static void draw(int cmd, NvnState& s, const DrawArgs& d);
// (the block runs once a draw: the static ratio is read at the first, as in draw())
static void draw_block(int cmd, NvnState& s, const DrawArgs& d, const Targets& at, const Program& p) {
    const int topo = 0;
    const Targets copy = at;
    const Targets* at_pass = feedback_open ? &copy : &at;
    (void)cmd, (void)topo, (void)at_pass, (void)dev, (void)d;
@BLOCK@
}
// (draw() called from its own block: the block again, one level down; a block that nests without end stops here)
static void draw(int cmd, NvnState& s, const DrawArgs& d) {
    if (depth >= 4) return;
    depth++;
    draw_block(cmd, s, d, *draw_at, *draw_p);
    depth--;
}
}  // namespace mkwvk
using namespace mkwvk;
static int bad;
static void check(bool ok, const char* what) { if (!ok) { std::printf("FAIL: %s\n", what); bad = 1; } }
static bool near(float a, float b) { return a - b < 0.01f && b - a < 0.01f; }
int main(int argc, char** argv) {
    picture = argc > 1 ? (float)std::atof(argv[1]) : 0.0f;   // (host->aspect_ratio: 0 at 16:9)
    const float game = 16.0f / 9.0f;
    const bool wide = picture > game * 1.01f, tall = picture > 0.0f && picture < game * 0.99f;   // (tall: narrower than 16:9)
    const int a = tall ? 1 : 0;   // (the axis the rules work along: x on a wide picture, y on a narrower one)
    const float size[2] = {2560, 1440}, half = size[a] * 0.5f;   // (the game's viewport in these cases)
    const float k = wide ? picture / game : tall ? game / picture : 1.0f;   // (what a widened draw is widened by, along a)
    const uint32_t cw = (uint32_t)(90.0f * (picture > 0.0f ? picture : game) + 0.5f);   // (the capture: 320 x 90 at 32:9)
    Texture window{2560, 1440, true}, capture{cw, 90, true}, file{cw, 90, false}, text{792, 104, true};
    Targets at;
    at.color[0] = &window, at.n = 1, at.width = 2560, at.height = 1440;
    NvnState s;
    s.viewport[0][0] = 0, s.viewport[0][1] = 0, s.viewport[0][2] = 2560, s.viewport[0][3] = 1440;
    s.ubo[0][0].addr = 0x1000, s.ubo[0][0].size = 560;
    // (a layout's program: its vertex stage reads its constants up to the pane, 560 bytes. Every layout camera is
    // narrowed by 16:9 over the picture's ratio on a wide picture, and its second row by the ratio over 16:9 on a
    // narrower one: m11 / m00 is then the picture's ratio)
    Stage layout_vs;
    layout_vs.info.constant_buffer_used_sizes[3] = 560;
    Program p{0xc7974d16c805e580ull, false, {layout_vs}};
    c3_mem[0] = 2.0f / 1920.0f * (wide ? game / picture : 1.0f), c3_mem[5] = 2.0f / 1080.0f * (tall ? picture / game : 1.0f);
    float* const matrix = c3_mem + 16;   // (scale x, shear, -, shift x; shear, scale y, -, shift y)
    const auto place = [&](float sx, float tx, float sy, float ty) { matrix[0] = sx, matrix[3] = tx, matrix[5] = sy, matrix[7] = ty; };
    place(1, 0, 1, 0);
    mkwvk::kirby_upscale::note_present(2560, 1440, nullptr);   // (the window texture of these cases)
    DrawArgs d;
    const float bg[4] = {2398, 1478, -1199, 739}, frost[4] = {228, 80, -114, 40}, off[4] = {2398, 1478, -1000, 739};
    const auto run = [&](const float* pane) {
        std::memcpy(pane_mem, pane, 16);
        nested.clear(), main_set = false, draw_at = &at, draw_p = &p;
        draw_block(0, s, d, at, p);
    };
    const auto left = [&] { return seen[0] == 0 && seen[1] == 0 && seen[2] == 2560 && seen[3] == 1440 && nested.empty(); };
    // (the other axis as the game set it)
    const auto across = [&] { return seen[1 - a] == 0 && seen[3 - a] == size[1 - a]; };
    const auto widened = [&] { return near(seen[a], half - half * k) && near(seen[2 + a], size[a] * k) && across() && nested.empty(); };
    const auto back = [&] { return s.viewport[0][0] == 0 && s.viewport[0][1] == 0 && s.viewport[0][2] == 2560 && s.viewport[0][3] == 1440; };
    sampled = {&text, &capture};
    run(bg);
    check(widened(), "the pause background's viewport wider by the ratio over 16:9 about its centre (higher by 16:9 over the ratio on a narrower picture; left at 16:9)");
    check(back(), "the game's viewport is back after the draw");
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
    if (wide || tall) check(widened(), "a viewport of 0 x 0: widened from the target's size");
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
        check(widened(), "a cutscene bar: its viewport wider by the ratio over 16:9 about its centre (higher by 16:9 over the ratio on a narrower picture: the bar back at the picture's edge; left at 16:9)");
        check(back(), "the game's viewport is back after the bar");
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
    p.stages.clear();
    at.color[0] = &window4k;
    sampled = {&y, &uv};
    run(bar);   // (the constants of the last layout drawn: a bar's must not widen it)
    check(near(seen[a], half - half / k) && near(seen[2 + a], size[a] / k) && across(),
          "a full-screen movie: its viewport narrower by 16:9 over the ratio about its centre (lower by the ratio over 16:9 on a narrower picture; left at 16:9)");
    check(back(), "the game's viewport is back after the movie");
    // (beside it Copy has drawn the scene target, grey while a movie plays: the two strips of the game's viewport the
    // narrowed one leaves are cleared to black, beside it on a wide picture, above and below it on a narrower one; the
    // block runs before the draw, which then covers its own columns or rows. A cleared rectangle along the axis and
    // across it: from, length)
    const auto along = [&](const Cleared& c, int32_t from, int32_t to) { return (a ? c.y : c.x) == from && (int32_t)(a ? c.h : c.w) == to - from; };
    const auto whole_across = [&](const Cleared& c, uint32_t other) { return (a ? c.x : c.y) == 0 && (a ? c.w : c.h) == other; };
    const int32_t in0 = (int32_t)std::ceil(seen[a]), in1 = (int32_t)std::floor(seen[a] + seen[2 + a]);   // (the narrowed viewport's edges)
    if (wide || tall)
        check(cleared.size() == 2 && cleared[0].black && cleared[1].black && along(cleared[0], 0, in0) && along(cleared[1], in1, (int32_t)size[a]) &&
              whole_across(cleared[0], (uint32_t)size[1 - a]) && whole_across(cleared[1], (uint32_t)size[1 - a]),
              "the movie's sides: the two strips beside it (above and below it on a narrower picture) cleared to black");
    else
        check(cleared.empty(), "a movie left as it is: nothing cleared");
    cleared.clear();
    s.viewport[0][2] = 0, s.viewport[0][3] = 0;
    at.width = 3840, at.height = 2160;   // (a viewport of 0 x 0 is the whole target)
    run(bar);
    const float whole[2] = {3840, 2160};
    if (wide || tall)
        check(cleared.size() == 2 && near(seen[a], whole[a] * 0.5f * (1.0f - 1.0f / k)) && along(cleared[0], 0, (int32_t)std::ceil(seen[a])) &&
              along(cleared[1], (int32_t)std::floor(seen[a] + seen[2 + a]), (int32_t)whole[a]) && whole_across(cleared[1], (uint32_t)whole[1 - a]),
              "the movie's sides with a viewport of 0 x 0: of the whole target");
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

    // ---- The wipes, the loading screen and the stage panel (measured at 5120 x 1440: work/runs/w26) ----
    // The window texture is 3840 x 2160, of which 2560 x 1440 is shown; a wipe's layer is drawn into a 2560 x 1440
    // target of its own
    Texture layer{2560, 1440, true}, title{1920, 120, true};
    const int crop[4] = {0, 0, 2560, 1440};
    mkwvk::kirby_upscale::note_present(3840, 2160, crop);
    at.color[0] = &window4k;
    p.stages = {layout_vs};
    const float full[4] = {1920, 1080, -960, 540}, big[4] = {1976, 1136, -988, 568}, ray[4] = {22, 512, -11, 256};
    const float outline[4] = {500, 500, -250, 250}, name[4] = {1920, 120, -960, 60};
    const float q = 1.0f / k;   // (what a layout camera is narrowed by, along a)
    // (the columns of the middle 16:9, the rows on a narrower picture: a pixel is the main draw's when its centre is
    // inside the narrowed pane)
    int32_t mid0 = 0, mid1 = (int32_t)size[a];
    while (mid0 + 0.5f < half - half * q) mid0++;
    while (mid1 - 0.5f >= half + half * q) mid1--;
    // Two draws of the block's own before the draw itself, one a side strip: the scissors are exactly the two strips,
    // the pane's outer edge is on the picture's edge (NDC -q at the left, +q at the right), the strip shows a slice of
    // the pane no wider than a tenth of the layout, the viewport is within the device's limit, and the draw itself
    // has the game's viewport and scissor. On a narrower picture the same along y: a strip above and one below
    const auto stripped = [&](const char* what, int sides = 3) {
        char text[200];
        const auto say = [&](bool ok, const char* part) {
            std::snprintf(text, sizeof text, "%s: %s", what, part);
            check(ok, text);
        };
        if (!wide && !tall) return say(left(), "left on a 16:9 picture");
        const size_t want = sides == 3 ? 2 : 1;
        say(nested.size() == want, sides == 3 ? "two draws of its own, one a side strip" : "one draw of its own, the strip of its side");
        if (nested.size() != want) return;
        const float limit = (float)dev.props.limits.maxViewportDimensions[a];
        for (size_t j = 0; j < want; j++) {
            const Nested& n = nested[j];
            const int i = sides == 3 ? (int)j : sides - 1;   // (0 the left strip, 1 the right; the rows from 0 and the rows to 1440)
            say(n.depth == 1 && n.before, "a strip's draw is one level down and before the draw itself");
            say(n.sc[a] == (i ? mid1 : 0) && n.sc[a] + n.sc[2 + a] == (i ? (int32_t)size[a] : mid0) && n.sc[1 - a] == 0 &&
                n.sc[3 - a] == (int32_t)size[1 - a], "a strip's scissor is the strip, to the pixel");
            say(n.vp[2 + a] > size[a] && n.vp[2 + a] <= limit && n.vp[1 - a] == 0 && n.vp[3 - a] == size[1 - a],
                "a strip's viewport is wider than the game's (higher on a narrower picture), within the limit");
            // (where the viewport puts the pane's outer edge, and how much of the layout's 1920 units the strip shows,
            // of its 1080 on a narrower picture)
            const float outer = n.vp[a] + n.vp[2 + a] * 0.5f * (1.0f + (i ? q : -q));
            const float slice = (float)n.sc[2 + a] / (n.vp[2 + a] * q);
            say(near(outer, i ? size[a] : 0.0f), "the pane's outer edge is on the picture's edge");
            say(slice > 0.0f && slice <= 0.1f, "a strip shows the pane's outer tenth at most");
        }
        say(seen[0] == 0 && seen[1] == 0 && seen[2] == 2560 && seen[3] == 1440 && seen_sc[0] == 0 && seen_sc[2] == 2560 &&
            seen_sc[1] == 0 && seen_sc[3] == 1440, "the draw itself has the game's viewport and scissor");
        say(back() && s.scissor[0] == 0 && s.scissor[1] == 0 && s.scissor[2] == 2560 && s.scissor[3] == 1440,
            "the game's viewport and scissor are back after the draw");
    };
    s.scissor[0] = 0, s.scissor[1] = 0, s.scissor[2] = 2560, s.scissor[3] = 1440;
    // (the loading screen's fill: the plain pane program, an 8 x 8 texture the game uploaded, no blend)
    p.key = 0x5cfce03bc8b25357ull;
    sampled = {};
    run(full);
    stripped("the loading screen's fill");
    // (the cover of the wipe out of a stage: a fill with the star's hole cut by a 1080 x 1080 mask, all uploaded)
    p.key = 0xb96bfac902d1c5f1ull;
    run(full);
    stripped("a wipe's cover with the star's hole");
    // (the cover of the wipe into a stage: the loading screen's layer, drawn off screen, through the same mask. The
    // layer is 16:9, not of the picture's shape: it is no capture of the picture)
    p.key = 0xf188a9d1a6fe0c21ull;
    sampled = {&layer};
    run(full);
    stripped("a wipe's cover that shows a layer");
    // (the stage panel's preview: two 1920 x 1080 pictures the game uploaded)
    p.key = 0x1a89a565c8e2f0b3ull;
    sampled = {};
    run(full);
    stripped("a full-screen picture");
    // (a viewport of 0 x 0 is the whole target, and a scissor of 0 x 0 none)
    at.width = 2560, at.height = 1440;
    s.viewport[0][2] = 0, s.viewport[0][3] = 0, s.scissor[2] = 0, s.scissor[3] = 0;
    run(full);
    if (wide || tall)
        check(nested.size() == 2 && nested[0].sc[a] == 0 && nested[0].sc[2 + a] == mid0 && nested[1].sc[a] == mid1 &&
              nested[1].sc[3 - a] == (int32_t)size[1 - a] && nested[0].vp[3 - a] == size[1 - a] && seen[2] == 0 && seen[3] == 0 && seen_sc[2] == 0,
              "the strips of a viewport of 0 x 0: of the whole target");
    check(s.viewport[0][2] == 0 && s.viewport[0][3] == 0 && s.scissor[2] == 0 && s.scissor[3] == 0, "and both given back as 0 x 0");
    s.viewport[0][2] = 2560, s.viewport[0][3] = 1440, s.scissor[2] = 2560, s.scissor[3] = 1440;
    // (not for a draw that cannot be drawn again as it is)
    p.key = 0x5cfce03bc8b25357ull;
    d.mesh = true;
    run(full);
    check(left(), "a mesh draw over the whole layout: left");
    d = DrawArgs{};
    d.indirect = 0x2000;
    run(full);
    check(left(), "an indirect draw over the whole layout: left");
    d = DrawArgs{};
    d.occ_pool = &d;
    run(full);
    check(left(), "a draw with an occlusion query over the whole layout: left");
    d = DrawArgs{};
    feedback_open = true;
    run(full);
    check(left(), "a draw into a copy of its target (it samples what it writes): left");
    feedback_open = false;
    // (a device whose widest viewport cannot stretch the slice: the pane is widened whole instead. The limit is the
    // one along the axis: the widest viewport on a wide picture, the highest on a narrower one. Under twice the
    // viewport: 4096 for the 2560 columns, 2048 for the 1440 rows)
    const uint32_t low = a ? 2048 : 4096;
    dev.props.limits.maxViewportDimensions[a] = low;
    run(full);
    check(widened(), "a viewport limit under twice the viewport (4096 wide, 2048 high): the pane widened by the ratio over 16:9 (heightened on a narrower picture), no strip");
    dev.props.limits.maxViewportDimensions[a] = 16384;
    // (a limit across the axis that holds the game's viewport and is under twice it: not the one that counts)
    dev.props.limits.maxViewportDimensions[1 - a] = a ? 4096 : 2048;
    run(full);
    stripped("a low limit across the axis only");
    if (wide || tall) check(nested.size() == 2 && nested[0].vp[2 + a] == 16384.0f && nested[1].vp[2 + a] == 16384.0f, "a strip's viewport takes the limit along the axis");
    dev.props.limits.maxViewportDimensions[1 - a] = 16384;
    // (left as they are)
    // (the loading screen's two blots: 900 x 500 panes in the top left and the bottom right corner, the second 2 units
    // past the edge; and a pane of the stage panel's preview, 480 x 270 scaled by 4)
    const float blot_l[4] = {900, 500, 0, 0}, blot_r[4] = {900, 500, -900, 500}, quarter[4] = {480, 270, -240, 135};
    const float button[4] = {530, 128, -265, 64}, halo[4] = {1950, 975, -975, 0};
    p.key = 0x17c677b41ed0780cull;
    place(1, -960, 0.85f, 540);
    // (moved, not stretched: the viewport keeps its width and goes aside by half of what the camera's narrowing leaves,
    // so the pane's outer edge is on the picture's edge and its shape is the game's; no strip, which would smear it.
    // On a narrower picture it goes up or down the same way, its height kept: the layout's +y is the higher row (this
    // game's window origin is the lower left, so dynamic_state does not turn the viewport over).
    // x_side, y_side: -1 towards 0, 1 away from it, on a wide picture and on a narrower one)
    const auto moved = [&](int x_side, int y_side) {
        return near(seen[a], (float)(a ? y_side : x_side) * half * (1.0f - q)) && seen[2 + a] == size[a] && across() && nested.empty() && back();
    };
    run(blot_l);
    check(moved(-1, 1), "a blot in the top left corner: moved whole to the picture's left edge (its top edge on a narrower picture), no strip");
    place(1, 962, 0.85f, -540);
    run(blot_r);
    check(moved(1, -1), "a blot in the bottom right corner: moved whole to the picture's right edge (its bottom edge on a narrower picture), no strip");
    p.key = 0x96eec856a2d41f77ull;
    place(4, 0, 4, 0);
    run(quarter);
    stripped("a pane scaled up to the whole layout");
    p.key = 0x5cfce03bc8b25357ull;
    place(1, 698, 1, -380);
    run(button);
    check(left(), "a button that slides in over the right edge (its top and bottom inside the layout): left");
    place(0.632f, 344, 0.76f, 42);
    run(halo);
    check(left(), "the pause menu's glow, its side on the layout's edge: left");
    place(1, 0, 1, 476);
    run(button);
    check(left(), "a pane that slides in over the top edge (its sides inside the layout): left");
    place(1, -960, 0.85f, 540);
    matrix[1] = 0.5f, matrix[4] = -0.5f;
    run(blot_l);
    check(left(), "a turned pane in a corner (a ray): left");
    matrix[1] = 0, matrix[4] = 0;
    place(1, 30, 1, 0);
    run(full);
    check(left(), "a whole pane moved aside (it slides): left");
    place(1, 0, 1, 30);
    run(full);
    check(left(), "a whole pane moved up (it slides): left");
    dev.props.limits.maxViewportDimensions[a] = low;
    place(1, -960, 0.85f, 540);
    run(blot_l);
    check(moved(-1, 1), "a low viewport limit and a pane in one corner: moved all the same (no wide viewport needed)");
    dev.props.limits.maxViewportDimensions[a] = 16384;
    place(1, 0, 1, 0);
    run(big);
    check(left(), "a pane larger than the layout with pictures the game uploaded: left");
    run(outline);
    check(left(), "a star outline (500 x 500): left");
    run(frost);
    check(left(), "a HUD pane: left");
    p.stages.clear();
    run(full);
    check(left(), "a program that reads no layout constants, the last layout's whole pane still bound: left");
    p.stages = {layout_vs};
    const float narrowed_m00 = c3_mem[0], narrowed_m11 = c3_mem[5];
    c3_mem[0] = 2.0f / 1920.0f, c3_mem[5] = 2.0f / 1080.0f;
    run(full);
    check(wide || tall ? left() : true, "a whole pane under a camera that is not narrowed: left");
    c3_mem[0] = narrowed_m00, c3_mem[5] = narrowed_m11;
    oot = 1;
    pane_reads = 0;
    run(full);
    check(left() && pane_reads == 0, "the other game's whole pane: left, its constants not read");
    oot = 0;
    // (the stage's name on the loading screen: a 1920 x 120 pane of text the GPU drew. A cutscene's bar is of that
    // shape, with textures the game uploaded)
    p.key = 0x36da1a91054fc5e9ull;
    sampled = {&title};
    run(name);
    check(left(), "the stage's name, a pane of a bar's shape with text the GPU drew: left");

    // A wipe's layer: the loading screen drawn into a 16:9 target of its own (2560 x 1440) by the narrowed cameras, then
    // shown by a narrowed pane. Its draws are widened back, so that the layer holds the screen at 16:9
    at.color[0] = &layer;
    p.key = 0x5cfce03bc8b25357ull;
    sampled = {};
    run(ray);
    check(widened(), "a layer's draw (a ray, 22 x 512): its viewport wider by the ratio over 16:9 about its centre (higher by 16:9 over the ratio on a narrower picture)");
    check(back(), "the game's viewport is back after the layer's draw");
    run(full);
    check(widened(), "a layer's fill: widened as the layer's other draws, no strip");
    // (a blot in the layer would end at the layer's side, and the cover's strips would smear it over the picture's:
    // the blots are not in a wipe's layer, they come with the loading screen itself)
    place(1, -960, 0.85f, 540);
    run(blot_l);
    check(!wide && !tall ? left() : nested.empty() && seen[2 + a] == size[a] && (seen[a] >= size[a] || seen[a] <= -size[a]) && across(),
          "a blot in a wipe's layer: its viewport off the target (not drawn), on a picture not 16:9");
    check(back(), "the game's viewport is back after the layer's blot");
    place(1, 0, 1, 0);
    c3_mem[0] = 2.0f / 2560.0f, c3_mem[5] = -2.0f / 1440.0f;
    run(ray);
    check(left(), "a draw into a 16:9 target under a camera of the target's own (not narrowed): left");
    c3_mem[0] = narrowed_m00, c3_mem[5] = narrowed_m11;
    p.stages.clear();
    p.key = 0x21240c5afa2d2e61ull;
    run(ray);
    check(left(), "a blur into a 16:9 target, the last layout's constants still bound: left");
    p.stages = {layout_vs};
    p.key = 0x5cfce03bc8b25357ull;
    mkwvk::kirby_upscale::note_present(2560, 1440, nullptr);
    run(ray);
    check(left(), "a draw into the window texture (the last present's size): not widened as a layer's");
    mkwvk::kirby_upscale::texture.store(0);
    run(ray);
    check(left(), "before the first present: no target is taken for a layer's");
    mkwvk::kirby_upscale::note_present(3840, 2160, crop);
    oot = 1;
    run(ray);
    check(left(), "the other game's draw into a 16:9 target: left");
    oot = 0;
    for (const Nested& n : nested) check(n.depth == 1, "no draw of the block's own nests further");
    at.color[0] = &window;

    // (the factor on the header, as before)
    const mkwvk::kirby_wide::Sampled c21{215, 90, true};
    const float k21 = mkwvk::kirby_wide::keep_whole(true, 3440.0f / 1440.0f, 2560, 1440, 1, &c21, 1, bg);
    check(near(k21, (3440.0f / 1440.0f) / (16.0f / 9.0f)), "21:9: widened by the ratio over 16:9");
    check(mkwvk::kirby_wide::keep_whole(true, 16.0f / 9.0f, 2560, 1440, 1, &c21, 1, bg) == 1.0f, "a 16:9 picture: left");
    const mkwvk::kirby_wide::Sampled c1610{144, 90, true};
    check(near(mkwvk::kirby_wide::keep_whole(true, 1.6f, 2560, 1440, 1, &c1610, 1, bg), (16.0f / 9.0f) / 1.6f),
          "16:10: heightened by 16:9 over the ratio");
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
        raise SystemExit("the pause background, cutscene bar, movie, wipe or loading screen of a picture not 16:9 is not as "
                         "it should be, or another draw is changed: " + ", ".join(failed))
    print("PASS: the pause background and the cutscene bars at the picture's width, the movie at 16:9, a wipe's cover and "
          "the loading screen out to the picture's edges, a wipe's layer at 16:9, at 32:9 and 21:9, and along y at 16:10 "
          "and 4:3; HUD panes, hint videos, Copy, the other game and 16:9 left")


if __name__ == "__main__":
    main()
