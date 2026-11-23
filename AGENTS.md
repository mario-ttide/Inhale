# Notes for AI coding agents

Inhale is a work-in-progress PC port of one game by static recompilation: Python tools translate the game's AArch64
code to C, a native runtime in C stands in for the console's system, and a Vulkan back end replays the graphics
calls. It is a fork of Longshot (`PROVENANCE.md`), and most of the code is still Longshot's.

- **Building and running:** [README.md](README.md).
- **Stages, their exit checks and what is known about this game:** [docs/design.md](docs/design.md). Update it with
  what you find.
- [CONTRIBUTING.md](CONTRIBUTING.md) applies to agents as to everyone.
- **Fixing a bug:** follow the [fix-with-test skill](.claude/skills/fix-with-test/SKILL.md).
- **Bringing Longshot's later changes over:** follow the [sync-upstream skill](.claude/skills/sync-upstream/SKILL.md).
- **Before a push, and before a release:** follow the [verify skill](.claude/skills/verify/SKILL.md), a headless
  walk on this PC's GPUs with its shots compared (before a release, the Windows PC's too). The checks cannot see a
  picture.

## Following Longshot

Longshot moves fast (about 80 commits a day), and `scripts/sync_upstream.py` merges its changes into this tree. Every
line of an imported file that differs here can meet a change of Longshot's and conflict. So:

- **Keep diffs to imported files small.** This game's code goes in files of its own (`host/kirby_*.c`,
  `nx2/kirby_*.py`), and an imported file gets the few lines that call it.
- **Mark a change to imported code** with `(inhale)` in its comment, as the tree does (`nx2/lift.py`), and say why
  there. The mark tells the next sync which side of a conflict is this fork's.
- **The other game's code (`oot_*`) is gated on that game's build id, not deleted.** Those files are Longshot's and
  keep arriving. `nx2/oot_patches.py` is the one exception: a stand-in written here, which a sync does not touch.
- **Never rename by hand.** `scripts/rename_full.py` changed Longshot's name to this fork's through the tree, and a
  sync puts Longshot's files through the same rule. Write new code with this fork's names. A name that the rule gets
  wrong is fixed in the rule; `python -I scripts/rename_full.py` must report nothing left to rename.
- **In code and comments, Longshot is "upstream".** The rule renames its name wherever it stands, so a comment that
  says "Longshot's rows" becomes "Inhale's rows" at the next run and says the opposite. Only the files the rule keeps
  whole name it (`KEEP_FILES` and `KEEP_DIRS` in `scripts/rename_full.py`: this page, the documents, `.claude/`).
- **A menu text of this fork is translated in `gpu/vk/menu_i18n_inhale.h`**, never in `gpu/vk/menu_i18n.h`: that file
  is kept as Longshot has it, since a row added there conflicts with every row Longshot adds (each table's count is
  written in it). A text of Longshot's that this fork rewords or removes in `gpu/vk/vk_menu.cpp` keeps its row and is
  listed in `kRetired` (`tests/test_menu_i18n_inhale.py`).
- **Do not reformat, reorder or tidy imported code**, and do not fix what is Longshot's to fix in a way that will
  differ from its fix: every such line is a conflict later.

## Make the change

- **Tests read the source.** Many checks in `tests/` cut a function out of a source file by its text and compile it
  with stubs. Renaming or reshaping a function can break a check far from your change: run
  `python -I -B tests/run_all.py` and update the check in the same commit rather than weakening it. A new check cuts
  with `tests/srccut.py` (`block`, `between`), which stops with one message naming the source and the marker when a
  marker is missing or appears twice; many older checks still carry a brace counter of their own.
- **A `doc:` comment names a rule.** `// doc: docs/design.md#...` above a function says the rule it keeps is written
  there: read it before you simplify a capture, a wait or a pass split away. `tests/test_doc_anchors.py` checks that
  every anchor resolves.
- **The renderer's interface is versioned.** A change to `MkwVkHost` or `MkwVkRenderer` in `gpu/vk/vk_api.h` bumps
  `MKWVK_API_VERSION`.
- **Generated files are generated.** The SPIR-V headers in `gpu/vk/shaders/` (`*_spv.h`) are compiled from the shader
  beside them, and name its SHA-256: regenerate them with glslang (the shaders' tests show the command) rather than
  editing them.
- **third_party/ is checked.** Its parts must match the `tree-sha256` in their `PROVENANCE.md`
  (`python -I scripts/check_third_party.py`); a fix goes outside them, not into them.
- **Paths are UTF-8.** Keep host code portable (Longshot builds it for Windows too) and paths UTF-8 (no `CP_ACP`;
  `tests/test_utf8_paths.py`).
- **CI runs after the push, and no game in the checks.** `.github/workflows/ci.yml` runs `tests/run_all.py --strict`,
  the `third_party/` check and the rename on every push to `main` and every pull request, on Linux. That is after your
  change has landed: run `python -I -B tests/run_all.py` yourself first and say what it printed. Compare a failure
  with the tree before your change before you call it yours. The checks run without the game; a run in the game is
  yours to do and report.
- **A skip is not a pass.** A check whose compiler, headers or tool this PC lacks is skipped, and CI has them all, so
  a run with nothing failed here can still fail there. The Vulkan headers are found only by
  `INHALE_VULKAN_HEADERS=<folder holding vulkan/vulkan.h>` (not in `/usr/include`); set it, add `--strict`, and read
  what is still skipped.
- **A change a player sees updates `README.md` in the same commit**: a menu row, a setting or environment variable a
  player may set, what the first start does, a line of the status table. `docs/design.md` is for how and why; the
  README is what a player reads. Before a release, check that the README says what the release changes.
- **Builds go under `work/`**, which git ignores, and never on a RAM file system (`/tmp` is often one).
