#!/usr/bin/env python3
"""vm_emulator.py — emulator bytecode VM SAP (skeleton + dispatch table).

Dibangun dari:
  - interpreter body: sdk/vm_Z_full.txt (dispatch tree)
  - bytecode snapshot: vm_bytecode_snapshot.json (ac[0:6000])
  - runtime trace: vm_patch_trace.json (200k opcode execs)

Tujuan: eksekusi bytecode VM di luar browser → petakan opcode → rekonstruksi
program signer. Ini melewati 'stop-line' (platform bilang multi-hari); kita
bangun bertahap dari bukti runtime.

Status: SKELETON + dispatch dict. Handler di-isi inkremental dari analisis opcode.
"""
import json, os, re, sys

ROOT = os.environ.get("SHOPEE_ROOT") or os.path.dirname(os.path.abspath(__file__))

# === 1. Dispatch boundaries (dari interpreter, urut binary-search) ===
DISPATCH_BOUNDS = [443, 188, 97, 48, 25, 23, 21, 2, 24, 35, 34, 28, 36, 83, 66, 64, 63, 76,
                   90, 89, 88, 95, 141, 117, 111, 103, 100, 113, 130, 129, 127, 137, 175,
                   160, 157, 149, 163, 185, 180, 186, 346, 282, 213, 200, 199, 193, 202,
                   250, 241, 233, 266, 303, 293, 287, 285, 296, 318, 312, 304, 340]

# === 2. Opcode table (dari boundary → opcode ranges) ===
def opcode_boundaries():
    """Boundary terurut = batas opcode. Setiap opcode X memenuhi prev_bound <= X < bound."""
    b = sorted(set(DISPATCH_BOUNDS))
    return b

# === 3. Helper fn roles (dari analisis body) ===
HELPERS = {
    "tM": "read/coerce value (202x)",
    "tB": "operand fetch (188x)",
    "tG": "write var (102x)",
    "tE": "string-decode (47x)",
    "G":  "FNV-hash (98x) — 0xdeadbeef/0x41c6ce57 basis",
    "H":  "async device-info collector (30x)",
    "V":  "pako/zlib hash (31x)",
    "tP": "helper (13x)",
    "tU": "helper (4x)",
    "tX": "helper (6x)",
    "tY": "helper (4x)",
}

# === 4. Runtime opcode histogram (dari trace) ===
def opcode_histogram(trace_file=None):
    trace_file = trace_file or f"{ROOT}/vm_patch_trace.json"
    d = json.load(open(trace_file))
    t = d["t"] if isinstance(d, dict) else d
    from collections import Counter
    return Counter(x[1] for x in t), len(t)

# === 5. Bytecode loader ===
def load_bytecode(f=None):
    f = f or f"{ROOT}/vm_bytecode_snapshot.json"
    return json.load(open(f))

# === 6. Module entry table (dari trace: pc besar->kecil) ===
def module_entries(trace_file=None):
    trace_file = trace_file or f"{ROOT}/vm_patch_trace.json"
    d = json.load(open(trace_file)); t = d["t"] if isinstance(d, dict) else d
    entries = []
    for i in range(1, len(t)):
        if t[i-1][0] > 1000 and t[i][0] == 1:
            entries.append(t[i-1][0])
    return sorted(set(entries))

# === 7. Disassembler (opcode + operand decoding) ===
# Dari snapshot: [23, 57572, 67536, 70732, 63, 476, 693, 0, 199, 97, ...]
# Opcode = nilai; operand = nilai lanjutan. Encoding perlu di-reverse.
def disasm(bc, start=0, count=80):
    """Tampilkan bytecode mentah utk spot-check encoding."""
    return bc[start:start+count]

def main():
    print("=== VM EMULATOR — SAP bytecode ===\n")
    print(f"dispatch boundaries: {len(DISPATCH_BOUNDS)}")
    print(f"helpers: {list(HELPERS.keys())}")
    print()
    hist, n = opcode_histogram()
    print(f"trace: {n} execs, {len(hist)} unique opcodes")
    print(f"top: {hist.most_common(12)}")
    print()
    ent = module_entries()
    print(f"modules: {len(ent)} (entries {ent[:8]}...)")
    print()
    bc = load_bytecode()
    print(f"bytecode: {len(bc)} slots")
    print(f"first 40: {disasm(bc, 0, 40)}")
    print()
    # Cari pola op+operand: opcode biasanya < 1000, operand bisa besar
    print("=== candidate opcode encoding (pairs) ===")
    for i in range(0, 12, 2):
        print(f"  [{i}] op={bc[i] if i<len(bc) else '?'}  nxt={bc[i+1] if i+1<len(bc) else '?'}")

if __name__ == "__main__":
    main()
