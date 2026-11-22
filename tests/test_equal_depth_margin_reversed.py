"""(inhale) The EQUAL depth margin goes towards the camera under reversed depth too (issue 15, Iris Xe).

On Intel a colour pass that tests EQUAL gets a margin towards the camera (tests/test_equal_depth_margin.py has why):
upstream's margin is LESS_OR_EQUAL with a negative bias, which assumes a smaller depth is nearer. This game draws
reversed depth: its draws that write depth test GREATER_OR_EQUAL. There LESS_OR_EQUAL passes every fragment behind the
depth already drawn, and the ground's colour pass painted over Kirby and the enemies in front of it. This check cuts the
margin out of vk_draw.cpp's dynamic_state, compiles it with stand-ins and runs draws through it: after a draw that
writes depth with GREATER or GREATER_OR_EQUAL, an EQUAL pass becomes GREATER_OR_EQUAL with a positive bias; after one
with LESS or LESS_OR_EQUAL, and before any such draw, it stays LESS_OR_EQUAL with a negative bias, as upstream has it.

python -I -B tests/test_equal_depth_margin_reversed.py --headers <Vulkan-Headers/include> [--cxx g++]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, between   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "gpu" / "vk" / "vk_draw.cpp"

FIXTURE = r'''
#include <vulkan/vulkan_core.h>
#include <atomic>
#include <cstdio>
struct nvn_blend_st { int src_rgb = 0, dst_rgb = 0; };
struct { nvn_blend_st blend[8]; struct { unsigned blend_en = 0; } color; } s;
struct { int n = 1; int color_format[8] = {1}; } at;
struct { struct { float equal_depth_bias = 64.0f; } policy; } dev;
int p;
static unsigned target_write_mask(int, decltype(s)&, int) { return 0xf; }
static VkBlendFactor blend_factor(int) { return VK_BLEND_FACTOR_ONE; }
struct { bool dt, dw; VkCompareOp dop; VkBool32 bias_en; float bias[3]; } d;

static void draw(bool dw, VkCompareOp op) {
    d = {};
    d.dt = true, d.dw = dw, d.dop = op;
    MARGIN
}

static int fails = 0;
static void expect(const char* what, VkCompareOp op, float bias) {
    if (d.dop != op || d.bias[0] != bias || !d.bias_en) {
        std::printf("%s: op %d bias %g, want op %d bias %g\n", what, (int)d.dop, d.bias[0], (int)op, bias);
        fails++;
    }
}

int main() {
    draw(false, VK_COMPARE_OP_EQUAL);
    expect("before any draw that writes depth", VK_COMPARE_OP_LESS_OR_EQUAL, -64.0f);
    draw(true, VK_COMPARE_OP_GREATER_OR_EQUAL);
    draw(false, VK_COMPARE_OP_EQUAL);
    expect("after GREATER_OR_EQUAL writes", VK_COMPARE_OP_GREATER_OR_EQUAL, 64.0f);
    draw(true, VK_COMPARE_OP_ALWAYS);
    draw(false, VK_COMPARE_OP_EQUAL);
    expect("an ALWAYS write tells nothing", VK_COMPARE_OP_GREATER_OR_EQUAL, 64.0f);
    draw(true, VK_COMPARE_OP_LESS_OR_EQUAL);
    draw(false, VK_COMPARE_OP_EQUAL);
    expect("after LESS_OR_EQUAL writes", VK_COMPARE_OP_LESS_OR_EQUAL, -64.0f);
    draw(true, VK_COMPARE_OP_GREATER);
    draw(false, VK_COMPARE_OP_EQUAL);
    expect("after GREATER writes", VK_COMPARE_OP_GREATER_OR_EQUAL, 64.0f);
    draw(true, VK_COMPARE_OP_LESS);
    draw(false, VK_COMPARE_OP_EQUAL);
    expect("after LESS writes", VK_COMPARE_OP_LESS_OR_EQUAL, -64.0f);
    if (fails) return 1;
    std::printf("EQUAL depth margin towards the camera both ways ok\n");
    return 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--headers", type=Path, required=True)
    ap.add_argument("--cxx", default="g++")
    a = ap.parse_args()
    state = block(SOURCE.read_text(encoding="utf-8"), "void dynamic_state(VkCommandBuffer cmd")
    margin = between(state, "{   // (longshot) A colour pass after a depth pass tests EQUAL", "    d.st = stencil && s.ds.st;")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "margin.cpp"
        exe = Path(tmp) / "margin"
        src.write_text(FIXTURE.replace("MARGIN", margin), encoding="utf-8")
        cc = subprocess.run([a.cxx, "-std=c++17", "-O1", "-Wall", "-Werror", "-Wno-unused-variable", "-I", str(a.headers),
                             str(src), "-o", str(exe)], capture_output=True, text=True)
        if cc.returncode:
            raise SystemExit("the margin does not compile with its stand-ins:\n" + cc.stderr[-3000:])
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        sys.stdout.write(run.stdout)
        if run.returncode:
            raise SystemExit("the EQUAL depth margin does not go towards the camera")


if __name__ == "__main__":
    main()
