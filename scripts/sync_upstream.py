"""Bring Longshot's changes since the recorded base into this clone (PROVENANCE.md, its `upstream-base:` line).

    python -I scripts/sync_upstream.py [--upstream ../Longshot] [--to REV] [--list]

It takes Longshot's diff from the base to REV (default: the upstream clone's HEAD) over the imported paths and applies
it with `git apply -3`, so a file changed on both sides is merged or left with conflict marks, then rewrites the base
line. Nothing is committed: look at `git status`, settle the conflicts, run the tests, commit.

This clone carries the project's name changed through the tree (scripts/rename_full.py). Both sides of Longshot's
diff are put through that same rule first, file names and text, so the diff that is applied is between two renamed
trees: it merges with the renamed files here, and what is new in Longshot arrives renamed.

Not applied, and listed:
  - nx2/oot_patches.py: the file here is a stand-in, and Longshot's holds text made from the other game. When
    Longshot changed its file, the top-level names it gained and the stand-in lacks are printed: the lift calls them.
    The other game's other files (oot_*) are Longshot's own, gated here, and are applied as any file;
  - a change or a removal of a file this clone does not track (left out at the import, or removed since);
  - a removal of a file this clone changed (its text here is not Longshot's at the base, renamed): git cannot apply
    it, and one such removal stops the whole apply. Listed: `git rm` it, or keep what this fork needs of it.
A file new in Longshot is applied; whether it belongs here is for the review (a test bound to something left out
does not). --list prints what would be applied and what would not, and changes nothing.

The work tree must have no changes under the imported paths: `git apply -3` works on the index. Standard library and
git only.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rename_full  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVENANCE = os.path.join(ROOT, "PROVENANCE.md")
UPSTREAM = os.path.join(ROOT, "..", "Longshot")   # (the clone of Longshot; scripts/sync_nightly.py fetches it)
BASE_LINE = re.compile(r"^(\s*upstream-base:\s*)([0-9a-f]{40})\s*$", re.M)
PATHS = ["nx2", "host", "gpu", "third_party", "tests", "scripts", "LICENSE", "requirements.txt", ".gitattributes",
         ".gitignore", "docs/compiler-memory-accounting.md"]


def git(where, *args, data=None, check=True):
    r = subprocess.run(["git", "-C", where] + list(args), input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and r.returncode:
        sys.exit("git %s failed in %s:\n%s" % (" ".join(args), where, r.stderr.decode("utf-8", "replace")))
    return r


def read_base(text):
    m = BASE_LINE.search(text)
    if not m:
        sys.exit("%s has no `upstream-base: <40 hex digits>` line" % PROVENANCE)
    return m.group(2)


STAND_IN = "nx2/oot_patches.py"
TOP_NAME = re.compile(r"^(?:def (\w+)|(\w+) =)", re.M)


def names_lacking(old, new, here):
    """Three texts of a Python file -> the top-level names (def x, X =) `new` has and neither `old` nor `here` has"""
    names = [{a or b for a, b in TOP_NAME.findall(text)} for text in (old, new, here)]
    return sorted(names[1] - names[0] - names[2])


def split(changes, tracked, changed_here=()):
    """changes: (status letter, path) of the upstream diff; changed_here: the removed paths whose text here differs.
    -> (paths to apply, [(path, why not)])"""
    take, skip = [], []
    for status, path in changes:
        if path == STAND_IN:
            skip.append((path, "a stand-in here"))
        elif status == "D" and path in changed_here:
            skip.append((path, "removed in Longshot, changed here"))
        elif status != "A" and rename_full.map_path(path) not in tracked:
            skip.append((path, "not tracked here"))
        else:
            take.append(path)
    return take, skip


def renamed_tree(upstream, rev, paths, index):
    """The tree, in this repository, of Longshot's files `paths` at `rev` after the rename (a file `rev` lacks is left out)"""
    env = dict(os.environ, GIT_INDEX_FILE=index)
    listed = git(upstream, "ls-tree", "-r", "-z", rev, "--", *paths).stdout.decode("utf-8").split("\0")
    for entry in filter(None, listed):
        head, path = entry.split("\t", 1)
        mode, kind, blob = head.split()
        if kind != "blob":
            sys.exit("%s at %s is a %s: not handled" % (path, rev[:8], kind))
        data = git(upstream, "cat-file", "blob", blob).stdout
        if mode != "120000":   # (a link's target is not text of the project)
            data = rename_full.map_bytes(path, data)
        new = git(ROOT, "hash-object", "-w", "--stdin", data=data).stdout.decode().strip()
        subprocess.run(["git", "-C", ROOT, "update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, new, rename_full.map_path(path))],
                       env=env, check=True)
    return subprocess.run(["git", "-C", ROOT, "write-tree"], env=env, stdout=subprocess.PIPE, check=True).stdout.decode().strip()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--upstream", default=UPSTREAM, help="a clone of Longshot")
    p.add_argument("--to", default="HEAD", help="the upstream revision to sync to (default HEAD)")
    p.add_argument("--list", action="store_true", help="print what would be applied, change nothing")
    a = p.parse_args()

    with open(PROVENANCE, encoding="utf-8") as f:
        text = f.read()
    base = read_base(text)
    to = git(a.upstream, "rev-parse", "--verify", a.to + "^{commit}").stdout.decode().strip()
    if git(a.upstream, "merge-base", "--is-ancestor", base, to, check=False).returncode:
        sys.exit("the base %s is not an ancestor of %s in %s" % (base[:8], to[:8], a.upstream))
    if base == to:
        print("already at %s: nothing to do" % base[:8])
        return

    # (no rename detection: a renamed file is a removal and a new file, each judged on its own path)
    names = git(a.upstream, "diff", "--no-renames", "--name-status", "-z", base, to, "--", *PATHS).stdout.decode("utf-8").split("\0")
    changes = list(zip(names[0::2], names[1::2]))
    tracked = set(git(ROOT, "ls-files", "-z").stdout.decode("utf-8").split("\0"))
    changed_here = set()   # (compared as blobs, the index's with the base's renamed: no line-ending filter between)
    for status, path in changes:
        if status == "D" and rename_full.map_path(path) in tracked:
            old = rename_full.map_bytes(path, git(a.upstream, "show", "%s:%s" % (base, path)).stdout)
            if (git(ROOT, "hash-object", "--stdin", data=old).stdout.strip() !=
                    git(ROOT, "rev-parse", ":" + rename_full.map_path(path)).stdout.strip()):
                changed_here.add(path)
    take, skip = split(changes, tracked, changed_here)
    print("Longshot %s..%s: %d files changed, %d to apply, %d not applied" % (base[:8], to[:8], len(changes), len(take), len(skip)))
    for path, why in skip:
        print("  not applied (%s): %s" % (why, path))
    if any(path == STAND_IN for _, path in changes):
        old, new = (git(a.upstream, "show", "%s:%s" % (rev, STAND_IN), check=False).stdout.decode("utf-8", "replace")
                    for rev in (base, to))
        with open(os.path.join(ROOT, STAND_IN), encoding="utf-8") as f:
            lacking = names_lacking(old, new, f.read())
        print("  %s: Longshot's gained %s" % (STAND_IN, "these names, which the stand-in lacks: " + ", ".join(lacking)
                                               if lacking else "no name that the stand-in lacks"))
    if a.list:
        for path in take:
            print("  to apply: %s" % path)
        return
    if git(ROOT, "status", "--porcelain", "--", *PATHS).stdout.strip():
        sys.exit("the work tree has changes under the imported paths: commit or stash them first")

    failed = False
    if take:
        # (--full-index: the blobs' whole ids, which the three-way merge needs to find the base's files here: the renamed
        # files of both sides are written into this repository as blobs, so git has them)
        with tempfile.TemporaryDirectory() as tmp:
            old = renamed_tree(a.upstream, base, take, os.path.join(tmp, "base"))
            new = renamed_tree(a.upstream, to, take, os.path.join(tmp, "to"))
        diff = git(ROOT, "diff", "--no-renames", "--binary", "--full-index", old, new).stdout
        r = git(ROOT, "apply", "-3", "--whitespace=nowarn", data=diff, check=False)
        sys.stderr.write(r.stderr.decode("utf-8", "replace"))
        failed = r.returncode != 0
        # (a patch git could not even try, e.g. a base file it does not have, stops the whole apply with nothing changed)
        if failed and not git(ROOT, "status", "--porcelain", "--", *PATHS).stdout.strip():
            sys.exit("nothing was applied (above); the base stays at %s" % base[:8])
    with open(PROVENANCE, "w", encoding="utf-8", newline="\n") as f:
        f.write(BASE_LINE.sub(lambda m: m.group(1) + to, text, count=1))
    print("upstream-base is now %s (PROVENANCE.md). Not committed." % to)
    if failed:
        sys.exit("some files have conflicts or did not apply (above): settle them, `git add` them, then test and commit")


if __name__ == "__main__":
    main()
