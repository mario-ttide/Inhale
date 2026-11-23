"""The game's nn::fs::CommitSaveData publishes its save, and the save survives a new mount (issue #24).

Since the v3.1.1 sync, host/nn_fs.c stages a save: the game writes into <user>/save-work/<uid>, nn::fs::Commit copies
that into <user>/save/<uid>, and each MountSaveData starts the work copy again from save/<uid>. The game calls
CommitSaveData, SDK 19's name of Commit, whose HLE is in host/kirby_hle.c. When it only answered 0, nothing was ever
published and every start lost the progress of the last.

Linux only. Builds host/nn_fs.c whole, as it is in the tree, over host/posix/win32_posix.c's file functions, with a
small hos.h of stand-ins (guest addresses are host addresses here), and CommitSaveData's HLE cut from
host/kirby_hle.c. Then, as the game does: mount the save, create and write file0, close it, CommitSaveData; checks that
file0 is in save/<uid>, and that after an unmount and a new mount the work copy has it again.

python -I -B tests/test_kirby_save_commit.py [--cc gcc]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# (what nn_fs.c takes from host/hos.h and the rest of the runtime)
HOS_H = r'''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <time.h>
#define INHALE_ENV_H
typedef struct { uint64_t x[32]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))
#define G64(a) (*(uint64_t *)GP(a))
#define G32(a) (*(uint32_t *)GP(a))
#define HOS_SPACE_END 0x7fffffffffffffffULL
#define HOS_WRITTEN(p, n) ((void)0)
static int hos_trace;
static void hos_log(const char *f, ...) { va_list a; va_start(a, f); fputs("log: ", stdout); vprintf(f, a); putchar('\n'); va_end(a); }
static void hos_fatal(Ctx *c, const char *f, ...) { (void)c; fprintf(stderr, "fatal: %s\n", f); abort(); }
static int64_t hos_now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1000000000LL + t.tv_nsec; }
static void hos_sleep_ns(int64_t n) { (void)n; }
static int hos_vcore_away(void) { return 0; }
static void hos_vcore_back(void) {}
static int env_on(const char *n) { const char *e = getenv(n); return e && *e && *e != '0'; }
static void *hos_guest_range(uint64_t a, uint64_t n) { (void)n; return GP(a); }
static int hos_commit(uint64_t a, uint64_t n) { (void)a; (void)n; return 1; }
int hos_mods_romfs(const char *rel, char *out, size_t cap) { (void)rel; (void)out; (void)cap; return 0; }
int hos_mods_dir_extras(const char *rel, const char *base_dir, void (*fn)(void *, const char *, int, uint64_t), void *arg) {
    (void)rel; (void)base_dir; (void)fn; (void)arg; return 0;
}
int hos_blank_cached_icon(const char *guest, const char *host) { (void)guest; (void)host; return 0; }
int hos_ultrawide_redirect(const char *guest, char *out, size_t cap) { (void)guest; (void)out; (void)cap; return 0; }
int hos_stand_in_damaged(const char *guest, char *path, size_t cap) { (void)guest; (void)path; (void)cap; return 0; }
void kirby_read_done(const char *guest, int64_t off, uint8_t *buf, uint64_t n) { (void)guest; (void)off; (void)buf; (void)n; }
'''

MAIN = r'''
#include <sys/stat.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); return 1; } } while (0)
#define UID "00000000000000020000000000000001"
static int file_says(const char *path, const char *want) {
    char got[16] = {0};
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    const size_t n = fread(got, 1, sizeof got - 1, f);
    fclose(f);
    return n == strlen(want) && !memcmp(got, want, n);
}
static uint64_t a(const void *p) { return (uint64_t)(uintptr_t)p; }
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    hos_user_dir = argv[1];
    static const uint64_t uid[2] = {1, 2};
    static const char data[] = "KIRB", option[8] = {0};
    uint64_t handle = 0;
    char committed[4096], work[4096];
    snprintf(committed, sizeof committed, "%s/save/" UID "/file0", argv[1]);
    snprintf(work, sizeof work, "%s/save-work/" UID "/file0", argv[1]);
    Ctx c = {0};
    c.x[0] = a("save"), c.x[1] = a(uid);
    imp__ZN2nn2fs13MountSaveDataEPKcRKNS_7account3UidE(&c);
    CHECK(c.x[0] == 0);
    c.x[0] = a("save:/file0"), c.x[1] = 4;
    imp__ZN2nn2fs10CreateFileEPKcl(&c);
    CHECK(c.x[0] == 0);
    c.x[0] = a(&handle), c.x[1] = a("save:/file0"), c.x[2] = 2;   /* (OpenMode_Write) */
    imp__ZN2nn2fs8OpenFileEPNS0_10FileHandleEPKci(&c);
    CHECK(c.x[0] == 0);
    c.x[0] = handle, c.x[1] = 0, c.x[2] = a(data), c.x[3] = 4, c.x[4] = a(option);
    imp__ZN2nn2fs9WriteFileENS0_10FileHandleElPKvmRKNS0_11WriteOptionE(&c);
    CHECK(c.x[0] == 0);
    c.x[0] = handle;
    imp__ZN2nn2fs9CloseFileENS0_10FileHandleE(&c);
    CHECK(file_says(work, "KIRB"));         /* (staged: written into the work copy) */
    c.x[0] = a("save");
    imp__ZN2nn2fs14CommitSaveDataEPKc(&c);
    CHECK(c.x[0] == 0);
    CHECK(file_says(committed, "KIRB"));    /* published: the next start reads it from here */
    c.x[0] = a("save");
    imp__ZN2nn2fs7UnmountEPKc(&c);
    c.x[0] = a("save"), c.x[1] = a(uid);
    imp__ZN2nn2fs13MountSaveDataEPKcRKNS_7account3UidE(&c);
    CHECK(c.x[0] == 0);
    CHECK(file_says(work, "KIRB"));         /* and a new mount starts from it */
    printf("PASS: CommitSaveData publishes save-work into save, and a new mount keeps it\n");
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    args = p.parse_args()
    if os.name == "nt" or sys.platform == "darwin":
        print("SKIP: the posix layer's checks run on Linux")
        return
    fs = (ROOT / "host/nn_fs.c").read_text(encoding="utf-8")
    kirby = (ROOT / "host/kirby_hle.c").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="kirby-save-") as tmp:
        tmp = Path(tmp)
        (tmp / "hos.h").write_text(HOS_H, encoding="utf-8")
        src = tmp / "fixture.c"   # (beside the stand-in hos.h, so that nn_fs.c's #include "hos.h" finds it)
        src.write_text(fs + "\n" + block(kirby, "HLE(_ZN2nn2fs14CommitSaveDataEPKc)") + "\n" + MAIN, encoding="utf-8")
        exe = tmp / "fixture"
        subprocess.run([args.cc, "-std=gnu11", "-I", str(tmp), "-I", str(ROOT / "host/posix"), "-Wno-unused-function",
                        str(src), str(ROOT / "host/posix/win32_posix.c"), "-o", str(exe), "-pthread"], check=True)
        user = tmp / "user"
        user.mkdir()
        r = subprocess.run([str(exe), str(user)], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "HOS_FS_TRACE": "1"})
        print(r.stdout, end="")
        if r.returncode:
            print(r.stderr, end="")
            raise SystemExit("test_kirby_save_commit: failed (exit %d)" % r.returncode)


if __name__ == "__main__":
    main()
