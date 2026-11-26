// (inhale) A draw that samples a colour target it writes is drawn into a copy of that target.
//
// Kirby and the Forgotten Land's lighting pass (program 62830cf22f14b2ae) is one full-screen draw into the scene's
// target that also samples it: the G-buffer pass left the light each surface gives off there, and the lit colour is
// written over it. Its tone map (5be22000a0782116) reads and writes the scene the same way. The console's GPU gives each
// pixel what was there before the draw. Vulkan leaves the read undefined, and AMD's Windows driver (a Radeon 780M,
// driver 26.11.2) answered garbage in the 8x8 texel blocks that the draw's two triangles share, along the picture's
// diagonal: a few texels of 35,000 in the scene, which the game's bloom and lens flare made into coloured discs and a
// dotted line. RADV (RX 7900 XTX, the integrated Radeon of a Ryzen 9 7900X) and NVIDIA's driver (RTX 2080 SUPER) drew
// the same draw right.
//
// So such a draw's pass is begun with a copy of each colour target it samples and writes: the target is copied into
// the copy, the draw is drawn there while it samples the target, which nothing writes then, and the copy is copied
// back when the draw ends. Two copies of the target a draw: on by default only where the fault was seen
// (feedback_copy.h: AMD's Windows driver; RX_VK_FEEDBACK_COPY=1 or 0 on any driver). The depth target a draw samples
// and writes stays as it is.
//
// A frame dump (RX_VK_DUMP) and a probe read such a pass's target as its pass ends, before the copy back: they show it
// as it was before the draw, and the draw's result in the next pass that writes it.
#pragma once

#include <cstdint>

#include "vk_internal.h"

namespace mkwvk {

struct Texture;

namespace feedback {

/// What one draw drew into copies. Its destructor ends the draw's pass and copies each back into its target: declared
/// in the draw, so that it runs on every way out of it. Every draw has one: nothing is set or called for a draw with
/// no copy
struct Draw {
    struct Item {
        VkImage target, copy;
        uint32_t level, layer;
    };
    VkCommandBuffer cmd = VK_NULL_HANDLE;   // (null: nothing was drawn aside)
    int n = 0;
    uint32_t width = 0, height = 0;
    Item item[8];   // (the first n)
    Draw() = default;
    Draw(const Draw&) = delete;
    Draw& operator=(const Draw&) = delete;
    ~Draw() {
        if (cmd) end();
    }
    void end();
};

/// feedback_copy::wanted for this device and run, said once in the log
bool wanted();

/// Before the pass of a draw that samples and writes the colour targets in `targets` (feedback_copy::targets), outside
/// a pass: each such target's viewed level and layer is copied into a copy of its size, and color_view[i] becomes the
/// copy's view, in the format the target is drawn in. A target this cannot copy (not a plain 2D image, or one that
/// cannot be copied from and into) keeps its view. False when none was replaced
bool begin(Draw& draw, VkCommandBuffer cmd, uint16_t targets, Texture* const color[8], VkImageView color_view[8],
           const VkFormat color_format[8], const uint32_t color_level[8], const uint32_t color_layer[8], uint32_t width,
           uint32_t height);

/// Outside a pass: `t` (its level 0 and layer 0, whole) is copied into a copy, which the draw's end copies back into it.
/// What the draw's commands change in `t` meanwhile is then undone (a ReShade preset on this game's scene, which the
/// next frame reads: kirby_reshade.h). False, and nothing recorded, when `t` cannot be copied from and into, or the
/// draw holds copies already
bool keep(Draw& draw, VkCommandBuffer cmd, const Texture* t);

} // namespace feedback
} // namespace mkwvk
