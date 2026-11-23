/* (inhale) The cameras at the screen's ratio (Kirby and the Forgotten Land, Switch 2 Edition): nx2/kirby_wide.py, and
   docs/design.md, "issue #20, ultrawide".

   host/hos_main.c keeps every game but upstream's at 16:9, and lets this one through when its main is the build that
   nx2/kirby_wide.py hooks (kirby_wide_ok). It then sets hos_wide_ratio to the picture's ratio (2.3889 at 3440 x 1440,
   3.5556 at 5120 x 1440) and the window's shape to it, and the present stretches the game's 16:9 picture to the window
   (gpu/vk/vk_present_rect.h). The hooks give the cameras that ratio in place of 16:9, so what is stretched was drawn for
   it: the world is wider, and the HUD and menus, drawn for 16:9, are stretched with it. */
#include <math.h>
#include <stdint.h>
#include <string.h>

extern volatile float hos_wide_ratio;   /* hos_main.c: 0 at 16:9 */
extern const char hos_main_build_id[];   /* gen/hos_image.c */

/* The build nx2/kirby_wide.py hooks: the picture may take another shape */
int kirby_wide_ok(void) { return !strcmp(hos_main_build_id, "395fc326c2e5b1651d937074f8cfd75de63184d9"); }

/* An aspect in a vector register (its low 32 bits): 16:9 becomes the picture's ratio, any other is left */
void kirby_wide_aspect(uint64_t *v) {
    const float r = hos_wide_ratio;
    float a;
    memcpy(&a, v, 4);
    if (r > 0.0f && fabsf(a - 16.0f / 9.0f) < 1e-4f) memcpy(v, &r, 4);
}
