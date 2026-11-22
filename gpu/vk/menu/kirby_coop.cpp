// (inhale) The Controls tab's One controller per player row: each controller its own Npad, for local co-op
// (host/kirby_npad.c, issue #16). Off, the default, every controller drives the first player, as upstream has it.
#include "menu_module.h"

namespace mkwvk {

MENU_MODULE(kirby_coop) {
    menu::tab("controls")
        .row({.key = "pad_per_player",
              .label = "One controller per player",
              .help = "On: each controller is a player of its own, in the order they were connected, for co-op. The first "
                      "also has the keyboard and mouse. Off: every controller plays as the first player. Applies at once.",
              .kind = menu::Kind::Toggle,
              .value = &opts.pad_per_player,
              .lo = 0, .hi = 1,
              .preset_exempt = true}, menu::after("controller_in_background"));
}

} // namespace mkwvk
