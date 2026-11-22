"""Game-free test of host/kirby_queue.c and its five calls in host/nvn_native.c: issue #6, the crystal overlay that
dropped out for a frame. Each frame this game submits A1 on its first queue, then B on its second (the compute work
A1's draws read), presents, and submits A2 on the first. Handed to the replay in arrival order, A1 read the frame
before's grid: the order the replay gets must be B, A1, the present, A2.

The real entry points are cut out of host/nvn_native.c (nvnQueueSubmitCommands, nvnQueueFenceSync, nvnQueueFlush,
nvnSyncWait, nvnQueueFinish, nvnQueuePresentTexture, and upstream's held submissions) and compiled with
host/kirby_queue.c and stand-ins for the replay (which records the order and numbers the submissions), the virtual
core and the window. The test then makes the game's own calls and checks:

- nothing is held while one queue alone has submitted (each submission is handed over at its submit);
- the game's frame reaches the replay as B, A1, the present, A2, also for a thread that holds no virtual core;
- a frame without B: A1 goes at the present, before it, and a queue flush hands nothing over;
- two submissions of the first queue in a row keep their order; a queue finish hands over; a submission of two command
  buffers is held and handed over whole;
- a submission right after a present or a finish (A2) is handed over at its submit, not held (held, the main thread
  handed it over just before its wait, and with the render thread on that wait timed out in the game now and then);
- a sync wait for the held submission's fence hands it over first, and waits for the submission's own number, never
  for one not handed over; a wait for another fence leaves it held (the main thread's waits for the frame before,
  falling between A1 and B, must leave the order);
- every fence is its submission's number once handed over, two fences on one held submission too;
- the count that a dead recording copy outlives (kirby_queue_pushed) is past the held submission, also when the other
  queue's goes before it; that nvn_native.c's two places use that count is read from their text, as their code (the
  recordings' buckets and pools) is not compiled here;
- every hand-over is made with the virtual core given up, and the core is back after each call;
- HOS_KIRBY_QUEUE_ORDER=0 gives arrival order (A1, B, the present, A2), and so does upstream's HOS_NVN_HOLD=1, where
  the fix stands aside.

Each way runs twice: with a queue's fence its own last submission, and with every fence the replay's latest (the real
replay's answer while its render thread runs), where a fence is checked to be no lower than its submission's number.

Not modelled: threads (the game submits on its render thread and waits on its main thread; the lock, the unlocked
"nothing held" read and the order of taking the core again and letting the lock go are not exercised), timing, and
the replay itself.

    python -I tests/test_kirby_queue.py --cxx clang++
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
RUN_ALL_SKIP = {"windows": "the fixture is compiled as C with gcc's or clang's driver: checked on Linux"}

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between, block

PREFIX = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
void InitializeCriticalSection(CRITICAL_SECTION *cs) { pthread_mutex_init(cs, NULL); }   /* (host/posix/win32_posix.c) */

/* ---- the calling convention and the objects, as host/nvn_native.c and gpu/render/rx_nvn.h have them ---- */
typedef struct { uint64_t x[31]; } Ctx;
#define NV(name) static void n_##name(Ctx *c, void *u_)
#define P(i) ((void *)(uintptr_t)c->x[i])
#define PN(i, n) ((void *)(uintptr_t)c->x[i])
#define I(i) ((int)c->x[i])
#define U64(i) (c->x[i])
#define RET(v) (c->x[0] = (uint64_t)(v))
typedef struct { uint32_t magic, fenced; uint64_t fence; } nvn_sync;
typedef struct { uint32_t magic; uint64_t submits; } nvn_queue;
typedef struct { int ntex, crop[4], presents; } nvn_win;
typedef struct { int unused; } nvn_tex;
enum { NVN_SYNC_WAIT_RESULT_ALREADY_SIGNALED, NVN_SYNC_WAIT_RESULT_CONDITION_SATISFIED, NVN_SYNC_WAIT_RESULT_TIMEOUT_EXPIRED };
#define HOS_CHAIN(kind, key) ((void)(key))

/* ---- the replay: the order it is handed things in, and each submission's number (what a fence is) ---- */
static char order[256];
static void note(const char *s) { if (*order) strcat(order, " "); strcat(order, s); }
#define SUBMITS 64
static const char *names[SUBMITS];              /* by handle: the test's name of the submission */
static uint64_t queue_of[SUBMITS], number[SUBMITS];
static uint64_t latest, q_last[2], q_id[2];
static int global_fences;                       /* every queue's fence the latest (the real replay's, its render thread on) */
static int has_core = 1, core = 1;              /* the thread's virtual core: whether it has one at all, and holds it now */
static void handed(const uint64_t *h, int n, uint64_t queue, int with_queue) {
    latest++;
    for (int k = 0; k < n; k++) {
        assert(h[k] < SUBMITS && names[h[k]]);
        assert(!with_queue || queue == queue_of[h[k]]);
        note(names[h[k]]);
        number[h[k]] = latest;
    }
    for (int i = 0; i < 2; i++) if (q_id[i] == queue_of[h[0]]) q_last[i] = latest;
}
void rx_nvn_submit_q(const uint64_t *h, int n, uint64_t queue) {
    if (has_core && core) { printf("FAIL: %s handed to the replay with the virtual core held\n", names[h[0]]); exit(1); }
    handed(h, n, queue, 1);
}
void rx_nvn_submit(const uint64_t *h, int n) { handed(h, n, 0, 0); }   /* (upstream's held ones: HOS_NVN_HOLD=1) */
uint64_t rx_nvn_fence(void) { return latest; }
uint64_t rx_nvn_pushed(void) { return latest; }
static uint64_t rx_nvn_fence_q(uint64_t queue) { return global_fences ? latest : q_last[queue == q_id[1]]; }
static uint64_t rx_nvn_replayed(void) { return latest; }
static uint64_t waited;
static int rx_nvn_wait(uint64_t fence, uint64_t timeout) {
    (void)timeout;
    if (fence > latest) { printf("FAIL: a wait for submission %llu, the latest handed over is %llu\n",
                                 (unsigned long long)fence, (unsigned long long)latest); exit(1); }
    waited = fence;
    return 1;
}
static void rx_nvn_finish(void) {}
static const nvn_tex *win_tex(const nvn_win *o, int i) { static nvn_tex t; (void)o; (void)i; return &t; }
static void rx_nvn_present(const nvn_tex *t, const int crop[4]) { (void)t; (void)crop; note("P"); latest++; }   /* (a present takes a number too) */
/* (upstream's live output preview, which nvnQueuePresentTexture reads: off, as it is until a preview is staged) */
typedef struct { nvn_win window; } detached_window;
static int detached_idle_enabled;
static uint64_t detached_published_generation, detached_boot_addr;
static void *detached_received_queue;
static unsigned detached_received_instance;
uint64_t detached_last_present_window, detached_last_present_generation;   /* (not static: set and not read here) */
void *detached_last_present_queue;
unsigned detached_last_present_instance;
#define GP(a) ((void *)(uintptr_t)(a))
static uint64_t h2g(const void *p) { return (uint64_t)(uintptr_t)p; }
static void rx_nvn_present_trial(const nvn_tex *t, const int crop[4], uint64_t generation) {
    (void)t; (void)crop; (void)generation; printf("FAIL: a preview's present with no preview staged\n"); exit(1);
}

/* ---- the rest of the host ---- */
int hos_vcore_away(void) { const int had = has_core && core; core = 0; return had; }
void hos_vcore_back(void) { core = 1; }
void hos_renderer_wait(void) {}
volatile LONG64 hos_present_count;
static int hos_vi_present_trace_enabled(void) { return 0; }
static void hos_vi_native_presented(const int64_t phases[4]) { (void)phases; }
static int64_t hos_now_ns(void) { return 0; }
static void wait_note(int kind, int64_t t0) { (void)kind; (void)t0; }
static int sync_log(void) { return 0; }
static int env_on(const char *name) {   /* (the "1" and "0" of the runs below: upstream's HOS_NVN_HOLD reads it now) */
    const char *v = getenv(name);
    return v && *v && strcmp(v, "0") != 0;
}
void hos_log(const char *fmt, ...) { (void)fmt; }
static void die(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vprintf(fmt, ap); va_end(ap); exit(91); }
static void check_handle(uint64_t h) { (void)h; }
static void resolve_deferred(uint8_t *p) { (void)p; }
int kirby_queue_submit(uint64_t queue, const uint64_t *handles, int n);
void kirby_queue_fenced(uint64_t queue, uint64_t *fence);
void kirby_queue_flush(const uint64_t *fence);
uint64_t kirby_queue_pushed(void);
'''

SUFFIX = r'''
/* ---- the game's calls ---- */
static nvn_queue qa, qb;
static nvn_win window = {1, {0}, 0};
static int nsubmits = 1;
static void cored(void) { assert(!has_core || core); }   /* (after each call the thread has its core again) */
static int submit2(nvn_queue *q, const char *name, const char *second) {   /* (second: a second command buffer, or NULL) */
    const uint64_t h[2] = {(uint64_t)nsubmits, (uint64_t)nsubmits + 1};
    const int n = second ? 2 : 1;
    nsubmits += n;
    assert(nsubmits <= SUBMITS);
    names[h[0]] = name, names[h[1]] = second;
    queue_of[h[0]] = queue_of[h[1]] = (uint64_t)(uintptr_t)q;
    Ctx c = {{(uint64_t)(uintptr_t)q, (uint64_t)n, (uint64_t)(uintptr_t)h}};
    n_nvnQueueSubmitCommands(&c, NULL);
    cored();
    return (int)h[0];
}
static int submit(nvn_queue *q, const char *name) { return submit2(q, name, NULL); }
static void fence(nvn_queue *q, nvn_sync *s) {
    Ctx c = {{(uint64_t)(uintptr_t)q, (uint64_t)(uintptr_t)s}};
    memset(s, 0, sizeof *s);
    n_nvnQueueFenceSync(&c, NULL);
    cored();
}
static void flush(nvn_queue *q) { Ctx c = {{(uint64_t)(uintptr_t)q}}; n_nvnQueueFlush(&c, NULL); cored(); }
static void finish(nvn_queue *q) { Ctx c = {{(uint64_t)(uintptr_t)q}}; n_nvnQueueFinish(&c, NULL); cored(); }
static void present(void) { Ctx c = {{(uint64_t)(uintptr_t)&qa, (uint64_t)(uintptr_t)&window, 0}}; n_nvnQueuePresentTexture(&c, NULL); cored(); }
/* (a wait: answered, for this fence's own submission) */
static void wait_for(nvn_sync *s, int h) {
    Ctx c = {{(uint64_t)(uintptr_t)s, 1000000}};
    waited = ~0ull;
    n_nvnSyncWait(&c, NULL);
    cored();
    if (c.x[0] != NVN_SYNC_WAIT_RESULT_ALREADY_SIGNALED || waited != s->fence ||
        (global_fences ? s->fence < number[h] : s->fence != number[h])) {
        printf("FAIL: the wait for %s (submission %llu): result %llu, waited for %llu, the fence is %llu\n", names[h],
               (unsigned long long)number[h], (unsigned long long)c.x[0], (unsigned long long)waited, (unsigned long long)s->fence);
        exit(1);
    }
}
static void want(const char *what, const char *wanted) {
    if (strcmp(order, wanted)) { printf("FAIL: %s: the replay got \"%s\", wanted \"%s\"\n", what, order, wanted); exit(1); }
}
static void fresh(void) { order[0] = 0; }
/* (what a dead recording copy outlives: past the held submission, also when the other queue's goes before it) */
static void pushed_is(const char *what, uint64_t more) {
    if (kirby_queue_pushed() != latest + more) {
        printf("FAIL: %s: kirby_queue_pushed is %lld past the replay's count, wanted %llu\n", what,
               (long long)(kirby_queue_pushed() - latest), (unsigned long long)more);
        exit(1);
    }
}

/* The game's frame, and then its main thread's three waits. A2 is handed over by the present's flush of the frame
   after, or by the first wait: here the first wait */
static void frame(const char *what, const char *wanted) {
    nvn_sync s[3];
    int h[3];
    fresh();
    h[0] = submit(&qa, "A1"), fence(&qa, &s[0]), flush(&qa);
    h[1] = submit(&qb, "B"), fence(&qb, &s[1]), flush(&qb);
    present();
    h[2] = submit(&qa, "A2"), fence(&qa, &s[2]), flush(&qa);
    for (int i = 0; i < 3; i++) wait_for(&s[i], h[i]);
    want(what, wanted);
}

int main(int argc, char **argv) {
    if (argc != 3) return 90;
    const int fixed = !strcmp(argv[1], "fixed"), hold = !strcmp(argv[1], "hold");
    global_fences = !strcmp(argv[2], "global");
    q_id[0] = (uint64_t)(uintptr_t)&qa, q_id[1] = (uint64_t)(uintptr_t)&qb;
    nvn_sync s, s2;
    int h, h2;

    if (!hold) {
        /* one queue alone: each submission handed over at its submit */
        fresh();
        submit(&qa, "a"), want("one queue, the first submit", "a");
        h = submit(&qa, "b"), want("one queue, the second submit", "a b");
        fence(&qa, &s), present(), want("one queue, the present", "a b P");
        wait_for(&s, h);
    }

    /* the first frame with a second queue: A1 came before B was ever seen, so it is in arrival order */
    frame("the first frame with two queues", "A1 B P A2");
    /* the game's frame from then on: this is issue #6 */
    frame("the game's frame", fixed ? "B A1 P A2" : "A1 B P A2");
    frame("the game's frame again", fixed ? "B A1 P A2" : "A1 B P A2");
    has_core = 0;   /* (a thread that holds no virtual core: nothing to give up, the same order) */
    frame("the game's frame, no virtual core", fixed ? "B A1 P A2" : "A1 B P A2");
    has_core = 1, core = 1;
    if (!fixed) {   /* (nothing is ever held by kirby_queue.c: the count is the replay's) */
        submit(&qa, "A1"), pushed_is(argv[1], 0), finish(&qa);
        puts("ok");
        return 0;
    }

    /* a frame without B: a queue flush hands nothing over, the present hands A1 over before it; a finish hands A2 over */
    fresh();
    pushed_is("nothing held", 0);
    h = submit(&qa, "A1"), fence(&qa, &s), flush(&qa), want("no B, after the queue flush", "");
    pushed_is("A1 held", 2);
    present(), want("no B, the present", "A1 P");
    h2 = submit(&qa, "A2"), fence(&qa, &s2), want("no B, A2 at its submit", "A1 P A2");
    finish(&qa), want("no B, the finish", "A1 P A2");
    pushed_is("after the finish", 0);
    wait_for(&s, h), wait_for(&s2, h2);

    /* two of the first queue in a row: the one before goes first, one is held; a wait for the first one's fence, which
       is handed over, leaves the second held */
    fresh();
    h = submit(&qa, "A1"), fence(&qa, &s);
    h2 = submit(&qa, "A1b"), fence(&qa, &s2), want("two in a row, the second submit", "A1");
    wait_for(&s, h), want("two in a row, a wait for the first", "A1");
    wait_for(&s2, h2), want("two in a row, a wait for the second", "A1 A1b");

    /* a sync wait for the held one's fence hands it over before it asks the replay */
    fresh();
    h = submit(&qa, "A1"), fence(&qa, &s), want("a wait, before it", "");
    wait_for(&s, h), want("a wait", "A1");

    /* the main thread's wait for a fence of the frame before, falling between A1 and B: B still goes first */
    fresh();
    h2 = submit(&qa, "A1"), fence(&qa, &s2);
    wait_for(&s, h), want("a wait for another fence", "");
    submit(&qb, "B"), want("a wait for another fence, then B", "B A1");
    wait_for(&s2, h2);

    /* A2, right after a present, and a submission right after a finish: handed over at the submit, not held; the one
       after them is held again, also when the other queue's came between the present and it */
    fresh();
    h = submit(&qa, "A1"), fence(&qa, &s), submit(&qb, "B"), present();
    h2 = submit(&qa, "A2"), fence(&qa, &s2), want("A2, at its submit", "B A1 P A2");
    pushed_is("A2 not held", 0);
    wait_for(&s, h), wait_for(&s2, h2);
    finish(&qa), h2 = submit(&qa, "A"), want("after a finish, at the submit", "B A1 P A2 A");
    submit(&qa, "A1"), want("the next one, held", "B A1 P A2 A");
    present(), submit(&qb, "B"), submit(&qa, "A1"), want("B after a present, then A1: held", "B A1 P A2 A A1 P B");
    finish(&qa), want("then the finish", "B A1 P A2 A A1 P B A1");

    /* a submission of two command buffers: held and handed over whole */
    fresh();
    submit(&qa, "A0"), submit2(&qa, "A1", "A1+"), submit(&qb, "B"), want("two command buffers", "A0 B A1 A1+");   /* (A0: after the finish above) */

    /* two fences on one held submission: both its number */
    fresh();
    h = submit(&qa, "A1"), fence(&qa, &s), fence(&qa, &s2);
    h2 = submit(&qb, "B"), want("two fences", "A1 B");
    wait_for(&s, h), wait_for(&s2, h);

    /* a fence on the other queue while the first's is held: the other queue's own last submission, nothing handed over */
    fresh();
    h = submit(&qa, "A1"), fence(&qb, &s2), want("the other queue's fence", "");
    wait_for(&s2, h2), want("the other queue's fence, the wait", "");
    finish(&qa), want("the other queue's fence, the finish", "A1");
    puts("ok");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    native = (ROOT / "host/nvn_native.c").read_text(encoding="utf-8")
    # (the two places a recording's copy is given the submission it must outlive: read, not run)
    for marker in ("static void release_copies(", "static size_t sweep_overwritten_copies("):
        assert "const uint64_t after = kirby_queue_pushed() + held_count();" in block(native, marker), \
            marker + ": a dead copy's `after` no longer counts the submission host/kirby_queue.c holds"
    cut = [
        # (upstream's held submissions and nvnQueueFenceSync)
        between(native, "typedef struct { int n; uint64_t h[64]; } held_submit;", "/* (the GPU waits the game makes:"),
        block(native, "NV(nvnSyncWait) {"),
        block(native, "NV(nvnQueueFlush) {"),
        block(native, "NV(nvnQueueFinish) {"),
        block(native, "NV(nvnQueueSubmitCommands) {"),
        block(native, "NV(nvnQueuePresentTexture) {"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.c"
        test.write_text(PREFIX + "\n".join(cut) + SUFFIX, encoding="utf-8")
        exe = Path(tmp) / "test"
        # (-x c before each file: g++ 16 takes the second of two .c files as C++ after a single one)
        subprocess.run([args.cxx, "-std=gnu11", "-Wall", "-Werror", "-I", str(ROOT / "host/posix"),
                        "-x", "c", str(ROOT / "host/kirby_queue.c"), "-x", "c", str(test), "-o", str(exe), "-pthread"],
                       check=True)
        # (each switch is read once, so each way is a run of its own)
        for mode, switches in (("fixed", {}), ("arrival", {"HOS_KIRBY_QUEUE_ORDER": "0"}), ("hold", {"HOS_NVN_HOLD": "1"})):
            env = {k: v for k, v in os.environ.items() if k not in ("HOS_KIRBY_QUEUE_ORDER", "HOS_NVN_HOLD")}
            for fences in ("queue", "global"):
                out = subprocess.run([str(exe), mode, fences], capture_output=True, text=True, env={**env, **switches})
                sys.stdout.write(out.stdout)
                assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), (mode, fences, out.returncode, out.stderr)
    print("test_kirby_queue: ok")


if __name__ == "__main__":
    main()
