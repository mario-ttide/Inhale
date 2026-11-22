"""The project's own name through the tree: upstream's name becomes this fork's, in file names and in text.

    python -I scripts/rename_full.py            (what would change: counts, the paths renamed, what is kept)
    python -I scripts/rename_full.py --write    (do it)

The imported files call the project by upstream's name: output files, environment variables, include guards, the
player's texts, the comments. This script maps all of it, case by case (lower, Capital, UPPER), with one rule, so
that it can be run again after every upstream sync and so that scripts/sync_upstream.py can put upstream's files
through the same rule before it merges them (map_path, map_text). A second run changes nothing.

Kept as they are:
  - whole files: the provenance and credit documents, the readme and the design notes (they speak of upstream as
    upstream), the notes for coding agents (AGENTS.md, CLAUDE.md, .claude/: the same), the sync script and this one
    with their test (it has upstream's spellings as its input), everything under third_party/ (each part's tree hash
    is checked, scripts/check_third_party.py), the renderer's own shader sources and their compiled headers (a header
    names the hash of the source it was compiled from, and the name is only in their comments), the script that holds
    the shader text upstream changed in AMD's FSR 3 passes (scripts/shaders.py: those headers are compiled from
    it, and its functions have the name) and the check that cuts those functions out of it by their names
    (tests/test_fsr3fi_hud_mask.py), and the other game's item table with its test (an item of that game has
    the name);
  - the marks `(longshot)`, `(longshot: ...)`, `(longshot-amd)`, `(version 26, longshot)` on upstream's changes to
    the code it took from others and to the renderer's interface: they say whose change it is, and they stay true; and
    such a mark escaped in a check's regular expression, so the check still finds it;
  - the two variables the vendored a64-kit reads by name;
  - upstream's repository, the issues and pull requests a comment names, and launcher issue references.
Two spans have an answer of their own. The window's application id, which is under upstream's domain (FIXED). And
upstream's tracker where the program shows it or opens it (TRACKER): in a text for the player, which has no
`https://` before it, in a link that starts a string, and in a link that opens a new report. It becomes a host that
never resolves: this fork has no tracker, and its problems are not upstream's to receive.
A length written after a string that holds the name, as in memcpy(path + n, "<name>_env.txt", 17) or
strstr(line, "] <name> ") ... at + 11), follows the string's new length (LENGTH): the two names are not as long as
each other.

Tracked and untracked files are both covered (ignored ones are not). A tracked file is renamed with `git mv`, which
stages the rename and nothing else. Standard library and git only.
"""
import argparse
import collections
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "longshot", "inhale"

KEEP_FILES = {"PROVENANCE.md", "gpu/PROVENANCE.md", "host/PROVENANCE.md", "CREDITS.md", "README.md", "CONTRIBUTING.md",
              "AGENTS.md", "CLAUDE.md",
              "docs/design.md", "scripts/sync_upstream.py", "scripts/rename_full.py", "tests/test_sync_rules.py",
              "scripts/shaders.py", "tests/test_fsr3fi_hud_mask.py",
              "gpu/vk/oot_cheat_items.h", "tests/test_cheat_items.py"}
KEEP_DIRS = ("third_party/", "gpu/vk/shaders/", "gpu/vk/host_shaders/", ".claude/")
# (spans that stay, tried before the name itself at each place)
KEEP_TEXT = [r"\(longshot(?=[):, -])",                      # the marks on upstream's changes
             r"\(version \d+, longshot\)",                  # the same on a member of the renderer's interface
             r"\\\(version \d+, longshot\\\)",              # that mark in a check's regular expression
             r"LONGSHOT_MINGW", r"LONGSHOT_LIGHT_PASSES",   # read by third_party/a64-kit
             r"(?i:magicbeandev/longshot)",                 # upstream's repository and tracker
             r"LongshotLauncher#\d+"]                       # an issue of upstream's launcher
# (whole spans with an answer of their own. The window's application id is under upstream's domain, and this fork has
# no domain: a plain name, so the two projects' windows are not taken for one program)
FIXED = {"dev.magicbean.Longshot": "inhale"}
# (upstream's tracker, tried before KEEP_TEXT: with no scheme before it, or with the scheme at a string's start, and
# /issues after it; or with /issues/new after it. `https://.../issues/52` in a comment fits none of them and stays)
UPSTREAM = re.escape("git.magicbean.dev/MagicBeanDev/Longshot")
TRACKER = r"(?:(?<!https://)|(?<=[\"']https://))%s(?=/issues)|%s(?=/issues/new)" % (UPSTREAM, UPSTREAM)
TRACKER_NEW = "tracker.inhale.invalid"
RULE = re.compile("(?P<tracker>%s)|(?P<fixed>%s)|(?P<keep>%s)|(?P<name>longshot|Longshot|LONGSHOT)"
                  % (TRACKER, "|".join(map(re.escape, FIXED)), "|".join(KEEP_TEXT)))
