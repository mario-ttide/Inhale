"""Game-free test of HDR in this game: the presented picture's view in vk_replay.cpp's do_present, and the HDR rows in
vk_menu.cpp (docs/design.md#2026-11-26-hdr-in-this-game).

This game presents RGBA8_SRGB over an RGBA8 image. do_present made the view the present's scale and HDR passes read in the
picture's format, sRGB, so the sampler decoded it to linear; the HDR pass's Expanded (hdr_encode.comp mode 0) then decoded
it again: mid grey came out at about 0.04 of the paper white instead of 0.21, a dark picture with far too much contrast.

This checks, with no game and no GPU:
- the view (present_view and do_present's direct view, cut out by their text, against a texture_view that makes the view
  in the picture's format unless one is asked for): an sRGB picture on an RGBA8 or BGRA8 image is read through the image's
  UNORM format and not called sRGB; a UNORM picture and Native's RGB10A2 one are read as they were;
- what the HDR pass makes of mid grey (sRGB 0.5) through that view: hdr_encode.comp's sRGB decode, once, about 0.214 of
  the paper white;
- the rows (is_oot_row, env_override, saved_value, oot_rows_hold and menu_option_set's HOS_OPT_OOT_GAME branch, cut out by
  their text): with this game the HDR row stops at Expanded, a saved Native is held at Expanded for the run (the file keeps
  its value), the tone mapper is held at Vanilla, and the HDR and HDR contrast rows take help that does not speak of
  Native; with the other game all of it is as it was.

    python -I -B tests/test_kirby_hdr.py --cxx clang++
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"

VIEW = r'''
#include <cstdint>
#include <cstdio>
enum VkFormat { VK_FORMAT_UNDEFINED, VK_FORMAT_R8G8B8A8_UNORM, VK_FORMAT_R8G8B8A8_SRGB, VK_FORMAT_B8G8R8A8_UNORM,
                VK_FORMAT_B8G8R8A8_SRGB, VK_FORMAT_A8B8G8R8_SRGB_PACK32, VK_FORMAT_A2B10G10R10_UNORM_PACK32 };
enum VkImageViewType { VK_IMAGE_VIEW_TYPE_2D };
enum class ViewUse { Sample, Attachment, Storage };
using VkImageView = uint64_t;
struct Texture { VkFormat format; };
struct nvn_tex { VkFormat shown; };   // (the format the game presents in)
struct nvn_view;
// (vk_texture.cpp's rule for a sampled view: the picture's format, unless one is asked for)
VkImageView texture_view(Texture*, const nvn_tex* t, const nvn_view*, VkImageViewType, ViewUse, VkFormat* out = nullptr,
                         VkFormat force = VK_FORMAT_UNDEFINED) {
    const VkFormat f = force != VK_FORMAT_UNDEFINED ? force : t->shown;
    if (out) *out = f;
    return 1 + (VkImageView)f;
}
/* PRESENT_VIEW */
int main() {
    const VkFormat cases[][2] = {{VK_FORMAT_R8G8B8A8_UNORM, VK_FORMAT_R8G8B8A8_SRGB}, {VK_FORMAT_B8G8R8A8_UNORM, VK_FORMAT_B8G8R8A8_SRGB},
                                 {VK_FORMAT_R8G8B8A8_UNORM, VK_FORMAT_R8G8B8A8_UNORM},
                                 {VK_FORMAT_A2B10G10R10_UNORM_PACK32, VK_FORMAT_A2B10G10R10_UNORM_PACK32}};
    for (const auto& c : cases) {
        Texture image{c[0]};
        const nvn_tex picture{c[1]};
        Texture* tex = &image;
        const nvn_tex* t = &picture;
        VkImageView direct_view = 0;
        bool source_srgb = false;
        { /* DIRECT */ }
        std::printf("%d %d %d %d\n", (int)c[0], (int)c[1], (int)(direct_view - 1), source_srgb ? 1 : 0);
    }
    return 0;
}
'''

ROWS = r'''
#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <vector>
enum MenuTab { TAB_GRAPHICS, TAB_AUDIO, TAB_DEBUG, TAB_SIM_TURF };
namespace menu { struct Setting; }
constexpr int HOS_OPT_OOT_GAME = 1;
/* OPTIONS */
Options opts;
struct Row {
    MenuTab tab;
    const char* name;
    int* value;
    int lo, hi, step;
    const char* (*text)(int v);
    const char* help;
    const char* (*hint)(int v, int variant) = nullptr;
    bool restart = false;
    bool preset_exempt = false;
    signed char cheat = -1;
    bool heading = false;
    const menu::Setting* setting = nullptr;
};
std::vector<Row> rows;
std::recursive_mutex menu_mu;
struct { void restart_value(int, int) {} } restart_state;
int restart_slot_of(const Row&) { return 0; }
int row_restart_value(const Row&) { return 0; }
void samplers_changed() {}
const char* hn_preset_plain(int, int) { return nullptr; }
const char* hn_shadow_res_kirby(int, int) { return nullptr; }
const char* const kPresetHelpPlain = "";
const char* const kLaptopHelpPlain = "";
const char* const kShadowHelpKirby = "";
bool is_laptop_row(const Row&) { return false; }
std::atomic<int> oot_game{-1};
/* ACTUAL */
void option_set(int id, int value) { /* BRANCH */ }
#define CHECK(name, cond) do { if (!(cond)) { std::printf("FAIL: %s (line %d)\n", name, __LINE__); return 1; } } while (0)
const char* const kHdrHelp = "with Native";
const char* const kContrastHelp = "with Native too";
int run(int game) {
    opts = Options{};
    env_override_count = 0;
    rows = {Row{TAB_GRAPHICS, "HDR", &opts.hdr, 0, 2, 1, nullptr, kHdrHelp},
            Row{TAB_GRAPHICS, "HDR contrast", &opts.hdr_contrast, 50, 200, 5, nullptr, kContrastHelp},
            Row{TAB_GRAPHICS, "HDR tone mapper", &opts.hdr_tonemap, 0, 1, 1, nullptr, ""}};
    opts.hdr = 2, opts.hdr_tonemap = 1;   // (the file's: Native, PsychoV35)
    option_set(HOS_OPT_OOT_GAME, game);
    if (game) {
        CHECK("the other game: HDR stays Native, its row goes to Native", opts.hdr == 2 && rows[0].hi == 2);
        CHECK("the other game: the tone mapper stays PsychoV35", opts.hdr_tonemap == 1);
        CHECK("the other game: the rows' help stays upstream's", rows[0].help == kHdrHelp && rows[1].help == kContrastHelp);
        CHECK("the other game: the tone mapper is its row", is_oot_row(rows[2]) && !is_oot_row(rows[0]));
        return 0;
    }
    CHECK("this game: the HDR row stops at Expanded", rows[0].lo == 0 && rows[0].hi == 1);
    CHECK("this game: a saved Native runs as Expanded", opts.hdr == 1);
    CHECK("this game: the file keeps Native", saved_value(&opts.hdr) == 2);
    CHECK("this game: the tone mapper is hidden", is_oot_row(rows[2]) && !is_oot_row(rows[0]) && !is_oot_row(rows[1]));
    CHECK("this game: the tone mapper is held at Vanilla, the file keeps its own", opts.hdr_tonemap == 0 && saved_value(&opts.hdr_tonemap) == 1);
    CHECK("this game: the HDR row's help", rows[0].help == kHdrHelpKirby);
    CHECK("this game: the HDR contrast row's help", rows[1].help == kHdrContrastHelpKirby);
    CHECK("this game: no Native in the help", !strstr(kHdrHelpKirby, "Native") && !strstr(kHdrContrastHelpKirby, "Native"));
    opts.hdr = 0;   // (Off chosen in the menu: the player's from now on)
    CHECK("this game: Off chosen is saved as Off", saved_value(&opts.hdr) == 0);
    opts.hdr = 1;
    oot_rows_hold();   // (again, at the replay's next window: Expanded stays the player's)
    CHECK("this game: Expanded chosen stays Expanded", opts.hdr == 1 && saved_value(&opts.hdr) == 1);
    return 0;
}
int main() {
    if (run(1) || run(0)) return 1;
    std::printf("ok\n");
    return 0;
}
'''


def compile_run(cxx, source, tmp, name):
    src, exe = Path(tmp) / (name + ".cpp"), Path(tmp) / name
    src.write_text(source, encoding="utf-8")
    subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", str(src), "-o", str(exe)],
                   check=True)
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        sys.exit("FAIL: %s: %s%s" % (name, r.stdout, r.stderr))
    return r.stdout


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def check_view(cxx, tmp):
    replay = (VK / "vk_replay.cpp").read_text(encoding="utf-8")
    view = block(replay, "VkImageView present_view(Texture* tex, const nvn_tex* t")
    direct = between(replay, "VkFormat sampled_format = VK_FORMAT_UNDEFINED;", "tex->last_frame = texture_frame_no();")
    out = compile_run(cxx, VIEW.replace("/* PRESENT_VIEW */", view).replace("/* DIRECT */", direct), tmp, "view")
    names = ["UNDEFINED", "RGBA8", "RGBA8_SRGB", "BGRA8", "BGRA8_SRGB", "ABGR8_SRGB", "RGB10A2"]
    srgb = {2, 4, 5}
    # (the HDR pass's mode 0 decodes the sRGB it samples, once: the line this check models)
    shader = (VK / "shaders" / "hdr_encode.comp").read_text(encoding="utf-8")
    if "return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), greaterThan(c, vec3(0.04045)));" not in shader or \
            "const vec3 lin = srgb_to_linear(clamp(c, 0.0, 1.0));" not in shader:
        sys.exit("FAIL: hdr_encode.comp's Expanded no longer decodes sRGB as this check models it")
    want = {(1, 2): 1, (3, 4): 3, (1, 1): 1, (6, 6): 6}   # (image, picture): the view's format
    for row in out.strip().splitlines():
        image, shown, got, source_srgb = map(int, row.split())
        case = "a %s picture on a %s image" % (names[shown], names[image])
        sampled = srgb_to_linear(0.5) if got in srgb else 0.5   # (what the sampler gives the pass for sRGB 0.5)
        if shown in (2, 4):
            grey = srgb_to_linear(sampled)   # (mid grey under the knee: no highlight gain, light = lin x paper white)
            if abs(grey - 0.214) > 0.005:
                sys.exit("FAIL: %s: read as %s, Expanded shows mid grey at %.3f x paper white, not 0.214 (decoded twice)"
                         % (case, names[got], grey))
        if got != want[(image, shown)] or source_srgb != (got in srgb):
            sys.exit("FAIL: %s is read as %s (sRGB said: %d), not %s" % (case, names[got], source_srgb, names[want[(image, shown)]]))
    print("PASS: the presented picture's view: an sRGB picture read as its bytes, mid grey at 0.214 x paper white; "
          "UNORM and Native's RGB10A2 as before")


def check_rows(cxx, tmp):
    menu = (VK / "vk_menu.cpp").read_text(encoding="utf-8")
    texts = [between(menu, "const char* const %s =" % k, '";\n') + '";' for k in ("kHdrHelpKirby", "kHdrContrastHelpKirby")]
    actual = "\n".join(texts + [
        block(menu, "bool is_oot_row(const Row& r) {"),
        between(menu, "struct EnvOverride {", "/// The value save() writes"),
        block(menu, "int saved_value(int* value) {"),
        block(menu, "bool env_holds(const int* value) {"),
        block(menu, "void oot_rows_hold() {"),
        "bool oot_rows() { return oot_game.load(std::memory_order_relaxed) != 0; }",
    ])
    branch = block(menu, "if (id == HOS_OPT_OOT_GAME) {")
    fields = sorted(set(re.findall(r"opts\.(\w+)", actual + branch)) | {"hdr", "hdr_contrast", "hdr_tonemap"})
    arrays = {"pad_speaker": 12}
    options = "struct Options {\n%s\n};" % "\n".join(
        "    int %s%s{};" % (f, "[%d]" % arrays[f] if f in arrays else "") for f in fields)
    source = ROWS.replace("/* OPTIONS */", options).replace("/* ACTUAL */", actual).replace("/* BRANCH */", branch)
    compile_run(cxx, source, tmp, "rows")
    print("PASS: the HDR rows: Off and Expanded with this game (a saved Native held at Expanded, the tone mapper hidden, "
          "help without Native), all three with the other")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="kirby-hdr-") as tmp:
        check_view(args.cxx, tmp)
        check_rows(args.cxx, tmp)


if __name__ == "__main__":
    main()
