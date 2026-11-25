// (inhale) The FPS counter footer's record (upscale_route.h) for this game (Kirby and the Forgotten Land, Switch 2
// Edition): docs/design.md, "the footer's render lines". Every path that publishes one is upstream's and knows the other
// game only: its two network keys, or an upscale that reads a picture of the scene's format and size. So the footer said
// "Resolution: not in gameplay" in this game at all times. This game draws its scene (B10G11R11, at the dynamic
// resolution's size) into the window texture with one Copy draw; when the scene is under 720 lines, through its network
// instead (kirby_upscale.h), which reads an RGBA8 picture, or through the blit that stands in for it. Here what each of
// the three records: the scene's size, and the picture's, which is the part of the window texture that is shown.
#pragma once

#include <cstdint>

#include "kirby_upscale.h"
#include "kirby_wide.h"
#include "upscale_route.h"

namespace mkwvk::kirby_route {

/// The picture's size for an image of w x h: the part of the window texture that is shown when the image is that
/// texture, shown in part (handheld: 1920 x 1080 of 3840 x 2160), else the whole image
inline void out_size(uint32_t w, uint32_t h, upscale_route::Sample* out) {
    int part[4];
    const bool shown = kirby_upscale::shown_part(w, h, part);
    out->out_w = shown ? (uint32_t)part[2] : w, out->out_h = shown ? (uint32_t)part[3] : h;
}

/// An upscale by `route` of a picture of in_w x in_h into an image of w x h (this game's network, or the blit in its
/// place), while this game runs. False for the other game, an image that is not of the last present's texture size (a
/// network that upscales something else) or an empty picture. A picture larger than what is shown is recorded at its
/// own size, as not scaled: at an output above 2560 x 1440 the docked scene is drawn at the output's size, or at an
/// ultrawide picture's (host/kirby_res.c), while the window still shows 2560 x 1440 of its texture, which the present
/// stretches to the output. The output's size is not known here, so a scene stepped down from such a size reads 100% too
inline bool upscaled(bool this_game, upscale_route::Route route, uint32_t in_w, uint32_t in_h, uint32_t w, uint32_t h,
                     upscale_route::Sample* out) {
    if (!this_game || !in_w || !in_h) return false;
    if (kirby_upscale::texture.load(std::memory_order_relaxed) != (w << 16 | (h & 0xffff))) return false;
    upscale_route::Sample r;
    r.route = route, r.in_w = in_w, r.in_h = in_h;
    out_size(w, h, &r);
    if (r.out_w < in_w || r.out_h < in_h) r.out_w = in_w, r.out_h = in_h;
    *out = r;
    return true;
}

/// The Copy draw that puts the scene into the window texture: Copy's program, into a target of the last present's
/// texture size that is not of the scene's format (target_scene), sampling first a picture of the scene's format
/// (in_scene) of in_w x in_h. A Copy between two scene targets, or one of a layout's capture, is not it
inline bool copy_drawn(bool this_game, uint64_t program, uint32_t target_w, uint32_t target_h, bool target_scene,
                       uint32_t in_w, uint32_t in_h, bool in_scene, upscale_route::Sample* out) {
    if (program != kirby_wide::kCopy || target_scene || !in_scene) return false;
    return upscaled(this_game, upscale_route::Route::Stretch, in_w, in_h, target_w, target_h, out);
}

}  // namespace mkwvk::kirby_route