CASES = {OLD: NEW, OLD.capitalize(): NEW.capitalize(), OLD.upper(): NEW.upper()}
# (a string, then in the same statement the first number that ends an argument or a sum before a closing bracket: taken
# for the string's length where it is that length, with or without the end's zero)
LENGTH = re.compile(r'"((?:[^"\\\n]|\\.)*)"([^;"\n]*?[,+]\s*)(\d+)(?=\s*\))')


def kept_file(path):
    """path: relative to the root, with /"""
    return path in KEEP_FILES or path.startswith(KEEP_DIRS)


def map_text(text, count=None):
    """count: a Counter that takes 'renamed' and each kept span"""
    def one(m):
        if m.group("tracker"):
            if count is not None:
                count["renamed"] += 1
            return TRACKER_NEW
        if m.group("fixed"):
            if count is not None:
                count["renamed"] += 1
            return FIXED[m.group("fixed")]
        if m.group("keep"):
            if count is not None:
                count[m.group("keep")] += 1
            return m.group(0)
        if count is not None:
            count["renamed"] += 1
        return CASES[m.group("name")]
    def length(m):
        old, new = m.group(1), RULE.sub(one_quiet, m.group(1))
        chars = len(re.sub(r"\\.", "x", old))   # (an escape is one character: none of these strings has a longer one)
        if new == old or int(m.group(3)) not in (chars, chars + 1):
            return m.group(0)
        if count is not None:
            count["a length after a string"] += 1
        return '"%s"%s%d' % (old, m.group(2), int(m.group(3)) - (len(old) - len(new)))

    def one_quiet(m):
        if m.group("keep"):
            return m.group(0)
        return TRACKER_NEW if m.group("tracker") else FIXED.get(m.group(0)) or CASES[m.group("name")]
    return RULE.sub(one, LENGTH.sub(length, text))


def map_path(path):
    """The path a file has after the rename (only the name itself is mapped: no kept span fits a file name)"""
    return path if kept_file(path) else map_text(path)


def map_bytes(path, data):
    """A file's content after the rename; the same bytes for a kept file and for one that is not UTF-8 text"""
    if kept_file(path) or b"\0" in data:
        return data
    try:
        return map_text(data.decode("utf-8")).encode("utf-8")
    except UnicodeDecodeError:
        return data


def git_files(*args):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", *args], stdout=subprocess.PIPE, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--write", action="store_true", help="change the files (without it: only say what would change)")
    a = p.parse_args()

    tracked = set(git_files())
    count = collections.Counter()
    changed, moved, not_text = [], [], []
    for path in sorted(tracked | set(git_files("-o", "--exclude-standard"))):
        full = os.path.join(ROOT, path)
        if kept_file(path) or os.path.islink(full) or not os.path.isfile(full):
            continue
        with open(full, "rb") as f:
            data = f.read()
        if RULE.search(path) or re.search(OLD.encode(), data, re.I):
            try:
                text = None if b"\0" in data else data.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is None:
                if re.search(OLD.encode(), data, re.I):
                    not_text.append(path)
            else:
                new = map_text(text, count).encode("utf-8")
                if new != data:
                    changed.append(path)
                    if a.write:
                        with open(full, "wb") as f:
                            f.write(new)
            if map_path(path) != path:
                moved.append((path, map_path(path)))
    for old, new in moved:
        if a.write:
            if os.path.exists(os.path.join(ROOT, new)):
                sys.exit("%s is in the way of %s" % (new, old))
            if old in tracked:
                subprocess.run(["git", "-C", ROOT, "mv", old, new], check=True)
            else:
                os.rename(os.path.join(ROOT, old), os.path.join(ROOT, new))
        print("  %s -> %s" % (old, new))
    for path in not_text:
        print("  not text, left as it is: %s" % path)
    for span, n in sorted(count.items()):
        if span != "renamed":
            print("  kept %5d  %s" % (n, span))
    print("%s: %d places in %d files, %d files renamed" % ("renamed" if a.write else "to rename (--write does it)",
                                                            count["renamed"], len(changed), len(moved)))


if __name__ == "__main__":
    main()
