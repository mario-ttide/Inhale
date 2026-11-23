"""This game's cameras at the screen's ratio (nx2/kirby_wide.py, host/kirby_wide.c), game-free.

The hook: an aspect of 16:9 in the register becomes hos_wide_ratio, so the projection the game then builds (p00 = p11 /
aspect, main+0x74dd4c) is the one measured in the game at 21:9 (0.8977 at p11 2.1445); another aspect, or a ratio of 0
(a 16:9 screen), is left as the game made it. The install: three sites into the lifter's after-code, none for another
build or code. Also the build id host/hos_main.c lets through (kirby_wide_ok) is the one the lift hooks.

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
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
volatile float hos_wide_ratio;
const char hos_main_build_id[] = BUILD;
void kirby_wide_aspect(uint64_t *v);
int kirby_wide_ok(void);
int main(int argc, char **argv) {
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


def install_checks():
    bad = []
    base = 0x80020000
    good = {base + off: old for off, old, _ in kirby_wide.SITES}
    lifter = Lifter()
    lifter.after[base + 0x74dc80] = "/* before */"
    if kirby_wide.install(lifter, Image(good), base, kirby_wide.BUILD_ID) != 3 or len(lifter.after) != 3:
        bad.append("install: %d sites, expected 3" % len(lifter.after))
    if not lifter.after[base + 0x74dc80].startswith("/* before */\n"):
        bad.append("install: the code already after main+0x74dc80 was not kept first")
    for off, _, reg in kirby_wide.SITES:
        if "kirby_wide_aspect(c->vreg[%d])" % reg not in lifter.after.get(base + off, ""):
            bad.append("install: main+%#x does not hand v%d to kirby_wide_aspect" % (off, reg))
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
        (Path(tmp) / "fixture.c").write_text(FIXTURE, encoding="utf-8")
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
    if bad:
        raise SystemExit("FAIL:\n  " + "\n  ".join(bad))
    print("PASS: 16:9 cameras at 21:9, 32:9 and 16:10, others and a 16:9 screen left; 3 sites, none for another build or code")


if __name__ == "__main__":
    main()
