/* (inhale) The 3D frame at the output size (Kirby and the Forgotten Land, Switch 2 Edition): docs/design.md, "issue #1,
   dynamic resolution".

   The game's dynamic resolution takes its sizes from data: basil/ScnCommon.bin of the data title holds, at 0x97ca0, six
   docked levels as (index, width, height), 2560 x 1440 down to 854 x 480, which the game makes its scene targets at and
   steps between by GPU load. Its own pass then stretches the scene to the output. So at a 3840 x 2160 output the scene
   drew at 2560 x 1440 at most.

   As the file is read, the six sizes are scaled by the output's width over 2560 where the output is 16:9 and between
   2560 x 1440 and 3840 x 2160 (the largest of the game's own size table, main+0x9aaa70): at 3840 x 2160 they become
   3840 x 2160 down to 1280 x 720. A picture of another shape (21:9, 32:9, 16:10: host/kirby_wide.c gives the cameras its
   ratio) takes the picture's shape, at least 1440 lines high and at most 3840 x 2160's pixels: 3440 x 1440 for a 3440 x
   1440 output, 5120 x 1440 for 5120 x 1440, 4434 x 1870 for 5120 x 2160 (docs/design.md, "issue #20"). Another output
   keeps the game's sizes.

   The steps are off by default: all six levels get the first one's size, so the docked scene never steps down (at the
   output's size where it is scaled, at 2560 x 1440 at any other output). At 3840 x 2160 the game stepped to 3360 x 1890
   with an RX 7900 XTX at 2.9 ms of a 16.6 ms frame: the steps cost sharpness on a PC that has no need of them.
   HOS_DYNAMIC_RES=1 gives the game's steps back. The handheld profile (the menu's Profile row, HOS_HANDHELD) keeps the
   file as the game ships it, steps and all: it draws from another set of sizes (1920 x 1080 down), but was seen at a
   docked level's size too, so the fixed size is not given to it. The table's bytes are checked first: another version
   of the file is left as it is, and says so.

   The handheld set follows the docked levels in the file: five sizes, 1920 x 1080, 1600 x 900, 1120 x 630, 960 x 540,
   640 x 360. The game does not step down it under this PC's GPU load (docs/design.md, "handheld on a slow GPU"), so
   HOS_SCENE_HEIGHT=<lines> holds the handheld scene at one size, 16:9, 360 to 1080 lines (the set's smallest and
   largest): all five sizes become it. Under 720 lines the game upscales the scene with its network, which a card
   without it gets as a plain stretch (gpu/vk/kirby_upscale.h). */
#ifndef INHALE_ENV_H   /* (env_on: the switches' one rule) */
#include "../gpu/vk/compat/inhale_env.h"
#endif
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

void hos_log(const char *fmt, ...);
uint32_t hos_output_size(int height);   /* nn_applet.c */
extern volatile uint64_t hos_wide_out;  /* hos_main.c: the picture of another shape, height << 32 | width, or 0 */
extern volatile float hos_wide_ratio;   /* hos_main.c: its ratio, 0 at 16:9 */
int hos_handheld(void);                 /* nn_applet.c */

#define KIRBY_SCN_TABLE 0x97ca0
#define KIRBY_SCN_LEVELS 6
/* (index, width, height) of each docked level, as the game ships them */
static const uint32_t kirby_scn_levels[KIRBY_SCN_LEVELS * 3] = {
    0, 2560, 1440, 1, 2240, 1260, 2, 1862, 1048, 3, 1536, 864, 4, 1280, 720, 5, 854, 480,
};
/* the handheld set, right after them: (width, height) of each of its five sizes */
#define KIRBY_SCN_HANDHELD (KIRBY_SCN_TABLE + (int64_t)sizeof kirby_scn_levels)
static const uint32_t kirby_scn_handheld[] = {
    1920, 1080, 1600, 900, 1120, 630, 960, 540, 640, 360,
};

/* Where the `size` bytes at file offset `table` lie in a read of [off, off + n) of guest: -1 when the file is not
   ScnCommon.bin, the read does not hold all of them, or they are not `known` (said, as `what`) */
static int64_t kirby_scn_at(const char *guest, int64_t off, const uint8_t *buf, uint64_t n, int64_t table,
                            const void *known, size_t size, const char *what) {
    static const char name[] = "/basil/ScnCommon.bin";
    const size_t len = guest ? strlen(guest) : 0, tail = sizeof name - 1;
    if (len < tail || strcmp(guest + len - tail, name)) return -1;
    const int64_t at = table - off;
    if (at < 0 || (uint64_t)at + size > n) return -1;   /* (not this read, or not all of it in it) */
    if (memcmp(buf + at, known, size)) {
        hos_log("kirby: %s: the %s at %#x are not the ones known: left as they are", guest, what, (unsigned)table);
        return -1;
    }
    return at;
}

