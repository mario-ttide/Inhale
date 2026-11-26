// (inhale) The pause menu's background, the cutscene bars and the movies on a picture wider than 16:9 (Kirby and the
// Forgotten Land, Switch 2 Edition):
// docs/design.md, "issue #20, ultrawide". nx2/kirby_wide.py narrows every layout camera still at 16:9 by 16:9 over the
// picture's ratio, so the present's stretch of the 16:9 window texture gives the HUD and menus their own shape in the
// middle. The pause menu draws its background with such a camera too: a blurred capture of the whole picture (the
// scene copied, then cut to 320 x 90 at 5120 x 1440 and blurred), a pane over the whole layout. Narrowed, it covers the
// middle 16:9 only, and the sides show the scene behind it unblurred. Its draw is told by what it samples, a texture the
// GPU drew, of the picture's shape, while it draws into a 16:9 target, and by its pane, the whole layout (the layout
// programs' vertex constants, c3 at +528: width, height and the top left corner, 2398 x 1478 at -1199, 739 here). The
// frosted panes of the HUD and the menus sample that capture too (228 x 80, 80 x 80): their viewports stay. The
// background's is widened back by the ratio over 16:9, about its centre. Copy (the one program of every blit, not a
// layout's) draws the captured scene into the window texture at its whole width already and is left. Every camera here is of one class, its screens driven by the game's
// scripts: no screen the game side could key, as upstream keys its game's (nx2/oot_wide.py KEEP_VTABLES).
//
// Two more draws, measured on a first start at 5120 x 1440 (docs/design.md, "the cutscene bars and the movies"):
// - A cutscene's black bars are layout panes, 1920 x 64 at -960, 32, each drawn twice (a 1920 x 64 picture and an 8 x 8
//   fill, by two layout programs, the second the one of most plain panes). Narrowed, they end at the middle 16:9 and
//   the scene shows beside them. A pane as wide as the layout, centred, and no higher than an eighth of it is widened
//   as the pause background is. The only other pane that wide seen is 975 high (a picture of the pause menu) and stays.
// - A full-screen movie (mov/EventMovie, 1920 x 1080) is no pane: one program turns the decoded frame's two planes into
//   colours and draws them over the whole window texture, so the present stretched it to the picture's width. Its
//   viewport is narrowed by 16:9 over the ratio about its centre. Copy draws the scene target there first, grey (188)
//   while a movie plays, so the two strips the narrowed viewport leaves are cleared to black before the draw. A hint
//   video (mov/GuideMovie, 480 x 270) goes through the same program into a target of the frame's own size, which a
//   pane then shows: left.
//
// The wipes, the loading screen and the stage panel, measured on a walk into a stage and out of it at 5120 x 1440
// (docs/design.md, "the wipes, the loading screen and the stage panel"):
// - A wipe's cover and a loading screen's fill are panes of the layout's own size, 1920 x 1080 at -960, 540: a fill
//   with an 8 x 8 texture, a fill with the star's hole cut by a mask in the same draw, a layer shown through that mask,
//   the stage panel's preview picture (one of its panes 480 x 270, scaled by 4). Narrowed, each ends at the middle
//   16:9 with the scene, black or the blurred map beside it.
//   Widened whole, the star and the picture would be stretched. So the draw is drawn again for each side strip, before
//   the draw itself (plan, side_strips): the scissor is the strip, and the viewport puts the pane's outer edge on the
//   picture's edge and is as wide as the device allows, so that the strip shows the pane's outer slice stretched (100
//   of the middle's 1280 columns at 32:9 with a limit of 16384). Strips and middle share no pixel, so blend and the
//   order with other draws stay the game's. A shape that reaches the slice is smeared along the strip. Only for a
//   camera that is narrowed, a program of a layout's (reads_pane) and a pane in all four corners of the screen
//   (corner_sides): a pane that only touches a side (a button sliding in, the pause menu's glow) is left.
// - The loading screen also has a 900 x 500 blot in two corners. A strip smeared its outer slice down the whole side,
//   a seam at the middle's edge. A pane in one corner is moved instead: its viewport goes aside by half of what the
//   narrowing leaves, so the blot is in the picture's corner with the game's shape, over the fill's strip. In a wipe's
//   layer (below) it would end at the layer's side and the cover's strips would smear it: there its viewport is put
//   off the target, and the blots come when the wipe is over.
// - A wipe draws its layer (the loading screen, the rays) into a 16:9 target of its own with the narrowed cameras, and
//   a narrowed pane then shows that target: narrowed twice, a band in the middle of the middle. A layout's draw into
//   a 16:9 target that is not the window texture (not of the last present's size: kirby_upscale.h) is widened back by
//   the ratio over 16:9, so the layer holds the screen at 16:9.
// - The stage's name on the loading screen is a 1920 x 120 pane of text the GPU drew: a bar's shape. A bar's textures
//   are the game's own uploads, so a pane that samples a texture the GPU drew is no bar.
//
// A pane's clip (docs/design.md, "the 2D effects and a layout's clip"; issue #20's later shots at 5120 x 1440): the game
// sets a scissor for some panes (File 1's ribbon inside its card, a world's name, a portrait at the layout's left edge),
// in the viewport's pixels for the layout at 16:9. The pane is drawn narrowed and the clip was not: the ribbon came
// out of its card's left and was cut after "Wild", a name's text or the portrait was cut away whole. For a layout's
// program under a narrowed camera the clip is narrowed with the pane, about the viewport's centre, and moved with a
// pane that is moved (plan, clip). An edge of the clip on the viewport's own edge stays there (the layouts are not cut
// to the middle 16:9: a strip and a moved pane draw beside it), so a scissor over the whole viewport along the axis is
// left; and so is the clip of a draw that is widened back (a layer's).
//
// A picture narrower than 16:9 (16:10, 4:3; docs/design.md, "16:10 and 4:3: the HUD and menus at their own shape",
// issue #25): the present squeezes the 16:9 window texture to the picture's width, so nx2/kirby_wide.py scales the
// second row of every layout camera still at 16:9 by the ratio over 16:9 (0.9 at 16:10). The HUD and menus then have
// their own shape at the picture's whole width, and every layout ends short of the picture's top and bottom (5% of the
// height each at 16:10). Each rule above has its twin along y (axis): the pause background and a bar are heightened
// by 16:9 over the ratio (a bar is back at the picture's edge), a movie is lowered by the ratio over 16:9 with the
// strips above and below it cleared, a layer's draws are heightened, a pane in all four corners gets a strip above
// and one below, and a pane in one corner is moved up or down. The layout's +y is the higher row of the target: this
// game's window origin is the lower left, so dynamic_state does not turn its viewports over.
#pragma once

