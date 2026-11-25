"""This game's cameras at the screen's ratio (nx2/kirby_wide.py, host/kirby_wide.c), game-free.

The hook: an aspect of 16:9 in the register becomes hos_wide_ratio, so the projection the game then builds (p00 = p11 /
aspect, main+0x74dd4c) is the one measured in the game at 21:9 (0.8977 at p11 2.1445); another aspect, or a ratio of 0
(a 16:9 screen), is left as the game made it. The install: five sites into the lifter's after-code, none for another
build or code. Also the build id host/hos_main.c lets through (kirby_wide_ok) is the one the lift hooks.

The frustum: the update levels judge an object outside the view by the planes the frustum builder (main+0x627680) makes
from its s0 (vertical angle) and s1 (aspect). A builder shaped like the game's (the hooks the install put at its first
instruction, then the side plane from tan(angle / 2) x aspect) must see a sphere beside the 16:9 view but inside a
32:9 one at 32:9, and not at 16:9.

The HUD and menus: the UI hook (after the ld4 at main+0x85a808, rows in v0 and v1) scales the first row of a projection
still at 16:9 by 16:9 over the ratio: the layouts' orthographic 1920 x 1080 and their 2.5D camera (2.537, 4.511) at 32:9
and 21:9. On a picture narrower than 16:9 (16:10, 4:3) it scales the second row by the ratio over 16:9 and leaves the
first: the layouts keep their shape at the picture's whole width (issue #25: they were left, and the present's squeeze
made them 11% too high at 16:10). A world camera already at the ratio and a 16:9 screen are left.

    python -I -B tests/test_kirby_wide.py [--cc gcc]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import kirby_wide  # noqa: E402

FIXTURE = r'''
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
volatile float hos_wide_ratio;
const char hos_main_build_id[] = BUILD;
void kirby_wide_aspect(uint64_t *v);
void kirby_wide_ui(uint64_t *r0, uint64_t *r1);
int kirby_wide_ok(void);
typedef struct { uint64_t vreg[32][2]; } Ctx;
/* The builder's start with the lift's after-code at main+0x627680, then one side plane: visible when the sphere's
   distance to it is under its radius */
static int builder_sees(Ctx *c, float x, float z, float r) {
    FRUSTUM_HOOK
    float angle, aspect;
    memcpy(&angle, &c->vreg[0][0], 4);
    memcpy(&aspect, &c->vreg[1][0], 4);
    const float h = atanf(tanf(angle * 0.5f) * aspect);
    return x * cosf(h) - z * sinf(h) < r;
}
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "ui")) {   /* ui <ratio> <m00> <m11>: the first row and the second after the hook */
        hos_wide_ratio = (float)atof(argv[2]);
        float r0[4] = {(float)atof(argv[3]), 0.0f, 0.0f, 0.25f}, r1[4] = {0.0f, (float)atof(argv[4]), 0.0f, 0.5f};
        uint64_t v0[2], v1[2];
        memcpy(v0, r0, 16), memcpy(v1, r1, 16);
        kirby_wide_ui(v0, v1);
        memcpy(r0, v0, 16), memcpy(r1, v1, 16);
        printf("%.6f %.4f %.6f %.4f\n", r0[0], r0[3], r1[1], r1[3]);
        return 0;
    }
    if (argc > 1 && !strcmp(argv[1], "frustum")) {
        hos_wide_ratio = (float)atof(argv[2]);
        Ctx c = {{{0}}};
        uint32_t angle = 0x3f5f66f4u, aspect = 0x3fe38e39u;   /* world+0x300's: 50 degrees, 16 / 9 (probed at 32:9) */
        memcpy(&c.vreg[0][0], &angle, 4);
        memcpy(&c.vreg[1][0], &aspect, 4);
        /* at 10 ahead the half-width is 8.29 at 16:9 and 16.58 at 32:9: a sphere of radius 1 at 12 is between */
        printf("%d %d\n", builder_sees(&c, 12.0f, 10.0f, 1.0f), builder_sees(&c, 4.0f, 10.0f, 1.0f));
        return 0;
    }
    hos_wide_ratio = (float)atof(argv[1]);
    float a = (float)atof(argv[2]), p11 = 2.1445f;
    if (argc > 3) a = 16.0f / 9.0f;
    uint64_t v[2] = {0, 0x1234};
    memcpy(v, &a, 4);
    kirby_wide_aspect(v);
    memcpy(&a, v, 4);
    printf("%.4f %.4f %d %llx\n", a, p11 / a, kirby_wide_ok(), (unsigned long long)v[1]);
    return 0;
}
'''


class Lifter:
    def __init__(self):
        self.after = {}


class Image:
    _base = 0x80000000

    def __init__(self, words):
        self.words = words

    def word(self, a):
        return self.words.get(a, 0)


def game_words(base):
    """The words of the build the hooks are written for, at each site"""
    return {**{base + off: old for off, old, _ in kirby_wide.SITES}, base + kirby_wide.UI_SITE[0]: kirby_wide.UI_SITE[1]}


def frustum_hook():
    """The C the install puts after the frustum builder's first instruction, as the fixture's statement"""
    base = 0x80020000
    lifter = Lifter()
    kirby_wide.install(lifter, Image(game_words(base)), base, kirby_wide.BUILD_ID)
    return lifter.after.get(base + 0x627680, "/* no hook */")


def install_checks():
    bad = []
    base = 0x80020000
    good = game_words(base)
    lifter = Lifter()
    lifter.after[base + 0x74dc80] = "/* before */"
    if kirby_wide.install(lifter, Image(good), base, kirby_wide.BUILD_ID) != 5 or len(lifter.after) != 5:
        bad.append("install: %d sites, expected 5" % len(lifter.after))
    if not lifter.after[base + 0x74dc80].startswith("/* before */\n"):
        bad.append("install: the code already after main+0x74dc80 was not kept first")
    for off, _, reg in kirby_wide.SITES:
        if "kirby_wide_aspect(c->vreg[%d])" % reg not in lifter.after.get(base + off, ""):
            bad.append("install: main+%#x does not hand v%d to kirby_wide_aspect" % (off, reg))
    if "kirby_wide_ui(c->vreg[0], c->vreg[1])" not in lifter.after.get(base + kirby_wide.UI_SITE[0], ""):
        bad.append("install: main+%#x does not hand v0 and v1 to kirby_wide_ui" % kirby_wide.UI_SITE[0])
    for what, words, build in (("another build", good, "another"),
                               ("another word", {**good, base + 0x80e20c: 0x1e221800}, kirby_wide.BUILD_ID)):
        lifter = Lifter()
        if kirby_wide.install(lifter, Image(words), base, build) != 0 or lifter.after:
            bad.append("install: %s was hooked" % what)
    return bad


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    bad = install_checks()
    with tempfile.TemporaryDirectory(prefix="kirby-wide-") as tmp:
        exe = Path(tmp) / "fixture.exe"
        (Path(tmp) / "fixture.c").write_text(FIXTURE.replace("FRUSTUM_HOOK", frustum_hook()), encoding="utf-8")
        for build, ok in ((kirby_wide.BUILD_ID, "1"), ("e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348", "0")):
            subprocess.run([args.cc, "-std=c11", "-DBUILD=\"%s\"" % build, str(Path(tmp) / "fixture.c"),
                            str(ROOT / "host/kirby_wide.c"), "-o", str(exe), "-lm"], check=True)
            # (ratio, aspect, [16:9 exactly]) -> aspect after, p00 at p11 2.1445, the build let through, the register's top half
            for argv, expect in (
                (("2.388889", "0", "x"), "2.3889 0.8977 %s 1234" % ok),   # 21:9 (3440 x 1440): the game's p00 at 21:9
                (("3.555556", "0", "x"), "3.5556 0.6031 %s 1234" % ok),   # 32:9 (5120 x 1440)
                (("1.6", "0", "x"), "1.6000 1.3403 %s 1234" % ok),        # 16:10: narrower
                (("0", "0", "x"), "1.7778 1.2063 %s 1234" % ok),          # a 16:9 screen: the game's
                (("2.388889", "1.3333"), "1.3333 1.6084 %s 1234" % ok),   # a camera of its own aspect: left
                (("2.388889", "1.7800"), "1.7800 1.2048 %s 1234" % ok),   # near 16:9 is not 16:9
            ):
                got = subprocess.run([str(exe), *argv], capture_output=True, text=True, check=True).stdout.strip()
                if got != expect:
                    bad.append("build %.8s, ratio %s aspect %s: %s, expected %s" % (
                        build, argv[0], "16/9" if len(argv) > 2 else argv[1], got, expect))
            # (ratio) -> the sphere beside the 16:9 view seen, a sphere inside it seen
            for ratio, expect in (("3.555556", "1 1"), ("0", "0 1"), ("2.388889", "1 1")):
                got = subprocess.run([str(exe), "frustum", ratio], capture_output=True, text=True,
                                     check=True).stdout.strip()
                if got != expect:
                    bad.append("build %.8s, frustum at ratio %s: %s, expected %s" % (build, ratio, got, expect))
            # (ratio, m00, m11) -> m00, m03, m11 and m13 after: the 0.25 in m03 and the 0.5 in m13 scale with their row
            for argv, expect in (
                (("3.555556", "0.0010416667", "0.0018518519"), "0.000521 0.1250 0.001852 0.5000"),   # 32:9: the 1920 x 1080 ortho, halved
                (("3.555556", "2.537270", "4.510710"), "1.268635 0.1250 4.510710 0.5000"),           # 32:9: the 2.5D layout camera
                (("2.388889", "0.0010416667", "0.0018518519"), "0.000775 0.1860 0.001852 0.5000"),   # 21:9: by 1.7778 / 2.3889
                (("3.555556", "1.268635", "4.510710"), "1.268635 0.2500 4.510710 0.5000"),           # a world camera at the ratio: left
                (("0", "0.0010416667", "0.0018518519"), "0.001042 0.2500 0.001852 0.5000"),          # a 16:9 screen: left
                # (a picture narrower than 16:9: the second row by the ratio over 16:9, the first left: the whole width)
                (("1.6", "0.0010416667", "0.0018518519"), "0.001042 0.2500 0.001667 0.4500"),        # 16:10: the ortho, by 0.9
                (("1.6", "2.537270", "4.510710"), "2.537270 0.2500 4.059639 0.4500"),                # 16:10: the 2.5D layout camera
                (("1.333333", "0.0010416667", "0.0018518519"), "0.001042 0.2500 0.001389 0.3750"),   # 4:3: by 0.75
                (("1.333333", "2.537270", "4.510710"), "2.537270 0.2500 3.383032 0.3750"),           # 4:3: the 2.5D layout camera
                (("1.6", "2.819194", "4.510710"), "2.819194 0.2500 4.510710 0.5000"),                # 16:10: a world camera at the ratio: left
                # (under 1% narrower: left, as the renderer leaves the bars and the covers there: gpu/vk/kirby_wide.h axis)
                (("1.765", "0.0010416667", "0.0018518519"), "0.001042 0.2500 0.001852 0.5000"),
            ):
                got = subprocess.run([str(exe), "ui", *argv], capture_output=True, text=True, check=True).stdout.strip()
                if got != expect:
                    bad.append("build %.8s, UI at ratio %s, m00 %s: %s, expected %s" % (build, argv[0], argv[1], got, expect))
    if bad:
        raise SystemExit("FAIL:\n  " + "\n  ".join(bad))
    print("PASS: 16:9 cameras at 21:9, 32:9 and 16:10, others and a 16:9 screen left; the update levels' frustum as wide;"
          " the UI at its 16:9 shape at 32:9, 21:9, 16:10 and 4:3; 5 sites, none for another build or code")


if __name__ == "__main__":
    main()