/* The read of [off, off + n) of a file the game opened as guest, now in buf: the table rewritten in it when it is
   there whole. Returns 1 when the sizes were changed. shaped: out_w x out_h is the picture's own shape (kirby_scn_shape),
   taken whatever its ratio. */
int kirby_scn_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, uint32_t out_w, uint32_t out_h, int fixed,
                    int shaped) {
    const int64_t at = kirby_scn_at(guest, off, buf, n, KIRBY_SCN_TABLE, kirby_scn_levels, sizeof kirby_scn_levels,
                                    "frame sizes");
    if (at < 0) return 0;
    uint32_t v[KIRBY_SCN_LEVELS * 3];
    memcpy(v, buf + at, sizeof v);
    const int bigger = shaped ? out_w && out_h : (uint64_t)out_w * 9 == (uint64_t)out_h * 16 && out_w > 2560 && out_w <= 3840;
    if (!bigger && !fixed) return 0;
    for (int k = 0; k < KIRBY_SCN_LEVELS; k++) {
        const int from = fixed ? 0 : k;
        const uint32_t w = kirby_scn_levels[from * 3 + 1], h = kirby_scn_levels[from * 3 + 2];
        v[k * 3 + 1] = bigger ? (uint32_t)((uint64_t)w * out_w / 2560) & ~1u : w;
        v[k * 3 + 2] = bigger ? (uint32_t)((uint64_t)h * out_h / 1440) & ~1u : h;
    }
    memcpy(buf + at, v, sizeof v);
    hos_log("kirby: 3D frame %ux%u down to %ux%u%s", v[1], v[2], v[KIRBY_SCN_LEVELS * 3 - 2], v[KIRBY_SCN_LEVELS * 3 - 1],
            fixed ? " (fixed: HOS_DYNAMIC_RES=1 for the game's steps)" : "");
    return 1;
}

/* The same read, for the handheld set: each of its five sizes becomes the 16:9 size of `height` lines, held to 360 to
   1080 lines, each side even. 0: left as read. Returns 1 when the sizes were changed. */
int kirby_scn_handheld_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, uint32_t height) {
    if (!height) return 0;
    const int64_t at = kirby_scn_at(guest, off, buf, n, KIRBY_SCN_HANDHELD, kirby_scn_handheld,
                                    sizeof kirby_scn_handheld, "handheld frame sizes");
    if (at < 0) return 0;
    height = (height < 360 ? 360 : height > 1080 ? 1080 : height) & ~1u;
    const uint32_t size[2] = {(height * 16 / 9) & ~1u, height};
    for (size_t k = 0; k < sizeof kirby_scn_handheld; k += sizeof size) memcpy(buf + at + k, size, sizeof size);
    hos_log("kirby: 3D frame %ux%u (handheld, fixed: HOS_SCENE_HEIGHT)", size[0], size[1]);
    return 1;
}

/* The scene for a picture of pw x ph: its shape, at least 1440 lines (the game's own) and at most 3840 x 2160's pixels (the
   largest the game was seen to draw), each side even */
void kirby_scn_shape(uint32_t pw, uint32_t ph, uint32_t *w, uint32_t *h) {
    double s = ph && ph < 1440 ? 1440.0 / ph : 1.0;
    const double px = (double)pw * ph * s * s, most = 3840.0 * 2160.0;
    if (px > most) s *= sqrt(most / px);
    *w = (uint32_t)(pw * s) & ~1u, *h = (uint32_t)(ph * s) & ~1u;
}

/* nn_fs.c's read, for each file read: the output size, the profile and HOS_DYNAMIC_RES asked only for the one file */
void kirby_read_done(const char *guest, int64_t off, uint8_t *buf, uint64_t n) {
    if (!guest || !strstr(guest, "ScnCommon")) return;
    uint32_t w = hos_output_size(0), h = hos_output_size(1);
    const uint64_t wide = hos_wide_out;
    const int shaped = hos_wide_ratio > 0.0f && wide && !hos_handheld();   /* (handheld: the file as read, as at 16:9) */
    if (shaped) kirby_scn_shape((uint32_t)wide, (uint32_t)(wide >> 32), &w, &h);
    kirby_scn_patch(guest, off, buf, n, w, h, !hos_handheld() && !env_on("HOS_DYNAMIC_RES"), shaped);
    /* (handheld: the scene held at HOS_SCENE_HEIGHT lines, unless the game's steps are asked for) */
    const int lines = env_int("HOS_SCENE_HEIGHT", 0);
    if (hos_handheld() && lines > 0 && !env_on("HOS_DYNAMIC_RES"))
        kirby_scn_handheld_patch(guest, off, buf, n, (uint32_t)lines);
    void kirby_shadow_read(const char *guest, int64_t off, uint8_t *buf, uint64_t n);   /* (the shadow map's size: kirby_shadow.c) */
    kirby_shadow_read(guest, off, buf, n);
}
