/* (inhale) SDK functions Kirby and the Forgotten Land (Switch 2 Edition, SDK 19.3.7) calls that the runtime taken from
   upstream leaves to the lifted SDK, where they end in a system service this runtime does not have. Each note says what the
   lifted function did and where the game calls it from. Nothing here reads a guest address of the game's own: these are SDK
   names, found at lift time (nx2/standalone.py), so they need no build id gate. */
#include "hos.h"

void imp__ZN2nn2os19GenerateRandomBytesEPvm(Ctx *c);   /* nn_os_sync.c */

/* nn::crypto::GenerateCryptographicallyRandomBytes(void*, unsigned long): the lifted one opens the csrng service through
   sm:, gets an empty answer and aborts. First reached from a static initializer of main (std::random_device through musl's
   getentropy), before nnMain. The bytes are nn::os::GenerateRandomBytes': not secret ones, which nothing offline needs, and
   the same every run, which keeps two runs comparable. */
HLE(_ZN2nn6crypto36GenerateCryptographicallyRandomBytesEPvm) {
    imp__ZN2nn2os19GenerateRandomBytesEPvm(c);
}

/* ---- nn::audio: names of SDK 19 that the audio renderer in nn_audio.c has under SDK 22's ------------------------------ */
void imp__ZN2nn5audio16AcquireVoiceSlotEPNS0_19AudioRendererConfigEPNS0_9VoiceTypeEiiNS0_12SampleFormatEiPKvmPKNS3_15BehaviorOptionsE(Ctx *c);
void imp__ZN2nn5audio29SetVoiceBiquadFilterParameterEPNS0_9VoiceTypeEiRKNS0_21BiquadFilterParameterE(Ctx *c);

/* nn::audio::IsValidAudioRendererParameter(AudioRendererParameter const&) -> bool: the stub's 0 made the game abort before
   it opened its renderer (lr main+0x567f38). The renderer here takes any parameter. */
HLE(_ZN2nn5audio29IsValidAudioRendererParameterERKNS0_22AudioRendererParameterE) { RET(1); }

/* nn::audio::AcquireVoiceSlot without SDK 22's last argument (BehaviorOptions const*), which nn_audio.c does not read */
HLE(_ZN2nn5audio16AcquireVoiceSlotEPNS0_19AudioRendererConfigEPNS0_9VoiceTypeEiiNS0_12SampleFormatEiPKvm) {
    imp__ZN2nn5audio16AcquireVoiceSlotEPNS0_19AudioRendererConfigEPNS0_9VoiceTypeEiiNS0_12SampleFormatEiPKvmPKNS3_15BehaviorOptionsE(c);
}

/* nn::audio::SetVoiceBiquadFilterParameter with TBiquadFilterParameter<short>: the layout nn_audio.c reads as
   BiquadFilterParameter (bool at 0, int16 numerator[3] at 2, int16 denominator[2] at 8, Q14) */
HLE(_ZN2nn5audio29SetVoiceBiquadFilterParameterEPNS0_9VoiceTypeEiRKNS0_22TBiquadFilterParameterIsEE) {
    imp__ZN2nn5audio29SetVoiceBiquadFilterParameterEPNS0_9VoiceTypeEiRKNS0_21BiquadFilterParameterE(c);
}

/* ---- nn::hid ----------------------------------------------------------------------------------------------------------- */
void imp__ZN2nn3hid20GetTouchScreenStatesILm16EEEiPNS0_16TouchScreenStateIXT_EEEi(Ctx *c);   /* nn_hid.c */

/* nn::hid::GetTouchScreenState<16>(TouchScreenState<16>*): the newest state alone, no touches. The lifted one reads the
   touch screen's shared memory, which this runtime does not have, and aborts (the game's pad update, main+0x84c930). */
HLE(_ZN2nn3hid19GetTouchScreenStateILm16EEEvPNS0_16TouchScreenStateIXT_EEE) {
    c->x[1] = 1;   /* (the count of the plural form) */
    imp__ZN2nn3hid20GetTouchScreenStatesILm16EEEiPNS0_16TouchScreenStateIXT_EEEi(c);
}

/* nn::hid::GetNpadState(State*, unsigned const &id) for the five styles, and GetSixAxisSensorState(State*, Handle const&):
   the newest state alone. As stubs they left the game's state unwritten, and the game answered its own first dialogs with
   what its memory held (the pad update, main+0x84d354 and +0x84c5b8). The plural forms of nn_hid.c with a count of 1. */
