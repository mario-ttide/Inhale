/* (inhale) The software keyboard (issue #30): the text the game asks the player to type, at the post office of Waddle Dee
   Town (a present code), typed on the PC's keyboard instead of on the console.

   The game asks through nn::swkbd::ShowKeyboard, the console's full-screen keyboard applet, of which this port has none. Its
   imports were generated stubs, which answer 0, success, having written nothing: the game read an empty text back at once and
   said the code had been cancelled. Two of them are answered here; the other three stay stubs (the end of this file).

   What the game's own wrapper of ShowKeyboard does with the answer (main +0x807a0d20: MakePreset, GetRequiredWorkBufferSize,
   GetRequiredStringBufferSize, one allocation each for the work buffer and the answer, ShowKeyboard, then the result and the
   buffer):
     +0: a guest uint16_t* to write the answer into, NUL-terminated (the game scans it for the 0 unit);
     +8: how many bytes it may hold.
   The result: 0 when the player accepted; nn::swkbd::ResultCanceled when they left the keyboard, or when nothing could be
   drawn, whose low 22 bits are the 0x29F the game tests for.

   The characters typed come through the Insert menu's own queue (host/rx_backend.c take_text: the window's thread on both
   OSes puts them in, whether or not that menu is open), the frame is drawn and presented by the renderer
   (gpu/vk/kirby_swkbd.cpp, MkwVkRenderer's swkbd_frame), and the game's thread waits here while the keyboard is up, as it
   does on the console. With no window to draw on (HOS_HEADLESS=1), the game hears a cancel at once, as before.
   A controller accepts and leaves it with the buttons the Switch's A and B are bound to, as in the Insert menu, so a
   player with no keyboard is not stuck on it. The key or button that ended it, and any key of the game's controls typed
   into it, is let go before the game reads its input again: Enter is bound to A by default, and held, it was a fresh A
   press that dismissed the message after the code.
   HOS_SWKBD=<text>: that answer, typed by nobody: a headless or scripted run's, or a player's with no keyboard. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"   /* (MkwVkSwkbd, HOS_TEXT_*) */
#include <stdlib.h>
#include <string.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>   /* (VK_RETURN and the editing keys: host/posix's shim on Linux) */

/* the renderer's frame of the keyboard, and the window's typed text (host/rx_backend.c) */
int rx_swkbd_frame(const MkwVkSwkbd *state);
void rx_swkbd_close(void);
int hos_text_take(int focus, uint32_t *out, int max);
/* the pads read now and what the Switch's buttons are bound to (host/nn_hid.c) */
uint32_t kirby_pads_poll(void);
int hos_binding(int set, int button, int slot);

enum { SWKBD_TEXT = 64 };          /* an answer with its NUL, and what one line of the keyboard shows: far more than a code */
enum { SWKBD_UNITS = 0x17F };      /* the most UTF-16 units the game's own copy of the answer takes (it compares with 0x17F) */
enum { SWKBD_BYTES = 0x1000 };     /* GetRequiredStringBufferSize: 0x800 units, four times SWKBD_UNITS */
enum { SWKBD_CANCELED = 0x29F };   /* nn::swkbd::ResultCanceled's low 22 bits: the description the game tests for */
enum { SWKBD_GO_ON, SWKBD_ACCEPTED, SWKBD_CANCELLED };
enum { SWKBD_FRAME_NS = 16666667 };   /* (a frame of the keyboard every 1/60 s, as the console's shows it) */

/* how much of the answer the game's string can hold: what fits of SWKBD_UNITS and of its own size, the 0 unit included */
static int swkbd_room(uint64_t string) {
    const uint64_t bytes = G64(string + 8);
    const int room = bytes >= 2 ? (int)(bytes / 2 - 1) : 0;
    return room < SWKBD_UNITS ? room : SWKBD_UNITS;
}

/* the answer into the game's nn::swkbd::String: the text as UTF-16 at its buffer, NUL-terminated, what fits of it; the units
   written */
static int swkbd_answer(uint64_t string, const char *text, int len) {
    const uint64_t buffer = G64(string);
    const int room = swkbd_room(string);
    uint16_t units[SWKBD_UNITS + 1];
    if (len < 0) len = 0;
    if (len > room) len = room;
    if (len > SWKBD_TEXT - 1) len = SWKBD_TEXT - 1;
    for (int i = 0; i < len; i++) units[i] = (uint16_t)(unsigned char)text[i];
    units[len] = 0;
    if (buffer) hos_guest_copy(buffer, units, (uint64_t)(len + 1) * 2);
    return len;
}

