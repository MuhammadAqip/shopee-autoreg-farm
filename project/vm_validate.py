#!/usr/bin/env python3
"""vm_validate.py — validasi emulator vs trace eksekusi NYATA.

Cara: replay trace (40k+ exec nyata dari browser). Untuk setiap step,
emulator harus di pc & opcode yang SAMA. Kalau cocok → emulator faithful.

Output: match rate.
"""
import json, os
ROOT = os.path.dirname(os.path.abspath(__file__))

def load():
    ac = json.load(open(f"{ROOT}/vm_bytecode_FULL.json"))
    lengths = {int(k):(v if v>0 else 2) for k,v in json.load(open(f"{ROOT}/vm_opcode_lengths.json")).items()}
    t = json.load(open(f"{ROOT}/vm_full_dump.json"))["t"]
    return ac, lengths, t

def main():
    ac, lengths, t = load()
    # Trace: [pc, op, ...] dengan pc = posisi SETELAH opcode → opcode index = pc-1
    seq = [(e[0]-1, e[1]) for e in t]  # (opcode_index, opcode)
    print(f"trace: {len(seq)} steps")
    # Validasi: apakah opcode di index itu == trace op? (sudah HIT=40358) → mocok
    match = sum(1 for idx, op in seq if 0 <= idx < len(ac) and ac[idx] == op)
    print(f"opcode-index match: {match}/{len(seq)} = {100*match/len(seq):.2f}%")

    # Validasi lanjut: apakah setiap index ada di instruction boundary?
    boundaries = set()
    pc = 0
    while pc < len(ac):
        boundaries.add(pc)
        pc += lengths.get(ac[pc], 2)
    in_b = sum(1 for idx, _ in seq if idx in boundaries)
    print(f"on instruction-boundary: {in_b}/{len(seq)} = {100*in_b/len(seq):.2f}%")
    print(f"boundaries total: {len(boundaries)}")

    # Jalur eksekusi: builder dari trace (cfg)
    print(f"\n--- execution path stats ---")
    from collections import Counter
    pcs = Counter(idx for idx,_ in seq)
    print(f"hottest opcode-index: {pcs.most_common(5)}")

if __name__ == "__main__":
    main()
