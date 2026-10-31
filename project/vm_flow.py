#!/usr/bin/env python3
"""vm_flow.py — rekonstruksi control flow dari trace eksekusi nyata.

Karena disasm terverifikasi (HIT=40358, MISS=0), trace = urutan eksekusi asli.
Dari sini: 
  1. explosive instruction sequence per eksekusi
  2. detect fungsi (blok antar jump besar)
  3. DWARF: petakan 163 modul ke rentang pc
  4. output: annotated execution trace
"""
import json, os
ROOT = os.path.dirname(os.path.abspath(__file__))

def load():
    ac = json.load(open(f"{ROOT}/vm_bytecode_FULL.json"))
    lengths = {int(k):(v if v>0 else 2) for k,v in json.load(open(f"{ROOT}/vm_opcode_lengths.json")).items()}
    t = json.load(open(f"{ROOT}/vm_full_dump.json"))["t"]
    return ac, lengths, t

def build_boundary_map(ac, lengths, end=70943):
    pc2op = {}
    pc = 0
    while pc < end:
        op = ac[pc]; pc2op[pc] = op
        pc += lengths.get(op, 2)
    return pc2op

def main():
    ac, lengths, t = load()
    bmap = build_boundary_map(ac, lengths)
    # Trace jadi sequence: (pc_idx=pc-1, op)
    seq = [(e[0]-1, e[1]) for e in t]
    # Detect fn entries: pc sebelumnya >2000, pc baru <2000 (call into code)
    fns = []
    for i in range(1, len(seq)):
        if seq[i-1][0] > 3000 and seq[i][0] < 3000:
            fns.append(seq[i][0])
    from collections import Counter, OrderedDict
    fn_calls = OrderedDict()
    for f in fns:
        fn_calls[f] = fn_calls.get(f, 0) + 1
    print(f"trace: {len(seq)} exec steps")
    print(f"boundaries: {len(bmap)} instructions in code section")
    print(f"function entries (jump>3000 -> <3000): {len(fn_calls)}")
    for f, n in list(fn_calls.items())[:25]:
        op = bmap.get(f, "?")
        print(f"  fn@{f:5} (op{op}) called {n}×")
    # Simpan annotated trace
    with open(f"{ROOT}/vm_flow.txt", "w") as fh:
        for (idx, op) in seq[:5000]:
            fh.write(f"{idx:5}: op{op}\n")
    print(f"\nsaved vm_flow.txt")
    json.dump({"fn_entries": {str(k): v for k, v in fn_calls.items()}},
              open(f"{ROOT}/vm_functions.json", "w"), indent=1)
    print(f"saved vm_functions.json ({len(fn_calls)} full count)")

if __name__ == "__main__":
    main()
