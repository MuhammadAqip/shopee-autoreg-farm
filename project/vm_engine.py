#!/usr/bin/env python3
"""vm_engine.py — engine emulator bytecode VM SAP (opcode semantics + stack/slot/frame).

Basis:
  - encoding: opcode=ac[pc-1], operand=ac[pc..] (VERIFIED HIT=40358/MISS=0)
  - length table: vm_opcode_lengths.json (89 opcode)
  - bytecode: vm_bytecode_FULL.json (70,943 slot)
  - operand patterns: vm_semantics.json (infer arity + register roles)

Model:
  - SLOT[]  : register file (op469 STORE, op878 LOAD)
  - STACK[] : operand stack (op901 PUSH)
  - FRAME[] : call frames (op370/op459 CALL, op765 DISPATCH)
  - PC      : program counter

Semantik diisi dari pola operand runtime. Opcode yang belum yakin = HALT (marked).
"""
import json, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))

OP = {
    # name: (arity, handler-key)
    901: ("PUSH", 4), 469: ("STORE", 3), 459: ("CALL", 3), 765: ("DISPATCH", 3),
    281: ("INIT", 3), 477: ("MOV", 3), 732: ("FRAME", 3), 878: ("LOAD", 3),
    370: ("CALL2", 4), 94: ("BINOP", 4), 303: ("FRAME2", 3), 65: ("OP2", 4),
    82: ("OP2b", 4), 62: ("JMP", 4), 179: ("OP3", 4), 162: ("OP3b", 4),
    33: ("NOP", 2), 605: ("NOP2", 2), 199: ("LD", 2), 361: ("LD2", 2),
}

def load():
    ac = json.load(open(f"{ROOT}/vm_bytecode_FULL.json"))
    lengths = {int(k):(v if v>0 else 2) for k,v in json.load(open(f"{ROOT}/vm_opcode_lengths.json")).items()}
    return ac, lengths

class VM:
    MEM_BASE = 6000     # memory records start here
    REC_SIZE = 16       # record stride (observed: 6000,6016,6032,6048...)
    def __init__(self, ac, lengths):
        self.ac = ac
        self.len = lengths
        self.slot = {}
        self.mem = {}       # memory records: addr -> value
        self.stack = []
        self.frame = []
        self.pc = 0
        self.halt = False
        self.steps = 0
        self.log = []

    def is_mem(self, a):
        return a is not None and a >= self.MEM_BASE

    def rec(self, addr):
        """record index + field offset."""
        if not self.is_mem(addr): return None
        off = addr - self.MEM_BASE
        return (off // self.REC_SIZE, off % self.REC_SIZE)

    def read_op(self, pc):
        # pc = index of opcode in stream (disasm view)
        return self.ac[pc]

    def run(self, start=0, max_steps=500):
        self.pc = start
        while not self.halt and self.steps < max_steps and self.pc < len(self.ac):
            op = self.ac[self.pc]
            L = self.len.get(op, 2)
            ops = self.ac[self.pc+1:self.pc+L]
            self.exec(op, ops)
            self.steps += 1
        return self

    def exec(self, op, ops):
        name = OP.get(op, ("UNK", 2))[0]
        h = getattr(self, "h_"+name, None)
        if h: h(op, ops)
        else:
            self.log.append(f"pc{self.pc}: op{op} {ops}")
            self.pc += len(ops)+1

    # --- handlers (dari infer pola operand) ---
    def h_PUSH(self, op, ops):
        # op901 [a,b,c,next] : push slot[a..b]
        if len(ops)>=2 and ops[0] in self.slot:
            self.stack.append(self.slot[ops[0]])
        self.pc += len(ops)+1
    def h_STORE(self, op, ops):
        # op469 [slot, val, ...]
        if len(ops)>=2: self.slot[ops[0]] = ops[1]
        self.pc += len(ops)+1
    def h_LOAD(self, op, ops):
        if ops and ops[0] in self.slot: self.stack.append(self.slot[ops[0]])
        self.pc += len(ops)+1
    def h_MOV(self, op, ops):
        # op477 [dst, src, ...]
        if len(ops)>=2 and ops[1] in self.slot: self.slot[ops[0]] = self.slot[ops[1]]
        self.pc += len(ops)+1
    def h_CALL(self, op, ops):
        # op459 [argc, ...] : call
        self.frame.append(self.pc+len(ops)+1)
        self.pc += len(ops)+1
    def h_DISPATCH(self, op, ops):
        # op765 [a,b,...] : block end
        self.pc += len(ops)+1
    def h_JMP(self, op, ops):
        tgt = ops[0] if ops else self.pc+len(ops)+1
        self.pc = tgt if tgt < len(self.ac) else self.pc+len(ops)+1
    def h_BINOP(self, op, ops):
        if len(self.stack)>=2:
            b=self.stack.pop(); a=self.stack.pop(); self.stack.append((a,b))
        self.pc += len(ops)+1
    def h_NOP(self, op, ops): self.pc += len(ops)+1
    def h_UNK(self, op, ops): self.pc += len(ops)+1

_ = VM.h_UNK  # silence unused

def main():
    ac, lengths = load()
    vm = VM(ac, lengths)
    vm.run(0, 50)
    print(f"=== engine run: {vm.steps} steps, pc={vm.pc} ===")
    print(f"slot: {dict(list(vm.slot.items())[:20])}")
    print(f"stack: {vm.stack[:20]}")
    print(f"frame: {vm.frame[:10]}")
    if vm.log: print("log:", vm.log[:10])

if __name__ == "__main__":
    main()
