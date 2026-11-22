/* (inhale) The order of this game's two queues (Kirby and the Forgotten Land, Switch 2 Edition): docs/design.md,
   "issue #6, the crystal overlay drops out for a frame".

   Each frame the game's render thread submits A1 on its first queue (shadows, G-buffer, lighting, the window's blit),
   then B on its second (three compute dispatches, the first of which builds the grid the crystal overlay's draws in A1
   sample), presents, and submits A2 on the first (exposure). No event waits between the queues: on the console they
   run side by side, and B's short work is done long before A1 reaches its G-buffer pass. The replay runs submissions
   in arrival order on one queue, so A1's draws read the grid of the frame before, and the overlay drops out for a
   frame where the lists the grid is built from change (a jump, a camera turn).

   So the first queue's submission is held here, and handed to the replay
     - after the other queue's next submission, which goes first (B before A1);
     - before the first queue's next one (at most one is held);
     - at a present, a queue finish, or a sync wait for its own fence.
   One submitted right after a present or a finish (A2) is not held: it goes at its submit, as before. Nothing would
   overtake it (the next A1 sends it first), and held, it went to the replay from the main thread's wait instead, just
   before the wait asked for it: with the render thread on, that wait timed out after 10 s now and then, the replay's
   batched submit sent to the GPU before the render thread had recorded A2 (boot, 2 runs in 6; section 9).
   The first queue is the one of the first submission ever, and nothing is held until a second queue has submitted: a
   game with one queue is handed over as before. A queue flush hands nothing over: the game flushes its first queue
   right after A1, which is where B must still overtake it.

   A held submission is captured by the replay when it is handed over, not when the game submitted it: later by what
   the game does up to its next submission, a present or a wait. What the game hands the replay meanwhile that is no
   submission (a texture's registration or release) gets there first: the game keeps what a submission names until it
   has waited for its fence, and that wait hands over.

   A fence taken on the first queue while its submission is held cannot know its value yet (one more than the
   replay's latest, or two when the other queue's comes first): it gets the lower one and is set to the exact one at
   the hand-over. A wait for that fence hands over first, so no wait sees the value before. A wait for another fence
   leaves it held: the main thread's waits for the frame before would else send A1 ahead of B when they fall between
   the two.

   The recordings a held submission names must outlive it: nvn_native.c frees a recording's copy once the replay has
   passed the submissions made by then, which it counts by kirby_queue_pushed.

   The game's render thread submits and its main thread waits, so the state is under a lock. The virtual core is given
   up for a hand-over as nvnQueueSubmitCommands gives it up, and taken again only after the lock is let go: a thread
   waiting for a core with the lock held could stall the one that holds a core and waits for the lock.

   HOS_KIRBY_QUEUE_ORDER=0: off, arrival order. With upstream's HOS_NVN_HOLD=1 nvnQueueSubmitCommands does not ask. */
#ifndef INHALE_ENV_H   /* (env_on: the switches' one rule) */
#include "../gpu/vk/compat/inhale_env.h"
#endif
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

void hos_log(const char *fmt, ...);
void rx_nvn_submit_q(const uint64_t *handles, int n, uint64_t queue);   /* rx_backend.c */
uint64_t rx_nvn_fence(void);                                            /* rx_backend.c: the latest submission's value */
uint64_t rx_nvn_pushed(void);                                           /* rx_backend.c: the submissions handed over */
int hos_vcore_away(void);                                               /* hos_thread.c */
void hos_vcore_back(void);

static SRWLOCK lock = SRWLOCK_INIT;
static uint64_t first;          /* the queue whose submissions are held: the one of the first submission ever */
static volatile LONG two;       /* a second queue has submitted */
static volatile LONG holding;   /* one of the first queue's is held (read without the lock too) */
static uint64_t held[64];       /* its handles (nvnQueueSubmitCommands takes 64 at most) */
static int held_n;
static uint64_t *held_fence;    /* the fence taken on it, set at the hand-over */
static volatile LONG flushed;   /* a present or a finish was the last call here: nothing submitted since */
static uint64_t handed;         /* the value of the last one handed over */

