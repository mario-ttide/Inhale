"""Compile the actual voice calls, queued updates and the mixer's buffer consumption around authored passes, and check
GetVoicePlayedSampleCount (issues #23, #11, #17: the music after a boss).

The game's sound engine sets isEndOfStream on every wave buffer it appends, and takes a voice's position as the start
of the buffer it is on plus the played sample count (0x805a2360). The console's renderer starts the count again when an
end-of-stream buffer finishes, and at Stop; ours counted on from the voice's acquisition, so every position past the
first buffer was too far. The count is also the one of the last update, as the released buffers are.
No game, SDK or output device is used. Run: python -I tests/test_audio_voice_played_count.py [--source <nn_audio.c>]
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ENV_ON_H = str(ROOT / "gpu" / "vk" / "compat" / "inhale_env.h")
APPEND = "_ZN2nn5audio16AppendWaveBufferEPNS0_9VoiceTypeEPKNS0_10WaveBufferE"
STATE = "_ZN2nn5audio17SetVoicePlayStateEPNS0_9VoiceTypeENS1_9PlayStateE"
PLAYED = "_ZN2nn5audio25GetVoicePlayedSampleCountEPKNS0_9VoiceTypeE"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--source", type=Path, default=ROOT / "host/nn_audio.c")
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    constants = []
    for name in ("FRAME", "RATE", "AU_MAGIC", "MAX_VOICES", "MAX_MIXES", "MAX_SPLITTERS", "MAX_SPLIT_DESTS",
                 "MAX_CH", "MAX_BUF", "MAX_WB", "MAX_REL", "MAX_EFFECTS"):
        matches = re.findall(r"^#define " + name + r"\s+[^\n]+", source, re.M)
        assert len(matches) == 1, name
        constants.extend(matches)
    actual = ["\n".join(constants), between(source, "enum { K_VOICE", "static CRITICAL_SECTION lock;"), """
static Voice voices[MAX_VOICES];
static Mix mixes[MAX_MIXES];
static Splitter splitters[MAX_SPLITTERS];
static uint64_t split_bq_epoch;
static int sink_mix = -1;
/* (the samples are not looked at here: only which buffer the mixer is on) */
static void source_frame(Voice *v, const WB *w, int64_t s, float *out) { (void)v; (void)w; (void)s; out[0] = 0; }
static void adpcm_seek(Voice *v, const WB *w) { (void)v; (void)w; }
static int16_t adpcm_sample(Voice *v, const WB *w, int64_t s) { (void)v; (void)w; (void)s; return 0; }
"""]
    # (apply owns the Aux state too: its declarations and reset, as upstream's wave buffer check takes them)
    aux = source.index("typedef struct {", source.index("/* ---- Aux:"))
    actual.append(source[aux:source.index("static int aux_ring_read(", aux)])
    actual.append(block(source, "static void aux_reset("))
    actual.extend(block(source, marker) for marker in (
        "static void put_handle(", "static int get_handle(", "static int voice_index(", "static Voice *voice_of(",
        "static WB read_wb(", "static int wb_in_guest(", "static void release_wb(", "static int next_source_frame("))
    actual.extend([between(source, "enum { OP_VOICE_RELEASE", "static int64_t last_update_ns;"),
                   block(source, "static void apply("), block(source, "static void submit("),
                   block(source, "static void commit(")])
    actual.extend(block(source, "HLE(" + name + ")") for name in (APPEND, STATE, PLAYED))
    flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="audio-voice-played-") as temporary:
        folder = Path(temporary)
        (folder / "actual_audio_voice_played.inc").write_text("\n\n".join(actual), encoding="utf-8")
        executable = folder / "fixture.exe"
        compile_ = [args.cc, "-std=c11", "-include", ENV_ON_H, "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                    "-I" + str(folder), str(ROOT / "tests/audio_voice_played_count_test.c"), "-lm", "-o", str(executable)]
        for command in (compile_, [str(executable)]):
            result = subprocess.run(command, creationflags=flags, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=30)
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            if result.returncode:
                raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
