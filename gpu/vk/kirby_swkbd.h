// (inhale) The software keyboard (issue #30): the text the game asks the player to type, at the post office of Waddle Dee Town
// (a present code), while its thread waits in nn::swkbd::ShowKeyboard (host/kirby_swkbd.c). Drawn over the whole window and
// presented from that wait, a frame at a time, as the start-up screen is from its own thread (present_image, vk_framegen.h):
// vk_menu.cpp's menu_record draws it in the frame, this file keeps what it shows. docs/design.md, "issue #30, the post
// office's present code".
#pragma once

#include "vk_api.h"   // (MkwVkSwkbd: what a frame shows)
#include "vk_ui.h"    // (ui::Ctx)

namespace mkwvk::kirby_swkbd {

/// The keyboard is up: menu_record draws it, and the Insert menu stays closed under it
bool up();

/// One frame of it over the window, presented: 1 drawn, 0 when there is nothing to draw on (a headless run), which the host
/// takes as the player's cancel
int frame(const MkwVkSwkbd* state);

/// Its last frame shown: nothing of it from the next present on, which is the game's own
void close();

/// It over the window's image, in the frame menu_record began (the game's picture is stopped behind: this covers it)
void draw(ui::Ctx& c);

}  // namespace mkwvk::kirby_swkbd
