---
name: verify
description: Run S5's headless walk on this PC's two GPUs before every push, and on the Windows PC's two as well before a release tag, and compare each run's shots with a reference walk on the same GPU. Use when asked to push, to tag or release, to verify, to test in the game or to run headless.
---

# A headless walk on every GPU, its shots compared

`tests/run_all.py` runs without the game: it cannot see a picture. The v3.1.1 sync passed every check and its headless
runs (which counted fence stalls in the log) and still drew the scene black on every GPU (issues #18 and #19,
`docs/design.md`). A run is checked by its shots, on each GPU, every time.

## When

- **Before every push** of a change that reaches the game (`host/`, `gpu/`, `nx2/`, a sync): this PC's two GPUs.
- **Before a release** (a tag and its push): this PC's two GPUs, the Windows PC's two and the Intel PC's integrated one.
- Not for a push of documents or checks alone, and not after each edit: the walks cost minutes.

A GPU that cannot be reached is named in the report as not run, never left out in silence, and the push or the
release waits for the person you work for to say go on without it.

## The walk

S5's walk, with a shot every 300 presents:

    HOS_INPUT_FRAME_CLOCK=1 RX_VK_SHOT_EVERY=300 RX_VK_SHOTS=<folder>
    HOS_INPUT_SCRIPT="10:A,20:LUP/9000,23:A,26:A,30:LRIGHT/2000,33:LUP/10000,36:B,40:A/800,45:LLEFT/2000,48:LUP/8000,52:B/1500,58:LUP/10000"

110 s on a discrete GPU, 240 s on an integrated one. A build that translates the programs again (a new renderer on
Windows) needs 300 s more on its first run: run it once to warm the cache, then the walk.

## The GPUs

1. **This PC (Linux)**, both GPUs: `RX_VK_DEVICE=1` and `RX_VK_DEVICE=0` (the log's `vk: device <n>:` lines name
   them; the `vk: policy: facts` line names the one taken). Run with `work/boot.sh <name> <s>` and `RUNDIR=<dir>
   TRACE=`; it builds first.
2. **The Windows PC** (releases only), both GPUs, with a Windows build of the same tree (exe and DLL). Its scripts,
   folders and build recipe are in the agent's notes for this project, not here.
3. **The Intel PC** (releases only, since v0.5.0): its Intel integrated GPU, the one Intel driver for Windows in the
   walks (the renderer takes paths of its own there, such as the float atomic add's). The integrated GPU's 240 s,
   with the same Windows build. Which PC and how to reach it are in the agent's notes; its device number is read
   from the log's `vk: device <n>:` lines on the first run and kept there. The first release it walks has no
   reference: walk the last release and the candidate, look at both runs' shots, compare the two with each other,
   and keep the last release's walk as the reference when both draw right.

## The check

For each GPU, compare with a reference walk of the last build known to draw right on that GPU (a release, or the last
verified commit):

    .venv/bin/python -I scripts/kirby_shot_compare.py <reference shots> <run shots>

It fails on a frame that differs by more than 30 (good runs differ by up to about 15) or on a run with under 80% of the
reference's frames. Then look at the shots yourself as well: a contact sheet of every other frame is enough to see a
black scene, a missing model or a wrong colour that a difference of the whole frame understates. A frame that fails
because the walk took another path (a timing change) is shown, and compared again with a run of the reference build
made now; it is not explained away.

A new reference is made from a build that passed, never from the run being checked.

## The report

One line per GPU: the GPU, the build, `ok` or the frames over the limit, and what was seen in the shots. With the
log's errors and the `vk: page table census` and `failed` counts beside them when they moved.
