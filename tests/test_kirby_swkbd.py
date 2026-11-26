"""The software keyboard (host/kirby_swkbd.c; issue #30: the post office's present code, cancelled at once).

The game asks for a text through nn::swkbd::ShowKeyboard, the console's full-screen keyboard applet. Its imports were
generated stubs, which answer 0, success, having written nothing: the game read an empty text back and said the code had
been cancelled. host/kirby_swkbd.c answers two of them with a keyboard of this port's own, and this checks the parts of
it that need no game, no window and no GPU, cut from that file and compiled with stand-ins for the renderer's frame, the
window's typed text and the clock:

- the editing keys: printable ASCII characters alone, up to the room, Backspace, Delete, Left, Right, Home and End at the
  caret, Enter accepted and Escape cancelled;
- the answer: the game's nn::swkbd::String is a guest buffer pointer at +0 and its size in bytes at +8, and the text goes
  in as UTF-16 with its 0 unit, capped by that size and by the 0x17F units the game reads;
- the wait: a frame presented every iteration, with the game thread's virtual core given up around it (present_image can
  wait on V-Sync), the window's text taken with the focus on and the focus off and the frame closed once the player is
  done, and a cancel at once when there is nothing to draw on (a headless run);
- a controller alone: the buttons the Switch's A and B are bound to accept and leave, as in the Insert menu (the bottom
  and the right one when they are bound to no face button), on a fresh press only (the A that asked for the keyboard,
  still held, does not accept it);
- the key or button that ended it let go before the game reads its input again: Enter is bound to A, and a held Enter
  was a fresh A press at the game's next read, which dismissed the message after the code; so is a key typed into it
  that is one of the game's controls (a letter, Space), but not a mouse button;
- ShowKeyboard's own HLE: 0 and the text on Enter, nn::swkbd::ResultCanceled (0x29F, which the game tests for) on Escape,
  and HOS_SWKBD answering for nobody;
- GetRequiredStringBufferSize's answer, which the game allocates its string with, holds those 0x17F units;
- nx2/standalone.py hooks both functions instead of stubbing them, which is what the game got before;
- the renderer gives its two functions: fill_replay_table (gpu/vk/vk_replay.cpp) or init_body sets every function of
  MkwVkRenderer, so the keyboard's frame is not NULL, which the host answers as a cancel at once, as before the fix;
- the overlay (gpu/vk/kirby_swkbd.cpp, compiled whole with stand-ins for the renderer and Dear ImGui): no window
  (HOS_HEADLESS=1, no swapchain) is a cancel; a minimized window keeps the keyboard up with no frame presented, so the
  player's text is not lost; and the Accept and Cancel prompts are drawn even when the text fits at no size;
- and the Insert menu's keys (vk_menu.cpp menu_tick, cut and compiled with stand-ins): the keys pressed and the pad's
  buttons held while the keyboard is up are taken then, and are not new presses once it closes (Escape left the
  keyboard and opened the menu); the menu's other work (fullscreen, the output's countdown) goes on under it.

python -I -B tests/test_kirby_swkbd.py [--cc gcc] [--cxx g++]
"""
import argparse
import contextlib
import io
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between, block  # noqa: E402
from test_cxx_escape import renderer_members  # noqa: E402