#include <cmath>
#include <cstdint>

namespace mkwvk {
bool menu_oot_rows();   // (vk_menu.cpp: false only once the host said this game runs)
}

namespace mkwvk::kirby_wide {

/// Where a layout program's vertex constants (c3) hold its pane: width, height, left, top, in layout units (1920 x 1080
/// the screen, the origin at its centre, +y up)
inline constexpr uint32_t kPaneAt = 528;

/// Whether a pane (width, height, left, top) covers the whole 1920 x 1080 layout and is centred on it
inline bool whole_layout(const float pane[4]) {
    return pane[0] >= 1920.0f && pane[1] >= 1080.0f && std::fabs(pane[2] + pane[0] * 0.5f) < 1.0f &&
           std::fabs(pane[3] - pane[1] * 0.5f) < 1.0f;
}

/// Whether a pane (width, height, left, top) is a strip as wide as the 1920 x 1080 layout, centred on it, and no higher
/// than an eighth of it: a cutscene's bar (64 high; a 2.35:1 picture's bars would be 131)
inline bool bar(const float pane[4]) {
    return pane[0] >= 1920.0f && pane[1] > 0.0f && pane[1] <= 135.0f && std::fabs(pane[2] + pane[0] * 0.5f) < 1.0f;
}

/// Copy, the program of every blit (shader/Copy): a full-screen draw that takes no layout's projection
inline constexpr uint64_t kCopy = 0x272f3b6f806b3a33ull;
/// The program that draws a decoded movie frame (its two planes to colours): a full-screen draw, no layout's either.
/// Neither has a pane: the constants at kPaneAt are still the last layout's when they draw
inline constexpr uint64_t kMovie = 0x6f37d965729ec917ull;

/// The axis the rules work along: 0 (x) on a picture wider than 16:9, 1 (y) on a narrower one, -1 on a 16:9 picture
/// (ratio: host->aspect_ratio, 0 at 16:9)
inline int axis(float ratio) {
    constexpr float game = 16.0f / 9.0f;
    return ratio > game * 1.01f ? 0 : ratio > 0.0f && ratio < game * 0.99f ? 1 : -1;
}

/// What nx2/kirby_wide.py scales a layout camera by along that axis: 16:9 over the ratio on a wider picture, the ratio
/// over 16:9 on a narrower one (under 1)
inline float narrowing(float ratio) {
    constexpr float game = 16.0f / 9.0f;
    return ratio > game ? game / ratio : ratio / game;
}

/// What gives a narrowed draw the whole picture back along that axis: the ratio over 16:9, or 16:9 over the ratio
/// (over 1)
inline float widening(float ratio) {
    constexpr float game = 16.0f / 9.0f;
    return ratio > game ? ratio / game : game / ratio;
}

/// What the draw samples: a texture's size and whether the GPU drew it
struct Sampled {
    uint32_t width = 0, height = 0;
    bool drawn = false;
};

/// The factor the draw's viewport is widened by, about its centre: the picture's ratio over 16:9 for a bar (a pane of
/// that shape that samples nothing the GPU drew), and for a pane that shows a capture of the picture, in a 16:9 target,
/// while this game runs on a picture wider than 16:9; 1 for any other draw. On a picture narrower than 16:9 it is the
/// factor the viewport is heightened by, 16:9 over the ratio (widening).
/// this_game: the host said this game runs (vk_menu.cpp, !menu_oot_rows()); ratio: the picture's (host->aspect_ratio,
/// 0 at 16:9); target: the draw's first colour target; pane: the draw's pane (whole_layout), nullptr when it has none
inline float keep_whole(bool this_game, float ratio, uint32_t target_w, uint32_t target_h, uint64_t program,
                        const Sampled* sampled, int n, const float* pane) {
    constexpr float game = 16.0f / 9.0f;
    if (!this_game || axis(ratio) < 0 || program == kCopy || program == kMovie || target_h == 0 || !pane) return 1.0f;
    if (std::fabs((float)target_w / (float)target_h - game) > game * 0.01f) return 1.0f;
    if (bar(pane)) {   // (a pane of that shape with text the GPU drew is a title, not a bar)
        for (int i = 0; i < n; i++)
            if (sampled[i].drawn) return 1.0f;
        return widening(ratio);
    }
    if (!whole_layout(pane)) return 1.0f;
    for (int i = 0; i < n; i++) {
        const Sampled& t = sampled[i];
        if (t.drawn && t.height > 0 && std::fabs((float)t.width / (float)t.height - ratio) <= ratio * 0.02f)
            return widening(ratio);
    }
    return 1.0f;
}

/// The factor a full-screen movie's viewport is narrowed by, about its centre: 16:9 over the picture's ratio for the
/// movie program's draw into a 16:9 target that is not of a sampled texture's size (a frame drawn into a target of its
/// own size is a hint video's, shown by a pane), while this game runs on a picture wider than 16:9; 1 for any other
/// draw. On a picture narrower than 16:9 it is the factor the viewport is lowered by, the ratio over 16:9 (narrowing)
inline float narrow_movie(bool this_game, float ratio, uint32_t target_w, uint32_t target_h, uint64_t program,
                          const Sampled* sampled, int n) {
    constexpr float game = 16.0f / 9.0f;
    if (!this_game || axis(ratio) < 0 || program != kMovie || target_h == 0) return 1.0f;
    if (std::fabs((float)target_w / (float)target_h - game) > game * 0.01f) return 1.0f;
    for (int i = 0; i < n; i++)
        if (sampled[i].width == target_w && sampled[i].height == target_h) return 1.0f;
    return narrowing(ratio);
}

/// Where a layout program's vertex constants hold the pane's matrix, three rows of four (scale, shear and shift)
inline constexpr uint32_t kMatrixAt = 64;

/// The sides of the layout (1: left, 2: right) a pane (width, height, left, top) moved by its matrix `m` (kMatrixAt)
/// ends on, within 4 units, while its top or its bottom ends on the layout's: a pane in a corner of the screen, and the
/// pane over the whole screen in all four. Not a turned pane (a wipe's rays), a pane that reaches past the layout (it
/// is drawn beside the middle 16:9 already), or one that only crosses an edge on its way (a button that slides in).
/// axis 1 (a picture narrower than 16:9): the same turned, 1: bottom, 2: top, while its left or its right ends on the
/// layout's
inline int corner_sides(const float pane[4], const float m[12], int axis) {
    if (m[1] != 0.0f || m[4] != 0.0f || !(pane[0] > 0.0f) || !(pane[1] > 0.0f)) return 0;
    const float xa = m[0] * pane[2] + m[3], xb = m[0] * (pane[2] + pane[0]) + m[3];
    const float ya = m[5] * pane[3] + m[7], yb = m[5] * (pane[3] - pane[1]) + m[7];
    const auto on = [](float v, float edge) { return std::fabs(v - edge) <= 4.0f; };
    const float lo[2] = {std::fmin(xa, xb), std::fmin(ya, yb)}, hi[2] = {std::fmax(xa, xb), std::fmax(ya, yb)}, edge[2] = {960.0f, 540.0f};
    const int a = axis, b = 1 - axis;   // (the sides are along a; the pane also ends on an edge across it)
    if (!on(hi[b], edge[b]) && !on(lo[b], -edge[b])) return 0;
    return (on(lo[a], -edge[a]) ? 1 : 0) | (on(hi[a], edge[a]) ? 2 : 0);
}

/// Whether a camera is a layout's as nx2/kirby_wide.py narrowed it: its projection's m11 over m00 is the picture's
/// ratio (16:9 before the hook; a perspective layout camera and an orthographic one alike)
inline bool narrowed(float m00, float m11, float ratio) {
    return m00 != 0.0f && std::fabs(std::fabs(m11 / m00) - ratio) <= ratio * 0.01f;
}

/// Whether a program is a layout's: its vertex stage reads its constants (c3) up to the pane. A blit, a blur or a
/// movie's program reads none of them and draws with the last layout's still bound
template <class Program>
bool reads_pane(const Program& p) {
    for (const auto& st : p.stages)
        if (st.nvn_stage == 0) return st.info.constant_buffer_used_sizes[3] >= kPaneAt + 16;
    return false;
}

/// (set around a side strip's draw: draw() runs its block again there, and plan gives it nothing to do)
inline thread_local bool in_strip = false;

/// A side strip's draw: its viewport (x, y, width, height) and its scissor (x, y, width, height)
struct Strip {
    float viewport[4];
    int32_t scissor[4];
};

/// The two side strips of a pane over the whole layout, drawn by a camera narrowed to 16:9 over ratio in the viewport
/// vp (x, y, width, height). A strip's scissor is the columns between the viewport's edge and the narrowed pane's (a
/// pixel is the pane's when its centre is inside it), inside the game's scissor (width or height 0: none) and the
/// target_w x target_h pass. Its viewport is `limit` wide (the device's widest) and puts the pane's outer edge on the
/// viewport's: the strip then shows the pane's outer slice, stretched. sides: which to make (1: left, 2: right).
/// axis 1 (a camera lowered to ratio over 16:9, on a picture narrower than 16:9): the same along y, the strips the
/// rows from the viewport's first and the rows to its last, their viewports `limit` high (the device's highest).
/// Returns how many are not empty
inline int side_strips(const float vp[4], float ratio, const int32_t scissor[4], uint32_t target_w, uint32_t target_h, float limit,
                       int sides, int axis, Strip out[2]) {
    const int a = axis, b = 1 - axis;
    const float q = narrowing(ratio), half = vp[2 + a] * q * 0.5f, centre = vp[a] + vp[2 + a] * 0.5f;
    int32_t lo[2] = {0, 0}, hi[2] = {(int32_t)target_w, (int32_t)target_h};
    if (scissor[2] > 0 && scissor[3] > 0)
        for (int i = 0; i < 2; i++) {
            lo[i] = scissor[i] > lo[i] ? scissor[i] : lo[i];
            hi[i] = scissor[i] + scissor[2 + i] < hi[i] ? scissor[i] + scissor[2 + i] : hi[i];
        }
    const auto px = [&lo, &hi, a](float x) { return (int32_t)std::fmin(std::fmax(std::ceil(x - 0.5f), (float)lo[a]), (float)hi[a]); };
    const int32_t x[2][2] = {{px(vp[a]), px(centre - half)}, {px(centre + half), px(vp[a] + vp[2 + a])}};
    const float from[2] = {vp[a] - limit * (1.0f - q) * 0.5f, vp[a] + vp[2 + a] - limit * (1.0f + q) * 0.5f};
    int n = 0;
    for (int i = 0; i < 2; i++) {
        if (!(sides & (1 << i)) || x[i][1] <= x[i][0] || hi[b] <= lo[b]) continue;
        Strip& s = out[n++];
        s.viewport[a] = from[i], s.viewport[2 + a] = limit, s.viewport[b] = vp[b], s.viewport[2 + b] = vp[2 + b];
        s.scissor[a] = x[i][0], s.scissor[2 + a] = x[i][1] - x[i][0], s.scissor[b] = lo[b], s.scissor[2 + b] = hi[b] - lo[b];
    }
    return n;
}

/// A scissor (x, y, width, height) the game set for a pane at 16:9, as the pane is drawn in the viewport vp. An edge
/// inside the viewport goes about the viewport's centre by q (what the camera is narrowed by), then by shift pixels,
/// along the axis; a pixel is in when its centre is. An edge on the viewport's own edge stays: there the game cuts
/// nothing a 16:9 screen shows, and the layouts are not cut to the middle 16:9 (a strip and a moved pane draw beside
/// it). One narrowed to no pixel is put off the target, since a width or a height of 0 is no scissor
inline void clip(const int32_t scissor[4], const float vp[4], float q, float shift, int axis, int32_t out[4]) {
    const int a = axis;
    const float centre = vp[a] + vp[2 + a] * 0.5f;
    const auto px = [&](int32_t x) { return (int32_t)std::ceil(centre + ((float)x - centre) * q + shift - 0.5f); };
    const int32_t from = scissor[a], to = scissor[a] + scissor[2 + a];
    for (int i = 0; i < 4; i++) out[i] = scissor[i];
    out[a] = (float)from > vp[a] ? px(from) : from;
    out[2 + a] = ((float)to < vp[a] + vp[2 + a] ? px(to) : to) - out[a];
    if (out[2 + a] <= 0) out[a] = -1, out[2 + a] = 1;
}

/// What draw() does for a draw: its viewport scaled by k about its centre along an axis, side strips drawn first, and
/// a scissor in place of the game's
struct Plan {
    int axis = 0;   // (0: the viewport's x and width, 1: its y and height, on a picture narrower than 16:9)
    float k = 1.0f;
    float shift = 0.0f;   // (the viewport moves by this many pixels along the axis, after k)
    int strips = 0;
    Strip side[2];
    bool clipped = false;   // (scissor is the draw's, the game's given back after it)
    int32_t scissor[4];
};

/// A draw's plan, while this game runs on a picture wider than 16:9 and its first colour target (Texture: width, height)
/// is 16:9: narrow_movie, or keep_whole; for a layout's program (p: key, reads_pane) under a narrowed camera, widened
/// back by the ratio over 16:9 in a target that is not the window texture (window: the last present's texture size,
/// width << 16 | height; 0: no present yet), the side strips for a pane over the whole screen (corner_sides,
/// side_strips; with a limit under twice the viewport it is widened instead), and for a pane in one corner the pixels
/// its viewport moves by to put the pane in the picture's corner (off the target in a layer). Such a draw's scissor
/// is the game's for the pane at 16:9: its edges inside the viewport are narrowed and moved with the pane (clip), and
/// it cuts the strips, unless the draw is widened back (a layer's: the two factors' product is
/// 1). vp and scissor are the game's; plain: the draw can be drawn again as it is (no mesh, indirect or query draw, no
/// copy of its target open). sampled: the textures it samples (gpu_written). read(from, out, bytes) reads its layout constants and returns
/// false when it cannot (asked last: it reads guest memory). On a picture narrower than 16:9 the same along y (axis 1):
/// heightened, lowered, a strip above and one below, moved up or down. limit: the device's widest and highest viewport
/// (maxViewportDimensions), the one along the axis taken
template <class Targets, class Program, class List, class Read>
Plan plan(bool this_game, float ratio, const Targets& at, const Program& p, uint32_t window, const List& sampled, const float vp[4],
          const int32_t scissor[4], bool plain, const uint32_t limit[2], Read read) {
    Plan out;
    const int a = axis(ratio);
    if (in_strip || !this_game || a < 0 || at.n < 1 || !at.color[0]) return out;
    out.axis = a;
    const uint32_t tw = at.color[0]->width, th = at.color[0]->height;
    Sampled s[8];
    int n = 0;
    for (const auto* t : sampled) {
        if (n == 8) break;
        if (t) s[n++] = {t->width, t->height, t->gpu_written};
    }
    if (out.k = narrow_movie(this_game, ratio, tw, th, p.key, s, n); out.k != 1.0f) return out;
    const float a_bar[4] = {1920.0f, 64.0f, -960.0f, 32.0f};   // (it passes whenever the target and the program do: the constants are read only then)
    float pane[4];
    if (keep_whole(this_game, ratio, tw, th, p.key, nullptr, 0, a_bar) <= 1.0f || !read(kPaneAt, pane, 16)) return out;
    if (out.k = keep_whole(this_game, ratio, tw, th, p.key, s, n, pane); out.k != 1.0f) return out;
    float head[kMatrixAt / 4 + 12];   // (the camera, m00 the first and m11 the sixth, then the pane's matrix)
    if (!reads_pane(p) || !read(0, head, sizeof head) || !narrowed(head[0], head[5], ratio)) return out;
    const int sides = corner_sides(pane, head + kMatrixAt / 4, a);
    const float whole[4] = {vp[0], vp[1], vp[2], vp[3]}, target[4] = {0.0f, 0.0f, (float)at.width, (float)at.height};
    const float* const v = vp[2] == 0.0f && vp[3] == 0.0f ? target : whole;
    const bool layer = window && window != (tw << 16 | (th & 0xffff));
    // (one corner: moved whole, by half of what the narrowing leaves of the viewport; in a layer, off the target. Side 1
    // is the left, or the bottom: towards 0 along the axis, the layout's +y being the higher row)
    bool strips = false;
    if (sides == 1 || sides == 2) out.shift = (sides == 1 ? -v[2 + a] : v[2 + a]) * (layer ? 2.0f : (1.0f - narrowing(ratio)) * 0.5f);
    else if (layer) out.k = widening(ratio);
    else if (sides == 3 && plain) {
        if ((float)limit[a] < v[2 + a] * 2.0f) out.k = widening(ratio);
        else strips = true;
    }
    // (a clip of the pane's own: the game's is where the pane was at 16:9. The strips are cut by the clip as it is
    // drawn: a clip that reaches the layout's side goes on over that side's strip, any other leaves the strip out)
    out.clipped = out.k == 1.0f && scissor[2] > 0 && scissor[3] > 0;
    if (out.clipped) clip(scissor, v, narrowing(ratio), out.shift, a, out.scissor);
    if (strips) out.strips = side_strips(v, ratio, out.clipped ? out.scissor : scissor, at.width, at.height, (float)limit[a], sides, a, out.side);
    return out;
}

/// The viewport (x, width) widened by k about its centre (narrowed by a k under 1)
inline void widen(float& x, float& width, float k) {
    const float centre = x + width * 0.5f;
    width *= k;
    x = centre - width * 0.5f;
}

/// The two strips a viewport narrowed by k (under 1) about its centre leaves of the one it was, in whole pixels of a
/// target_w x target_h target: out[i] = x, y, width, height. They reach a pixel into the narrowed viewport's edge
/// columns, which the draw that follows covers. axis 1: a viewport lowered by k, the strips above and below it.
/// Returns how many are not empty
inline int sides(const float narrowed[4], float k, uint32_t target_w, uint32_t target_h, int axis, int32_t out[2][4]) {
    const int a = axis, b = 1 - axis;
    const float size[2] = {(float)target_w, (float)target_h};
    const float half = narrowed[2 + a] / k * 0.5f, centre = narrowed[a] + narrowed[2 + a] * 0.5f;
    const auto px = [&size](float x, int i) { return (int32_t)std::fmin(std::fmax(x, 0.0f), size[i]); };
    const int32_t b0 = px(std::floor(narrowed[b]), b), b1 = px(std::ceil(narrowed[b] + narrowed[2 + b]), b);
    const int32_t x[2][2] = {{px(std::floor(centre - half), a), px(std::ceil(narrowed[a]), a)},
                             {px(std::floor(narrowed[a] + narrowed[2 + a]), a), px(std::ceil(centre + half), a)}};
    int n = 0;
    for (const auto& s : x)
        if (s[1] > s[0] && b1 > b0) out[n][a] = s[0], out[n][b] = b0, out[n][2 + a] = s[1] - s[0], out[n][2 + b] = b1 - b0, n++;
    return n;
}

}  // namespace mkwvk::kirby_wide
