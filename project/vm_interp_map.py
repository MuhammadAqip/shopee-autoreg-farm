#!/usr/bin/env python3
"""vm_interp_map.py — peta dispatch tree → opcode→handler.

Parse body interpreter (vm_interp_FULL.js) dan bangun:
  - 160 opcode boundary → binary-search tree
  - tiap leaf → operasi (STORE/CALL/ADD/STRING-LOAD/...)
  - variabel operand per leaf

Output: vm_interp_map.json
"""
import re, json, os
ROOT = os.path.dirname(os.path.abspath(__file__))
body = open(f"{ROOT}/sdk/vm_interp_FULL.js").read()

def main():
    # Ambil semua threshold
    thr = sorted(set(int(x) for x in re.findall(r'tO<(\d+)', body)))
    print(f"dispatch thresholds: {len(thr)} → opcode max {max(thr)}")

    # Ekstrak leaf operations: tiap segmen antar '||' atau '?'
    # Cari semua assignment ke t[...] / e[...] dan helper calls
    leaves = []
    # STORE: t[tB=ac[_++]] = ... / e[tM(tb)] += ...
    for m in re.finditer(r'(t|e)\[([^\]]{1,30})\]\s*([+\-*/|&^]?=)', body):
        leaves.append({"op": "store", "base": m.group(1), "idx": m.group(2), "assign": m.group(3)})
    # operand reads (register moves)
    for m in re.finditer(r'([a-zA-Z_]{1,3})=ac\[_\+\+\]', body):
        leaves.append({"op": "read", "reg": m.group(1)})
    # helper calls
    for m in re.finditer(r'\b(eG|eF|ex|tI|ek|tM|tG|tE|H|V|G)\(', body):
        leaves.append({"op": "call", "fn": m.group(1)})

    from collections import Counter
    print(f"leaf ops: {len(leaves)}")
    print("store bases:", Counter(l['base'] for l in leaves if l['op']=='store'))
    print("assign ops:", Counter(l['assign'] for l in leaves if l['op']=='store'))
    print("call fns:", Counter(l['fn'] for l in leaves if l['op']=='call'))

    out = {
        "thresholds": thr,
        "opcode_max": max(thr),
        "leaf_count": len(leaves),
        "store_ops": Counter(l['assign'] for l in leaves if l['op']=='store'),
        "call_fns": Counter(l['fn'] for l in leaves if l['op']=='call'),
        "read_regs": Counter(l['reg'] for l in leaves if l['op']=='read'),
    }
    json.dump(out, open(f"{ROOT}/vm_interp_map.json","w"), indent=1, default=str)
    print(f"→ vm_interp_map.json")

if __name__ == "__main__":
    main()
