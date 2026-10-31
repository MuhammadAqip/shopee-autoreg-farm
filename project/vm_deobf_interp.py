#!/usr/bin/env python3
"""vm_deobf_interp.py — deobfuscate interpreter penuh.

Ganti semua `eI(k)` / `ad("0x..")` / `X(idx)` dgn string dari table ae/aj.
Hasil: interpreter yang bisa dibaca manusia.

Table:
  eI = ad → ae table (identifiers: now/slice/for/while/return/...)
  ak → aj table (strings/primitives)
"""
import re, os, json
ROOT = os.path.dirname(os.path.abspath(__file__))

def load_tables():
    tbl = {}
    for l in open(f"{ROOT}/sdk/strings_decoded.txt"):
        m = re.match(r'\[(\w+):(\d+)\]\s*(.*)', l)
        if m: tbl.setdefault(m.group(1), {})[int(m.group(2))] = m.group(3)
    return tbl

def deobf(src, tables, decode_fn='eI'):
    ae = tables.get('ae', {})
    aj = tables.get('aj', {})
    def rep_hex(m):
        idx = int(m.group(2), 16)
        return f'/*{m.group(1)}({m.group(2)})*/"{ae.get(idx, "?")}"'
    def rep_dec(m):
        idx = int(m.group(2))
        return f'/*{m.group(1)}({m.group(2)})*/"{ae.get(idx, "?")}"'
    # eI("0x..") / ad("0x..")
    src = re.sub(r'\b(eI|ad)\("0x([0-9a-fA-F]+)"\)', rep_hex, src)
    # eI(123) / ad(123)
    src = re.sub(r'\b(eI|ad)\((\d+)\)', rep_dec, src)
    return src

def main():
    tables = load_tables()
    body = open(f"{ROOT}/sdk/vm_interp_FULL.js").read()
    out = deobf(body, tables)
    open(f"{ROOT}/vm_interp_deobf.js", "w").write(out)
    print(f"deobfuscated interpreter: {len(body)} -> {len(out)} chars")
    subs = len(re.findall(r'/\*eI', out)) 
    print(f"substitutions: {subs}")
    print("\n=== first 600 chars deobfuscated ===")
    print(out[:600])

if __name__ == "__main__":
    main()