/* one input, a character typed (a Unicode code point) or HOS_TEXT_KEY | its key code, into the text, its length and the
   caret: SWKBD_ACCEPTED for Enter, SWKBD_CANCELLED for Escape, else SWKBD_GO_ON. A printable ASCII character alone, as the
   menu's glyphs are baked for it and a present code is one */
static int swkbd_edit(char *text, int *len, int *caret, int room, uint32_t in) {
    if (*len > room) *len = room;
    if (*caret > *len) *caret = *len;
    if (*caret < 0) *caret = 0;
    if (in & HOS_TEXT_KEY) {
        switch (in & ~(uint32_t)HOS_TEXT_KEY) {
        case VK_RETURN: return SWKBD_ACCEPTED;
        case VK_ESCAPE: return SWKBD_CANCELLED;
        case VK_LEFT: if (*caret > 0) (*caret)--; break;
        case VK_RIGHT: if (*caret < *len) (*caret)++; break;
        case VK_HOME: *caret = 0; break;
        case VK_END: *caret = *len; break;
        case VK_BACK:
            if (*caret > 0) memmove(text + *caret - 1, text + *caret, (size_t)(*len - *caret + 1)), (*caret)--, (*len)--;
            break;
        case VK_DELETE:
            if (*caret < *len) memmove(text + *caret, text + *caret + 1, (size_t)(*len - *caret)), (*len)--;
            break;
        }
        return SWKBD_GO_ON;
    }
    if (in < 0x20 || in > 0x7e || *len >= room || *len >= SWKBD_TEXT - 1) return SWKBD_GO_ON;
    memmove(text + *caret + 1, text + *caret, (size_t)(*len - *caret + 1));
    text[(*caret)++] = (char)in, (*len)++;
    return SWKBD_GO_ON;
}

/* one frame of the keyboard, presented: 1 drawn, 0 nothing to draw on. present_image can wait on V-Sync or a fence, so the
   game thread's virtual core is given up around it, as around any host call that may block (rx_nvn_texture_released) */
static int swkbd_frame(const char *text, int len, int caret) {
    MkwVkSwkbd state;
    memset(&state, 0, sizeof state);
    state.len = len, state.caret = caret;
    memcpy(state.text, text, (size_t)len + 1);
    const int away = hos_vcore_away();
    const int drawn = rx_swkbd_frame(&state);
    if (away) hos_vcore_back();
    return drawn;
}

/* the pad buttons that accept and leave (1 << HOS_PAD_*): the ones the Switch's A and B are bound to, as the Insert menu's
   confirm and back are (gpu/vk/vk_menu_keys.h confirm_back: one bound to no face button falls back to the bottom one
   accepting and the right one leaving) */
static void swkbd_pad_keys(uint32_t *accept, uint32_t *leave) {
    const int a = hos_binding(HOS_BIND_PAD, HOS_SW_A, 0), b = hos_binding(HOS_BIND_PAD, HOS_SW_B, 0);
    const int ok = a >= HOS_PAD_SOUTH && a <= HOS_PAD_NORTH ? a : HOS_PAD_SOUTH;
    const int back = b >= HOS_PAD_SOUTH && b <= HOS_PAD_NORTH && b != ok ? b : ok == HOS_PAD_EAST ? HOS_PAD_SOUTH : HOS_PAD_EAST;
    *accept = 1u << ok, *leave = 1u << back;
}

/* Enter, Escape, a key of one of the game's controls (a letter typed into the keyboard, Space on A: each would be a fresh
   press at the game's next read) or one of the pad's buttons (pad: 1 << HOS_PAD_*) still held, as the game's input reads
   them. A mouse button bound to a control (its codes are below VK_BACK) is not waited on: no key typed into it */
static int swkbd_held(uint32_t pad) {
    if ((GetAsyncKeyState(VK_RETURN) & 0x8000) || (GetAsyncKeyState(VK_ESCAPE) & 0x8000) || (kirby_pads_poll() & pad))
        return 1;
    for (int i = 0; i < HOS_KEY_N; i++)
        for (int slot = 0; slot < 2; slot++) {
            const int vk = hos_binding(HOS_BIND_KEY, i, slot);
            if (vk >= VK_BACK && vk <= 0xFF && (GetAsyncKeyState(vk) & 0x8000)) return 1;
        }
    return 0;
}

