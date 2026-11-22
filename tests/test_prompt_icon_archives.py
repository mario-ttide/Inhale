"""Game-free: every archive that holds a copy of a button label is served with the face's icons (host/prompts.c
hos_prompts_romfs, icons_file), issue #14. The world map's DLC stage marker (lyt/Wmap/MarkerDlcStage/Body.arc.cmp), the
arena's entry, the hero panel and the ball minigame carry a BtnIconA^t of their own beside the common one
(lyt/Cmn/BtnIcon/Parts.arc.cmp), and their layouts draw that copy: served only the common archive, the DLC stage bubble
showed the Switch's "A". Each key (lower case, as mods.c asks) gets the face's file at its own path, its variants read
from beside it (.var for .cmp), and two archives on the same controls get two cache files. The text font, a mod's own
file and another path are served as before. And the list is nx2/kirby_prompts.py ARCHIVES, the files the build writes.

python -I -B tests/test_prompt_icon_archives.py [--cc gcc]
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between  # noqa: E402

ARCHIVES = ["lyt/Cmn/BtnIcon/Parts.arc.cmp", "lyt/Wmap/MarkerDlcStage/Body.arc.cmp", "lyt/Arena/Entry/Parts.arc.cmp",
            "lyt/Cmn/HeroPanel/Parts.arc.cmp", "lyt/MgameBall/Game/Parts.arc.cmp"]
WITH_VAR = ARCHIVES[:2]   # (a variants file beside these: the controls changed, a cache file each)
FONT = "font/Region/STD/Ext-Operation.bffnt.cmp"


def check(cond, what):
    if not cond:
        raise SystemExit("FAIL: " + what)


STUBS = r"""
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include "gpu/vk/vk_api.h"
#define MAX_PATH 1024
#define INVALID_FILE_ATTRIBUTES 0xFFFFFFFFu
#define MOVEFILE_REPLACE_EXISTING 1
#define _stricmp strcasecmp
typedef long LONG;
static const char *root;
/* a file in cache/ is there already (icons_file serves it without writing); any other as the disk has it */
static unsigned GetFileAttributesA(const char *p) {
    struct stat st;
    return strstr(p, "/cache/") || !stat(p, &st) ? 0x80 : INVALID_FILE_ATTRIBUTES;
}
static int made_dir(char *out, size_t cap) { snprintf(out, cap, "%s/cache/", root); return 1; }
static int first_key(int b) { (void)b; return 0x20; }
static int hos_binding(int set, int b, int slot) { (void)set; (void)b; (void)slot; return 1; }   /* (not the default, 0) */
static uint8_t *read_all(const char *p, const char *m, long *n) { (void)p; (void)m; *n = 0; return NULL; }
static int MoveFileExA(const char *a, const char *b, int f) { (void)a; (void)b; (void)f; return 0; }
static int DeleteFileA(const char *a) { (void)a; return 0; }
static void hos_log(const char *f, ...) { (void)f; }
static int setup(char *dir, size_t cap, int *face) { snprintf(dir, cap, "%s/", root); *face = HOS_PROMPT_XBOX; return 1; }
static int sizes(const char *dir, const char *mod, char *out, size_t cap) { (void)dir; (void)mod; (void)out; (void)cap; return 0; }
/* (upstream's size table with the font's entry raised, which hos_prompts_romfs serves before the archives: none here) */
static char opened_table[MAX_PATH];
static int own_sizes(const char *key, char *out, size_t cap) { (void)key; (void)out; (void)cap; return 0; }
static volatile LONG romfs_state[3];
static LONG InterlockedCompareExchange(volatile LONG *p, LONG x, LONG c) { LONG o = *p; if (o == c) *p = x; return o; }
static LONG InterlockedExchange(volatile LONG *p, LONG x) { LONG o = *p; *p = x; return o; }
static void Sleep(int ms) { (void)ms; }
static int build(char *o, size_t c) { (void)o; (void)c; return 0; }
static int build_textures(char *o, size_t c) { (void)o; (void)c; return 0; }
static int build_layouts(char *o, size_t c) { (void)o; (void)c; return 0; }
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    src = (ROOT / "host" / "prompts.c").read_text(encoding="utf-8")
    keys = [x.lower() for x in ARCHIVES] + [FONT.lower()]
    harness = "\n".join([
        STUBS,
        between(src, "#define FONT_PATH", "#define MAGIC"),
        between(src, "static const char *const faces[HOS_PROMPT_N]", ";") + ";",
        block(src, "static uint32_t rd32le("),
        block(src, "static uint64_t fnv("),
        between(src, "#define ICONS_HEAD", "/* the face's button-icon layout for the controls now"),
        block(src, "static uint32_t sheet_block("),
        block(src, "static int icons_file("),
        block(src, "int hos_prompts_romfs("),
        "int main(int argc, char **argv) {",
        "    char out[MAX_PATH];",
        "    (void)argc;",
        "    root = argv[1];",
        *('    out[0] = 0; printf("%%d %%s\\n", hos_prompts_romfs("%s", NULL, out, sizeof out), out);' % k for k in keys),
        '    printf("%%d\\n", hos_prompts_romfs("%s", "mod/file", out, sizeof out));' % keys[1],
        '    printf("%d\\n", hos_prompts_romfs("lyt/wmap/markerdlcstage/other.arc.cmp", NULL, out, sizeof out));',
        "    return 0;",
        "}", ""])
    var = b"KBIV" + struct.pack("<II", 1, 17) + struct.pack("<IIIII", 0, 0, 16, 32, 0)   # (one label, A, its default pad input 0)
    with tempfile.TemporaryDirectory() as tmp:
        game = Path(tmp) / "game"
        for rel in ARCHIVES + [FONT]:
            f = game / "prompts" / "xbox" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"cmp")
            if rel in WITH_VAR:
                f.with_suffix(".var").write_bytes(var)
        c, exe = Path(tmp) / "archives.c", Path(tmp) / "archives"
        c.write_text(harness, encoding="utf-8")
        subprocess.run([a.cc, "-std=c11", "-D_DEFAULT_SOURCE", "-Wall", "-Wextra", "-Werror", "-Wno-format-truncation", "-I",
                        str(ROOT), str(c), "-o", str(exe)], check=True)
        out = subprocess.run([str(exe), str(game)], check=True, capture_output=True, text=True).stdout.split("\n")
        cached = []
        for rel, key, line in zip(ARCHIVES + [FONT], keys, out):
            served, _, path = line.partition(" ")
            check(served == "1", "%s: not served (the game's own file, with the Switch's labels)" % key)
            if rel in WITH_VAR:
                name = os.path.basename(path)
                check(path.startswith(str(game) + "/cache/btnicon-xbox-"), "%s: served %s, not a cache file" % (key, path))
                cached.append(name)
            else:
                check(path == str(game / "prompts" / "xbox" / rel), "%s: served %s, not the face's file" % (key, path))
        check(len(set(cached)) == len(cached), "two archives on the same controls share one cache file: %s" % cached)
        check(out[len(keys)] == "0", "a mod's own marker archive: the prompts' served in its place")
        check(out[len(keys) + 1] == "0", "another archive of the marker's folder served")
    sys.path.insert(0, str(ROOT / "nx2"))
    import kirby_prompts
    check(getattr(kirby_prompts, "ARCHIVES", None) == ARCHIVES, "nx2/kirby_prompts.py ARCHIVES is not the list served here")
    print("ok: %d archives with a label served at their own paths, %d cache files apart; the font, a mod and another path"
          % (len(ARCHIVES), len(cached)))


if __name__ == "__main__":
    main()
