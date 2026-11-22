/* Which Inhale this is (nx2/version.py: the release and a fingerprint of the sources), for the log's first line, the
   control bridge, the Discord status and the crash record. nx2/build.py gives INHALE_VERSION to this file alone: the
   fingerprint changes with every source, and a new one then compiles this one small file, not hos_main.c. */
#ifndef INHALE_VERSION
#define INHALE_VERSION "unknown"
#endif

const char *hos_version(void) { return INHALE_VERSION; }
