"""Game-free test of the Depth of field row (gpu/vk/kirby_post.h): the DoF code keys match the three DoF fragment stages
and nothing else on made-up program code strings (the shared vertex stage alone does not), each program is asked once,
vk_draw.cpp leaves a draw out only with the row Off and after RX_VK_SKIP_CODE's block, and the row is hidden only while the
other game runs.

    python -I tests/test_kirby_post.py --cxx clang++
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
#include "kirby_post.h"
using namespace mkwvk;

int main() {
    // (program_code_keys' " <stage>:<key>" strings; the vertex stage 20c3d9b7a221506d is DoF's own but alone is not a match)
    assert(skip_code::matches(" 0:20c3d9b7a221506d 1:976a0ce23a971ed0", kirby_post::kDofCodes));
    assert(skip_code::matches(" 0:20c3d9b7a221506d 1:912173d38909e3fd", kirby_post::kDofCodes));
    assert(skip_code::matches(" 0:20c3d9b7a221506d 1:3FE01C0D0629E41F", kirby_post::kDofCodes));
    assert(!skip_code::matches(" 0:20c3d9b7a221506d 1:70a47a2c6cd6f415", kirby_post::kDofCodes));
    assert(!skip_code::matches(" 0:70a47a2c6cd6f415 1:03a2f72e86791140", kirby_post::kDofCodes));
    assert(!skip_code::matches(" 5:976a0ce23a971ed", kirby_post::kDofCodes));   // (a key cut short is not the key)
    assert(!skip_code::matches("", kirby_post::kDofCodes));
    // (asked once a program, the answer kept)
    int asked = 0;
    auto dof = [&] { asked++; return std::string(" 0:20c3d9b7a221506d 1:976a0ce23a971ed0"); };
    auto other = [&] { asked++; return std::string(" 0:70a47a2c6cd6f415 1:03a2f72e86791140"); };
    assert(kirby_post::is_dof(0x0383c5894eee303dull, dof) && kirby_post::is_dof(0x0383c5894eee303dull, dof) && asked == 1);
    assert(!kirby_post::is_dof(0x1111ull, other) && !kirby_post::is_dof(0x1111ull, other) && asked == 2);
    puts("ok");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()

    # (vk_draw.cpp: after RX_VK_SKIP_CODE's block, before the waits; Off only)
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    after_skip = between(draw, 'static const char* skip_code_list = getenv("RX_VK_SKIP_CODE");',
                         "// Wait for translation before reading its stages.")
    assert "if (!opts.dof && kirby_post::is_dof(cp->key, [&] { return program_code_keys(s); })) return;" in after_skip, \
        "vk_draw.cpp: the Depth of field row's skip is not after RX_VK_SKIP_CODE's block"
    # (the row, a module's (gpu/vk/menu/kirby_dof.cpp): an On/Off toggle in the Detail section, On by default (vk_menu.h);
    # vk_menu.cpp hides it only for the other game)
    module = (ROOT / "gpu/vk/menu/kirby_dof.cpp").read_text(encoding="utf-8")
    row = between(module, '.key = "depth_of_field",', "},")
    for field in ('.label = "Depth of field",', ".kind = menu::Kind::Toggle,", ".value = &opts.dof,", ".lo = 0, .hi = 1,"):
        assert field in row, "kirby_dof.cpp: the row lost %s" % field
    assert '.section("detail")' in module and 'menu::before("shadow_resolution")' in module, \
        "kirby_dof.cpp: the row is not in the Detail section before Shadow resolution"
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    assert "int dof = 1;" in (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
    assert "bool kirby_row(const Row& r) {\n    return r.value == &opts.dof ||" in menu
    shown = block(menu, "bool row_shown(int i) {")
    assert "(!kirby_row(rows[i]) || oot_game.load(std::memory_order_relaxed) != 1)" in shown, \
        "row_shown: the Depth of field row is not hidden for the other game"
    assert "v == &opts.dof" not in block(menu, "bool is_oot_row(const Row& r) {"), "the row must not be one of the other game's"

    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.cpp"
        test.write_text(FIXTURE, encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Werror", "-I", str(ROOT / "gpu/vk"), str(test), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        assert out.returncode == 0 and out.stdout.strip() == "ok", out.stdout + out.stderr
    print("test_kirby_post: ok")


if __name__ == "__main__":
    main()
