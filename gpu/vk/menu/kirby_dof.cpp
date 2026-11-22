// (inhale) The Insert menu's Depth of field row: this game's depth of field (gpu/vk/kirby_post.h), in the Graphics tab's
// Detail section before Shadow resolution. vk_menu.cpp's row_shown hides it while the other game runs (kirby_row).
#include "menu_module.h"

namespace mkwvk {

MENU_MODULE(kirby_dof) {
    menu::tab("graphics")
        .section("detail")   // (menu/detail.cpp's heading)
        .row({.key = "depth_of_field",
              .label = "Depth of field",
              .help = "The blur the game puts on what is far from the camera. Off keeps the whole picture sharp. Applies at once.",
              .kind = menu::Kind::Toggle,
              .value = &opts.dof,
              .lo = 0, .hi = 1,
              .preset_exempt = true}, menu::before("shadow_resolution"));
}

} // namespace mkwvk
