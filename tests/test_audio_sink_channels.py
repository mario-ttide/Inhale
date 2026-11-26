"""The output opens stereo when the game's device sink has two inputs, whatever the speakers (host/nn_audio.c, issue #28).

This game's sound engine adds its device sink with two inputs (FL FR) and pans in stereo even with 5.1 speakers: it
never asks for the speakers (GetActiveAudioDeviceChannelCountForOutput). Opened 5.1, the device played the game from
its front pair alone; opened stereo, Windows or a receiver can spread it. The real au_out_channels is compiled with a
small driver and asked: 5.1 speakers with a two-input sink open stereo, with a six-input sink (upstream's game) 5.1;
stereo speakers stay stereo; no sink yet keeps the speakers. output_open and output_retry_named are read for the call,
and renderer_main for the output opening once the renderer runs (after the game added its sink), not when it opens.
The down-mix calls the game makes on its sink are implemented (no "unimplemented import" in the log). No device is
opened.

python -I -B tests/test_audio_sink_channels.py [--cxx clang++]   (--cxx cl: MSVC, from a developer prompt)
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, find   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <cstdio>
#include <cstdlib>
@HELPER@
int main(int argc, char **argv) {
    int failed = 0;
    for (int i = 1; i + 2 < argc; i += 3) {
        const int speakers = atoi(argv[i]), sink = atoi(argv[i + 1]), want = atoi(argv[i + 2]);
        const int got = au_out_channels(speakers, sink);
        if (got != want) {
            std::printf("FAIL: %d speakers, a sink of %d inputs: the device opens %d channels (want %d)\n",
                        speakers, sink, got, want);
            failed = 1;
        }
    }
    return failed;
}
"""

# (the game's speakers, its device sink's inputs (0: none yet), the device's channels)
CASES = (
    (6, 2, 2),   # this game with 5.1 chosen (issue #28)
    (6, 6, 6),   # upstream's game: six inputs, 5.1
    (6, 1, 2),   # a mono sink
    (6, 0, 6),   # no sink yet: the speakers
    (2, 2, 2),   # stereo
    (2, 6, 2),   # stereo speakers, six inputs: mixed down as before
)

HLES = (
    "HLE(_ZN2nn5audio19SetDownMixParameterEPNS0_14DeviceSinkTypeEPKNS1_16DownMixParameterE)",
    "HLE(_ZN2nn5audio26SetDownMixParameterEnabledEPNS0_14DeviceSinkTypeEb)",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()

    path = ROOT / "host/nn_audio.c"
    audio = path.read_text(encoding="utf-8")
    helper = block(audio, "static int au_out_channels(int speakers, int sink_inputs) {", where=path)
    for name in ("static void output_open(void) {", "static void output_retry_named(void) {"):
        body = block(audio, name, where=path)
        assert "au_out_channels(au_speakers(), sink_n)" in body, f"{name[12:-6]} opens the device without au_out_channels"
    main_loop = block(audio, "static DWORD WINAPI renderer_main(void *p) {", where=path)
    running = find(main_loop, "if (!renderer_running) continue;", where=path)
    opens = [i for i in range(len(main_loop)) if main_loop.startswith("output_open()", i)]
    assert len(opens) == 1 and opens[0] > running, \
        "renderer_main opens the output before the renderer runs: the game's device sink is not known yet"
    for hle in HLES:
        assert hle in audio, f"host/nn_audio.c lacks {hle}"
    with tempfile.TemporaryDirectory(prefix="audio-sink-channels-") as tmp:
        work = Path(tmp)
        source, exe = work / "fixture.cpp", work / "fixture.exe"
        source.write_text(FIXTURE.replace("@HELPER@", helper), encoding="utf-8")
        if os.path.splitext(os.path.basename(args.cxx))[0].lower() == "cl":
            command = [args.cxx, "/nologo", "/std:c++17", "/W4", "/WX", "/EHsc", str(source), "/Fe:" + str(exe),
                       "/Fo:" + str(work) + os.sep]
        else:
            command = [args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)]
        subprocess.run(command, check=True, cwd=work)
        subprocess.run([str(exe)] + [str(v) for case in CASES for v in case], check=True)
    print("PASS: a two-input device sink opens the output stereo with 5.1 speakers; six inputs 5.1; the down-mix calls are HLEs")


if __name__ == "__main__":
    main()
