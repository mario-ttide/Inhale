// Which Inhale this is (nx2/version.py: the release and a fingerprint of the sources), for the Insert menu, the start-up
// screen and a bug report. nx2/build.py gives INHALE_VERSION to this file alone: the fingerprint changes with every
// source, and a new one then compiles this one small file, not vk_menu.cpp.
#ifndef INHALE_VERSION
#define INHALE_VERSION "unknown"
#endif

const char* mkwvk_version() { return INHALE_VERSION; }
