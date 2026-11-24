#pragma once
// (inhale) A host-memory import does not pay a walk over the game's memory. Windows answers a question about an address's
// region (VirtualQuery) by walking page by page from that address to the end of the run of pages with the same state and
// protection, and the driver's vkAllocateMemory for a host pointer asks it: all of an import's time is that call (the log's
// "vk: import N ms: ... allocate N"). This game's pools in play lie in long runs of committed read-write pages: on aubox's
// RTX 2080 SUPER and Radeon 780M, Windows, each of the ~115 imports of a 100 s walk took 20-36 ms, whatever its size (4 MB
// or 64 MB), on the thread that replays the frame: every frame over 40 ms of the walk was one. Linux has no such walk
// (the RX 7900 XTX's imports take under 2 ms).
//
// Which call asks is the driver's choice, so the fence stands for both of a host pointer's (import_pool, vk_memory.cpp): from
// before vkGetMemoryHostPointerPropertiesEXT until the import returns, vkAllocateMemory between them. AMD's Windows driver
// for the RX 7900 XTX (26.10.1, 26.11.2) walks in the first: with the fence around the allocation alone, as it was until
// 2026-11-24, that call took 16 ms on average and up to 33 (the log's "commit+properties"), and 0.07 ms with it.
//
// While the driver is asked, the page after the range has another protection that reads and writes the same,
// PAGE_EXECUTE_READWRITE, so the run from the range's start ends with the range; then it has its own back. Only a
// committed PAGE_READWRITE page is changed: anything else (reserved, a write watch's read-only page) already ends the run.
// Nothing runs from guest memory, with the page's protection or without: the game's code is the lifted host code. A data
// fault pending on that page when another thread committed it is tried again by commit_on_touch (host/mkw_glue.c).
//
// Upstream's PR #334, not merged there (with its lazy heap upstream's game measured no gain): jarynclouatre's Hookshot
// PR 3043 (commit 771a9e46), re-sent by DUDUYG with the first-touch retry (76393403), GPL-3.0. Taken whole if upstream
// merges it: then delete this file and its lines marked (inhale) in vk_memory.cpp and mkw_glue.c.
#include <cstdint>
#ifndef __linux__
#include <windows.h>
#endif

namespace mkwvk {

class InhaleImportFence {
#ifndef __linux__
    void* page_ = nullptr;

public:
    /// The page after [ptr, ptr + bytes) ends the region that starts at ptr, until this goes out of scope
    InhaleImportFence(uint8_t* ptr, uint64_t bytes, bool on) {
        if (!on || !ptr || !bytes) return;
        void* const page = ptr + bytes;
        DWORD old = 0;
        if (!VirtualProtect(page, 1, PAGE_EXECUTE_READWRITE, &old)) return;   // (not committed, or refused: the import as before)
        if (old != PAGE_READWRITE) {   // (not ours to change)
            VirtualProtect(page, 1, old, &old);
            return;
        }
        page_ = page;
    }
    ~InhaleImportFence() {
        if (!page_) return;
        DWORD old = 0;
        // (changed by someone else meanwhile: theirs stands)
        if (VirtualProtect(page_, 1, PAGE_READWRITE, &old) && old != PAGE_EXECUTE_READWRITE) VirtualProtect(page_, 1, old, &old);
    }
    bool set() const { return page_ != nullptr; }
#else
public:
    // (Linux: no region walk; a pool is a dma-buf or a host pointer the kernel pins)
    InhaleImportFence(uint8_t*, uint64_t, bool) {}
    bool set() const { return false; }
#endif
    InhaleImportFence(const InhaleImportFence&) = delete;
    InhaleImportFence& operator=(const InhaleImportFence&) = delete;
};

}   // namespace mkwvk