/* the keyboard up until the player accepts or leaves it: 1 accepted, 0 left or nothing to draw on, with what they typed in
   text and len (room is what fits) */
static int swkbd_ask(char *text, int *len, int room) {
    uint32_t typed[16], accept, leave;
    int caret = 0, accepted = 0, drawn;
    *len = 0, text[0] = 0;
    swkbd_pad_keys(&accept, &leave);
    uint32_t pad_was = kirby_pads_poll();   /* (a button held as it comes up, the A that asked for it, counts once let go) */
    hos_text_take(HOS_TEXT_ON, typed, 0);   /* (the window starts taking text: nothing read yet) */
    for (;;) {
        drawn = swkbd_frame(text, *len, caret);
        if (!drawn) break;   /* (no window: nothing to type on, as a headless run) */
        const int n = hos_text_take(HOS_TEXT_ON, typed, (int)(sizeof typed / sizeof typed[0]));
        int done = SWKBD_GO_ON;
        for (int i = 0; i < n && done == SWKBD_GO_ON; i++) done = swkbd_edit(text, len, &caret, room, typed[i]);
        const uint32_t pad = kirby_pads_poll(), pressed = pad & ~pad_was;
        pad_was = pad;
        if (done == SWKBD_GO_ON && (pressed & accept)) done = SWKBD_ACCEPTED;
        else if (done == SWKBD_GO_ON && (pressed & leave)) done = SWKBD_CANCELLED;
        if (done != SWKBD_GO_ON) {
            accepted = done == SWKBD_ACCEPTED;
            break;
        }
        hos_sleep_ns(SWKBD_FRAME_NS);
    }
    /* (a frame more, and more while the key or button that ended it is held, so the game reads no press of it: that frame's
       present runs vk_menu.cpp's menu_tick, which takes the Insert menu's own record of the key (Windows: host/display.c
       notes every key-down for the menu), so an Escape tapped between two frames does not open the menu once it is gone) */
    while (drawn) {
        hos_sleep_ns(SWKBD_FRAME_NS);
        drawn = swkbd_frame(text, *len, caret);
        if (!swkbd_held(accept | leave)) break;
    }
    hos_text_take(HOS_TEXT_OFF, typed, 0);   /* (the window takes no text again, and an input method's window closes) */
    rx_swkbd_close();
    return accepted;
}

/* HOS_SWKBD's answer into text, its printable ASCII alone as the keyboard types it (each byte becomes one UTF-16 unit): its
   length, or -1 when the switch is unset or has none */
static int swkbd_switch(char *text) {
    const char *answer = getenv("HOS_SWKBD");
    int len = 0;
    if (!answer) return -1;
    for (; *answer && len < SWKBD_TEXT - 1; answer++)
        if (*answer >= 0x20 && *answer <= 0x7e) text[len++] = *answer;
    text[len] = 0;
    return len ? len : -1;
}

HLE(_ZN2nn5swkbd27GetRequiredStringBufferSizeEv) { RET(SWKBD_BYTES); }

HLE(_ZN2nn5swkbd12ShowKeyboardEPNS0_6StringERKNS0_15ShowKeyboardArgE) {
    char text[SWKBD_TEXT];
    int len = 0;
    const int switched = swkbd_switch(text);
    const int accepted = switched >= 0 ? (len = switched, 1) : swkbd_ask(text, &len, swkbd_room(ARG(0)));
    if (!accepted) {
        hos_log("swkbd: the keyboard was left, or cannot be shown: the game hears a cancel");
        RET(SWKBD_CANCELED);
        return;
    }
    swkbd_answer(ARG(0), text, len);
    hos_log("swkbd: %d characters typed (%s)", len, switched >= 0 ? "HOS_SWKBD" : "the keyboard");
    RET(0);
}

/* (not answered here: nn::swkbd::MakePreset, SetGuideTextUtf8 and GetRequiredWorkBufferSize write a KeyboardConfig and a work
   buffer, and only ShowKeyboard reads them. This file reads neither: the work buffer stays unused (the game asks for none)
   and the keyboard's own text is the overlay's, translated like the menu's) */
