/* GetVoicePlayedSampleCount around the actual source bodies: authored wave buffers, the mixer's frames run by hand.
   No audio device or game is opened. tests/test_audio_voice_played_count.py */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t x[32]; } Ctx;
static _Alignas(8) uint8_t guest[4096];
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
#define CHECK_EQ(a, b) do { long long a_ = (long long)(a), b_ = (long long)(b); \
    if (a_ != b_) { fprintf(stderr, "FAIL:%d %s == %s (%lld, not %lld)\n", __LINE__, #a, #b, a_, b_); exit(1); } } while (0)
static void *guest_ptr(uint64_t address) { CHECK(address < sizeof guest); return guest + address; }
#define GP(a) guest_ptr(a)
static void *hos_guest_range(uint64_t a, uint64_t n) { return a < sizeof guest && n <= sizeof guest - a ? guest + a : NULL; }
#define G64(a) (*(uint64_t *)GP(a))
#define G32(a) (*(uint32_t *)GP(a))
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define HLE(sym) void imp_##sym(Ctx *c)
#define AUT(...) ((void)0)
static void hos_log(const char *format, ...) { (void)format; }
enum { AUDIO_SOURCE_NONE };
static int hos_pad_speaker_active(void) { return 0; }
static void hos_audio_source_load_async(void) {}
static int hos_audio_source_ready(void) { return 1; }
static int hos_audio_source_of(uint64_t data, uint32_t *crc) { (void)data, *crc = 0; return -1; }
static int hos_audio_source_trace(void) { return 0; }
static const char *hos_audio_source_name(int cls) { (void)cls; return ""; }
static int lock_depth;
static void au_lock(void) { CHECK(lock_depth++ == 0); }
static void au_unlock(void) { CHECK(--lock_depth == 0); }
static const char *fixture_getenv(const char *name) { (void)name; return NULL; }
#define getenv fixture_getenv
#define env_on(name) (getenv(name) && !env_value_off(getenv(name)))

#include "actual_audio_voice_played.inc"

#define APPEND imp__ZN2nn5audio16AppendWaveBufferEPNS0_9VoiceTypeEPKNS0_10WaveBufferE
#define STATE imp__ZN2nn5audio17SetVoicePlayStateEPNS0_9VoiceTypeENS1_9PlayStateE
#define PLAYED imp__ZN2nn5audio25GetVoicePlayedSampleCountEPKNS0_9VoiceTypeE

/* nn::audio::WaveBuffer structs (loop @0x18, isEndOfStream @0x19), PCM16 mono, LENGTH samples each */
enum { OBJECT = 0x40, PLAIN = 0x100, EOS = 0x140, LOOP_EOS = 0x180, SAMPLES = 0x400, LENGTH = 64 };
static uint64_t call(void (*hle)(Ctx *), uint64_t a0, uint64_t a1) {
    Ctx c = {0};
    c.x[0] = a0; c.x[1] = a1;
    hle(&c);
    CHECK(lock_depth == 0);
    return c.x[0];
}
static long long played(void) { return (long long)call(PLAYED, OBJECT, 0); }
static void wave_buffer(uint64_t p, int loop, int eos) {
    G64(p) = SAMPLES; G64(p + 8) = LENGTH * 2;
    G32(p + 0x10) = 0; G32(p + 0x14) = LENGTH;
    guest[p + 0x18] = (uint8_t)loop; guest[p + 0x19] = (uint8_t)eos;
}
static void reset(void) {
    memset(guest, 0, sizeof guest);
    memset(voices, 0, sizeof voices);
    ncmds = 0;
    wave_buffer(PLAIN, 0, 0);
    wave_buffer(EOS, 0, 1);
    wave_buffer(LOOP_EOS, 1, 1);
    voices[0].used = 1, voices[0].channels = 1, voices[0].format = FMT_PCM16, voices[0].rate = RATE;
    voices[0].state = voices[0].state_set = PLAY_STOPPED;
    put_handle(OBJECT, K_VOICE, 0);
}
static void append(uint64_t wb) { CHECK(call(APPEND, OBJECT, wb) == 1); }
static void frames(int n) { for (int i = 0; i < n; i++) CHECK(next_source_frame(&voices[0])); }

/* Buffers without the end-of-stream flag: the count runs on through them, as before. */
static void plain_buffers_keep_counting(void) {
    reset();
    append(PLAIN); append(PLAIN);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(LENGTH + 5);
    commit();
    CHECK_EQ(played(), LENGTH + 5);
}

/* A finished end-of-stream buffer starts the count again: the console's renderer does, and the sound engine adds the
   count to the start of the buffer it is on (0x805a2360 in this game). Every buffer it appends has the flag. */
static void end_of_stream_restarts_the_count(void) {
    reset();
    append(EOS); append(EOS); append(EOS);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(LENGTH - 4);
    commit();
    CHECK_EQ(played(), LENGTH - 4);
    frames(4 + 5);   /* the first one finished, 5 into the second */
    commit();
    CHECK_EQ(played(), 5);
    frames(LENGTH - 5 + 7);
    commit();
    CHECK_EQ(played(), 7);
}

/* The count the game reads is the one of the last update, as the released buffers are: never a buffer finished (and
   its count restarted) by the mixer before the game has seen that buffer released. */
static void count_as_of_the_last_update(void) {
    reset();
    append(EOS); append(EOS);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(LENGTH - 2);
    commit();
    CHECK_EQ(played(), LENGTH - 2);
    frames(2 + 3);   /* the mixer finishes the first buffer between two updates */
    CHECK_EQ(played(), LENGTH - 2);
    commit();
    CHECK_EQ(played(), 3);
}

/* A looping buffer never finishes: its count runs on past its length (the engine takes it modulo the loop). */
static void looping_buffer_keeps_counting(void) {
    reset();
    append(LOOP_EOS);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(2 * LENGTH + 3);
    commit();
    CHECK_EQ(played(), 2 * LENGTH + 3);
}

/* Stop starts the count again, and a voice started again counts from 0. */
static void stop_restarts_the_count(void) {
    reset();
    append(PLAIN); append(PLAIN);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(10);
    commit();
    CHECK_EQ(played(), 10);
    call(STATE, OBJECT, PLAY_STOPPED);
    commit();
    CHECK_EQ(played(), 0);
    append(PLAIN);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(3);
    commit();
    CHECK_EQ(played(), 3);
}

/* Pause keeps it. */
static void pause_keeps_the_count(void) {
    reset();
    append(PLAIN);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(10);
    call(STATE, OBJECT, PLAY_PAUSED);
    commit();
    CHECK_EQ(played(), 10);
    call(STATE, OBJECT, PLAY_STARTED);
    commit();
    frames(2);
    commit();
    CHECK_EQ(played(), 12);
}

int main(void) {
    plain_buffers_keep_counting();
    end_of_stream_restarts_the_count();
    count_as_of_the_last_update();
    looping_buffer_keeps_counting();
    stop_restarts_the_count();
    pause_keeps_the_count();
    free(cmds);
    puts("PASS: actual voice calls: the played sample count restarts at Stop and after an end-of-stream buffer, as of the update");
    return 0;
}