RUN_ALL_ARGS = ["--cc", "{cc}", "--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
SHOW = "_ZN2nn5swkbd12ShowKeyboardEPNS0_6StringERKNS0_15ShowKeyboardArgE"
SIZE = "_ZN2nn5swkbd27GetRequiredStringBufferSizeEv"
PRESET = "_ZN2nn5swkbd10MakePresetEPNS0_14KeyboardConfigENS0_6PresetE"

HARNESS = r"""
#define _POSIX_C_SOURCE 200809L   /* (setenv, in the HOS_SWKBD part of the test) */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vk_api.h"

/* (windows.h's virtual keys, as host/posix/windows.h has them too: this needs no window) */
enum { VK_BACK = 0x08, VK_RETURN = 0x0D, VK_ESCAPE = 0x1B, VK_END = 0x23, VK_HOME = 0x24,
       VK_LEFT = 0x25, VK_RIGHT = 0x27, VK_DELETE = 0x2E };

typedef struct { uint64_t x[32]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))   /* (the test's guest addresses are host pointers: the same macros work) */
#define G64(a) (*(uint64_t *)GP(a))

/* the guest write the answer is (host/hos.h hos_guest_copy) */
static void hos_guest_copy(uint64_t a, const void *src, uint64_t n) { memcpy(GP(a), src, (size_t)n); }
static int logged;
static void hos_log(const char *fmt, ...) {
    (void)fmt;
    logged++;
}

/* the game thread's virtual core (host/hos.h) */
static int away_now, frames_on_core;
static int hos_vcore_away(void) {
    away_now = 1;
    return 1;
}
static void hos_vcore_back(void) { away_now = 0; }

/* the renderer's frame of the keyboard, the window's typed text and the clock (host/rx_backend.c, gpu/vk/kirby_swkbd.cpp) */
static int can_draw = 1, frames, closes, sleeps_now, focus_off, focus_on;
static char shown[64];
static int shown_len;
int rx_swkbd_frame(const MkwVkSwkbd *state) {
    if (!can_draw || frames >= 50) return 0;   /* (a wait that would not end: the window gone, a cancel) */
    frames++;
    if (!away_now) frames_on_core++;
    snprintf(shown, sizeof shown, "%s", state->text), shown_len = state->len;
    return 1;
}
void rx_swkbd_close(void) { closes++; }
static uint32_t keys[64];
static int key_n, key_at;
int hos_text_take(int focus, uint32_t *out, int max) {
    if (focus == HOS_TEXT_OFF) {
        focus_off++, focus_on = 0, key_at = key_n = 0;
        return 0;
    }
    focus_on = 1;
    if (!out || max < 1 || key_at >= key_n) return 0;
    out[0] = keys[key_at++];
    return 1;
}
static void hos_sleep_ns(int64_t ns) {
    (void)ns;
    sleeps_now++;
}

/* the pads by position (1 << HOS_PAD_*) as each frame finds them, and what the Switch's A and B are bound to (host/nn_hid.c);
   the keyboard's keys as the game's input reads them: Enter down until a frame */
static uint32_t pads[16];
static int pad_n, bound_a = HOS_PAD_EAST, bound_b = HOS_PAD_SOUTH, enter_down_until, escape_down_until;
uint32_t kirby_pads_poll(void) { return pad_n ? pads[frames < pad_n ? frames : pad_n - 1] : 0; }
/* (the keys: Q on X's second slot, as a letter typed into the keyboard can be one of the game's controls, and the mouse's
   left button, held all along, on ZR's: a mouse button is no key here) */
enum { VK_LBUTTON = 0x01 };
static int q_down_until;
int hos_binding(int set, int button, int slot) {
    if (set == HOS_BIND_KEY) return button == HOS_SW_X && slot == 1 ? 'Q' : button == HOS_SW_ZR && slot == 0 ? VK_LBUTTON : 0;
    if (slot) return -1;
    return set != HOS_BIND_PAD ? -1 : button == HOS_SW_A ? bound_a : button == HOS_SW_B ? bound_b : -1;
}
static short GetAsyncKeyState(int vk) {
    return (vk == VK_RETURN && frames < enter_down_until) || (vk == VK_ESCAPE && frames < escape_down_until) ||
           (vk == 'Q' && frames < q_down_until) || vk == VK_LBUTTON ? (short)0x8000 : 0;
}
static void pads_are(int n, const uint32_t *p) {
    pad_n = n;
    for (int i = 0; i < n; i++) pads[i] = p[i];
}

@SWKBD@

static int bad;
static void check(const char *what, int ok) {
    if (!ok) printf("FAIL: %s\n", what), bad = 1;
}

/* the keys typed, then the answer they end with ("KIRBY" and Enter, as the script says) */
static void script(const char *text, uint32_t last) {
    key_at = key_n = 0;
    for (const char *p = text; *p; p++) keys[key_n++] = (uint32_t)(unsigned char)*p;
    keys[key_n++] = last;
}
static void switch_to(const char *text) {
#ifdef _WIN32
    _putenv_s("HOS_SWKBD", text);
#else
    if (text) setenv("HOS_SWKBD", text, 1);
    else unsetenv("HOS_SWKBD");
#endif
}

int main(void) {
    /* the editing keys */
    char text[64] = {0};
    int len = 0, caret = 0;
    for (const char *p = "kirby"; *p; p++) swkbd_edit(text, &len, &caret, 6, (uint32_t)(unsigned char)*p);
    check("five characters typed", len == 5 && !strcmp(text, "kirby") && caret == 5);
    swkbd_edit(text, &len, &caret, 6, '!');
    check("the room's last one", len == 6 && !strcmp(text, "kirby!"));
    swkbd_edit(text, &len, &caret, 6, '?');
    check("past the room: dropped", len == 6 && !strcmp(text, "kirby!"));
    swkbd_edit(text, &len, &caret, 6, 0x3042);
    check("not printable ASCII (a kana): dropped", len == 6 && !strcmp(text, "kirby!"));
    swkbd_edit(text, &len, &caret, 6, 0x09);
    check("a tab: dropped", len == 6 && !strcmp(text, "kirby!"));
    check("Backspace takes the last", swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_BACK) == SWKBD_GO_ON &&
                                     len == 5 && !strcmp(text, "kirby") && caret == 5);
    swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_LEFT);
    swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_LEFT);
    check("Left moves the caret", caret == 3);
    swkbd_edit(text, &len, &caret, 6, 'X');
    check("a character goes in at the caret", len == 6 && !strcmp(text, "kirXby") && caret == 4);
    swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_DELETE);
    check("Delete takes the one after it", len == 5 && !strcmp(text, "kirXy") && caret == 4);
    swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_HOME);
    check("Home", caret == 0);
    swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_RIGHT);
    check("Right", caret == 1);
    swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_END);
    check("End", caret == 5);
    check("Enter accepts", swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_RETURN) == SWKBD_ACCEPTED);
    check("Escape leaves", swkbd_edit(text, &len, &caret, 6, HOS_TEXT_KEY | VK_ESCAPE) == SWKBD_CANCELLED);

    /* the answer into the game's nn::swkbd::String: a guest pointer at +0, its size in bytes at +8 */
    uint16_t buffer[8] = {0};
    struct { uint64_t buffer, bytes; } string = {(uint64_t)(uintptr_t)buffer, sizeof buffer};
    check("the answer's units", swkbd_answer((uint64_t)(uintptr_t)&string, "KIRBY", 5) == 5);
    check("as UTF-16, NUL-terminated", buffer[0] == 'K' && buffer[4] == 'Y' && buffer[5] == 0);
    string.bytes = 6;   /* (two units and the 0) */
    check("capped by the string's own size", swkbd_answer((uint64_t)(uintptr_t)&string, "KIRBY", 5) == 2 && buffer[2] == 0);
    string.bytes = 0;   /* (what the game allocated while GetRequiredStringBufferSize answered 0: the bug) */
    buffer[0] = 0xAAAA;
    check("no room: nothing at all", swkbd_answer((uint64_t)(uintptr_t)&string, "KIRBY", 5) == 0 && buffer[0] == 0);
    check("GetRequiredStringBufferSize holds the most the game reads", SWKBD_BYTES / 2 - 1 >= SWKBD_UNITS);
    Ctx size = {{0}};
    imp__ZN2nn5swkbd27GetRequiredStringBufferSizeEv(&size);
    check("the size the game allocates with", (uint32_t)size.x[0] == SWKBD_BYTES);

    /* the wait: a frame every iteration, the text from the window, the focus off and the frame closed at the end */
    frames = closes = sleeps_now = focus_off = 0;
    script("KIRBY", HOS_TEXT_KEY | VK_RETURN);
    check("the player accepts", swkbd_ask(text, &len, 63) == 1);
    check("the text they typed", len == 5 && !strcmp(text, "KIRBY"));
    /* (and one more after Enter, though nothing is held: its present runs menu_tick, which takes the Insert menu's own record
       of that key (Windows: host/display.c notes every key-down for the menu), so it is no press of the menu's once the
       keyboard is gone) */
    check("a frame for every key, and one more after Enter", frames == 7 && shown_len == 5 && !strcmp(shown, "KIRBY"));
    check("one sleep before each frame but the first", sleeps_now == 6);
    check("the focus off once, the frame closed once", focus_off == 1 && closes == 1 && !focus_on);
    check("every frame with the game thread's core given up", frames_on_core == 0 && !away_now);

    /* Enter let go before the game reads its input again (Enter is bound to A) */
    frames = closes = sleeps_now = 0;
    enter_down_until = 9;
    script("KIRBY", HOS_TEXT_KEY | VK_RETURN);
    check("accepted with Enter", swkbd_ask(text, &len, 63) == 1 && !strcmp(text, "KIRBY"));
    check("Enter up when the game reads again", !(GetAsyncKeyState(VK_RETURN) & 0x8000));
    check("and the keyboard drawn while it was held", frames == 9 && closes == 1);
    enter_down_until = 0;
    frames = closes = 0;
    escape_down_until = 9;
    script("", HOS_TEXT_KEY | VK_ESCAPE);
    check("left with Escape", swkbd_ask(text, &len, 63) == 0);
    check("Escape up when the game reads again, the keyboard drawn while it was held",
          !(GetAsyncKeyState(VK_ESCAPE) & 0x8000) && frames == 9 && closes == 1);
    escape_down_until = 0;
    frames = closes = 0;
    q_down_until = 9;   /* (Q, one of the game's controls, typed last and still held after Enter is let go) */
    script("KIRBQ", HOS_TEXT_KEY | VK_RETURN);
    check("accepted with Q held", swkbd_ask(text, &len, 63) == 1 && !strcmp(text, "KIRBQ"));
    check("a key of the game's controls up when it reads again, the keyboard drawn while it was held",
          !(GetAsyncKeyState('Q') & 0x8000) && frames == 9 && closes == 1);
    q_down_until = 0;

    /* a controller alone (the Nintendo layout: A the right face button, B the bottom one) */
    const uint32_t A = 1u << HOS_PAD_EAST, B = 1u << HOS_PAD_SOUTH;
    const uint32_t a_held_then_pressed[] = {A, A, 0, 0, A, A, 0};
    frames = closes = 0;
    script("", 0), key_n = 0;
    pads_are(7, a_held_then_pressed);
    check("A accepts, the A that asked for the keyboard only once let go", swkbd_ask(text, &len, 63) == 1 && frames >= 5);
    check("and A up when the game reads again", !(kirby_pads_poll() & A) && closes == 1);
    const uint32_t b_pressed[] = {0, B, B, 0};
    frames = 0;
    pads_are(4, b_pressed);
    check("B leaves", swkbd_ask(text, &len, 63) == 0 && frames < 10 && !(kirby_pads_poll() & B));
    bound_a = bound_b = -1;   /* (A and B bound to no face button: the bottom one accepts, the right one leaves) */
    const uint32_t bottom[] = {0, B, 0}, right[] = {0, A, 0};
    frames = 0;
    pads_are(3, bottom);
    check("no face button bound: the bottom one accepts", swkbd_ask(text, &len, 63) == 1);
    frames = 0;
    pads_are(3, right);
    check("and the right one leaves", swkbd_ask(text, &len, 63) == 0 && frames < 10);
    bound_a = HOS_PAD_EAST, bound_b = HOS_PAD_SOUTH;
    pad_n = 0;
    frames = closes = sleeps_now = focus_off = 0;
    script("", HOS_TEXT_KEY | VK_ESCAPE);
    check("the player leaves", swkbd_ask(text, &len, 63) == 0 && len == 0);
    check("the focus off and the frame closed all the same", focus_off == 1 && closes == 1);
    frames = closes = sleeps_now = focus_off = 0;
    can_draw = 0;
    script("KIRBY", HOS_TEXT_KEY | VK_RETURN);
    check("nothing to draw on (a headless run): a cancel at once", swkbd_ask(text, &len, 63) == 0 && len == 0);
    check("no frame, no sleep, and the focus off again", frames == 0 && sleeps_now == 0 && focus_off == 1 && closes == 1);
    can_draw = 1;

    /* ShowKeyboard's own HLE, as the game calls it */
    switch_to(NULL);
    static uint16_t answer[0x800];
    struct { uint64_t buffer, bytes; } out = {(uint64_t)(uintptr_t)answer, sizeof answer};
    Ctx c = {{0}};
    c.x[0] = (uint64_t)(uintptr_t)&out;
    script("KIRBY", HOS_TEXT_KEY | VK_RETURN);
    imp__ZN2nn5swkbd12ShowKeyboardEPNS0_6StringERKNS0_15ShowKeyboardArgE(&c);
    check("the game hears success", c.x[0] == 0);
    check("and its code in its string", answer[0] == 'K' && answer[4] == 'Y' && answer[5] == 0 && logged == 1);
    memset(answer, 0, sizeof answer);
    c.x[0] = (uint64_t)(uintptr_t)&out;   /* (the argument again: the last call's result is in it) */
    script("", HOS_TEXT_KEY | VK_ESCAPE);
    imp__ZN2nn5swkbd12ShowKeyboardEPNS0_6StringERKNS0_15ShowKeyboardArgE(&c);
    check("left: the cancelled result", (uint32_t)c.x[0] == SWKBD_CANCELED && ((uint32_t)c.x[0] & 0x3FFFFF) == 671);
    check("and nothing written", answer[0] == 0);
    switch_to("ABCD1234");
    frames = closes = 0;
    c.x[0] = (uint64_t)(uintptr_t)&out;
    imp__ZN2nn5swkbd12ShowKeyboardEPNS0_6StringERKNS0_15ShowKeyboardArgE(&c);
    check("HOS_SWKBD answers for nobody", c.x[0] == 0 && answer[0] == 'A' && answer[7] == '4' && answer[8] == 0);
    check("with no frame drawn", frames == 0 && closes == 0);
    switch_to("A\tB\xc3\xa9" "C");   /* (a tab and UTF-8's two bytes of an e with an accent: printable ASCII alone, as typed) */
    memset(answer, 0, sizeof answer);
    c.x[0] = (uint64_t)(uintptr_t)&out;
    imp__ZN2nn5swkbd12ShowKeyboardEPNS0_6StringERKNS0_15ShowKeyboardArgE(&c);
    check("HOS_SWKBD's printable ASCII alone", c.x[0] == 0 && answer[0] == 'A' && answer[1] == 'B' && answer[2] == 'C' &&
                                               answer[3] == 0);
    switch_to(NULL);

    if (!bad) puts("ok");
    return bad;
}
"""


def run_c(cc: str) -> str:
    path = ROOT / "host/kirby_swkbd.c"
    if not path.exists():
        raise SystemExit("FAIL: %s is not there: nn::swkbd::ShowKeyboard is a stub, which answers 0, success, having "
                         "written nothing, so the game reads an empty code and says it was cancelled" % path)
    source = path.read_text(encoding="utf-8")
    # (the file's own includes are the host's; the harness makes what they bring: the macros, windows.h's keys, vk_api.h)
    cut = "\n".join(line for line in source.split("\n") if not line.startswith("#include"))
    fixture = HARNESS.replace("@SWKBD@", cut)
    compiler = shutil.which(cc)
    if not compiler:
        raise SystemExit("C compiler not found: " + cc)
    include = [str(ROOT / "gpu" / "vk")]
    with tempfile.TemporaryDirectory(prefix="kirby-swkbd-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.c").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        command = [compiler, "-std=c11", "-O1", "-Wall", "-Wno-unused-function"]
        command += [flag for folder_ in include for flag in ("-I", folder_)]
        subprocess.run(command + [str(folder / "fixture.c"), "-o", str(exe)], check=True, timeout=180)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    print(result.stdout, end="")
    if result.returncode:
        raise SystemExit("the fixture exited %d: %s" % (result.returncode, result.stderr.strip()))
    return result.stdout


def check_wiring() -> None:
    """nx2/standalone.py hooks the two, and leaves the three that only write a config stubbed"""
    from types import SimpleNamespace

    sys.path.insert(0, str(ROOT / "nx2"))   # (python -I: standalone.py imports kit and toolchain)
    spec = importlib.util.spec_from_file_location("standalone_under_test", ROOT / "nx2" / "standalone.py")
    standalone = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(standalone)
    imported = [SHOW, SIZE, PRESET]
    symbol = lambda name, defined: {"name": name, "defined": defined, "type": "func"}   # noqa: E731
    modules = [SimpleNamespace(name="main", symbols=[symbol(n, False) for n in imported]),
               SimpleNamespace(name="sdk", symbols=[symbol(n, True) for n in imported])]
    with contextlib.redirect_stdout(io.StringIO()):   # (hle_set lists every module's symbols: not this check's output)
        hooked, stubbed = standalone.hle_set(modules)
    for name, what in ((SHOW, "nn::swkbd::ShowKeyboard"), (SIZE, "nn::swkbd::GetRequiredStringBufferSize")):
        if name not in hooked or name in stubbed:
            raise SystemExit("FAIL: %s is still a stub (host/kirby_swkbd.c's HLE does not answer it)" % what)
    if PRESET not in stubbed:
        raise SystemExit("FAIL: nn::swkbd::MakePreset is no longer a stub")


def check_table() -> None:
    """Every function of MkwVkRenderer is set where the renderer fills its table: a NULL swkbd_frame is a cancel at once"""
    import re

    members = renderer_members((ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8"))
    filled = block((ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8"), "void fill_replay_table(MkwVkRenderer& t) {")
    filled += block((ROOT / "gpu/vk/vk_main.cpp").read_text(encoding="utf-8"),
                    "static const MkwVkRenderer* init_body(const MkwVkHost* h) {")
    unset = [m for m in members if not re.search(r"\b(?:t|table)\.%s\s*=" % m, filled)]
    if "swkbd_frame" not in members or unset:
        raise SystemExit("FAIL: the renderer never sets MkwVkRenderer::%s: the host calls NULL as nothing to draw on, and the "
                         "game hears a cancel at once (issue #30)" % ", ".join(unset or ["swkbd_frame"]))


MENU_HARNESS = r"""
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <set>
#include "vk_api.h"

typedef void* HWND;
typedef unsigned long DWORD;
enum { VK_BACK = 0x08, VK_TAB = 0x09, VK_RETURN = 0x0D, VK_SHIFT = 0x10, VK_CONTROL = 0x11, VK_ESCAPE = 0x1B, VK_PRIOR = 0x21,
       VK_NEXT = 0x22, VK_END = 0x23, VK_HOME = 0x24, VK_LEFT = 0x25, VK_UP = 0x26, VK_RIGHT = 0x27, VK_DOWN = 0x28,
       VK_INSERT = 0x2D, VK_DELETE = 0x2E, VK_F1 = 0x70, VK_F10 = 0x79 };
static HWND GetForegroundWindow() { return (HWND)1; }
static void GetWindowThreadProcessId(HWND, DWORD* pid) { *pid = 7; }
static DWORD GetCurrentProcessId() { return 7; }
static short GetAsyncKeyState(int) { return 0; }

namespace mkwvk {
static std::mutex menu_mu;
static int ticks_run;
static void share_finish() {}
static void fullscreen_tick() { ticks_run++; }
static void game_lang_tick() {}
static void outputs_follow_screen() {}
static double prof_now() { return 0; }
static void sim_turf_settings_tick(double) {}
static uint64_t output_preview_take_rebuilt_size() { return 0; }
static void menu_output_rebuilt(uint32_t, uint32_t) {}
static struct { uint32_t w; } output_preview_target;
static int output_preview_seconds() { return -1; }
static void answer_native_preview(bool) {}
static void edit_end(bool) {}
static void unavailable_native_preview() {}
static int listening, page, ask_sel, output_preview_countdown;
static std::atomic<bool> open_now{false};
static bool menu_refresh, pad_last;
static void logf(const char*, ...) {}
static void mic_test_tick(bool) {}
static struct { int menu_shortcut = 2, compact_menu_key = 0; } opts;
namespace kirby_swkbd {
static bool keyboard;
static bool up() { return keyboard; }
}
static std::set<int> queued;   // (the window thread's key presses, host/rx_backend.c host_take_key_press)
static uint32_t pad_now;
static MkwVkHost host_storage;
static const MkwVkHost* host = &host_storage;
static bool pressed[32];
static uint32_t pad_new;
static int acted;   // (menu_tick went on past the keys to act on them)

@TICK@
    acted++;
    for (int i = 0; i < K_N; i++) pressed[i] = press[i];
    pad_new = pad_press;
}
}  // namespace mkwvk

using namespace mkwvk;
int main() {
    host_storage.take_key_press = [](int key) -> int { return queued.erase(key) != 0; };
    host_storage.pad_raw = []() -> uint32_t { return pad_now; };
    int bad = 0;
    // (the keyboard up: Q, Enter and Escape typed into it, B held to leave it)
    kirby_swkbd::keyboard = true;
    queued = {'Q', VK_RETURN, VK_ESCAPE};
    pad_now = 1u << HOS_PAD_SOUTH;
    menu_tick();
    if (ticks_run != 1) puts("FAIL: the menu's other work stops while the keyboard is up"), bad = 1;
    if (acted) puts("FAIL: the menu acts on the keys typed into the keyboard while it is up (Escape opens it)"), bad = 1;
    // (it closes; B still held, no new key)
    kirby_swkbd::keyboard = false;
    menu_tick();
    for (int i = 0; i < 32; i++)
        if (pressed[i]) printf("FAIL: key %d, pressed into the keyboard, is a new press of the menu's once it closes\n", i), bad = 1;
    if (pad_new) puts("FAIL: B, held to leave the keyboard, is a new press of the menu's once it closes"), bad = 1;
    if (acted != 1) puts("FAIL: the menu does not act on its keys once the keyboard is closed"), bad = 1;
    if (!bad) puts("ok");
    return bad;
}
"""


def check_menu_keys(cxx: str) -> None:
    """menu_tick takes the keys and the pad's buttons while the keyboard is up, so none of them is new once it closes"""
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    tick = between(menu, "void menu_tick() {", "    {   // (RX_VK_UI_PROMPTS=pad or keys")
    compiler = shutil.which(cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + cxx)
    with tempfile.TemporaryDirectory(prefix="kirby-swkbd-menu-") as temporary:
        folder = Path(temporary)
        (folder / "menu.cpp").write_text(MENU_HARNESS.replace("@TICK@", tick), encoding="utf-8")
        exe = folder / ("menu.exe" if os.name == "nt" else "menu")
        subprocess.run([compiler, "-std=c++17", "-O1", "-Wall", "-Wno-unused-function", "-Wno-unused-variable",
                        "-I", str(ROOT / "gpu" / "vk"), str(folder / "menu.cpp"), "-o", str(exe)], check=True, timeout=180)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    print(result.stdout, end="")
    if result.returncode or "ok" not in result.stdout:
        raise SystemExit("FAIL: the keys typed into the software keyboard reach the Insert menu once it closes")


OVERLAY_HARNESS = r"""
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include "vk_api.h"

struct ImVec2 {
    float x, y;
    ImVec2(float a = 0, float b = 0) : x(a), y(b) {}
};
typedef unsigned ImU32;
struct ImFont;
struct ImDrawList {
    void AddRectFilled(ImVec2, ImVec2, ImU32) {}
};
namespace mkwvk {
struct {
    bool offscreen;
    struct { uint32_t width, height; } swap_extent;
} dev;
static int presents;
static uint32_t win_w, win_h;
void present_image(void*, uint32_t, uint32_t, const int*) { presents++; }
void kirby_window_size(uint32_t* w, uint32_t* h) { *w = win_w, *h = win_h; }
namespace ui {
const ImU32 kStartBg = 1, kInk = 2;
struct Fonts { ImFont *heading, *strong; };
struct Ctx {
    ImDrawList* d;
    Fonts f;
    float s, w, h, safe;
    bool pad;
};
enum Glyph { kConfirm, kBack };
struct Prompt { Glyph g; const char* what; };
static int bars, chars;
void text_centre(Ctx&, ImFont*, float, ImVec2, ImU32, const char*) {}
void box(Ctx&, ImVec2, ImVec2) {}
ImVec2 size_of(ImFont*, float px, const char*) { return ImVec2(px * 0.6f, px); }
template <class Width>
float fit_px(float px, float min_px, float step, float room, Width width) {
    for (float f = px; f >= min_px; f -= step)
        if (width(f) <= room) return f;
    return 0;
}
float text(Ctx&, ImFont*, float px, ImVec2, ImU32, const char*) { return chars++, px * 0.6f; }
float mid_top(ImFont*, float, float y) { return y; }
float prompt_bar(Ctx&, const Prompt*, int) { return bars++, 0; }
}  // namespace ui
}  // namespace mkwvk

@OVERLAY@

using namespace mkwvk;
int main() {
    int bad = 0;
    auto check = [&](const char* what, bool ok) {
        if (!ok) printf("FAIL: %s\n", what), bad = 1;
    };
    MkwVkSwkbd kb{};
    snprintf(kb.text, sizeof kb.text, "KIRBY"), kb.len = 5, kb.caret = 5;
    dev.offscreen = true;
    check("no window (HOS_HEADLESS=1): a cancel", kirby_swkbd::frame(&kb) == 0 && presents == 0);
    dev.offscreen = false;
    check("no swapchain: a cancel", kirby_swkbd::frame(&kb) == 0 && presents == 0);
    dev.swap_extent = {1280, 720};
    win_w = 1280, win_h = 720;
    check("a window: a frame presented", kirby_swkbd::frame(&kb) == 1 && presents == 1 && kirby_swkbd::up());
    win_w = win_h = 0;
    check("minimized: up, and no frame presented", kirby_swkbd::frame(&kb) == 1 && presents == 1 && kirby_swkbd::up());
    kirby_swkbd::close();
    check("closed", !kirby_swkbd::up());
    ImDrawList list;
    ui::Ctx c{&list, {nullptr, nullptr}, 1, 1280, 720, 0, false};
    kirby_swkbd::draw(c);
    check("the text and the prompts", ui::chars == 5 && ui::bars == 1);
    ui::chars = ui::bars = 0;
    c.w = 90;   // (a box too narrow for the text at the smallest size)
    kirby_swkbd::draw(c);
    check("too narrow for the text: the prompts all the same", ui::chars == 0 && ui::bars == 1);
    if (!bad) puts("ok");
    return bad;
}
"""


def check_overlay(cxx: str) -> None:
    """gpu/vk/kirby_swkbd.cpp: no window a cancel, minimized kept up, the prompts always drawn"""
    source = (ROOT / "gpu/vk/kirby_swkbd.cpp").read_text(encoding="utf-8")
    body = "\n".join(line for line in source.split("\n") if not line.startswith("#include"))
    compiler = shutil.which(cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + cxx)
    with tempfile.TemporaryDirectory(prefix="kirby-swkbd-overlay-") as temporary:
        folder = Path(temporary)
        (folder / "overlay.cpp").write_text(OVERLAY_HARNESS.replace("@OVERLAY@", body), encoding="utf-8")
        exe = folder / ("overlay.exe" if os.name == "nt" else "overlay")
        subprocess.run([compiler, "-std=c++17", "-O1", "-Wall", "-Wno-unused-function", "-I", str(ROOT / "gpu" / "vk"),
                        str(folder / "overlay.cpp"), "-o", str(exe)], check=True, timeout=180)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    print(result.stdout, end="")
    if result.returncode or "ok" not in result.stdout:
        raise SystemExit("FAIL: the software keyboard's overlay (gpu/vk/kirby_swkbd.cpp)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    failed = []
    for check in (lambda: run_c(args.cc), check_wiring, check_table, lambda: check_menu_keys(args.cxx),
                  lambda: check_overlay(args.cxx)):
        try:
            out = check()
        except SystemExit as e:
            failed.append(str(e))
            continue
        if isinstance(out, str) and "ok" not in out:
            failed.append("the software keyboard does not answer what the game asks (issue #30)")
    if failed:
        raise SystemExit("\n".join(failed))
    print("PASS: the keyboard's keys, its answer and its frames; the game is answered instead of a stub")


if __name__ == "__main__":
    main()
