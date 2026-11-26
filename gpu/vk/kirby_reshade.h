// (inhale) ReShade in this game (Kirby and the Forgotten Land, Switch 2 Edition): docs/design.md, "issue #31, ReShade
// presets do nothing". Upstream records a preset on its game's gameplay upscale output only (vk_draw.cpp
// upscale_picture), which this game never draws: its scene (B10G11R11, tone-mapped by ScreenFilter, at the dynamic
// resolution's size) goes into the window texture by one Copy draw, and the HUD is drawn after it. So the preset is
// recorded on the scene just before that draw samples it, the draw the FPS counter's footer records too (kirby_route.h
// copy_drawn).
#pragma once

#include <cstdint>

#include "kirby_route.h"

namespace mkwvk::kirby_reshade {

/// Whether the draw is the Copy of this game's scene into the window texture, with ReShade on (`enabled`): Copy's
/// program, into a target of the last present's texture size that is not of the scene's format (target_scene), sampling
/// first a picture of the scene's format (in_scene) of in_w x in_h
inline bool scene_copy(bool enabled, bool this_game, uint64_t program, uint32_t target_w, uint32_t target_h, bool target_scene,
                       uint32_t in_w, uint32_t in_h, bool in_scene) {
    upscale_route::Sample unused;
    return enabled &&
           kirby_route::copy_drawn(this_game, program, target_w, target_h, target_scene, in_w, in_h, in_scene, &unused);
}

}  // namespace mkwvk::kirby_reshade