void imp__ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj(Ctx *c);
void imp__ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE(Ctx *c);
static void newest_npad_state(Ctx *c) {
    c->x[2] = c->x[1];
    c->x[1] = 1;
    imp__ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj(c);   /* (one function for every style there) */
}
HLE(_ZN2nn3hid12GetNpadStateEPNS0_16NpadFullKeyStateERKj) { newest_npad_state(c); }
HLE(_ZN2nn3hid12GetNpadStateEPNS0_17NpadHandheldStateERKj) { newest_npad_state(c); }
HLE(_ZN2nn3hid12GetNpadStateEPNS0_16NpadJoyDualStateERKj) { newest_npad_state(c); }
HLE(_ZN2nn3hid12GetNpadStateEPNS0_16NpadJoyLeftStateERKj) { newest_npad_state(c); }
HLE(_ZN2nn3hid12GetNpadStateEPNS0_17NpadJoyRightStateERKj) { newest_npad_state(c); }
HLE(_ZN2nn3hid21GetSixAxisSensorStateEPNS0_18SixAxisSensorStateERKNS0_19SixAxisSensorHandleE) {
    c->x[2] = c->x[1];
    c->x[1] = 1;
    imp__ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE(c);
}

/* ---- nn::pl ------------------------------------------------------------------------------------------------------------ */
/* nn::pl::GetBuiltInFontDataSet(int *count, BuiltInFontDataOunce *out, const BuiltInFontTypeOunce *types, int n,
   nn::settings::LanguageCode, bool) -> bool: the console's own fonts, which the game's boot (main+0x65b460) asks for
   every 100 ms until the answer is true, before it draws anything. The lifted one asks a system service this runtime does
   not have. BuiltInFontDataOunce is 0x18 bytes (read from the lifted sdk, +0x4fc650): the type in byte 0, a flag in byte 1,
   the TrueType data's address at 8 and its size at 16; the game hands those two to its font texture cache. Every type gets
   the bundled Libertinus Sans (nx2/ui_fonts.py; nx2/build.py compiles it into the program): Latin, Greek and Cyrillic, no
   CJK and none of the console's button glyphs. The game draws its texts with fonts of its own. */
extern const unsigned char inhale_font_body[];
extern const unsigned inhale_font_body_size;
HLE(_ZN2nn2pl21GetBuiltInFontDataSetEPiPNS0_20BuiltInFontDataOunceEPKNS0_20BuiltInFontTypeOunceEiNS_8settings12LanguageCodeEb) {
    static uint64_t font;
    const uint64_t size = inhale_font_body_size;
    if (!font) {
        const uint64_t at = hos_sys_alloc(size, 0x1000);
        hos_guest_copy(at, inhale_font_body, size);
        font = at;
    }
    const int n = (int)ARG(3) < 6 ? (int)ARG(3) : 6;
    for (int i = 0; i < n; i++) {
        const uint64_t e = ARG(1) + 0x18 * (uint64_t)i;
        *(uint8_t *)GP(e) = *(uint8_t *)GP(ARG(2) + (uint64_t)i);
        *(uint8_t *)GP(e + 1) = 0;
        G64(e + 8) = font;
        G64(e + 16) = size;
    }
    G32(ARG(0)) = (uint32_t)n;
    RET(1);
}

/* ---- nn::fs ------------------------------------------------------------------------------------------------------------ */
/* nn::fs::CommitSaveData(char const*) -> Result: SDK 19's name of nn::fs::Commit. The lifted one finds no file system of
   its own for "save" and aborts (the game's first save, main+0x8b999c). Since the upstream v3.1.1 sync nn_fs.c stages a
   save: the game writes into <user>/save-work/<uid>, Commit publishes that into <user>/save/<uid>, and each mount starts
   the work copy again from save/<uid>. So this is Commit, and its result (0, or 0x2EE202 when publishing failed). Answering
   0 alone, as when files were written in place, published nothing: every start lost the last one's progress (#24). */
void imp__ZN2nn2fs6CommitEPKc(Ctx *c);   /* nn_fs.c */
HLE(_ZN2nn2fs14CommitSaveDataEPKc) { imp__ZN2nn2fs6CommitEPKc(c); }

/* ---- nn::codec: the VP9 decoder's names of SDK 19, on nn_video.c's functions (which have SDK 22's) --------------------- */
/* The game's movie player (main+0x4374xx to +0x437fxx; the opening movie is the first) demuxes WebM with the lifted
   nn::movie::MediaExtractor and decodes through these. As stubs they left the decoder unmade, and the first
   AcquireVp9DecoderOutputBuffer answered an error the game aborts on. */
