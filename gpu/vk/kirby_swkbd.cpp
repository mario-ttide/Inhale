// (inhale) The software keyboard (issue #30): what it shows and the frames it is shown in. host/kirby_swkbd.c has the wait, the
// typing and the game's own answer; this draws it with the rest of the overlays (vk_ui.h, the menu's style) and presents it
// through present_image with nothing of the game's under it, as the start-up screen's thread does while the shaders are made.
#include "kirby_swkbd.h"

#include <algorithm>
#include <atomic>
#include <mutex>

#include "vk_framegen.h"   // (present_image)
#include "vk_internal.h"   // (dev: the window's size, and whether there is a window at all)

namespace mkwvk {
void kirby_window_size(uint32_t* w, uint32_t* h);   // (vk_main.cpp: 0x0 minimized)
}

namespace mkwvk::kirby_swkbd {
namespace {

std::atomic<bool> open_now{false};
std::mutex state_mu;   // (the game's thread writes a frame's state, any presenter reads it: never held across a present)
MkwVkSwkbd state_now{};

}  // namespace

bool up() { return open_now.load(std::memory_order_relaxed); }

int frame(const MkwVkSwkbd* state) {
    // (no window: HOS_HEADLESS=1 draws into an image of its own, and no swapchain has none: the game is then answered as the
    // player's cancel, at once, as it was before there was a keyboard)
    if (dev.offscreen || !dev.swap_extent.width || !dev.swap_extent.height) return 0;
    {
        std::lock_guard lk(state_mu);
        state_now = *state;
    }
    open_now.store(true, std::memory_order_relaxed);
    // (a minimized window: no frame presented, as the start-up screen presents none, and the keyboard stays up with what was
    // typed until the window is shown again)
    uint32_t w = 0, h = 0;
    kirby_window_size(&w, &h);
    if (w && h) present_image(nullptr, dev.swap_extent.width, dev.swap_extent.height, nullptr);   // (a cleared window, the overlays on it)
    return 1;
}

void close() { open_now.store(false, std::memory_order_relaxed); }

void draw(ui::Ctx& c) {
    MkwVkSwkbd kb;
    {
        std::lock_guard lk(state_mu);
        kb = state_now;
    }
    if (kb.len < 0) kb.len = 0;
    if (kb.len > (int)sizeof kb.text - 1) kb.len = (int)sizeof kb.text - 1;
    kb.caret = std::clamp(kb.caret, 0, kb.len);
    const float s = c.s, w = c.w, h = c.h, cx = w * 0.5f;
    c.d->AddRectFilled(ImVec2(0, 0), ImVec2(w, h), ui::kStartBg);   // (the game's own picture, stopped)
    const float bw = std::min(w - 2 * (c.safe + 24 * s), 760 * s), bh = 96 * s;
    const float bx = cx - bw * 0.5f, by = h * 0.5f - bh * 0.5f, cy = by + bh * 0.5f;
    ui::text_centre(c, c.f.heading, 22 * s, ImVec2(cx, by - 56 * s), ui::kInk, "Enter the text");
    ui::box(c, ImVec2(bx, by), ImVec2(bx + bw, by + bh));
    // (what has been typed, a caret between the characters: the largest size that fits the box, down to 14 points)
    const float room = bw - 44 * s;
    const auto line_width = [&](float px) {
        float x = std::max(2.0f, 2 * s) + 2 * s;   // (the caret's bar and its gap)
        for (int i = 0; i < kb.len; i++) {
            const char ch[2] = {kb.text[i], 0};
            x += ui::size_of(c.f.strong, px, ch).x + 2 * s;
        }
        return x;
    };
    const float px = ui::fit_px(34 * s, 14 * s, 1 * s, room, line_width);   // (0: not even the smallest fits: the box alone)
    float x = bx + 22 * s;
    for (int i = 0; px > 0 && i <= kb.len; i++) {
        if (i == kb.caret) {
            const float bar = std::max(2.0f, 2 * s);
            c.d->AddRectFilled(ImVec2(x, cy - px * 0.62f), ImVec2(x + bar, cy + px * 0.62f), ui::kInk);
            x += bar + 2 * s;
        }
        if (i < kb.len) {
            const char ch[2] = {kb.text[i], 0};
            x += ui::text(c, c.f.strong, px, ImVec2(x, ui::mid_top(c.f.strong, px, cy)), ui::kInk, ch) + 2 * s;
        }
    }
    // (the prompts at the bottom: the keys' caps, or the pad's buttons when one was used last, which accept and leave too)
    const ui::Prompt prompts[] = {{ui::kConfirm, "Accept"}, {ui::kBack, "Cancel"}};
    ui::prompt_bar(c, prompts, (int)(sizeof prompts / sizeof prompts[0]));
}

}  // namespace mkwvk::kirby_swkbd
