"""Game-free test of ReShade in this game (issue #31): gpu/vk/kirby_reshade.h, its call in vk_draw.cpp's draw(), and
feedback::keep in gpu/vk/vk_feedback.cpp.

Upstream runs a ReShade preset on its game's gameplay upscale output only. This game never draws one: its scene
(B10G11R11, tone-mapped, at the dynamic resolution's size) goes into the window texture by one Copy draw. So a preset
never ran, and the menu said "Waiting for the gameplay scene" at all times. The fix runs the preset on the scene just
before that Copy draw samples it, and puts the scene back once the draw is done: the next frame's first post pass
(7e8ae0b3b6d8fe1e) samples the scene the frame before left.

This checks, with no game and no GPU:
- the rule (kirby_reshade.h, compiled as it is): Copy into the window texture, from a picture of the scene's format, is
  the draw; another program, a Copy between scene targets, a Copy of a picture of another format, a target that is not
  the window texture, the other game, ReShade off are not;
- the draw: draw() asks the rule, keeps the scene (feedback::keep) and records the preset on it outside a pass, after
  DLAA's commands (temporal_pre_bloom) and before the draw's pass is begun, only for a draw that pushes its descriptors
  again (!same_desc: the preset binds its own); and gives the kept scene up when the preset did not record (nothing to
  put back);
- the keeping (vk_feedback.cpp, cut out by its text, against stand-ins for the Vulkan calls): the scene is copied aside
  after a barrier, and copied back into it when the draw ends, after its pass is ended.

    python -I -B tests/test_kirby_reshade.py --cxx clang++ --headers <Vulkan headers>
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"

RULE = r'''
#include <cstdio>
#include "kirby_reshade.h"
using namespace mkwvk;

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

int main() {
    const uint64_t copy = kirby_wide::kCopy, layout = 0xc7974d16c805e580ull;
    CHECK("no present seen yet: no window texture to tell the draw by",
          !kirby_reshade::scene_copy(true, true, copy, 2560, 1440, false, 2240, 1260, true));
    kirby_upscale::note_present(2560, 1440, nullptr);
    CHECK("Copy of the scene into the window texture", kirby_reshade::scene_copy(true, true, copy, 2560, 1440, false, 2240, 1260, true));
    CHECK("at the picture's size too", kirby_reshade::scene_copy(true, true, copy, 2560, 1440, false, 2560, 1440, true));
    CHECK("ReShade off", !kirby_reshade::scene_copy(false, true, copy, 2560, 1440, false, 2240, 1260, true));
    CHECK("the other game", !kirby_reshade::scene_copy(true, false, copy, 2560, 1440, false, 2240, 1260, true));
    CHECK("another program", !kirby_reshade::scene_copy(true, true, layout, 2560, 1440, false, 2240, 1260, true));
    CHECK("a Copy between two scene targets (the bloom's steps)",
          !kirby_reshade::scene_copy(true, true, copy, 2560, 1440, true, 2240, 1260, true));
    CHECK("a Copy of a picture of another format", !kirby_reshade::scene_copy(true, true, copy, 2560, 1440, false, 2240, 1260, false));
    CHECK("a target that is not the window texture", !kirby_reshade::scene_copy(true, true, copy, 1120, 630, false, 2240, 1260, true));
    CHECK("an empty picture", !kirby_reshade::scene_copy(true, true, copy, 2560, 1440, false, 0, 0, true));
    std::printf("PASS: the Copy draw of the scene into the window texture, and no other\n");
    return 0;
}
'''

KEEP = r'''#include <vulkan/vulkan.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <mutex>
#include <vector>

#include "feedback_copy.h"

typedef struct VmaAllocation_T* VmaAllocation;
enum { kEndPass, kBarrier, kLayout, kCopy };
struct Event {
    int kind;
    VkImage src, dst;
    uint32_t width, height;
};
static std::vector<Event> events;
static int images_made;

namespace mkwvk {
struct Texture {
    VkImage image = VK_NULL_HANDLE;
    VkFormat format = VK_FORMAT_UNDEFINED;
    VkImageType type = VK_IMAGE_TYPE_2D;
    VkImageUsageFlags usage = 0;
    VkImageCreateFlags create_flags = 0;
    uint32_t width = 1, height = 1, levels = 1, layers = 1;
    VkSampleCountFlagBits samples = VK_SAMPLE_COUNT_1_BIT;
};
struct {
    VkDevice device = VK_NULL_HANDLE;
    VkDriverId driver_id = VK_DRIVER_ID_MESA_RADV;
} dev;
void logf(const char*, ...) {}
bool create_image(const VkImageCreateInfo&, VkImage& image, VmaAllocation& memory, bool = false, bool = false, bool = false) {
    image = (VkImage)(uintptr_t)(0x1000 + ++images_made), memory = (VmaAllocation)(uintptr_t)images_made;
    return true;
}
void destroy_image(VkImage, VmaAllocation) {}
uint64_t texture_frame_no() { return 100; }
uint64_t vk_retirement_value() { return 7; }
uint64_t vk_timeline_completed() { return 0; }
void end_pass(VkCommandBuffer) { events.push_back({kEndPass, {}, {}, 0, 0}); }
void full_barrier(VkCommandBuffer, const char* = "") { events.push_back({kBarrier, {}, {}, 0, 0}); }
} // namespace mkwvk
extern "C" {
VKAPI_ATTR VkResult VKAPI_CALL vkCreateImageView(VkDevice, const VkImageViewCreateInfo* ci, const VkAllocationCallbacks*, VkImageView* view) {
    *view = (VkImageView)((uintptr_t)ci->image + 0x100000);
    return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL vkDestroyImageView(VkDevice, VkImageView, const VkAllocationCallbacks*) {}
VKAPI_ATTR void VKAPI_CALL vkCmdPipelineBarrier2(VkCommandBuffer, const VkDependencyInfo* di) {
    for (uint32_t i = 0; i < di->imageMemoryBarrierCount; i++) events.push_back({kLayout, {}, di->pImageMemoryBarriers[i].image, 0, 0});
}
VKAPI_ATTR void VKAPI_CALL vkCmdCopyImage(VkCommandBuffer, VkImage src, VkImageLayout, VkImage dst, VkImageLayout, uint32_t n,
                                          const VkImageCopy* r) {
    for (uint32_t i = 0; i < n; i++) events.push_back({kCopy, src, dst, r[i].extent.width, r[i].extent.height});
}
}

namespace mkwvk {
@HEADER@
} // namespace mkwvk
@CODE@

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

using namespace mkwvk;

int main() {
    Texture scene;
    scene.image = (VkImage)0x10, scene.format = VK_FORMAT_B10G11R11_UFLOAT_PACK32, scene.width = 2240, scene.height = 1260;
    scene.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                  VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    VkImage kept = VK_NULL_HANDLE;
    {
        feedback::Draw d;
        CHECK("the scene is kept", feedback::keep(d, (VkCommandBuffer)0x42, &scene));
        CHECK("a barrier, the copy's layout, then the scene into the copy, whole",
              events.size() == 3 && events[0].kind == kBarrier && events[1].kind == kLayout && events[2].kind == kCopy &&
                  events[2].src == scene.image && events[2].dst == events[1].dst && events[2].width == 2240 &&
                  events[2].height == 1260);
        kept = events[2].dst;
        events.clear();
    }
    CHECK("when the draw ends: its pass ended, a barrier, the kept scene back into the scene",
          events.size() == 3 && events[0].kind == kEndPass && events[1].kind == kBarrier && events[2].kind == kCopy &&
              events[2].src == kept && events[2].dst == scene.image && events[2].width == 2240 && events[2].height == 1260);
    events.clear();
    {   // what cannot be copied back is not kept: a preset on it would stay in the scene
        Texture locked = scene;
        locked.usage &= ~(VkImageUsageFlags)VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        feedback::Draw d;
        CHECK("a scene that cannot be copied into is not kept", !feedback::keep(d, (VkCommandBuffer)0x42, &locked) && !d.cmd);
    }
    CHECK("and nothing recorded for it", events.empty());
    std::printf("PASS: the scene is kept aside and put back when the draw ends\n");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--headers", type=Path, help="the Vulkan headers, where the compiler does not find them itself")
    args = parser.parse_args()

    if not (VK / "kirby_reshade.h").exists():
        raise SystemExit("gpu/vk/kirby_reshade.h is missing: a ReShade preset never runs in this game (issue #31)")
    source = (VK / "vk_draw.cpp").read_text(encoding="utf-8")
    draw = block(source, "void draw(VkCommandBuffer cmd, NvnState& s, const DrawArgs& d) {")
    if "kirby_reshade::scene_copy(" not in draw:
        raise SystemExit("draw: the preset is never recorded on this game's scene (kirby_reshade::scene_copy is not asked)")
    ask = draw.index("kirby_reshade::scene_copy(")
    pre = draw.index("temporal_pre_bloom(cmd, p.key, gfx_sampled(), at.color, at.n);")
    passes = [at for at in range(len(draw)) if draw.startswith("begin_pass(cmd, ", at)]
    if ask < pre:
        raise SystemExit("draw: the preset is recorded before DLAA's commands (temporal_pre_bloom)")
    if not passes or any(at < ask for at in passes):
        raise SystemExit("draw: the Copy draw's pass is begun before the preset is recorded on the scene it samples")
    if "!same_desc" not in draw[draw.rindex("if (", 0, ask):ask]:
        raise SystemExit("draw: the preset may be recorded for a draw that does not push its descriptors again after it")
    after = draw[ask:passes[0]]
    for need, why in (("end_pass(cmd);", "the preset is recorded inside a pass"),
                      ("feedback::keep(", "the scene is not kept: the next frame's first post pass would read the preset"),
                      ("reshade::record(cmd, const_cast<Texture*>(gfx_sampled()[0]), 0,", "the preset is not recorded on the scene")):
        if need not in after:
            raise SystemExit("draw: " + why)
    if after.index("feedback::keep(") > after.index("reshade::record("):
        raise SystemExit("draw: the scene is kept after the preset changed it")
    if "feedback::Draw " not in draw or draw.index("feedback::Draw ") > ask:
        raise SystemExit("draw: nothing puts the kept scene back when the draw ends (feedback::Draw)")
    if ".cmd = VK_NULL_HANDLE" not in after:
        raise SystemExit("draw: the scene is put back even when the preset did not record")

    header = block((VK / "vk_feedback.h").read_text(encoding="utf-8"), "namespace feedback {")
    code = block((VK / "vk_feedback.cpp").read_text(encoding="utf-8"), "namespace mkwvk::feedback {")
    keep = KEEP.replace("@HEADER@", header).replace("@CODE@", code)

    with tempfile.TemporaryDirectory(prefix="kirby-reshade-") as tmp:
        for name, text, std in (("rule", RULE, "-std=c++17"), ("keep", keep, "-std=c++20")):
            cpp = Path(tmp) / (name + ".cpp")
            exe = Path(tmp) / name
            cpp.write_text(text, encoding="utf-8")
            subprocess.run([args.cxx, std, "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers",
                            "-I", str(VK), *(["-I", str(args.headers)] if args.headers else []), str(cpp), "-o", str(exe)],
                           check=True)
            subprocess.run([str(exe)], check=True)
    print("test_kirby_reshade: ok")


if __name__ == "__main__":
    main()
