"""Game-free test of the FPS counter footer's record for this game (gpu/vk/kirby_route.h and its three calls in
vk_draw.cpp). Every path that publishes a record is upstream's and knows the other game only, so the footer said
"Resolution: not in gameplay" in this game at all times. The header is compiled as it is, with the footer's own words
(upscale_route.h footer_lines): the Copy draw that puts the scene into the window texture, at the picture's size and
stepped down; this game's network and the blit in its place; a scene drawn larger than what the window shows; and what
is refused (another program, a target that is not the window texture or is of the scene's format, a sampled texture
of another format, the other game, an empty picture). And the three calls stand in vk_draw.cpp, each behind
upscale_route::wanted().

    python -I tests/test_kirby_route.py --cxx clang++
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
#include <string>
#include "kirby_route.h"
using namespace mkwvk;
namespace ur = upscale_route;

static std::string lines(const ur::Sample& s) {
    std::string out[2];
    ur::footer_lines(&s, upscaler_rows::GAME, 0, out);
    return out[0] + " | " + out[1];
}
static bool same(const std::string& got, const char* want) {
    if (got != want) printf("got:  %s\nwant: %s\n", got.c_str(), want);
    return got == want;
}

int main() {
    const uint64_t copy = kirby_wide::kCopy, layout = 0xc7974d16c805e580ull;
    ur::Sample r;
    // no present seen yet: no window texture to tell the draw by
    assert(!kirby_route::copy_drawn(true, copy, 2560, 1440, false, 2560, 1440, true, &r));
    // docked at 2560 x 1440, the window shows its whole texture: the scene at the picture's size
    kirby_upscale::note_present(2560, 1440, nullptr);
    assert(kirby_route::copy_drawn(true, copy, 2560, 1440, false, 2560, 1440, true, &r));
    assert(same(lines(r), "Resolution 2560x1440 (100%) | Upscaling: off, no AA"));
    // the dynamic resolution stepped down
    assert(kirby_route::copy_drawn(true, copy, 2560, 1440, false, 2240, 1260, true, &r));
    assert(same(lines(r), "Resolution 2240x1260 to 2560x1440 (88%) | Upscaling: off (stretched)"));
    // refused: another program; a target that is not the window texture; a target of the scene's format (a Copy
    // between two scene targets); a sampled texture of another format; the other game; an empty picture
    const ur::Sample kept = r;
    assert(!kirby_route::copy_drawn(true, layout, 2560, 1440, false, 2240, 1260, true, &r));
    assert(!kirby_route::copy_drawn(true, copy, 1280, 720, false, 640, 360, true, &r));
    assert(!kirby_route::copy_drawn(true, copy, 2560, 1440, true, 2240, 1260, true, &r));
    assert(!kirby_route::copy_drawn(true, copy, 2560, 1440, false, 2240, 1260, false, &r));
    assert(!kirby_route::copy_drawn(false, copy, 2560, 1440, false, 2240, 1260, true, &r));
    assert(!kirby_route::copy_drawn(true, copy, 2560, 1440, false, 0, 0, true, &r));
    assert(r.in_w == kept.in_w && r.out_w == kept.out_w && r.route == kept.route);   // (a refusal leaves the record)
    // handheld: the window shows 1920 x 1080 of its 3840 x 2160. The picture is that part
    const int handheld[4] = {0, 0, 1920, 1080};
    kirby_upscale::note_present(3840, 2160, handheld);
    assert(kirby_route::copy_drawn(true, copy, 3840, 2160, false, 1920, 1080, true, &r));
    assert(same(lines(r), "Resolution 1920x1080 (100%) | Upscaling: off, no AA"));
    assert(kirby_route::copy_drawn(true, copy, 3840, 2160, false, 1600, 900, true, &r));
    assert(same(lines(r), "Resolution 1600x900 to 1920x1080 (83%) | Upscaling: off (stretched)"));
    // under 720 lines the game's network draws the scene into that part, or the blit in its place
    assert(kirby_route::upscaled(true, ur::Route::Network, 960, 540, 3840, 2160, &r));
    assert(same(lines(r), "Resolution 960x540 to 1920x1080 (50%) | Upscaling: Built-in"));
    assert(kirby_route::upscaled(true, ur::Route::Blit, 960, 540, 3840, 2160, &r));
    assert(same(lines(r), "Resolution 960x540 to 1920x1080 (50%) | Upscaling: linear blit, no AA"));
    // refused: the other game; a network into an image that is not the window texture; an empty picture
    assert(!kirby_route::upscaled(false, ur::Route::Network, 960, 540, 3840, 2160, &r));
    assert(!kirby_route::upscaled(true, ur::Route::Network, 960, 540, 1920, 1080, &r));
    assert(!kirby_route::upscaled(true, ur::Route::Network, 0, 540, 3840, 2160, &r));
    // a 3840 x 2160 output, docked: the scene at the output's size, the window still showing 2560 x 1440 of its
    // texture. Recorded at the scene's size, as not scaled; so is an ultrawide picture's scene
    const int docked[4] = {0, 0, 2560, 1440};
    kirby_upscale::note_present(3840, 2160, docked);
    assert(kirby_route::copy_drawn(true, copy, 3840, 2160, false, 3840, 2160, true, &r));
    assert(same(lines(r), "Resolution 3840x2160 (100%) | Upscaling: off, no AA"));
    assert(kirby_route::copy_drawn(true, copy, 3840, 2160, false, 5120, 1440, true, &r));
    assert(same(lines(r), "Resolution 5120x1440 (100%) | Upscaling: off, no AA"));
    assert(kirby_route::copy_drawn(true, copy, 3840, 2160, false, 2240, 1260, true, &r));
    assert(same(lines(r), "Resolution 2240x1260 to 2560x1440 (88%) | Upscaling: off (stretched)"));
    // out_size alone: the part for the window texture, the whole image for any other
    ur::Sample o;
    kirby_route::out_size(3840, 2160, &o);
    assert(o.out_w == 2560 && o.out_h == 1440);
    kirby_route::out_size(1280, 720, &o);
    assert(o.out_w == 1280 && o.out_h == 720);
    puts("ok");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()

    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    # (the Copy draw: before the wide picture's plan, where the draw's targets, program and sampled textures are known)
    copy = between(draw, "        // (inhale) this game's scene goes into the window texture by a Copy draw",
                   "        // (inhale) this game's pause background, a capture of the whole picture")
    assert "upscale_route::wanted() &&" in copy and "kirby_route::copy_drawn(!menu_oot_rows(), p.key," in copy and \
        "upscale_route::publish(r);" in copy, "draw(): the Copy draw's record is not published"
    # (the blit in the network's place: in this game's block of upscale_stub, which tests/test_kirby_upscale.py runs)
    stub = block(draw, "bool upscale_stub(VkCommandBuffer cmd, const NvnState& s, uint64_t key) {")
    blit = between(stub, "    // (inhale) this game's network writes only the part of the window texture that is shown",
                   "    if (dst->format == VK_FORMAT_R8G8B8A8_UNORM && movie_upscale(cmd, in_h, out_h, dst)) {")
    assert "upscale_route::wanted() && kirby_route::upscaled(true, upscale_route::Route::Blit, src->width, src->height," in blit, \
        "upscale_stub: this game's blit does not publish its record"
    # (the network: before upstream's rule, which refuses a network that reads a picture of another format than it writes)
    net = block(draw, "static void route_network_drawn(const NvnState& s, const Program& p) {")
    assert "if (p.stages.empty() || !upscale_route::wanted()) return;" in net, "route_network_drawn no longer asks wanted()"
    ours = net.index("kirby_route::upscaled(!menu_oot_rows(), upscale_route::Route::Network, in->width, in->height,")
    assert ours < net.index("route_publish(upscale_route::Route::Network, known, in, out, level);"), \
        "route_network_drawn: this game's record must come before upstream's rule"

    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.cpp"
        test.write_text(FIXTURE, encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Werror", "-I", str(ROOT / "gpu/vk"), str(test), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        assert out.returncode == 0 and out.stdout.strip() == "ok", out.stdout + out.stderr
    print("test_kirby_route: ok")


if __name__ == "__main__":
    main()
