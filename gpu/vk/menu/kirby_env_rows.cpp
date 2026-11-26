// (inhale) The Insert menu's rows for this game's switches that were environment variables only: Handheld scene size
// (HOS_SCENE_HEIGHT) and Dynamic resolution (HOS_DYNAMIC_RES) after the Profile, Centre in front speakers
// (HOS_AUDIO_CENTRE) after the Speaker layout, Graphics queue order (HOS_KIRBY_QUEUE_ORDER) on the Debug tab. The host
// reads each once, the variable over the row's line (host/kirby_option.h, host/kirby_res.c), so each applies after a
// restart, and a row whose variable is set is locked. vk_menu.cpp's row_shown hides them while the other game runs
// (kirby_row). And Frame rate (HOS_KIRBY_FPS, 30 or 60) after Dynamic resolution: the host asks for it every present
// (HOS_OPT_KIRBY_FPS, host/kirby_fps.c), so that one applies in play. Keep speed under 20 FPS (HOS_KIRBY_KEEP_SPEED,
// 1 or 0) after it, the same way (HOS_OPT_KIRBY_KEEP_SPEED).
#include "menu_module.h"
#include "../compat/inhale_env.h"   // (env_int)

#include <cstdlib>
#include <cstring>

namespace mkwvk {

namespace {
const char* locked_by(const char* name) {
    // (as the host reads them: an on/off switch is set when it is there at all, the height when it is a number)
    if (!strcmp(name, "HOS_KIRBY_FPS")) {   // (a choice only at 30 or 60, as host/kirby_fps.c reads it)
        const int fps = env_int(name, 0);
        return fps == 30 || fps == 60
                   ? "Set by HOS_KIRBY_FPS (inhale_env.txt or the environment): remove that line to choose here."
                   : nullptr;
    }
    if (!strcmp(name, "HOS_KIRBY_KEEP_SPEED")) {   // (a choice only at 0 or 1, as host/kirby_fps.c reads it)
        const int on = env_int(name, -1);
        return on == 0 || on == 1
                   ? "Set by HOS_KIRBY_KEEP_SPEED (inhale_env.txt or the environment): remove that line to choose here."
                   : nullptr;
    }
    if (!strcmp(name, "HOS_SCENE_HEIGHT") ? env_int(name, -1) < 0 : !getenv(name)) return nullptr;
    if (!strcmp(name, "HOS_SCENE_HEIGHT"))
        return "Set by HOS_SCENE_HEIGHT (inhale_env.txt or the environment): remove that line to choose here.";
    if (!strcmp(name, "HOS_DYNAMIC_RES"))
        return "Set by HOS_DYNAMIC_RES (inhale_env.txt or the environment): remove that line to choose here.";
    if (!strcmp(name, "HOS_AUDIO_CENTRE"))
        return "Set by HOS_AUDIO_CENTRE (inhale_env.txt or the environment): remove that line to choose here.";
    return "Set by HOS_KIRBY_QUEUE_ORDER (inhale_env.txt or the environment): remove that line to choose here.";
}
} // namespace

MENU_MODULE(kirby_env_rows) {
    menu::tab("graphics")
        .row({.key = "handheld_scene_size",
              .label = "Handheld scene size",
              .help = "The size the handheld profile draws the scene at, stretched to the screen. Smaller is faster on a slow "
                      "graphics card, such as a laptop's integrated one. Applies after a restart.",
              .value = &opts.scene_size,
              .lo = 0, .hi = 4,
              .choices = {"1920 x 1080", "1600 x 900", "1280 x 720", "960 x 540", "640 x 360"},
              .restart = true,
              .preset_exempt = true,
              .shown = [] { return opts.handheld != 0; },
              .locked = [] { return locked_by("HOS_SCENE_HEIGHT"); }}, menu::after("handheld_profile"))
        .row({.key = "kirby_dynamic_res",
              .label = "Dynamic resolution",
              .help = "On: the game lowers the scene's size under load, as on the console. Off keeps it at the Output "
                      "resolution's. Applies after a restart.",
              .kind = menu::Kind::Toggle,
              .value = &opts.kirby_dynres,
              .lo = 0, .hi = 1,
              .restart = true,
              .preset_exempt = true,
              .shown = [] { return opts.handheld == 0; },
              .locked = [] { return locked_by("HOS_DYNAMIC_RES"); }}, menu::after("handheld_scene_size"))
        .row({.key = "kirby_frame_rate",
              .label = "Frame rate",
              .help = "60 is the game's. 30 draws half the frames at the same game speed, for a graphics card that holds "
                      "30 but swings under 60. On a card that stays under 30 it is slower than 60: leave it at 60 there. "
                      "Applies at once.",
              .value = &opts.kirby_fps,
              .lo = 0, .hi = 1,
              .choices = {"60", "30"},
              .preset_exempt = true,
              .locked = [] { return locked_by("HOS_KIRBY_FPS"); }}, menu::after("kirby_dynamic_res"))
        .row({.key = "kirby_keep_speed",
              .label = "Keep speed under 20 FPS",
              .help = "Off is the game's: under 20 frames a second it goes into slow motion. On keeps the game's speed "
                      "down to 10 frames a second, with larger steps than the game's makers allowed: turn it off if "
                      "something passes through a wall or a floor. Applies at once.",
              .kind = menu::Kind::Toggle,
              .value = &opts.kirby_keep_speed,
              .lo = 0, .hi = 1,
              .preset_exempt = true,
              .locked = [] { return locked_by("HOS_KIRBY_KEEP_SPEED"); }}, menu::after("kirby_frame_rate"));
    menu::tab("audio")
        .row({.key = "centre_to_front",
              .label = "Centre in front speakers",
              .help = "In a 5.1 mix, the centre channel also goes to the front pair, so a headset's virtual surround or a "
                      "driver that drops the centre still plays it. Applies after a restart.",
              .kind = menu::Kind::Toggle,
              .value = &opts.centre_front,
              .lo = 0, .hi = 1,
              .restart = true,
              .preset_exempt = true,
              .locked = [] { return locked_by("HOS_AUDIO_CENTRE"); }}, menu::after("audio_output"));
    menu::tab("debug")
        .row({.key = "kirby_queue_order",
              .label = "Graphics queue order",
              .help = "The order the game's graphics work reaches your PC in. Arrival is v0.2.0's, in which the crystal "
                      "covering of the Star-Crossed World stages vanishes for single frames: try it only if the picture "
                      "goes wrong where an older version drew it right. Applies after a restart.",
              .kind = menu::Kind::Toggle,
              .value = &opts.queue_order,
              .lo = 0, .hi = 1,
              .choices = {"Arrival", "The game's"},
              .restart = true,
              .preset_exempt = true,
              .locked = [] { return locked_by("HOS_KIRBY_QUEUE_ORDER"); }});
}

} // namespace mkwvk
