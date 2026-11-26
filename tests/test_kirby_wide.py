"""This game's cameras at the screen's ratio (nx2/kirby_wide.py, host/kirby_wide.c), game-free.

The hook: an aspect of 16:9 in the register becomes hos_wide_ratio, so the projection the game then builds (p00 = p11 /
aspect, main+0x74dd4c) is the one measured in the game at 21:9 (0.8977 at p11 2.1445); another aspect, or a ratio of 0
(a 16:9 screen), is left as the game made it. The install: six sites into the lifter's after-code, none for another
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

The 2D effects (issue #20, the reporter's last shots): a script hands the effect system each view's projection in memory
(main+0x776334: x1 points at it, 4 x 4 by columns, the view after it). The title's sparkles and a button's stars take
the layouts' orthographic 1920 x 1080 there, a deleted file's explosion their 2.5D camera, neither through the UI
hook's place, so they were drawn over the whole 16:9 window texture and the present stretched them 2 times at 32:9.
The C the install puts after that instruction, run on a guest memory stand-in, must scale the projection's first row
(its second on a narrower picture) as the UI hook does, write nothing else of the block and nothing at all for a world
camera's view or on a 16:9 screen.

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
typedef struct { uint64_t x[32]; uint64_t vreg[32][2]; } Ctx;
/* Guest memory from 0x5000 for the effect view's hook, and how many words it stored */
static uint8_t guest[256];
static int stores;
static uint64_t recomp_load32(Ctx *c, uint64_t a) { uint32_t v; (void)c; memcpy(&v, guest + (a - 0x5000), 4); return v; }
static void recomp_store32(Ctx *c, uint64_t a, uint32_t v) { (void)c; memcpy(guest + (a - 0x5000), &v, 4); stores++; }
/* The lift's after-code at main+0x776334: x1 is the script's block, the projection by columns and the view after it */
static void fx_site(Ctx *c) {
    (void)c, (void)recomp_load32, (void)recomp_store32;
    FX_HOOK
}
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
    if (argc > 1 && !strcmp(argv[1], "fx")) {   /* fx <ratio> <m00> <m11>: m00, m03, m11, m13, m02, m12 after, words changed outside the two rows, stores */
        hos_wide_ratio = (float)atof(argv[2]);
        float m[20], n[20];
        for (int i = 0; i < 20; i++) m[i] = 100.0f + (float)i;
        m[0] = (float)atof(argv[3]), m[4] = 0.0f, m[8] = 0.5f, m[12] = 0.25f;   /* (the first row: every fourth from 0) */
        m[1] = 0.0f, m[5] = (float)atof(argv[4]), m[9] = 0.75f, m[13] = 0.5f;   /* (the second: every fourth from 1) */
        memcpy(guest + 0x20, m, sizeof m);
        Ctx c;
        memset(&c, 0, sizeof c);
        c.x[1] = 0x5020;
        fx_site(&c);
        memcpy(n, guest + 0x20, sizeof n);
        int others = 0;
        for (int i = 0; i < 20; i++) others += (i >= 16 || (i & 3) > 1) && n[i] != m[i];
        printf("%.6f %.4f %.6f %.4f %.4f %.4f %d %d\n", n[0], n[12], n[5], n[13], n[8], n[9], others, stores);
        return 0;
    }
    if (argc > 1 && !strcmp(argv[1], "frustum")) {
        hos_wide_ratio = (float)atof(argv[2]);
        Ctx c;
        memset(&c, 0, sizeof c);
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


FX_AT, FX_WORD = 0x776334, 0xf9400921   # ldr x1, [x9, #0x10]   (the script's block for an effect view, as probed)


def game_words(base):
    """The words of the build the hooks are written for, at each site"""
    return {**{base + off: old for off, old, _ in kirby_wide.SITES}, base + kirby_wide.UI_SITE[0]: kirby_wide.UI_SITE[1],
            base + FX_AT: FX_WORD}


def hook_at(off):
    """The C the install puts after the instruction at main+off, as the fixture's statement"""
    base = 0x80020000
    lifter = Lifter()
    kirby_wide.install(lifter, Image(game_words(base)), base, kirby_wide.BUILD_ID)
    return lifter.after.get(base + off, "/* no hook */")


