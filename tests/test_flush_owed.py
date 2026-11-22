"""(inhale) A blocking wait's fence sends the batch its submit lands in: gpu/vk/flush_owed_inhale.h and its five lines in
gpu/vk/vk_replay.cpp.

    python -I -B tests/test_flush_owed.py [--cxx clang++]

For MSVC use --cxx cl in a configured developer prompt. No game or GPU.

The stall it checks against (docs/design.md section 9, "issue #6"): with batched submits (RX_VK_BATCH), a game's thread
waiting for fence value f sent what was held before the render thread had held the submit of f, and that submit then
stayed held, with the GPU busy, until the wait gave up after 10 s. Upstream's rec::take_flush_owed (#1866) does not cover
it: the wait came before the render thread had replayed f's job, so no part of it was handed over to be owed (the 4-6
stalls a walk after the sync to v3.1.1).

A model compiled with the real header: a stand-in for the held submits (pend), the replay's send (queue_flush_locked) and
the waiter's (queue_flush_for), a submit that holds and then asks whether a waiter is owed, and the GPU always busy (no
send because it is idle). The bug's order, the other order, a poll, two waiters, a wait for what is already sent, and a
waiter and a submitter on two threads racing 100,000 times: every owed value is sent by the end of its round, and a
submit no waiter owes stays held. Then the text of vk_replay.cpp: the five lines where the model puts them (the submit's
in both places that hold one: submit_recording and the recorder's part_submit).

Not modelled: the real wait's later sends and its driver wait, the frame gate, RX_VK_BATCH_MAX, the GPU idle send, the
recordings' timeline (wait_recorded), timing.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, find   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cxx", "{cxx}"]

MODEL = r'''
#include "flush_owed_inhale.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <thread>

static int failures;
#define CHECK(cond, ...) do { if (!(cond)) { std::printf("FAIL: " __VA_ARGS__); std::printf("\n"); failures++; } } while (0)

// (vk_replay.cpp's pend, pend_held, timeline_sent and dev.present_mu, the GPU always busy)
struct Replay {
    std::mutex present_mu;
    std::atomic<bool> pend_held{false};
    int held = 0;              // pend.cbs.size()
    uint64_t signal = 0;       // pend.signal
    std::atomic<uint64_t> sent{0};   // timeline_sent
    int sends = 0;
    mkwvk::FlushOwed owed;
    void flush_locked() {      // queue_flush_locked
        if (!held) return;
        if (signal > sent.load(std::memory_order_relaxed)) sent.store(signal, std::memory_order_relaxed);
        owed.met(signal);
        sends++;
        held = 0, signal = 0;
        pend_held.store(false, std::memory_order_release);
    }
    void flush_for() {         // queue_flush_for
        if (!pend_held.load(std::memory_order_acquire)) return;
        std::lock_guard<std::mutex> lk(present_mu);
        flush_locked();
    }
    void wait(uint64_t f, uint64_t timeout_ns) {   // wait, up to its driver wait
        if (timeout_ns) owed.owe(f, sent.load(std::memory_order_relaxed));
        flush_for();
    }
    void submit(uint64_t v) {  // submit_recording's batch branch
        std::lock_guard<std::mutex> lk(present_mu);
        held++;
        pend_held.store(true, std::memory_order_release);
        if (v > signal) signal = v;
        if (held && owed.due(signal)) flush_locked();
    }
};

int main() {
    const uint64_t kWait = 10000000000ull;
    {   // the bug's order: the wait's send finds nothing held, then the submit of its value
        Replay r;
        r.wait(5, kWait);
        CHECK(r.sends == 0, "the bug's order: the wait sent %d batches with nothing held", r.sends);
        r.submit(5);
        CHECK(r.sent.load() >= 5, "the bug's order: the submit of the value waited for stayed held (sent %llu)",
              (unsigned long long)r.sent.load());
        CHECK(r.owed.upto.load() == 0, "the bug's order: still owed %llu once sent", (unsigned long long)r.owed.upto.load());
        r.submit(6);
        CHECK(r.held == 1 && r.sent.load() == 5, "the bug's order: the next submit was not held (held %d, sent %llu)", r.held,
              (unsigned long long)r.sent.load());
    }
    {   // the submit first: the waiter's own send takes it, and the next submit stays held
        Replay r;
        r.submit(5);
        CHECK(r.held == 1 && r.sent.load() == 0, "submit first: sent before any wait");
        r.wait(5, kWait);
        CHECK(r.sent.load() >= 5, "submit first: the waiter's send did not send it");
        CHECK(r.owed.upto.load() == 0, "submit first: still owed %llu once sent", (unsigned long long)r.owed.upto.load());
        r.submit(6);
        CHECK(r.held == 1 && r.sent.load() == 5, "submit first: the next submit was sent at once (a batch of one)");
    }
    {   // a poll owes nothing
        Replay r;
        r.wait(5, 0);
        r.submit(5);
        CHECK(r.held == 1 && r.sent.load() == 0, "a poll: its value's submit was sent at once (held %d)", r.held);
    }
    {   // two waiters, f < g: both sent by g's submit at the latest, nothing owed after
        Replay r;
        r.wait(5, kWait);
        r.wait(7, kWait);
        r.submit(5);
        r.submit(6);
        r.submit(7);
        CHECK(r.sent.load() >= 7, "two waiters: g's submit stayed held (sent %llu)", (unsigned long long)r.sent.load());
        CHECK(r.owed.upto.load() == 0, "two waiters: still owed %llu", (unsigned long long)r.owed.upto.load());
        r.submit(8);
        CHECK(r.held == 1 && r.sent.load() == 7, "two waiters: the next submit was sent at once");
    }
    {   // a signal past the owed value (finish_recording's signal_at, a burst's): sent, nothing signals the value itself
        Replay r;
        r.wait(5, kWait);
        r.submit(7);
        CHECK(r.sent.load() >= 7, "a signal past the owed value: stayed held (sent %llu)", (unsigned long long)r.sent.load());
        CHECK(r.owed.upto.load() == 0, "a signal past the owed value: still owed %llu", (unsigned long long)r.owed.upto.load());
    }
    {   // a send of less than the owed value (another wait's, a poll's) leaves it owed: its submit still sends
        Replay r;
        r.wait(7, kWait);
        r.submit(5);
        r.flush_for();
        CHECK(r.owed.upto.load() == 7, "a lower send: owed %llu, wanted 7 still", (unsigned long long)r.owed.upto.load());
        r.submit(7);
        CHECK(r.sent.load() >= 7, "a lower send: the owed value's submit stayed held (sent %llu)", (unsigned long long)r.sent.load());
    }
    {   // a wait for what is already sent (the frame before's fence) owes nothing: the next submit stays held
        Replay r;
        r.submit(5);
        r.flush_for();
        r.wait(5, kWait);
        r.submit(6);
        CHECK(r.held == 1 && r.sent.load() == 5, "a wait for a sent value: the next submit was sent at once");
        CHECK(r.owed.upto.load() == 0, "a wait for a sent value: owed %llu", (unsigned long long)r.owed.upto.load());
    }
    {   // a waiter and a submitter racing: the waiter's value sent by the end of every round
        Replay r;
        const uint64_t rounds = 100000;
        std::atomic<uint64_t> go{0}, done{0};
        std::atomic<uint64_t> unsent{0}, first_unsent{0};
        std::thread waiter([&] {
            for (uint64_t i = 1; i <= rounds; i++) {
                while (go.load(std::memory_order_acquire) < i) {}
                for (uint64_t s = (i * 7) % 13; s; s--) std::atomic_signal_fence(std::memory_order_seq_cst);
                r.wait(i, kWait);
                done.fetch_add(1, std::memory_order_acq_rel);
            }
        });
        std::thread submitter([&] {
            for (uint64_t i = 1; i <= rounds; i++) {
                while (go.load(std::memory_order_acquire) < i) {}
                for (uint64_t s = (i * 5) % 11; s; s--) std::atomic_signal_fence(std::memory_order_seq_cst);
                r.submit(i);
                done.fetch_add(1, std::memory_order_acq_rel);
            }
        });
        for (uint64_t i = 1; i <= rounds; i++) {
            go.store(i, std::memory_order_release);
            while (done.load(std::memory_order_acquire) < 2 * i) {}
            if (r.sent.load() < i) {
                if (!unsent.load()) first_unsent = i;
                unsent++;
                std::lock_guard<std::mutex> lk(r.present_mu);   // (sent anyway, so the next round starts clean)
                r.flush_locked();
            }
        }
        waiter.join(), submitter.join();
        CHECK(unsent.load() == 0, "racing: %llu of %llu rounds left the waited value held (the first: round %llu)",
              (unsigned long long)unsent.load(), (unsigned long long)rounds, (unsigned long long)first_unsent.load());
        CHECK(r.owed.upto.load() == 0, "racing: still owed %llu at the end", (unsigned long long)r.owed.upto.load());
    }
    if (failures) return 1;
    std::printf("flush_owed model: ok\n");
    return 0;
}
'''


def text_checks(src):
    """Where vk_replay.cpp calls the header: the places the model puts them in"""
    problems = []
    if '#include "flush_owed_inhale.h"' not in src:
        problems.append('no #include "flush_owed_inhale.h"')

    wait = block(src, "int wait_inner(uint64_t f, uint64_t timeout_ns) {", "gpu/vk/vk_replay.cpp")
    owe = wait.find("flush_owed.owe(f")
    if owe < 0:
        problems.append("wait() owes nothing (flush_owed.owe(f, ...)) before its send")
    else:
        line = wait[wait.rfind("\n", 0, owe) + 1:wait.find("\n", owe)]
        if "if (timeout_ns)" not in line:
            problems.append("wait() owes for a poll too (not under if (timeout_ns)): %s" % line.strip())
        if "timeline_sent" not in line:
            problems.append("wait() owes what is already sent (no timeline_sent): %s" % line.strip())
        if owe > find(wait, "queue_flush_for(FR_WAIT", "wait_inner() in gpu/vk/vk_replay.cpp", unique=False):
            problems.append("wait() owes after its first send: a submit held between the two is not sent")

    for name, start, end in (("submit_recording", "void submit_recording(Recording& r", "return;"),
                             ("part_submit", "void part_submit(const PartSubmit& s) {", "} else {")):
        submit = block(src, start, "gpu/vk/vk_replay.cpp")
        held = find(submit, "pend_held.store(true", name + " in gpu/vk/vk_replay.cpp")
        signal = find(submit, "pend.signal = std::max(", name + " in gpu/vk/vk_replay.cpp")
        ret = submit.find(end, held)
        due = submit.find("flush_owed.due(pend.signal)")
        if due < 0:
            problems.append("%s's batch branch does not ask flush_owed.due(pend.signal)" % name)
            continue
        line = submit[submit.rfind("\n", 0, due) + 1:submit.find("\n", due)]
        if "queue_flush_locked()" not in line:
            problems.append("%s asks due and sends nothing: %s" % (name, line.strip()))
        if not held < due:
            problems.append("%s asks due before pend_held is raised" % name)
        if not signal < due:
            problems.append("%s asks due before pend.signal holds this submit's value" % name)
        if ret < 0 or due > ret:
            problems.append("%s asks due outside its batch branch (after its %s)" % (name, end))

    flush = block(src, "void queue_flush_locked() {", "gpu/vk/vk_replay.cpp")
    met = flush.find("flush_owed.met(pend.signal)")
    if met < 0:
        problems.append("queue_flush_locked does not clear what it sent (flush_owed.met(pend.signal))")
    else:
        line = flush[flush.rfind("\n", 0, met) + 1:flush.find("\n", met)]
        if "res == VK_SUCCESS" not in line or "pend.any_signal" not in line:
            problems.append("queue_flush_locked clears the owed value for a send that failed or signalled nothing: %s"
                            % line.strip())
        if met < find(flush, "submit_or_retry(si", "queue_flush_locked in gpu/vk/vk_replay.cpp"):
            problems.append("queue_flush_locked clears the owed value before it sends")
        if met > find(flush, "pend.cbs.clear()", "queue_flush_locked in gpu/vk/vk_replay.cpp"):
            problems.append("queue_flush_locked clears the owed value after pend.signal is reset")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()

    problems = text_checks((ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8"))
    for p in problems:
        print("FAIL: vk_replay.cpp: " + p)

    with tempfile.TemporaryDirectory(prefix="flush-owed-") as tmp:
        folder = Path(tmp)
        cpp, exe = folder / "model.cpp", folder / "model.exe"
        cpp.write_text(MODEL, encoding="utf-8")
        inc = str(ROOT / "gpu" / "vk")
        if Path(args.cxx).name.lower() in ("cl", "cl.exe", "clang-cl", "clang-cl.exe"):
            command = [args.cxx, "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2", "/I" + inc, str(cpp), "/Fe:" + str(exe)]
        else:
            command = [args.cxx, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "-I" + inc, str(cpp), "-o",
                       str(exe)]
        subprocess.run(command, cwd=folder, check=True)
        ran = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True, timeout=120)
        print(ran.stdout, end="")
        if ran.returncode:
            problems.append("the model")
    if problems:
        raise SystemExit("test_flush_owed: %d failed" % len(problems))
    print("test_flush_owed: ok")


if __name__ == "__main__":
    main()