void imp__ZN2nn5codec25MakeDecodeImagePreferenceEttNS0_24VideoDecoderOutputFormatENS0_15ImageTilingModeE(Ctx *c);
void imp__ZN2nn5codec26InitializeDecoderImagePoolEPNS0_25VideoDecoderImagePoolTypeEPvmRKNS0_27VideoDecoderImagePreferenceEj(Ctx *c);
void imp__ZN2nn5codec36InitializeVp9DecoderByTransferMemoryEPNS0_14Vp9DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE(Ctx *c);
void imp__ZN2nn5codec33GetVp9DecoderSubmissionReadyEventEPNS0_14Vp9DecoderTypeE(Ctx *c);
void imp__ZN2nn5codec35GetVp9DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_8TimeSpanEPbPNS0_14Vp9DecoderTypeEj(Ctx *c);

/* MakeDecodeImagePreference(u16 w, u16 h, OutputFormat, CodecMode): the last argument was ImageTilingMode; kept as it is */
HLE(_ZN2nn5codec25MakeDecodeImagePreferenceEttNS0_24VideoDecoderOutputFormatENS0_9CodecModeE) {
    imp__ZN2nn5codec25MakeDecodeImagePreferenceEttNS0_24VideoDecoderOutputFormatENS0_15ImageTilingModeE(c);
}
/* InitializeDecoderImagePool(pool, memory, size, Preference const&, u32 count, CodecMode): one argument more, not read */
HLE(_ZN2nn5codec26InitializeDecoderImagePoolEPNS0_25VideoDecoderImagePoolTypeEPvmRKNS0_27VideoDecoderImagePreferenceEjNS0_9CodecModeE) {
    imp__ZN2nn5codec26InitializeDecoderImagePoolEPNS0_25VideoDecoderImagePoolTypeEPvmRKNS0_27VideoDecoderImagePreferenceEj(c);
}
/* CalculateVp9DecoderWorkBuffer(u64 *size, u64 *alignment, u64, u16 w, u16 h) -> Result: the decoder here is libavcodec's
   and uses none of the game's memory; a page, so that the game's allocation is a real one */
HLE(_ZN2nn5codec29CalculateVp9DecoderWorkBufferEPmS1_mtt) {
    if (ARG(0)) G64(ARG(0)) = 0x1000;
    if (ARG(1)) G64(ARG(1)) = 0x1000;
    RET(0);
}
/* InitializeVp9Decoder(decoder, work memory, size, u64, u16 w, u16 h, u32, InputFormat, OutputFormat): SDK 22's
   ...ByTransferMemory without its last argument (the output mode), which nn_video.c does not read */
HLE(_ZN2nn5codec20InitializeVp9DecoderEPNS0_14Vp9DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE) {
    imp__ZN2nn5codec36InitializeVp9DecoderByTransferMemoryEPNS0_14Vp9DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE(c);
}
/* GetVp9DecoderSubmissionReadyEvent(SystemEventType **out, decoder) -> Result: SDK 22 returns the event */
HLE(_ZN2nn5codec33GetVp9DecoderSubmissionReadyEventEPPNS_2os15SystemEventTypeEPNS0_14Vp9DecoderTypeE) {
    const uint64_t out = ARG(0);
    c->x[0] = c->x[1];
    imp__ZN2nn5codec33GetVp9DecoderSubmissionReadyEventEPNS0_14Vp9DecoderTypeE(c);
    if (out) G64(out) = c->x[0];
    RET(0);
}
/* GetVp9DecoderOutputBufferProperties(u16 *w, u16 *h, u16 *display w, u16 *display h, nn::movie::ColorSpace*, TimeSpan *pts,
   bool *last, decoder, u32 index): SDK 22's has no colour space, so its last four arguments are one place later here and
   the index is on the stack. The colour space is left as the game set it. */
HLE(_ZN2nn5codec35GetVp9DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_5movie10ColorSpaceEPNS_8TimeSpanEPbPNS0_14Vp9DecoderTypeEj) {
    c->x[4] = c->x[5];
    c->x[5] = c->x[6];
    c->x[6] = c->x[7];
    c->x[7] = G32(c->x[31]);
    imp__ZN2nn5codec35GetVp9DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_8TimeSpanEPbPNS0_14Vp9DecoderTypeEj(c);
}