static int order_on(void) {
    static int on = -1;
    if (on < 0) on = env_on_or("HOS_KIRBY_QUEUE_ORDER", 1);
    return on;
}

/* (the lock held, the core given up) The held submission to the replay, and its fence to its value */
static void hand_held(void) {
    if (!holding) return;
    rx_nvn_submit_q(held, held_n, first);
    handed = rx_nvn_fence();
    if (held_fence) *held_fence = handed, held_fence = NULL;
    InterlockedExchange(&holding, 0);   /* (last: a wait that finds nothing held reads the exact fence) */
}

// doc: docs/design.md#4-the-lessons-from-mkw-as-rules-here (rule 1: queues that share no event still have an order)
/* nvnQueueSubmitCommands, in place of its hand-over. Returns 1 when the submission was taken (handed over or held),
   0 when the switch is off */
int kirby_queue_submit(uint64_t queue, const uint64_t *handles, int n) {
    if (!order_on()) return 0;
    AcquireSRWLockExclusive(&lock);
    if (!first) first = queue;
    const int other = queue != first;
    if (other && !two) {
        hos_log("kirby: two queues: %#llx's submissions go to the replay after %#llx's next one (HOS_KIRBY_QUEUE_ORDER=0: as they come)",
                (unsigned long long)first, (unsigned long long)queue);
        two = 1;
    }
    const int after_present = InterlockedExchange(&flushed, 0);   /* (any submission clears it) */
    const int hold = !other && two && !after_present;   /* (A2: not held) */
    const int away = hold && !holding ? 0 : hos_vcore_away();   /* (only held: nothing goes to the replay now) */
    if (other) rx_nvn_submit_q(handles, n, queue);   /* the other queue's goes first */
    hand_held();
    if (hold) {
        memcpy(held, handles, 8 * (size_t)n);
        held_n = n;
        InterlockedExchange(&holding, 1);
    } else if (!other) {
        rx_nvn_submit_q(handles, n, queue);
    }
    ReleaseSRWLockExclusive(&lock);
    if (away) hos_vcore_back();
    return 1;
}

/* nvnQueueFenceSync, after it set *fence from the replay: the value of a fence on the held submission. A second fence
   on the same one hands it over. */
void kirby_queue_fenced(uint64_t queue, uint64_t *fence) {
    if (!two || queue != first) return;
    AcquireSRWLockExclusive(&lock);
    const int away = holding && held_fence ? hos_vcore_away() : 0;
    if (holding && held_fence) hand_held();
    if (holding) *fence = rx_nvn_fence() + 1, held_fence = fence;
    else if (*fence < handed) *fence = handed;   /* (handed over by another thread's wait since the caller asked the replay) */
    ReleaseSRWLockExclusive(&lock);
    if (away) hos_vcore_back();
}

/* A present or a queue finish (fence NULL): what is held goes to the replay first. A sync wait, before it reads the
   sync's fence: only when that fence is the held submission's */
void kirby_queue_flush(const uint64_t *fence) {
    if (!fence) InterlockedExchange(&flushed, 1);
    if (!holding) return;
    AcquireSRWLockExclusive(&lock);
    const int go = holding && (!fence || fence == held_fence);
    const int away = go ? hos_vcore_away() : 0;
    if (go) hand_held();
    ReleaseSRWLockExclusive(&lock);
    if (away) hos_vcore_back();
}

/* rx_nvn_pushed for nvn_native.c's dead recording copies: the number of the last submission the game has made, the
   held one counted. It counts two: the other queue's next one may go before it. (Whether one is held is read first: a
   hand-over between the two reads gives a number too high, which frees a copy later, never too early) */
uint64_t kirby_queue_pushed(void) {
    const uint64_t more = holding ? 2 : 0;
    return rx_nvn_pushed() + more;
}
