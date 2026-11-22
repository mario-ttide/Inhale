"""gpu/vk/menu_i18n_inhale.h, this fork's own rows of the Insert menu's translations, beside upstream's tables in
gpu/vk/menu_i18n.h (which a sync merges, so nothing of this fork's is written there):

  - its languages are menu_i18n.h's, in the same order (vk_menu_i18n.cpp takes both lists by one index);
  - vk_menu_i18n.cpp's table(), cut from the source and compiled with the two files, holds for each language every
    row of both, and gives each text of this fork its translation here;
  - each of its texts is a text of vk_menu.cpp that menu_i18n.h's table does not have, every language has the same
    texts, sorted, and a translation keeps its text's printf conversions and its leading and trailing spaces;
  - a retired text (kRetired) is in every table of menu_i18n.h and is no text of vk_menu.cpp: when either stops being
    true the list is stale;
  - every other text of menu_i18n.h is the menu's (tests/test_menu_i18n.py checks its counts and its order).

No game.

    python -I -B tests/test_menu_i18n_inhale.py [--cxx g++]
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves this folder off the path)
import test_menu_i18n as base  # noqa: E402
from srccut import block  # noqa: E402
from menu_model_fixture import menu_sources  # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

VK = base.VK
TABLE = re.compile(r'inline constexpr Entry (k\w+)\[\] = \{\n(.*?)\n\};', re.S)
ROW = re.compile(r'^    \{"((?:[^"\\]|\\.)*)", "((?:[^"\\]|\\.)*)"\},$', re.M)
LANG = re.compile(r'^    \{"([\w-]+)", "(?:[^"\\]|\\.)*", (\w+), (?:0|sizeof (\w+) / sizeof (\w+)\[0\])\},$', re.M)
# (table() and what it calls, as the source has them, then: each language's table has the rows of both files, a text of
# this fork gives this fork's translation, and upstream's first text still gives upstream's)
FIXTURE = """
#include <cstdio>
#include <cstring>
#include <memory>
#include <mutex>
#include <string_view>
#include <unordered_map>
#include <vector>
#include "menu_i18n.h"
#include "menu_i18n_inhale.h"
namespace mkwvk::i18n {
/* ACTUAL */
}
int main() {
    using namespace mkwvk;
    int bad = 0;
    for (int lang = 1; lang < menu_i18n::kLangCount; lang++) {
        const menu_i18n::Lang& theirs = menu_i18n::kLangs[lang];
        const menu_i18n::Lang& own = menu_i18n::inhale::kLangs[lang];
        const i18n::Table& t = i18n::table(lang);
        if (own.count <= 0 || (int)t.exact.size() != theirs.count + own.count)
            bad++, printf("%s: %d texts, not %d + %d\\n", theirs.code, (int)t.exact.size(), theirs.count, own.count);
        for (int i = 0; i < own.count; i++) {
            auto it = t.exact.find(own.entries[i].en);
            if (it == t.exact.end() || it->second != own.entries[i].text)
                bad++, printf("%s: no translation for this fork's text: %s\\n", theirs.code, own.entries[i].en);
        }
        auto it = t.exact.find(theirs.entries[0].en);
        if (it == t.exact.end() || it->second != theirs.entries[0].text) bad++, printf("%s: upstream's first text is lost\\n", theirs.code);
    }
    return bad != 0;
}
"""


def lookup(cxx):
    cpp = (VK / "vk_menu_i18n.cpp").read_text(encoding="utf-8")
    actual = "\n".join([block(cpp, "size_t conversion("), block(cpp, "struct Table {") + ";", block(cpp, "const Table& table(int lang) {")])
    with tempfile.TemporaryDirectory(prefix="menu-i18n-inhale-") as temp:
        src, exe = os.path.join(temp, "fixture.cpp"), os.path.join(temp, "fixture.exe")
        with open(src, "w", encoding="utf-8") as f:
            f.write(FIXTURE.replace("/* ACTUAL */", actual))
        subprocess.run([cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(VK), src, "-o", exe], check=True)
        r = subprocess.run([exe], stdout=subprocess.PIPE, timeout=30)
        assert r.returncode == 0, "vk_menu_i18n.cpp table():\n" + r.stdout.decode("utf-8", "replace")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cxx", default="g++")
    args = p.parse_args()
    src = (VK / "menu_i18n_inhale.h").read_text(encoding="utf-8")
    theirs, their_langs = base.tables()
    menu = set(base.c_strings(menu_sources()))   # (vk_menu.cpp's texts and its modules', gpu/vk/menu/: upstream #1633)
    menu |= set(base.c_strings((VK / "vk_ui.h").read_text(encoding="utf-8")))   # (the prompt bar's key names: "Del")
    runtime = set()   # (and the ReShade status texts the renderer hands the menu, as test_menu_i18n.py takes them)
    for name in ("fx_runtime.cpp", "fx_preset.cpp"):
        runtime.update(base.c_strings((VK / "reshade" / name).read_text(encoding="utf-8")))
    menu.update(text for text in base.RESHADE_STATUS if text in runtime)
    retired = base.c_strings(re.search(r'kRetired\[\] = \{\n(.*?)\n\};', src, re.S).group(1))
    own = {}
    for name, body in TABLE.findall(src):
        own[name] = ROW.findall(body)
        assert len(own[name]) == body.count("\n") + 1, "%s: a line that is no row" % name

    langs = LANG.findall(src)
    assert [(code, table) for code, table, _, _ in langs] == [(code, table) for code, _, table, _ in their_langs], \
        "the languages are not menu_i18n.h's, in its order"
    for code, table, a, b in langs[1:]:
        assert a == b == table, "%s: its count is another table's" % code
    assert list(own) == list(theirs)

    texts = [en for en, _ in next(iter(own.values()))]
    assert texts, "no rows"
    for name, pairs in own.items():
        keys = [en for en, _ in pairs]
        assert keys == texts, "%s: not the texts of the first table, in its order" % name
        assert keys == sorted(set(keys)), "%s: not sorted, or a text twice" % name
        for en, text in pairs:
            assert en in menu, "%s: %r is no text of vk_menu.cpp (reworded? then translate it again)" % (name, en)
            assert en not in dict(theirs[name]), "%s: %r is in menu_i18n.h too" % (name, en)
            assert text, "%s: %r has an empty translation" % (name, en)
            assert base.conversions(en) == base.conversions(text), "%s: %r and %r" % (name, en, text)
            for side in (lambda s: s[:len(s) - len(s.lstrip(" "))], lambda s: s[len(s.rstrip(" ")):]):
                assert side(en) == side(text), "%s: the spaces around %r" % (name, en)

    assert retired == sorted(set(retired))
    for en in retired:
        assert en not in menu, "retired, but a text of vk_menu.cpp: %r" % en
        for name, pairs in theirs.items():
            assert en in dict(pairs), "retired, but %s of menu_i18n.h does not have it (upstream dropped it?): %r" % (name, en)
    for name, pairs in theirs.items():
        stale = [en for en, _ in pairs if en not in menu and en not in retired]
        assert not stale, "%s of menu_i18n.h: no text of vk_menu.cpp and not retired: %r" % (name, stale[:3])

    lookup(args.cxx)
    print("menu_i18n_inhale: %d texts in %d languages, %d retired" % (len(texts), len(own), len(retired)))


if __name__ == "__main__":
    main()
