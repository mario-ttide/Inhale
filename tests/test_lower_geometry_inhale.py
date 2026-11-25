"""The Ampere -> Maxwell lowering takes a geometry stage's own instructions (frontend/ampere/geometry_inhale.h).

Every geometry code of Kirby and the Forgotten Land stopped at its first instruction, "unsupported native opcode" (op
0x34e), so six mouthful forms and the stage decorations were drawn without the stage (issue #27). The code words here are
made up after their shape:

    LEPC R0 (0x34e); BMOV.64 <at exit>, R0 (0x357)      an EXIT then goes through the handler at the code's end
    ISBERD R3, [R5] (0x923, the map region)             an input vertex's handle from its number
    OUT R0, R0, RZ (0x324), bits 78-79 emit / cut       a vertex emitted, the strip ended
    EXIT; then the handler: OUT RZ, R0, RZ (neither); 0x957; EXIT

LEPC is a MOV of 0, the BMOV is nothing (the handler only ends the stream), ISBERD is Maxwell's (the handle is the vertex's
number) and OUT is Maxwell's OUT with stream 0. Refused as before: a handler that does more, a stream that is a register,
an OUT that neither emits nor cuts in the main code. The renderer's capture (vk_shader.cpp parse_code, cut from the source)
hands a geometry stage's code over whole: stopped at the EXIT as the other stages', the handler was not there to look at,
and every geometry code was refused at its BMOV.64.
python -I -B tests/test_lower_geometry_inhale.py [--cxx clang++]
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from srccut import between   # noqa: E402

FIXTURE = r'''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <string>
#include <vector>
#include <cstring>
#include "shader_recompiler/frontend/ampere/program_capture.h"
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
using Shader::Ampere::Instruction;
static Instruction insn(uint32_t a, uint32_t b = 0, uint32_t c = 0, uint32_t d = 0) { Instruction i{}; i.words[0] = a; i.words[1] = b; i.words[2] = c; i.words[3] = d; return i; }
static const Instruction lepc = insn(0x0000734e);                       // LEPC R0
static const Instruction bmov = insn(0x00007357);                       // BMOV.64 <at exit>, R0
static const Instruction handle = insn(0x05037923);                     // ISBERD R3, [R5]
static const Instruction emit_vertex = insn(0x00007324, 0xff, 0x4000);  // OUT R0, R0, RZ: emit
static const Instruction cut = insn(0x00007324, 0xff, 0x8000);          // cut
static const Instruction stream_end = insn(0x00ff7324, 0xff, 0);        // OUT RZ, R0, RZ: neither (the handler's)
static const Instruction at_exit_clear = insn(0x00007957);
static const Instruction exit_insn = insn(0x0000794d, 0, 0x03800000, 0x000fea00);   // EXIT
static const uint64_t pt = 7ULL << 16;
static std::string lower(const std::vector<Instruction>& code, std::vector<uint64_t>* words = nullptr) {
    const auto r = Shader::Ampere::LowerToMaxwell(code);
    if (words) *words = r.instructions;
    return std::string(r.error);
}
static std::vector<Instruction> captured(const std::vector<uint8_t>& area, unsigned st) {
    const uint32_t hdr = 0, len = static_cast<uint32_t>(area.size());
    std::vector<Instruction> native;
    Shader::Ampere::ProgramCaptureState capture;
@CAPTURE@
    return native;
}
int main() {
    {   // the whole shape
        std::vector<uint64_t> w;
        const std::string why = lower({lepc, bmov, handle, emit_vertex, cut, exit_insn, stream_end, at_exit_clear, exit_insn}, &w);
        if (!why.empty()) std::fprintf(stderr, "FAIL: a geometry code does not lower: %s\n", why.c_str());
        CHECK(why.empty());
        CHECK(w.size() == 5);
        CHECK(w[0] == (0x0100000000000000ULL | pt | (15ULL << 12)));            // MOV32I R0, 0
        CHECK(w[1] == (0xefd0000000000000ULL | pt | 3 | (5ULL << 8)));          // ISBERD R3, [R5]
        CHECK(w[2] == (0xf6e0000000000000ULL | pt | (1ULL << 39)));             // OUT R0, R0, 0: emit
        CHECK(w[3] == (0xf6e0000000000000ULL | pt | (1ULL << 40)));             // cut
        CHECK((w[4] >> 52) == 0xe30);                                           // EXIT
    }
    {   // emit and cut in one, under a predicate (P2)
        std::vector<uint64_t> w;
        CHECK(lower({lepc, bmov, insn(0x00002324, 0xff, 0xc000), exit_insn, stream_end, at_exit_clear, exit_insn}, &w).empty());
        CHECK(w.size() == 3 && w[1] == (0xf6e0000000000000ULL | (2ULL << 16) | (3ULL << 39)));
    }
    const std::string unsupported = "unsupported native opcode";
    // no handler, or one that does more than end the stream: setting it is refused
    CHECK(lower({lepc, bmov, exit_insn}) == unsupported);
    CHECK(lower({lepc, bmov, exit_insn, emit_vertex, at_exit_clear, exit_insn}) == unsupported);
    CHECK(lower({lepc, bmov, exit_insn, stream_end, at_exit_clear, emit_vertex, exit_insn}) == unsupported);
    // a stream that is a register (R4), and an OUT that neither emits nor cuts in the main code
    CHECK(lower({insn(0x00007324, 0x04, 0x4000), exit_insn}) == unsupported);
    CHECK(lower({stream_end, exit_insn}) == unsupported);
    CHECK(lower({insn(0x00007324, 0xff, 0), exit_insn}) == unsupported);
    // ISBERD in the map region with an offset: neither this form nor the task and mesh one
    CHECK(lower({insn(0x05037923, 0x00001000), exit_insn}) == "native stage buffer access mode");
    {   // as the renderer hands a stage's code over (vk_shader.cpp parse_code's capture, cut from the source): a geometry
        // stage whole, with the handler after its EXIT; any other stage to its EXIT, as before
        const std::vector<Instruction> code{lepc, bmov, handle, emit_vertex, cut, exit_insn, stream_end, at_exit_clear, exit_insn};
        std::vector<uint8_t> area(code.size() * sizeof(Instruction));
        std::memcpy(area.data(), code.data(), area.size());
        const std::vector<Instruction> geometry = captured(area, 2), vertex = captured(area, 0);
        CHECK(geometry.size() == 9 && lower(geometry).empty());
        CHECK(vertex.size() == 6);
    }
    std::printf("PASS: a geometry stage's LEPC, BMOV.64, ISBERD and OUT lower\n");
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default=shutil.which("clang++") and "clang++" or "g++")
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="lower-geometry-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        shader = (ROOT / "gpu" / "vk" / "vk_shader.cpp").read_text(encoding="utf-8")
        capture = between(shader, "    uint32_t outside = ~0u;   // (that word's instruction number)",
                          "    {   // (longshot, for bisecting a bad translation)")
        cpp.write_text(FIXTURE.replace("@CAPTURE@", capture), encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wno-everything" if "clang" in a.cxx else "-w",
                        "-I" + str(ROOT / "gpu" / "vk" / "eden"), "-I" + str(ROOT / "gpu" / "vk" / "compat"),
                        str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
