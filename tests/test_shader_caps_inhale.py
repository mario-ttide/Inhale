"""The translator puts 8- and 16-bit integers in a program only where the device has them (gpu/vk/shader_caps_inhale.h;
HeyListen 6f82d229, GPL-3.0).

upstream's profile (gpu/vk/vk_shader.cpp make_profile) says every device has shaderInt8 and shaderInt16, so a program that
used them declared the capability whatever the GPU, and such a module is invalid on a device without them
(VUID-VkShaderModuleCreateInfo-pCode-08740). The header is compiled with the Vulkan headers and checked: a device with both
gives both and no stamp word; each one missing turns that one off alone and sets its own bit. vk_shader.cpp is read for the
use: make_profile takes the two from it after upstream's defaults, and translator_stamp adds the word only when it is not
0 (so every GPU that has both keeps its program cache). (The 32-bit denorm modes are upstream's own since v3.1.1.)

python -I -B tests/test_shader_caps_inhale.py --headers <folder holding vulkan/vulkan.h> [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, find   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <cstdio>
#include "shader_caps_inhale.h"
static int bad;
static void check(bool ok, const char *what) { if (!ok) { std::printf("FAIL: %s\n", what); bad = 1; } }
struct Dev { VkPhysicalDeviceFeatures f{}; VkPhysicalDeviceVulkan12Features f12{}; };
static Dev all() {
    Dev d;
    d.f.shaderInt16 = VK_TRUE;
    d.f12.shaderInt8 = VK_TRUE;
    return d;
}
static InhaleShaderCaps caps(const Dev &d) { return inhale_shader_caps(d.f, d.f12); }
int main() {
    InhaleShaderCaps c = caps(all());
    check(c.int8 && c.int16, "a device with both gives both");
    check(c.missing() == 0, "a device with both adds no stamp word");

    Dev d = all();
    d.f12.shaderInt8 = VK_FALSE;
    c = caps(d);
    check(!c.int8 && c.int16 && c.missing() == 1, "no shaderInt8: Int8 off alone");
    d = all();
    d.f.shaderInt16 = VK_FALSE;
    c = caps(d);
    check(c.int8 && !c.int16 && c.missing() == 2, "no shaderInt16: Int16 off alone");
    c = caps(Dev{});
    check(!c.int8 && !c.int16 && c.missing() == 3, "a device with none: none");
    if (!bad) std::puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--headers", required=True, help="folder holding vulkan/vulkan.h")
    args = parser.parse_args()

    src = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8")
    profile = block(src, "Shader::Profile make_profile() {")
    caps = "const InhaleShaderCaps caps = inhale_shader_caps(dev.features, dev.vk12);"
    use = "p.support_int8 = caps.int8, p.support_int16 = caps.int16;"
    find(profile, use)
    if not profile.index("p.support_int8 = p.support_int16 = p.support_int64 = true;") < profile.index(caps) < profile.index(use):
        raise SystemExit("make_profile: the device's caps are not taken after upstream's defaults: " + use)
    stamp = block(src, "uint64_t translator_stamp() {")
    word = "if (const uint32_t missing = inhale_shader_caps(dev.features, dev.vk12).missing()) {"
    added = block(stamp, word)
    find(added, "add(narrow, sizeof narrow);")
    if "narrow" in stamp.replace(added, ""):
        raise SystemExit("translator_stamp: the caps' word is added outside its condition: every GPU's stamp would change")

    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="shader-caps-") as temporary:
        work = Path(temporary)
        source, exe = work / "fixture.cpp", work / ("fixture.exe" if os.name == "nt" else "fixture")
        source.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu/vk"), "-I", args.headers,
                        str(source), "-o", str(exe)], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("the translator's 8- and 16-bit integers do not follow the device")
    print("PASS: Int8 and Int16 follow the device; the stamp changes only where one is missing")


if __name__ == "__main__":
    main()
