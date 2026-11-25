"""A program's geometry stage reaches its key, its record and its translation (gpu/vk/vk_shader.cpp program_pick).

A program with a geometry stage (NVN stage 2) was keyed and translated by its vertex and fragment stages alone, and drawn
without the stage: six mouthful forms of Kirby and the Forgotten Land were drawn without the sums their geometry stage
adds to a storage buffer (issue #27).
Cut from the source: graphics_key, program_pick and geometry_stage_inhale.h's geometry_code and geometry_key, with stand-ins for what they
call. Checked:

  - a program with a geometry stage has another key than the same stages without it, and than with another geometry code;
    its record's third code is the stage's; the translation gets the stage (on the draw's thread, and as a queued job)
  - a program without one keeps the key and the record it had, so no kept program is translated again
  - a device without the geometryShader feature draws as before: the old key, no third code, the "dropped stages" line
python -I -B tests/test_geometry_stage_key_inhale.py [--cxx clang++]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from srccut import between, block   # noqa: E402

FIXTURE = r'''
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <functional>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vector>

#define PROF_EXACT()
enum class ProgramKind { Graphics, Compute, Mesh };
namespace Shader { enum class AttributeType { Float, SignedInt, UnsignedInt }; }
struct Code { uint64_t key = 0; int stage = 0; bool header_only = false; };
using SharedCode = std::shared_ptr<const Code>;
struct NvnState { uint32_t vattr[16]{}; std::vector<SharedCode> cs; };
struct Program {
    uint64_t key = 0;
    bool compute = false, failed = false, scene_tonemap = false;
    std::atomic<bool> ready{false};
    uint64_t codes[4]{};
};
struct { struct { bool geometryShader = true; } features; } dev;
std::mutex shader_mu;
std::unordered_map<uint64_t, std::vector<std::unique_ptr<Program>>> programs;
std::atomic<int64_t> st_translate_wait_ns;
static bool sync_shaders = true;
static int dropped = 0;
const std::vector<SharedCode>& codes_of(const NvnState& s) { return s.cs; }
void log_program_stages(const NvnState&, const char*) { dropped++; }
bool scene_tonemap_for(const Code*) { return false; }
void program_cache_load(uint64_t, std::vector<std::unique_ptr<Program>>&) {}
bool still_valid(const NvnState&, const Program&) { return true; }
void miss_note(uint64_t, const char*, uint64_t, uint64_t, const NvnState&, const uint8_t*, size_t) {}
bool env_on(const char*) { return sync_shaders; }
// (the key's parts, as plain as they can be: a vertex stage that reads no attribute, a fragment stage that writes no target)
struct Header { struct { std::array<bool, 4> InputGeneric(size_t) const { return {}; } } vtg; };
const Header& header_of(const Code&) { static const Header h; return h; }
Shader::AttributeType attribute_type_of(uint32_t) { return Shader::AttributeType::Float; }
void written_types(const Code*, const uint8_t*, uint8_t out[8]) { std::memset(out, 0, 8); }
uint64_t hash_bytes(const void* data, size_t n, uint64_t h = 1469598103934665603ull) {
    for (size_t i = 0; i < n; i++) h = (h ^ static_cast<const uint8_t*>(data)[i]) * 1099511628211ull;
    return h;
}
static const Code *seen_vs, *seen_fs, *seen_gs;
static int translations = 0;
void translate_into(Program& p, const NvnState&, const Code* vs, const Code* fs, const Code*, const uint8_t*, const Code* gs = nullptr) {
    seen_vs = vs, seen_fs = fs, seen_gs = gs, translations++;
    p.ready.store(true);
}
static std::function<void()> pending;
void jobs_push(std::function<void()> work, bool, std::atomic<bool>*, std::function<void()>) { pending = std::move(work); }
@GEOMETRY_CODE@
@GRAPHICS_KEY@
@PROGRAM_PICK@
#define CHECK(c) do { if (!(c)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #c); return 1; } } while (0)
static SharedCode code(uint64_t key, int stage) { return std::make_shared<const Code>(Code{key, stage, false}); }
int main(int argc, char**) {
    sync_shaders = argc < 2;   // (an argument: the queued job's path)
    const uint8_t types[8]{};
    const SharedCode vs = code(0x1111, 0), fs = code(0x2222, 1), gs = code(0x3333, 2), other = code(0x4444, 2);
    const auto pick = [&](std::vector<SharedCode> cs) {
        NvnState s;
        s.cs = std::move(cs);
        seen_vs = seen_fs = seen_gs = nullptr;
        const Program* p = program_pick(s, ProgramKind::Graphics, types);
        if (pending) pending(), pending = {};
        return p;
    };
    const Program* plain = pick({vs, fs});
    CHECK(plain && translations == 1 && seen_vs == vs.get() && seen_fs == fs.get() && !seen_gs);
    CHECK(plain->key == graphics_key(*vs, fs.get(), NvnState{}.vattr, types));   // (the key such a program had)
    CHECK(plain->codes[0] == 0x1111 && plain->codes[1] == 0x2222 && !plain->codes[2] && !plain->codes[3]);

    const Program* with = pick({vs, fs, gs});
    CHECK(with && translations == 2 && seen_vs == vs.get() && seen_fs == fs.get() && seen_gs == gs.get());
    CHECK(with != plain && with->key != plain->key);
    CHECK(with->codes[0] == 0x1111 && with->codes[1] == 0x2222 && with->codes[2] == 0x3333 && !with->codes[3]);
    CHECK(!dropped);

    const Program* another = pick({vs, fs, other});
    CHECK(another && translations == 3 && seen_gs == other.get() && another->key != with->key && another->key != plain->key);
    CHECK(pick({vs, fs, gs}) == with && translations == 3);   // (the same stages again: the program made for them)

    dev.features.geometryShader = false;   // (a device without the feature: as before the stage was translated)
    const Program* without = pick({vs, fs, gs});
    CHECK(without == plain && translations == 3 && dropped == 1);
    std::printf("PASS: a geometry stage is in its program's key, record and translation (%s)\n", sync_shaders ? "on the draw's thread" : "a queued job");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    shader = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8")
    stage = (ROOT / "gpu/vk/geometry_stage_inhale.h").read_text(encoding="utf-8")
    text = (FIXTURE.replace("@GEOMETRY_CODE@", between(stage, "/// The geometry code this device runs", "void dump_ir("))
            .replace("@GRAPHICS_KEY@", block(shader, "uint64_t graphics_key(const Code& vs, const Code* fs, const uint32_t vattr[16], "
                                                     "const uint8_t color_types[8],"))
            .replace("@PROGRAM_PICK@", block(shader, "const Program* program_pick(const NvnState& s, ProgramKind kind, "
                                                     "const uint8_t color_types[8]) {")))
    with tempfile.TemporaryDirectory(prefix="geometry-key-") as tmp:
        cpp, exe = Path(tmp) / "test.cpp", Path(tmp) / "test"
        cpp.write_text(text, encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
        subprocess.run([str(exe), "job"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
