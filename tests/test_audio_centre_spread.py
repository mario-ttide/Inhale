"""A 5.1 mix also puts the centre in the front pair, so what is on the centre survives a device that drops it
(host/nn_audio.c; HeyListen c782188b, GPL-3.0).

A headset's virtual surround or a driver can leave the centre channel of a 5.1 output out: what the game mixed there was
silent while the front pair played. The real au_spread_centre and au_centre_spread_on are compiled with a small driver:
in a six-channel mix the centre goes to front left and right at -3 dB as well and every other channel is untouched; a
stereo mix is never changed; HOS_AUDIO_CENTRE=0 (or off, false, no) turns the spread off and 1 leaves it on; unset,
the Audio tab's Centre in front speakers row decides (centre_to_front= in the options file, on without a line).
render_frame is read for the call: after the sink's channel map, before the limiter. No device is opened.

python -I -B tests/test_audio_centre_spread.py [--cxx clang++]
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

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
ENV_ON_H = str(ROOT / "gpu" / "vk" / "compat" / "inhale_env.h")

FIXTURE = r"""
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define FRAME 240
static int ini_centre = -1;   // (the options file's centre_to_front=, -1 no line)
int hos_ini_option(const char *key, int otherwise) {
    return !std::strcmp(key, "centre_to_front") && ini_centre >= 0 ? ini_centre : otherwise;
}
#include "kirby_option.h"
@HELPER@
static void set_env(const char *v) {
#ifdef _WIN32
    _putenv_s("HOS_AUDIO_CENTRE", v ? v : "");
#else
    if (v) setenv("HOS_AUDIO_CENTRE", v, 1);
    else unsetenv("HOS_AUDIO_CENTRE");
#endif
}
static int failed;
static void check(float got, float want, const char *what) {
    if (std::fabs(got - want) > 1e-5f) {
        std::printf("FAIL: %s: %f (want %f)\n", what, got, want);
        failed = 1;
    }
}
static void check_on(const char *v, int want) {
    set_env(v);
    if (au_centre_spread_on() != want) {
        std::printf("FAIL: HOS_AUDIO_CENTRE=%s reads %s\n", v ? v : "(unset)", want ? "off" : "on");
        failed = 1;
    }
}
int main() {
    static float out[6][FRAME], ref[6][FRAME];
    for (int ch = 0; ch < 6; ch++)
        for (int i = 0; i < FRAME; i++) ref[ch][i] = (float)(ch + 1) * 0.01f + (float)i * 0.001f;

    std::memcpy(out, ref, sizeof out);
    au_spread_centre(out, 0, 1);
    for (int ch = 0; ch < 6; ch++)
        for (int i = 0; i < FRAME; i++) check(out[ch][i], ref[ch][i], "a stereo mix changed");

    std::memcpy(out, ref, sizeof out);
    au_spread_centre(out, 1, 0);
    for (int ch = 0; ch < 6; ch++)
        for (int i = 0; i < FRAME; i++) check(out[ch][i], ref[ch][i], "the spread turned off changed the mix");

    std::memcpy(out, ref, sizeof out);
    au_spread_centre(out, 1, 1);
    for (int i = 0; i < FRAME; i++) {
        check(out[0][i], ref[0][i] + 0.7071f * ref[2][i], "front left lacks the centre at -3 dB");
        check(out[1][i], ref[1][i] + 0.7071f * ref[2][i], "front right lacks the centre at -3 dB");
        for (int ch = 2; ch < 6; ch++) check(out[ch][i], ref[ch][i], "a channel past the front pair changed");
    }

    check_on(nullptr, 1);
    check_on("1", 1);
    check_on("0", 0);
    check_on("off", 0);
    // (the Audio tab's Centre in front speakers row, centre_to_front=: read with the variable unset, the variable over it)
    ini_centre = 0;
    check_on(nullptr, 0);
    check_on("1", 1);
    ini_centre = 1;
    check_on(nullptr, 1);
    check_on("0", 0);
    if (!failed) std::puts("ok");
    return failed;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--source", type=Path, default=ROOT / "host/nn_audio.c")
    args = parser.parse_args()
    audio = args.source.read_text(encoding="utf-8")
    helper = (block(audio, "static int au_centre_spread_on(void) {") + "\n"
              + block(audio, "static inline void au_spread_centre(float out[6][FRAME], int six, int on) {"))
    frame = block(audio, "static void render_frame(int16_t *pcm, int channels) {")
    call = "au_spread_centre(out, six, centre_spread);"
    find(frame, call)
    if not frame.index("if (sink_mix >= 0") < frame.index(call) < frame.index("if (lim_enabled)"):
        raise SystemExit("render_frame spreads the centre before the sink's channel map or after the limiter")

    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="audio-centre-spread-") as temporary:
        work = Path(temporary)
        source, exe = work / "fixture.cpp", work / ("fixture.exe" if os.name == "nt" else "fixture")
        source.write_text(FIXTURE.replace("@HELPER@", helper), encoding="utf-8")
        subprocess.run([compiler, "-std=c++17", "-include", ENV_ON_H, "-I", str(ROOT / "host"), "-Wall", "-Wextra",
                        "-Werror", str(source), "-o",
                        str(exe)], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("a 5.1 mix does not spread its centre into the front pair as it should")
    print("PASS: a 5.1 mix spreads its centre to the front pair at -3 dB; stereo untouched; HOS_AUDIO_CENTRE=0 or the menu row's centre_to_front=0 turns it off")


if __name__ == "__main__":
    main()
