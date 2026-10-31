#!/usr/bin/env python3
"""vm_disasm.py — disassembler bytecode VM SAP.

Pakai instruction-length table (dari trace) untuk memecah bytecode `ac`
jadi instruction list: [opcode, operands...].

Verifikasi: disasm harus "pas" (total length == bytecode length) dan
semua opcode valid.
"""
import json, os, sys

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))

def load_lengths(f=None):
    f = f or f"{ROOT}/vm_opcode_lengths.json"
    d = json.load(open(f))
    # buang yang negatif (jump opcodes) — fallback len 2
    return {int(k): (v if v > 0 else 2) for k, v in d.items()}

def disasm(bc, lengths, start=0, max_ins=200):
    """Decode bytecode jadi [ (pc, opcode, [operands...]) ]."""
    ins = []
    pc = start
    n = len(bc)
    while pc < n and len(ins) < max_ins:
        op = bc[pc]
        L = lengths.get(op)
        if L is None:
            # opcode tak dikenal → assume len 2, mark
            ins.append((pc, op, [bc[pc+1] if pc+1<n else None]))
            pc += 2
            continue
        operands = [bc[pc+i] for i in range(1, L)]
        ins.append((pc, op, operands))
        pc += L
    return ins, pc

def main():
    lengths = load_lengths()
    print(f"instruction-length table: {len(lengths)} opcodes")
    bc = json.load(open(f"{ROOT}/vm_bytecode_snapshot.json"))
    print(f"bytecode: {len(bc)} slots\n")
    ins, endpc = disasm(bc, lengths, 0, 120)
    print(f"=== disassembly (first {len(ins)} instr, ended at pc={endpc}) ===")
    for row in ins[:60]:
        pc, op, ops = row[0], row[1], row[2]
        ops_s = ",".join(str(o) for o in ops)
        print(f"  {pc:5}: op{op:<4} [{ops_s}]")
    # statistik
    from collections import Counter
    known = sum(1 for row in ins if row[1] in lengths)
    print(f"\nknown opcodes: {known}/{len(ins)}")
    opc = Counter(row[1] for row in ins)
    print(f"histogram: {opc.most_common(15)}")

if __name__ == "__main__":
    main()
