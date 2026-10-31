#!/usr/bin/env python3
"""vm_decompile.py — decompile bytecode VM → pseudo-code.

Berdasarkan:
  - vm_code_disasm.txt (1045 instr code section)
  - vm_opcode_lengths.json (operand count per opcode)
  - trace operand observations

Output: pseudo-code listing yang bisa dibaca manusia.
"""
import json, os, re
ROOT = os.path.dirname(os.path.abspath(__file__))

def load_disasm(f=None):
    f = f or f"{ROOT}/vm_code_disasm.txt"
    ins = []
    for line in open(f):
        m = re.match(r"\s*(\d+):\s+op(\d+)\s+\[(.*)\]", line)
        if m:
            pc = int(m.group(1)); op = int(m.group(2))
            ops = [int(x) for x in m.group(3).split(",") if x.strip()]
            ins.append({"pc": pc, "op": op, "ops": ops})
    return ins

# Placeholder semantics (dari analisis + trace) — diisi bertahap
OP_SEMANTICS = {
    469: ("STORE", "slot[ops[0]] = ops[1]"),
    901: ("PUSH", "push(ops[0], ops[1], ops[2])"),
    765: ("DISPATCH", "block_end / jump ops[1]"),
    370: ("CALL", "call(ops[0], ops[1], ops[2])"),
    94:  ("BINOP", "r = combine(ops[0..3])"),
    878: ("LOAD", "slot[ops[0]] -> ops[1]"),
    1:   ("ELEM", "elem op (ops[0])"),
    477: ("MOV", "move ops[0] -> ops[1]"),
    394: ("CONST", "const op[ops[0]]"),
    868: ("REF", "ref ops[0]"),
    459: ("CALL_EXT", "external call"),
    128: ("BIGOP", "10-operand op"),
    62:  ("TEST", "test ops[0]"),
    65:  ("OP2", "op ops[0],ops[1]"),
    24:  ("OP2b", "op ops[0],ops[1]"),
    179: ("OP2c", "op ops[0],ops[1]"),
    33:  ("NOP", ""),
    605: ("NOP2", ""),
    281: ("INIT", "init[ops[0]] @ops[1]"),
    965: ("OP2d", ""),
    861: ("OP3", ""),
    694: ("OP3b", ""),
    823: ("OP3c", ""),
    481: ("OP3d", ""),
}

def decompile(ins):
    out = []
    for i in ins:
        sem = OP_SEMANTICS.get(i["op"])
        ops_s = ",".join(str(o) for o in i["ops"])
        if sem:
            name, tmpl = sem
            out.append(f"{i['pc']:5}  {name:10} ; op{i['op']} [{ops_s}]")
        else:
            out.append(f"{i['pc']:5}  {'?':10} ; op{i['op']} [{ops_s}]")
    return out

def main():
    ins = load_disasm()
    print(f"loaded {len(ins)} instructions\n")
    dec = decompile(ins)
    open(f"{ROOT}/vm_pseudo.txt", "w").write("\n".join(dec))
    print(f"saved vm_pseudo.txt ({len(dec)} lines)\n")
    print("=== first 50 ===")
    for l in dec[:50]: print(l)

if __name__ == "__main__":
    main()
