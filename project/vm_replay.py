#!/usr/bin/env python3
"""vm_replay.py — replay trace 80k-step NYATA lewat emulator, bangun state.

Bukan execute-from-scratch (bytecode perlu runtime init), tapi REPLAY:
  untuk tiap step trace: [pc, op, a,b,c,d]
    1. set pc
    2. terapkan efek opcode ke slot/stack (dari semantics)
    3. bandingkan dgn observasi berikutnya (konsistensi)

Ini membangun 'state timeline' → reveal apa yang signer hitung.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))

def load():
    ac = json.load(open(f"{ROOT}/vm_bytecode_FULL.json"))
    t = json.load(open(f"{ROOT}/vm_full_dump.json"))["t"]
    return ac, t

# handler: opcode -> fungsi(state, operands) -> mutasi
def make_handlers():
    def PUSH(s, o): s['stack'].append(('slot', o[0]) if o else None)
    def STORE(s, o): s['slot'][o[0]] = o[1]
    def LOAD(s, o): s['stack'].append(('slot', o[0]))
    def MOV(s, o): s['slot'][o[0]] = ('slot', o[1])
    def CALL(s, o): s['frame'].append(s['pc'])
    def DISPATCH(s, o): pass
    def JMP(s, o): s['jmp'] = o[0] if o else None
    def BINOP(s, o): 
        if len(s['stack'])>=2: b=s['stack'].pop(); a=s['stack'].pop(); s['stack'].append(('bin',a,b))
    def CALC(s,o): pass
    return {'PUSH':PUSH,'STORE':STORE,'LOAD':LOAD,'MOV':MOV,'CALL':CALL,
            'DISPATCH':DISPATCH,'JMP':JMP,'BINOP':BINOP}

OPNAME={901:'PUSH',469:'STORE',878:'LOAD',477:'MOV',459:'CALL',765:'DISPATCH',
        62:'JMP',370:'CALL',94:'BINOP',281:'INIT',732:'FRAME',303:'FRAME2'}

def main():
    ac, t = load()
    H = make_handlers()
    s = {'pc':0,'slot':{},'stack':[],'frame':[],'jmp':None}
    events = []
    for i, e in enumerate(t[:20000]):
        pc, op = e[0]-1, e[1]
        ops = e[2:7]
        s['pc'] = pc
        name = OPNAME.get(op)
        if name and name in H:
            H[name](s, [x for x in ops if x is not None])
            if name in ('STORE','MOV') and len(ops)>=2:
                events.append(('STORE' if name=='STORE' else 'MOV', ops[0], ops[1]))
        if len(s['slot'])>0 and i<200:
            pass
    print(f"replayed {min(20000,len(t))} steps")
    print(f"slot entries: {len(s['slot'])}")
    print(f"stack depth: {len(s['stack'])}")
    print(f"frames: {len(s['frame'])}")
    print(f"store/move events: {len(events)}")
    print(f"sample events: {events[:15]}")
    # slot yang sering ditulis = variabel penting
    from collections import Counter
    c=Counter(ev[1] for ev in events)
    print(f"hottest slots: {c.most_common(10)}")
    json.dump({'slots':len(s['slot']),'events':events[:5000]}, open(f"{ROOT}/vm_replay.json","w"))

if __name__ == "__main__":
    main()
