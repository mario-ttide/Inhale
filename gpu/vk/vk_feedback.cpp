// (inhale) A draw that samples a colour target it writes is drawn into a copy of that target. See vk_feedback.h.
//
// The copies are kept by format and size, a few of them, and shared by the threads that record (RX_VK_PARALLEL): each
// draw records its copy in, its pass and its copy back in its own command buffer, in that order, and the command
// buffers run one after the other, so two draws never hold one copy at once on the GPU.
#include "vk_feedback.h"

#include <algorithm>
#include <cstdlib>
#include <functional>
#include <mutex>
#include <vector>

#include "feedback_copy.h"
#include "vk_draw.h"   // (end_pass)
#include "vk_texture.h"

#include "vk_work.h"   // (after the others: counts the commands that do GPU work, for full_barrier)

namespace mkwvk::feedback {
namespace {

constexpr size_t kCopies = 4;   // (kept at once: the scene's two targets in play, and a size change's old ones for a while)

struct Copy {
    VkImage image = VK_NULL_HANDLE;   // (null: it could not be made, and is not asked of the driver at every draw)
    VmaAllocation memory = nullptr;
    VkImageView view = VK_NULL_HANDLE;
    VkFormat format = VK_FORMAT_UNDEFINED, view_format = VK_FORMAT_UNDEFINED;
    uint32_t width = 0, height = 0;
    uint64_t used = 0;   // (texture_frame_no when last drawn into)
};

struct State {
    std::mutex mu;
    std::vector<Copy> copies;
    // (what work in flight may still use, freed once the GPU is past it: as vk_reactive.cpp's)
    struct Dead { uint64_t frame; uint64_t value; std::function<void()> free; };
    std::vector<Dead> dead;
    bool told = false;
    uint64_t drawn = 0, said = 0, tenths = 0;   // (targets drawn into a copy since frame `said`, and the figure last logged)
};
State& st() {
    static State s;
    return s;
}

void free_dead() {
    State& s = st();
    const uint64_t now = texture_frame_no(), done = vk_timeline_completed();
    for (size_t i = 0; i < s.dead.size();) {
        if (now - s.dead[i].frame > 4 && s.dead[i].value && done >= s.dead[i].value) {
            s.dead[i].free();
            s.dead[i] = std::move(s.dead.back());
            s.dead.pop_back();
        } else {
            i++;
        }
    }
}

/// The copy for a target of this format, drawn in view_format, and this size: one that is kept and that this draw has
/// not taken for another of its targets, or a new one, made with the target's own flags (the one unused for longest goes
/// when kCopies are kept). Null when it cannot be made
Copy* copy_for(const Draw& draw, VkFormat format, VkFormat view_format, VkImageCreateFlags flags, uint32_t w, uint32_t h) {
    State& s = st();
    for (Copy& c : s.copies) {
        if (c.format != format || c.view_format != view_format || c.width != w || c.height != h) continue;
        if (!c.image) return nullptr;
        bool taken = false;
        for (int i = 0; i < draw.n; i++) taken |= draw.item[i].copy == c.image;
        if (!taken) return &c;
    }
    if (s.copies.size() >= kCopies) {
        const auto oldest = std::min_element(s.copies.begin(), s.copies.end(),
                                             [](const Copy& a, const Copy& b) { return a.used < b.used; });
        if (const Copy old = *oldest; old.image)
            s.dead.push_back({texture_frame_no(), vk_retirement_value(), [old] {
                                  vkDestroyImageView(dev.device, old.view, nullptr);
                                  destroy_image(old.image, old.memory);
                              }});
        s.copies.erase(oldest);
    }
    Copy c;
    c.format = format, c.view_format = view_format, c.width = w, c.height = h, c.used = texture_frame_no();
    VkImageCreateInfo ic{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    ic.flags = flags & (VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT | VK_IMAGE_CREATE_EXTENDED_USAGE_BIT);
    ic.imageType = VK_IMAGE_TYPE_2D, ic.format = format, ic.extent = {w, h, 1}, ic.mipLevels = 1, ic.arrayLayers = 1;
    ic.samples = VK_SAMPLE_COUNT_1_BIT, ic.tiling = VK_IMAGE_TILING_OPTIMAL;
    ic.usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    VkImageViewCreateInfo vc{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
    vc.viewType = VK_IMAGE_VIEW_TYPE_2D, vc.format = view_format;
    vc.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    if (create_image(ic, c.image, c.memory)) {
        vc.image = c.image;
        if (vkCreateImageView(dev.device, &vc, nullptr, &c.view) != VK_SUCCESS) {
            destroy_image(c.image, c.memory);
            c.image = VK_NULL_HANDLE, c.memory = nullptr, c.view = VK_NULL_HANDLE;
        }
    } else {
        c.image = VK_NULL_HANDLE, c.memory = nullptr;
    }
    s.copies.push_back(c);
    return c.image ? &s.copies.back() : nullptr;
}

/// Copies the target's level and layer into a copy of width x height (copy_for), after a barrier for the draws before
/// it, and adds it to the draw's items, which Draw::end copies back. Null when no copy could be made. With s.mu held
Copy* copy_in(Draw& draw, VkCommandBuffer cmd, const Texture* t, VkFormat view_format, uint32_t level, uint32_t layer,
              uint32_t width, uint32_t height) {
    State& s = st();
    Copy* c = copy_for(draw, t->format, view_format, t->create_flags, width, height);
    if (!c) {
        if (!s.told) logf("vk: a copy of a %ux%u target (format %d) was not made: its draw is left as it is", width, height, (int)t->format), s.told = true;
        return nullptr;
    }
    if (!draw.n) full_barrier(cmd, "barrier (feedback copy)");   // (the draws before, into the target)
    // (the copy's layout, at each use: what it held is not wanted, and the recordings are not made in the order they run)
    VkImageMemoryBarrier2 b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2};
    b.srcStageMask = b.dstStageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;
    b.srcAccessMask = b.dstAccessMask = VK_ACCESS_2_MEMORY_READ_BIT | VK_ACCESS_2_MEMORY_WRITE_BIT;
    b.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, b.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = c->image, b.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    VkDependencyInfo di{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
    di.imageMemoryBarrierCount = 1, di.pImageMemoryBarriers = &b;
    vkCmdPipelineBarrier2(cmd, &di);
    VkImageCopy r{};
    r.srcSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, level, layer, 1};
    r.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
    r.extent = {width, height, 1};
    vkCmdCopyImage(cmd, t->image, VK_IMAGE_LAYOUT_GENERAL, c->image, VK_IMAGE_LAYOUT_GENERAL, 1, &r);
    c->used = texture_frame_no();
    draw.item[draw.n++] = {t->image, c->image, level, layer};
    return c;
}

} // namespace

bool wanted() {
    static const bool on = [] {
        const char* e = getenv("RX_VK_FEEDBACK_COPY");
        const bool yes = feedback_copy::wanted(dev.driver_id == VK_DRIVER_ID_AMD_PROPRIETARY, e);
        if (yes)
            logf("vk: a draw that samples a colour target it writes is drawn into a copy of it (%s; RX_VK_FEEDBACK_COPY=0: "
                 "into the target itself)", e && *e ? "RX_VK_FEEDBACK_COPY" : "AMD's Windows driver");
        return yes;
    }();
    return on;
}

bool begin(Draw& draw, VkCommandBuffer cmd, uint16_t targets, Texture* const color[8], VkImageView color_view[8],
           const VkFormat color_format[8], const uint32_t color_level[8], const uint32_t color_layer[8], uint32_t width,
           uint32_t height) {
    State& s = st();
    std::lock_guard lk(s.mu);
    free_dead();
    const VkImageUsageFlags both = VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    for (int i = 0; i < 8; i++) {
        const Texture* t = color[i];
        if (!(targets >> i & 1) || !t || !t->image || !color_view[i]) continue;
        const uint32_t level = color_level[i], layer = color_layer[i];
        // (a plain 2D image whose viewed level is the pass's size, which can be copied from and into: the others stay)
        if (t->type != VK_IMAGE_TYPE_2D || t->samples != VK_SAMPLE_COUNT_1_BIT || (t->usage & both) != both ||
            level >= t->levels || layer >= t->layers || std::max(1u, t->width >> level) != width ||
            std::max(1u, t->height >> level) != height)
            continue;
        if (const Copy* c = copy_in(draw, cmd, t, color_format[i], level, layer, width, height)) color_view[i] = c->view;
    }
    if (!draw.n) return false;
    draw.cmd = cmd, draw.width = width, draw.height = height;
    // (what it costs, in the log: two copies of the target for each. Said when the figure of 600 frames is another)
    s.drawn += (uint64_t)draw.n;
    if (const uint64_t now = texture_frame_no(); now - s.said >= 600) {
        const uint64_t tenths = s.said ? s.drawn * 10 / (now - s.said) : s.tenths;
        if (tenths != s.tenths)
            logf("vk: %.1f colour targets a frame drawn into a copy (RX_VK_FEEDBACK_COPY)", (double)tenths / 10), s.tenths = tenths;
        s.said = now, s.drawn = 0;
    }
    return true;
}

bool keep(Draw& draw, VkCommandBuffer cmd, const Texture* t) {
    const VkImageUsageFlags both = VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    if (!t || !t->image || t->type != VK_IMAGE_TYPE_2D || t->samples != VK_SAMPLE_COUNT_1_BIT || (t->usage & both) != both ||
        draw.n)   // (Draw::end copies every item back at one size: a draw that keeps holds nothing else)
        return false;
    State& s = st();
    std::lock_guard lk(s.mu);
    free_dead();
    if (!copy_in(draw, cmd, t, t->format, 0, 0, t->width, t->height)) return false;
    draw.cmd = cmd, draw.width = t->width, draw.height = t->height;
    return true;
}

void Draw::end() {
    end_pass(cmd);   // (a copy cannot be made in a pass)
    full_barrier(cmd, "barrier (feedback copy back)");   // (the draw, into the copy)
    for (int i = 0; i < n; i++) {
        VkImageCopy r{};
        r.srcSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
        r.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, item[i].level, item[i].layer, 1};
        r.extent = {width, height, 1};
        vkCmdCopyImage(cmd, item[i].copy, VK_IMAGE_LAYOUT_GENERAL, item[i].target, VK_IMAGE_LAYOUT_GENERAL, 1, &r);
    }
}

} // namespace mkwvk::feedback