def install_checks():
    bad = []
    base = 0x80020000
    good = game_words(base)
    lifter = Lifter()
    lifter.after[base + 0x74dc80] = "/* before */"
    if kirby_wide.install(lifter, Image(good), base, kirby_wide.BUILD_ID) != 6 or len(lifter.after) != 6:
        bad.append("install: %d sites, expected 6" % len(lifter.after))
    if not lifter.after[base + 0x74dc80].startswith("/* before */\n"):
        bad.append("install: the code already after main+0x74dc80 was not kept first")
    for off, _, reg in kirby_wide.SITES:
        if "kirby_wide_aspect(c->vreg[%d])" % reg not in lifter.after.get(base + off, ""):
            bad.append("install: main+%#x does not hand v%d to kirby_wide_aspect" % (off, reg))
    if "kirby_wide_ui(c->vreg[0], c->vreg[1])" not in lifter.after.get(base + kirby_wide.UI_SITE[0], ""):
        bad.append("install: main+%#x does not hand v0 and v1 to kirby_wide_ui" % kirby_wide.UI_SITE[0])
    if "c->x[1]" not in lifter.after.get(base + FX_AT, ""):
        bad.append("install: main+%#x does not take the effect view's block at x1" % FX_AT)
    for what, words, build in (("another build", good, "another"),
                               ("another word", {**good, base + 0x80e20c: 0x1e221800}, kirby_wide.BUILD_ID),
                               ("another word at the effect view's site", {**good, base + FX_AT: 0xf9400922}, kirby_wide.BUILD_ID)):
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
        (Path(tmp) / "fixture.c").write_text(FIXTURE.replace("FRUSTUM_HOOK", hook_at(0x627680)).replace("FX_HOOK", hook_at(FX_AT)),
                                             encoding="utf-8")
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
            # (ratio, m00, m11) -> m00, m03, m11 and m13 after, m02 and m12 (0.5 and 0.75 before: every word of a row is
            # scaled), words changed outside the two rows, words stored (a row's three that are not 0)
            for argv, expect in (
                (("3.555556", "0.0010416667", "0.0018518519"), "0.000521 0.1250 0.001852 0.5000 0.2500 0.7500 0 3"),   # 32:9: the title's sparkles (ortho)
                (("3.555556", "2.537270", "4.510710"), "1.268635 0.1250 4.510710 0.5000 0.2500 0.7500 0 3"),           # 32:9: a deleted file's explosion (2.5D)
                (("2.388889", "0.0010416667", "0.0018518519"), "0.000775 0.1860 0.001852 0.5000 0.3721 0.7500 0 3"),   # 21:9
                (("3.555556", "0.603142", "2.144510"), "0.603142 0.2500 2.144510 0.5000 0.5000 0.7500 0 0"),           # the world's effects, at the ratio: left
                (("0", "0.0010416667", "0.0018518519"), "0.001042 0.2500 0.001852 0.5000 0.5000 0.7500 0 0"),          # a 16:9 screen: left
                (("1.6", "0.0010416667", "0.0018518519"), "0.001042 0.2500 0.001667 0.4500 0.5000 0.6750 0 3"),        # 16:10: the second row
                (("1.333333", "2.537270", "4.510710"), "2.537270 0.2500 3.383032 0.3750 0.5000 0.5625 0 3"),           # 4:3
            ):
                got = subprocess.run([str(exe), "fx", *argv], capture_output=True, text=True, check=True).stdout.strip()
                if got != expect:
                    bad.append("build %.8s, effect view at ratio %s, m00 %s: %s, expected %s" % (build, argv[0], argv[1], got, expect))
    if bad:
        raise SystemExit("FAIL:\n  " + "\n  ".join(bad))
    print("PASS: 16:9 cameras at 21:9, 32:9 and 16:10, others and a 16:9 screen left; the update levels' frustum as wide;"
          " the UI and the 2D effects' views at their 16:9 shape at 32:9, 21:9, 16:10 and 4:3; 6 sites, none for another build"
          " or code")


if __name__ == "__main__":
    main()
