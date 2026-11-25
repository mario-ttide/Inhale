// SPDX-License-Identifier: GPL-3.0-or-later
// Encoding reference: Mesa NAK sm70_encode.rs (MIT), Copyright 2022 Collabora, Ltd. (OUT; the others read from the game's code)
#pragma once
// The geometry stage's instructions for lower_to_maxwell.h, which includes this after its Instruction and calls it
// where it had no case. A file of this fork: upstream's lowering has no geometry stage.
//
// Kirby and the Forgotten Land's 15 geometry codes (six mouthful forms and the stage decorations) all have one shape:
//
//     LEPC R0; R0:R1 += <the handler's offset>; BMOV.64 <at exit>, R0     an EXIT then goes through the handler
//     S2R R0, SR_INVOCATION_INFO; ...; ISBERD Rn, [Rv] (x3)                each input vertex's handle from its number
//     ALD Rd, a[...], Rn; AST a[...], Rs; OUT R0, R0, RZ (emit, x3); OUT (cut); EXIT
//     handler: OUT RZ, R0, RZ (neither emit nor cut: the stream's end); 0x957 (the at-exit register cleared); EXIT
//
// The lowering stops at the main code's EXIT, so the handler is never lowered. It only ends the output stream, which
// SPIR-V does by itself: setting it is lowered to nothing, and only where the handler is that plain one. LEPC's value
// (its own address) goes nowhere else, so it is 0. A vertex's handle is its number, as Eden's Maxwell ISBERD has it
// (ALD's vertex operand is then gl_in's index). The names LEPC and BMOV.64 are this reading's, not a reference's.

#include <span>
#include <vector>
#include "common/common_types.h"

namespace Shader::Ampere {

/// Whether every at-exit handler of the code is "OUT (the stream's end); 0x957; EXIT", and there is one
inline bool GeometryPlainAtExit(std::span<const Instruction> code) {
    bool found = false;
    for (size_t i = 0; i < code.size(); ++i) {
        if (code[i].Bits(0, 12) != 0x957) continue;
        if (i == 0 || i + 1 >= code.size()) return false;
        const Instruction& out = code[i - 1];
        const Instruction& exit = code[i + 1];
        if (out.Bits(0, 16) != 0x7324 || out.Bits(78, 2) != 0 || out.Bits(16, 8) != 255) return false;
        if (exit.Bits(0, 16) != 0x794d || exit.Bits(84, 2) != 0 || exit.Bits(87, 4) != 7) return false;
        found = true;
    }
    return found;
}

/// The Maxwell words of the geometry instruction at index, appended to out: true when it is one of them and lowered
inline bool LowerGeometry(std::span<const Instruction> code, u32 index, u64 predicate, std::vector<u64>& out) {
    const Instruction& insn = code[index];
    const u64 dest = insn.Bits(16, 8);
    switch (insn.Bits(0, 12)) {
    case 0x34e: // LEPC Rd
        if (insn.words[1] || insn.words[2] || dest == 255) return false;
        out.push_back(0x0100000000000000ULL | predicate | dest | (u64{15} << 12));   // MOV32I Rd, 0
        return true;
    case 0x357: // BMOV.64 <at exit>, Ra
        return !insn.words[1] && !insn.words[2] && GeometryPlainAtExit(code);
    case 0x923: // ISBERD Rd, [Ra]: the map region, no offset (the task and mesh forms read .ATTR)
        if (insn.words[1] || insn.words[2] || dest == 255) return false;
        out.push_back(0xefd0000000000000ULL | predicate | dest | (u64{insn.Bits(24, 8)} << 8));
        return true;
    case 0x324: { // OUT Rd, Ra, Rb: 78-79 = 1 emit, 2 cut, 3 both; Rb the stream, only RZ (stream 0)
        const u32 type = insn.Bits(78, 2);
        if (!type || insn.Bits(32, 8) != 255 || dest == 255 || (insn.words[2] & ~0xc000U)) return false;
        out.push_back(0xf6e0000000000000ULL | predicate | dest | (u64{insn.Bits(24, 8)} << 8) |
                      (u64{type & 1} << 39) | (u64{type >> 1} << 40));   // OUT (imm), stream 0
        return true;
    }
    default:
        return false;
    }
}

} // namespace Shader::Ampere
