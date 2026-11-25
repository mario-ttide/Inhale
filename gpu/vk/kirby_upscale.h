// (inhale) The stand-in for this game's upscale network (Kirby and the Forgotten Land, Switch 2 Edition): docs/design.md,
// "handheld on a slow GPU". When the game's dynamic resolution steps down, its picture goes from colour grading through
// three passes and then a network (compute programs 2e0288cb2abe176e, cf6c798537325d54) that upscales it into the window
// texture. The window texture is 3840 x 2160 and the game shows a part of it (nvnWindowSetCrop: 1920 x 1080 in the
// handheld profile); the network writes that part only. Where the network is left out (a card without cooperative
// matrices: vk_shader.cpp), upstream's stand-in (vk_draw.cpp upscale_stub) fills the whole image, so the screen showed the
// lower left quarter of the scene, twice as large, and dark: its shader reads the picture decoded and stores it as read.
// Here the part the window shows, as the last present had it, for a blit of the scene into that part alone: both images
// hold the encoded bytes, which a blit copies as they are.
#pragma once

#include <atomic>
#include <cstdint>

namespace mkwvk::kirby_upscale {

/// The last present's texture size (tw << 16 | th) and the part of it the window shows (x, y, width, height, 16 bits
/// each; 0: the whole texture, or no present yet)
inline std::atomic<uint32_t> texture{0};
inline std::atomic<uint64_t> part{0};

/// A present of a tw x th texture with `crop` (x, y, width, height; null or empty: the whole texture). Noted as a part
/// only when it lies inside the texture and is less than all of it
inline void note_present(uint32_t tw, uint32_t th, const int crop[4]) {
    const bool in = tw <= 0xffff && th <= 0xffff && crop && crop[0] >= 0 && crop[1] >= 0 && crop[2] > 0 && crop[3] > 0 &&
                    (uint32_t)crop[0] + (uint32_t)crop[2] <= tw && (uint32_t)crop[1] + (uint32_t)crop[3] <= th &&
                    ((uint32_t)crop[2] < tw || (uint32_t)crop[3] < th);
    texture.store(tw << 16 | (th & 0xffff), std::memory_order_relaxed);
    part.store(in ? (uint64_t)crop[0] << 48 | (uint64_t)crop[1] << 32 | (uint64_t)crop[2] << 16 | (uint64_t)crop[3] : 0,
               std::memory_order_relaxed);
}

/// Whether an upscale's output image of w x h is the window texture, shown in part only; out: that part's x, y, width,
/// height
inline bool shown_part(uint32_t w, uint32_t h, int out[4]) {
    const uint64_t v = part.load(std::memory_order_relaxed);
    if (!v || texture.load(std::memory_order_relaxed) != (w << 16 | (h & 0xffff))) return false;
    out[0] = (int)(v >> 48), out[1] = (int)(v >> 32 & 0xffff), out[2] = (int)(v >> 16 & 0xffff), out[3] = (int)(v & 0xffff);
    return true;
}

}  // namespace mkwvk::kirby_upscale
