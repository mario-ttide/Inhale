"""Game-free test of the stand-in for this game's upscale network (gpu/vk/kirby_upscale.h and its block in vk_draw.cpp's
upscale_stub): when the window shows a part of its texture (handheld: 1920 x 1080 of 3840 x 2160), the scene is blitted
into that part alone, where upstream's stand-ins fill the whole image and the screen showed a quarter of the scene. The
block is cut from vk_draw.cpp and compiled with stand-ins for Vulkan: what it blits and where, and that it leaves the
footer's record (kirby_route.h: the scene's size into that part, a linear blit) only while the footer asks, and leaves the
dispatch to the stand-ins below for the other game, for unlike formats, for an image that is not the window texture's
size, and while the window shows its whole texture or no present was seen. And vk_replay.cpp's do_present notes each
present.

    python -I tests/test_kirby_upscale.py --cxx clang++
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between

FIXTURE = r'''
#include <cassert>
#include <cstdio>
#include "kirby_route.h"
#include "kirby_upscale.h"
using namespace mkwvk;
// (the footer's record, upscale_route.cpp's: what the block publishes, and whether the footer asks)
static bool footer_asks;
static int records;
static upscale_route::Sample record;
bool mkwvk::upscale_route::wanted() { return footer_asks; }
void mkwvk::upscale_route::publish(const Sample& s) { record = s, records++; }

// (stand-ins for what the block calls)
struct Texture { int format; uint32_t width, height; int image; };
typedef int VkCommandBuffer;
struct VkOffset3D { int32_t x, y, z; };
struct VkImageSubresourceLayers { int aspectMask, mipLevel, baseArrayLayer, layerCount; };
struct VkImageBlit { VkImageSubresourceLayers srcSubresource; VkOffset3D srcOffsets[2]; VkImageSubresourceLayers dstSubresource; VkOffset3D dstOffsets[2]; };
enum { VK_IMAGE_ASPECT_COLOR_BIT = 1, VK_IMAGE_LAYOUT_GENERAL = 1, VK_FILTER_LINEAR = 1 };
static bool other_game;
bool mkwvk::menu_oot_rows() { return other_game; }   // (kirby_wide.h declares it; the block may stop asking, and the check must then fail in a case)
static VkImageBlit got;
static int blits, barriers, written, from, into, filter;
static void vkCmdBlitImage(VkCommandBuffer, int src, int, int dst, int, int n, const VkImageBlit* b, int f) {
    assert(n == 1);
    got = *b, from = src, into = dst, filter = f, blits++;
}
static void full_barrier(VkCommandBuffer) { barriers++; }
static void texture_written(Texture*) { written++; }

static bool stand_in(VkCommandBuffer cmd, Texture* src, Texture* dst) {
@BLOCK@
    return false;   // (the stand-ins below)
}

int main() {
    Texture scene{37, 1120, 630, 7}, window{37, 3840, 2160, 9}, other{37, 2560, 1440, 11}, srgb{43, 3840, 2160, 13};
    // no present seen yet: left to the stand-ins below
    assert(!stand_in(0, &scene, &window) && !blits);
    // handheld: the window shows 1920 x 1080 of its 3840 x 2160. The whole scene into that part, linear, once
    const int handheld[4] = {0, 0, 1920, 1080};
    kirby_upscale::note_present(3840, 2160, handheld);
    assert(stand_in(0, &scene, &window) && blits == 1 && written == 1 && barriers == 1);
    assert(from == 7 && into == 9 && filter == VK_FILTER_LINEAR);
    assert(got.srcOffsets[0].x == 0 && got.srcOffsets[0].y == 0 && got.srcOffsets[1].x == 1120 && got.srcOffsets[1].y == 630);
    assert(got.dstOffsets[0].x == 0 && got.dstOffsets[0].y == 0 && got.dstOffsets[1].x == 1920 && got.dstOffsets[1].y == 1080);
    assert(got.srcOffsets[1].z == 1 && got.dstOffsets[1].z == 1 && got.srcSubresource.layerCount == 1 &&
           got.dstSubresource.layerCount == 1 && got.srcSubresource.aspectMask == VK_IMAGE_ASPECT_COLOR_BIT);
    // the footer's record: none while nobody asks; then the scene's size into the part, as a linear blit
    assert(!records);
    footer_asks = true;
    assert(stand_in(0, &scene, &window) && blits == 2 && records == 1);
    assert(record.route == upscale_route::Route::Blit && record.in_w == 1120 && record.in_h == 630 && record.out_w == 1920 &&
           record.out_h == 1080);
    footer_asks = false, blits = 1;
    // the other game; unlike formats; an image that is not the window texture's size: the stand-ins below
    other_game = true;
    assert(!stand_in(0, &scene, &window));
    other_game = false;
    assert(!stand_in(0, &scene, &srgb) && !stand_in(0, &scene, &other) && blits == 1 && records == 1);
    // a part with a corner of its own: the blit goes there
    const int corner[4] = {100, 50, 1280, 720};
    kirby_upscale::note_present(3840, 2160, corner);
    assert(stand_in(0, &scene, &window) && blits == 2);
    assert(got.dstOffsets[0].x == 100 && got.dstOffsets[0].y == 50 && got.dstOffsets[1].x == 1380 && got.dstOffsets[1].y == 770);
    // less than all of it in one direction only: still a part
    const int wide[4] = {0, 0, 3840, 1080};
    kirby_upscale::note_present(3840, 2160, wide);
    assert(stand_in(0, &scene, &window) && blits == 3 && got.dstOffsets[1].x == 3840 && got.dstOffsets[1].y == 1080);
    // the window shows its whole texture (docked at 3840 x 2160), by a crop or with none: the stand-ins below
    const int whole[4] = {0, 0, 3840, 2160};
    kirby_upscale::note_present(3840, 2160, whole);
    assert(!stand_in(0, &scene, &window));
    kirby_upscale::note_present(3840, 2160, nullptr);
    assert(!stand_in(0, &scene, &window));
    const int empty[4] = {0, 0, 0, 0};
    kirby_upscale::note_present(3840, 2160, empty);
    assert(!stand_in(0, &scene, &window));
    // a part that would leave the image: not taken
    const int outside[4] = {3000, 0, 1920, 1080};
    kirby_upscale::note_present(3840, 2160, outside);
    assert(!stand_in(0, &scene, &window) && blits == 3);
    puts("ok");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()

    # (upscale_stub: the block stands after the pass is ended and before the first of upstream's stand-ins)
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    stub = block(draw, "bool upscale_stub(VkCommandBuffer cmd, const NvnState& s, uint64_t key) {")
    cut = between(stub, "    // (inhale) this game's network writes only the part of the window texture that is shown",
                  "    if (dst->format == VK_FORMAT_R8G8B8A8_UNORM && movie_upscale(cmd, in_h, out_h, dst)) {")
    before = stub[:stub.index(cut)]
    assert before.rstrip().endswith("end_pass(cmd);\n    full_barrier(cmd);"), \
        "upscale_stub: this game's block must follow end_pass and full_barrier"
    # (do_present notes the texture's size and the crop of each present)
    present = block((ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8"),
                    "void do_present(const nvn_tex* t, const int crop[4], uint64_t native_generation = 0) {")
    assert "if (t) kirby_upscale::note_present(t->d.width, t->d.height, crop);" in present, \
        "do_present does not note the present for the upscale stand-in"

    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.cpp"
        test.write_text(FIXTURE.replace("@BLOCK@", cut), encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Werror", "-I", str(ROOT / "gpu/vk"), str(test), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        assert out.returncode == 0 and out.stdout.strip() == "ok", out.stdout + out.stderr
    print("test_kirby_upscale: ok")


if __name__ == "__main__":
    main()
