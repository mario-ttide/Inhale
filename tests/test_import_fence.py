"""(inhale) A host-memory import's region ends with its range while the driver is asked (gpu/vk/import_fence_inhale.h;
upstream's PR #334, GPL-3.0).

On Windows the fixture runs the fence on real pages: VirtualQuery from the range's start reports the whole run of
read-write pages without it and the range alone with it, the page gets its protection back, and a reserved or
read-only page after the range is left as it is. Elsewhere it checks that the header builds and does nothing.

On Windows a second fixture takes the game's first-touch handler as it is (host/mkw_glue.c commit_on_touch) and delivers
it a data fault on the page the real fence holds, as when a guest thread faulted on that page just before another thread
committed it and the importer fenced it: the access is tried again (EXCEPTION_CONTINUE_EXECUTION), with the fence and
after it. An execute fault there, a guard page and a write watch's read-only page are not tried again.
No Vulkan or game data. That the import's questions to the driver, its memory types and its allocation, are made behind
the fence, and a dma-buf's without one, is tests/import_buffer_binding_test.cpp's.
python -I -B tests/test_import_fence.py [--cxx g++]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

# (Windows: the game's first-touch handler as it is, with stand-ins for what it calls; the guest window starts 2 MB below the
# pages, so that their guest addresses are past the null-pointer page the handler leaves to the game)
FIRST_TOUCH = r"""
#include "import_fence_inhale.h"
#include <cstdint>
#include <cstdio>
static const uint8_t *A64_MEM;
#define HOS_GUEST_SPACE (1ULL << 39)
#define GP(a) ((void *)(A64_MEM + (a)))
static void hos_log(const char *, ...) {}
static int commit_wait(void *, SIZE_T) { return 0; }
static void commit_refused(uint64_t, uint64_t, DWORD) {}
@HANDLER@
static int bad;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); bad++; } } while (0)
static LONG deliver(void *where, ULONG_PTR kind) {   // (the fault the OS would hand the handler: 0 read, 1 write, 8 execute)
    EXCEPTION_RECORD rec{};
    CONTEXT ctx{};
    rec.ExceptionCode = EXCEPTION_ACCESS_VIOLATION;
    rec.NumberParameters = 2;
    rec.ExceptionInformation[0] = kind;
    rec.ExceptionInformation[1] = (ULONG_PTR)where;
    EXCEPTION_POINTERS ep{&rec, &ctx};
    return commit_on_touch(&ep);
}
int main() {
    SYSTEM_INFO si{};
    GetSystemInfo(&si);
    const SIZE_T page = si.dwPageSize;
    uint8_t *base = (uint8_t *)VirtualAlloc(nullptr, 0x40000, MEM_RESERVE, PAGE_NOACCESS);
    if (!base || VirtualAlloc(base, page * 2, MEM_COMMIT, PAGE_READWRITE) != base) return 2;
    A64_MEM = base - 0x200000;
    uint8_t *after = base + page;   // (the page after a one-page import's range: another thread committed it)
    DWORD old = 0;
    {
        const mkwvk::InhaleImportFence fence(base, page, true);
        CHECK(fence.set());
        // (the fault that was pending when the importer fenced the page, delivered now: tried again)
        CHECK(deliver(after, 1) == EXCEPTION_CONTINUE_EXECUTION);
        CHECK(deliver(after + 8, 0) == EXCEPTION_CONTINUE_EXECUTION);
        CHECK(deliver(after, 8) == EXCEPTION_CONTINUE_SEARCH);   // (an execute fault is never tried again)
    }
    CHECK(deliver(after, 1) == EXCEPTION_CONTINUE_EXECUTION);   // (the plain read-write page, as before)
    CHECK(VirtualProtect(after, page, PAGE_READWRITE | PAGE_GUARD, &old));
    CHECK(deliver(after, 1) == EXCEPTION_CONTINUE_SEARCH);   // (a guard page: not plain read-write)
    CHECK(VirtualProtect(after, page, PAGE_READONLY, &old));
    CHECK(deliver(after, 1) == EXCEPTION_CONTINUE_SEARCH);   // (a write watch's read-only page: its own handler's)
    printf("first touch with the fence: failures=%d\n", bad);
    VirtualFree(base, 0, MEM_RELEASE);
    return bad ? 1 : 0;
}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cxx", default="g++")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="import-fence-") as tmp:
        exe = Path(tmp) / "import_fence_test.exe"
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu/vk"),
                        str(ROOT / "tests/import_fence_test.cpp"), "-o", str(exe)], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout.strip(), result.stderr.strip())
        if result.returncode:
            raise SystemExit("FAIL: import_fence_test")
        if sys.platform == "win32":
            glue = (ROOT / "host/mkw_glue.c").read_text(encoding="utf-8")
            handler = block(glue, "static LONG CALLBACK commit_on_touch(EXCEPTION_POINTERS *info)")
            fixture = Path(tmp) / "first_touch_fence.cpp"
            fixture.write_text(FIRST_TOUCH.replace("@HANDLER@", handler), encoding="utf-8")
            exe2 = Path(tmp) / "first_touch_fence.exe"
            subprocess.run([args.cxx, "-std=c++20", "-O1", "-I", str(ROOT / "gpu/vk"), str(fixture), "-o", str(exe2)],
                           check=True, timeout=120)
            result = subprocess.run([str(exe2)], capture_output=True, text=True, timeout=30)
            print(result.stdout.strip(), result.stderr.strip())
            if result.returncode:
                raise SystemExit("FAIL: a data fault on the fenced page is not tried again, or another is")
    print("PASS: an import's region ends with its range while the fence stands, and the page is as it was after")


if __name__ == "__main__":
    main()
