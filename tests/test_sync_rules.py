"""The two rules a sync with Longshot stands on (scripts/rename_full.py, scripts/sync_upstream.py), on texts and lists
made here: no clone of Longshot, no game.

  - the tracker: Longshot's tracker becomes this fork's host in a text shown to the player, in a link that starts a
    string and in a link that opens a new report, and stays in a comment that names an issue or a pull request;
    a second pass changes nothing;
  - the marks on Longshot's changes stay, with a version before the name too, and so does the text of a file kept
    whole (the script that holds the shader text its compiled headers are checked against);
  - what a sync applies: a file of the other game (oot_*) is taken like any file, new or changed, and only the
    stand-in nx2/oot_patches.py is not, nor a file Longshot removed and this fork changed; the names Longshot's
    file gained that the stand-in lacks are found.

    python -I -B tests/test_sync_rules.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rename_full  # noqa: E402
import sync_upstream  # noqa: E402

UP = "git.magicbean.dev/MagicBeanDev/Longshot"
NEW = "tracker.inhale.invalid"
# (a text of Longshot, the same text here)
TEXTS = [
    # shown to the player: no scheme
    ('"To send it, open %s/issues, choose New issue"' % UP, '"To send it, open %s/issues, choose New issue"' % NEW),
    ('{"Open %s/issues/14 and attach", "Abra %s/issues/14 e anexe"},' % (UP, UP),
     '{"Open %s/issues/14 and attach", "Abra %s/issues/14 e anexe"},' % (NEW, NEW)),
    # a link that starts a string
    ('kIssueUrl = "https://%s/issues/14";' % UP, 'kIssueUrl = "https://%s/issues/14";' % NEW),
    ('ISSUE_URL = "https://%s/issues/%%d" %% ISSUE' % UP, 'ISSUE_URL = "https://%s/issues/%%d" %% ISSUE' % NEW),
    ("URL = 'https://%s/issues/14'" % UP, "URL = 'https://%s/issues/14'" % NEW),
    # a link that opens a new report, wherever it is
    ('#define FORM "https://%s/issues/new?template=a.yml"' % UP, '#define FORM "https://%s/issues/new?template=a.yml"' % NEW),
    ('"Report it: https://%s/issues/new/choose"' % UP, '"Report it: https://%s/issues/new/choose"' % NEW),
    # named in a comment: stays
    ("/// ice and snow (https://%s/issues/123," % UP, "/// ice and snow (https://%s/issues/123," % UP),
    ("// review of https://%s/pulls/9, finding 4" % UP, "// review of https://%s/pulls/9, finding 4" % UP),
    ('"see https://%s/issues/52"' % UP, '"see https://%s/issues/52"' % UP),
    # the repository itself: stays
    ("upstream: https://%s.git" % UP, "upstream: https://%s.git" % UP),
    ('REMOTE = "%s"' % UP.lower(), 'REMOTE = "%s"' % UP.lower()),
    # the name beside it is still renamed, and a length after a string follows the string
    ('longshot_log("Open %s/issues");' % UP, 'inhale_log("Open %s/issues");' % NEW),
    ('memcpy(p, "%s/issues", %d)' % (UP, len(UP) + 7), 'memcpy(p, "%s/issues", %d)' % (NEW, len(NEW) + 7)),
    # the marks on Longshot's changes: they say whose change it is
    ("/* (longshot) the Longshot log */", "/* (longshot) the Inhale log */"),
    ("/* (version 26, longshot) asked by longshot_ctl */", "/* (version 26, longshot) asked by inhale_ctl */"),
]


def main():
    for old, new in TEXTS:
        got = rename_full.map_text(old)
        assert got == new, "%r\n  became   %r\n  expected %r" % (old, got, new)
        assert rename_full.map_text(got) == got, "a second pass changed %r" % got

    # (a kept file: this text is compiled into a header under gpu/vk/shaders/, which is kept too)
    shader = b'"FfxBoolean LongshotSame(FfxInt32x2 iPx)\\n"'
    assert rename_full.map_bytes("scripts/fsr3_shaders.py", shader) == shader
    assert rename_full.map_bytes("scripts/ffx_sdk.py", shader) == shader.replace(b"Longshot", b"Inhale")

    tracked = {"nx2/lift.py", "nx2/oot_shadow.py", "host/oot_fov.c", "nx2/oot_patches.py", "scripts/inhale_ctl.py"}
    changes = [("A", "nx2/oot_new.py"), ("M", "nx2/oot_shadow.py"), ("D", "host/oot_fov.c"), ("M", "nx2/oot_patches.py"),
               ("A", "nx2/oot_patches.py"), ("M", "scripts/longshot_ctl.py"), ("M", "scripts/forge.py"), ("M", "nx2/lift.py")]
    take, skip = sync_upstream.split(changes, tracked)
    assert take == ["nx2/oot_new.py", "nx2/oot_shadow.py", "host/oot_fov.c", "scripts/longshot_ctl.py", "nx2/lift.py"], take
    assert skip == [("nx2/oot_patches.py", "a stand-in here"), ("nx2/oot_patches.py", "a stand-in here"),
                    ("scripts/forge.py", "not tracked here")], skip
    # (a file Longshot removed and this fork changed: a removal git cannot apply stops the whole apply, so it is left
    # out and listed; one removed with no change here is applied)
    take, skip = sync_upstream.split([("D", "host/oot_fov.c"), ("D", "nx2/lift.py")], tracked, {"nx2/lift.py"})
    assert take == ["host/oot_fov.c"], take
    assert skip == [("nx2/lift.py", "removed in Longshot, changed here")], skip

    old = "import re\nA = 1\ndef f(s):\n    B = 2\n    return s\n"
    new = old + "C = [\n]\ndef g(s, n=0):\n    return s\ndef h():\n    pass\nD: int = 3\n"
    here = "A = None\n\n\ndef f(s):\n    return s\n\n\ndef h():\n    pass\n"
    assert sync_upstream.names_lacking(old, new, here) == ["C", "g"], sync_upstream.names_lacking(old, new, here)
    assert sync_upstream.names_lacking(old, "", here) == []   # (Longshot removed its file)
    print("sync rules: %d texts through the rename, twice; what a sync applies; the stand-in's missing names" % len(TEXTS))


if __name__ == "__main__":
    main()
