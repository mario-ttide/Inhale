"""Compare the shots of a headless walk with a reference walk's (the verify skill, .claude/skills/verify/SKILL.md).

Both folders hold the renderer's shots (RX_VK_SHOTS=<folder> RX_VK_SHOT_EVERY=300: vk_000300.png, vk_000600.png, ...) of the
same walk (S5's input script, HOS_INPUT_FRAME_CLOCK=1) on the same GPU. Each frame both have is scaled to 320x180 in grey
and the mean difference of its pixels taken (0-255). Two good runs of the same build differ by up to about 15 where a
frame catches a moving thing; the black scene of issues #18 and #19 differed by 52 to 131. A frame over --limit, or a run
with fewer than --min-share of the reference's frames (it stopped, hung or slowed down), fails.

    .venv/bin/python -I scripts/kirby_shot_compare.py <reference folder> <run folder> [--limit 30] [--min-share 0.8]

Needs Pillow (the repo's .venv has it). Exit 0 when every frame is within the limit, 1 otherwise.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def grey(path):
    return Image.open(path).convert("L").resize((320, 180))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference", type=Path)
    ap.add_argument("run", type=Path)
    ap.add_argument("--limit", type=float, default=30.0)
    ap.add_argument("--min-share", type=float, default=0.8)
    a = ap.parse_args()
    ref = sorted(a.reference.glob("vk_*.png"))
    if not ref:
        print(f"no shots in {a.reference}")
        return 1
    bad, have = [], 0
    for r in ref:
        p = a.run / r.name
        if not p.exists():
            continue
        have += 1
        d = ImageStat.Stat(ImageChops.difference(grey(r), grey(p))).mean[0]
        flag = d > a.limit
        print(f"{r.name}  {d:6.1f}{'  OVER' if flag else ''}")
        if flag:
            bad.append(r.name)
    share = have / len(ref)
    print(f"{have} of {len(ref)} reference frames in the run ({share:.0%}); {len(bad)} over {a.limit:g}")
    if bad or share < a.min_share:
        print("FAIL" + (f": {', '.join(bad)} differ" if bad else "") + (": too few frames" if share < a.min_share else ""))
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
