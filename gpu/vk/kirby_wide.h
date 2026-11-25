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

/// What the draw samples: a texture's size and whether the GPU drew it
struct Sampled {
    uint32_t width = 0, height = 0;
    bool drawn = false;
};

/// The factor the draw's viewport is widened by, about its centre: the picture's ratio over 16:9 for a bar, and for a
/// pane that shows a capture of the picture, in a 16:9 target, while this game runs on a picture wider than 16:9; 1 for
/// any other draw.
/// this_game: the host said this game runs (vk_menu.cpp, !menu_oot_rows()); ratio: the picture's (host->aspect_ratio,
/// 0 at 16:9); target: the draw's first colour target; pane: the draw's pane (whole_layout), nullptr when it has none
inline float keep_whole(bool this_game, float ratio, uint32_t target_w, uint32_t target_h, uint64_t program,
                        const Sampled* sampled, int n, const float* pane) {
    constexpr float game = 16.0f / 9.0f;
    if (!this_game || !(ratio > game * 1.01f) || program == kCopy || program == kMovie || target_h == 0 || !pane) return 1.0f;
    if (std::fabs((float)target_w / (float)target_h - game) > game * 0.01f) return 1.0f;
    if (bar(pane)) return ratio / game;
    if (!whole_layout(pane)) return 1.0f;
    for (int i = 0; i < n; i++) {
        const Sampled& t = sampled[i];
        if (t.drawn && t.height > 0 && std::fabs((float)t.width / (float)t.height - ratio) <= ratio * 0.02f)
            return ratio / game;
    }
    return 1.0f;
}

/// The factor a full-screen movie's viewport is narrowed by, about its centre: 16:9 over the picture's ratio for the
/// movie program's draw into a 16:9 target that is not of a sampled texture's size (a frame drawn into a target of its
/// own size is a hint video's, shown by a pane), while this game runs on a picture wider than 16:9; 1 for any other draw
inline float narrow_movie(bool this_game, float ratio, uint32_t target_w, uint32_t target_h, uint64_t program,
                          const Sampled* sampled, int n) {
    constexpr float game = 16.0f / 9.0f;
    if (!this_game || !(ratio > game * 1.01f) || program != kMovie || target_h == 0) return 1.0f;
    if (std::fabs((float)target_w / (float)target_h - game) > game * 0.01f) return 1.0f;
    for (int i = 0; i < n; i++)
        if (sampled[i].width == target_w && sampled[i].height == target_h) return 1.0f;
    return game / ratio;
}

/// narrow_movie or keep_whole for a draw: at its first colour target (Texture: width, height), the textures it samples
/// (gpu_written), and read_pane(float[4]), which reads its pane and returns false when it cannot (asked last: it reads
/// guest memory)
template <class Targets, class List, class ReadPane>
float viewport_scale(bool this_game, float ratio, const Targets& at, uint64_t program, const List& sampled, ReadPane read_pane) {
    if (!this_game || !(ratio > 16.0f / 9.0f * 1.01f) || at.n < 1 || !at.color[0]) return 1.0f;
    Sampled s[8];
    int n = 0;
    for (const auto* t : sampled) {
        if (n == 8) break;
        if (t) s[n++] = {t->width, t->height, t->gpu_written};
    }
    if (const float k = narrow_movie(this_game, ratio, at.color[0]->width, at.color[0]->height, program, s, n); k != 1.0f) return k;
    const float a_bar[4] = {1920.0f, 64.0f, -960.0f, 32.0f};   // (it passes whenever the target and the program do: the pane is read only then)
    if (keep_whole(this_game, ratio, at.color[0]->width, at.color[0]->height, program, s, n, a_bar) <= 1.0f) return 1.0f;
    float pane[4];
    return read_pane(pane) ? keep_whole(this_game, ratio, at.color[0]->width, at.color[0]->height, program, s, n, pane) : 1.0f;
}

/// The viewport (x, width) widened by k about its centre (narrowed by a k under 1)
inline void widen(float& x, float& width, float k) {
    const float centre = x + width * 0.5f;
    width *= k;
    x = centre - width * 0.5f;
}

/// The two strips a viewport narrowed by k (under 1) about its centre leaves of the one it was, in whole pixels of a
/// target_w x target_h target: out[i] = x, y, width, height. They reach a pixel into the narrowed viewport's edge
/// columns, which the draw that follows covers. Returns how many are not empty
inline int sides(const float narrowed[4], float k, uint32_t target_w, uint32_t target_h, int32_t out[2][4]) {
    const float half = narrowed[2] / k * 0.5f, centre = narrowed[0] + narrowed[2] * 0.5f;
    const auto col = [target_w](float x) { return (int32_t)std::fmin(std::fmax(x, 0.0f), (float)target_w); };
    const int32_t y0 = (int32_t)std::fmin(std::fmax(std::floor(narrowed[1]), 0.0f), (float)target_h);
    const int32_t y1 = (int32_t)std::fmin(std::fmax(std::ceil(narrowed[1] + narrowed[3]), 0.0f), (float)target_h);
    const int32_t x[2][2] = {{col(std::floor(centre - half)), col(std::ceil(narrowed[0]))},
                             {col(std::floor(narrowed[0] + narrowed[2])), col(std::ceil(centre + half))}};
    int n = 0;
    for (const auto& s : x)
        if (s[1] > s[0] && y1 > y0) out[n][0] = s[0], out[n][1] = y0, out[n][2] = s[1] - s[0], out[n][3] = y1 - y0, n++;
    return n;
}

}  // namespace mkwvk::kirby_wide
