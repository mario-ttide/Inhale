"""The cameras at the screen's ratio on a screen wider or narrower than 16:9 (Kirby and the Forgotten Land, Switch 2
Edition).

The game's cameras are 16:9 because a script says so: its interpreter (main+0x7cff00) calls one of two projection builders
(main+0x74dc50, main+0x74dd4c), closures whose captures hold the camera, the vertical angle, the aspect (+0x10), near and
far. Each builds the projection (p11 = 1 / tan(angle / 2), p00 = p11 / aspect) and keeps the aspect at the camera's +0xf4.
The script hands them 16 / 9. The per-frame camera buffer (c16, written by main+0x80e090) also carries an aspect of its own,
the width over the height of the last of the graphics system's six sizes (2560 x 1440, main+0x64fbb4): 16 / 9 too.

The patch: C after each of the three places where that aspect is in a register (the builders' load of the capture's +0x10,
and main+0x80e20c's divide) gives host/kirby_wide.c's ratio instead, when the aspect is 16 / 9 and the host chose a
picture of another shape (hos_wide_ratio, host/hos_main.c). The vertical angle stays the game's, so a 21:9 screen shows
more at the sides and nothing less above and below. A 16:9 screen, or a camera of another aspect, keeps the game's.

The fourth place is not a camera: the frustum builder (main+0x627680; s0 the vertical angle, s1 the aspect, s2 near, s3
far) that main+0x79f0c0 calls each frame for the planes at world+0x300. The update levels test each object's spheres
against those planes (main+0x628380 from main+0x8e1dc0), and an object outside them updates at 30 or 15 a second
(docs/design.md, "far objects at 30 and 15 updates a second"). Its aspect is 16 / 9 from data the camera hooks do not
reach, so at 32:9 the objects beside the middle 16:9 were judged out of view. C after its first instruction (an adrp,
which leaves s1) gives the builder the screen's ratio too; its other callers' 16:9 frustums widen the same way.

The lead came from Fl4sh9174's 21:9 mod for the Switch 1 game, whose notes say the game takes the camera's ratio from one
size pair (a mov / movk of 2580 x 1080 in place of 1920 x 1080). That pair has no twin here: each 16:9 size constant of
this build was rewritten in turn and none moved the cameras (docs/design.md, "issue #20"). Nothing of the mod is copied.

The HUD, menus and prompts: drawn for 16:9 into the 16:9 window texture, which the present stretches to the picture's
shape. Every 2D layer's camera hands its projection to the view in f_8087a75c (main+0x85a75c): ld4 at main+0x85a808 loads it
as rows (v0 the first, v1 the second), then main+0x5e28e0 copies them. The layouts' cameras are an orthographic 1920 x
1080 (2 / 1920, 2 / 1080) and a perspective one of the same 16:9 shape (2.537, 4.511, the 2.5D panes); the world's
cameras are at the picture's ratio by then. C after the ld4 scales the first row by (16 / 9) / ratio when the second's
m11 over the first's m00 is still 16 / 9 (host/kirby_wide.c kirby_wide_ui): the UI keeps its shape, in the middle of
the picture. On a picture narrower than 16:9 (16:10, 4:3) the stretch is a squeeze, and the same C scales the second
row by ratio / (16 / 9) instead: the UI keeps its shape at the picture's whole width, short of its top and bottom
(issue #25). The pause menu's background is a capture of the whole picture drawn by such a camera; the renderer keeps
that draw the picture's width, or its height (gpu/vk/kirby_wide.h).

Gated on main's build id and the five words; another build leaves it out, and says so.
"""

BUILD_ID = "395fc326c2e5b1651d937074f8cfd75de63184d9"
# (offset in main, the game's word, the vector register that holds the aspect after it)
SITES = (
    (0x74dc80, 0xbd401109, 9),   # ldr s9, [x8, #0x10]   (the builder at main+0x74dc50)
    (0x74dd80, 0xbd401108, 8),   # ldr s8, [x8, #0x10]   (the builder at main+0x74dd4c)
    (0x80e20c, 0x1e211800, 0),   # fdiv s0, s0, s1       (c16's aspect: the size's width over its height)
    (0x627680, 0xd0012be8, 1),   # adrp x8, ...          (the frustum builder's first: s1 is its aspect, not yet read)
)
# (offset in main, the game's word): a camera's projection as rows in v0 to v3, before the view takes it
UI_SITE = (0x85a808, 0x4c400900)   # ld4 {v0.4s-v3.4s}, [x8]   (f_8087a75c: the camera's +0x250)
UI_HOOK = ("{ extern void kirby_wide_ui(uint64_t *r0, uint64_t *r1); kirby_wide_ui(c->vreg[0], c->vreg[1]); }"
           "   /* (nx2/kirby_wide.py: the HUD and menus at their 16:9 shape) */")


def _hook(reg):
    return ("{ extern void kirby_wide_aspect(uint64_t *v); kirby_wide_aspect(c->vreg[%d]); }"
            "   /* (nx2/kirby_wide.py: the screen's ratio) */" % reg)


def install(lifter, img, main_base, build_id):
    """The hooks into lifter.after; returns how many (0 when this is another build or code)"""
    hooks = [(off, old, _hook(reg)) for off, old, reg in SITES] + [(UI_SITE[0], UI_SITE[1], UI_HOOK)]
    if build_id != BUILD_ID or any(img.word(main_base + off) != old for off, old, _ in hooks):
        print("wide cameras: unsupported camera code, left out")
        return 0
    for off, _, text in hooks:
        pc = main_base + off
        lifter.after[pc] = (lifter.after[pc] + "\n" if pc in lifter.after else "") + text
    print("wide cameras: the 16:9 aspect at the screen's ratio, the UI at 16:9 (%d sites)" % len(hooks))
    return len(hooks)
